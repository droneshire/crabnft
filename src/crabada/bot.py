import json
import logging
import os
import time
import typing as T
from twilio.rest import Client
from web3.types import TxReceipt

from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.crabada_web3_client import CrabadaWeb3Client
from crabada.factional_advantage import get_faction_adjusted_battle_point
from crabada.strategies.mining_reinforcement import have_reinforced_mine_at_least_once
from crabada.types import CrabForLending, IdleGame, Team
from utils import logger
from utils.config_types import UserConfig, SmsConfig
from utils.email import Email, send_email
from utils.game_stats import GameStats, NULL_GAME_STATS
from utils.game_stats import get_game_stats, get_lifetime_stats_file, write_game_stats
from utils.price import tus_to_wei, wei_to_tus, wei_to_cra_raw, wei_to_tus_raw
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.web3_client import web3_transaction


class CrabadaMineBot:
    TIME_BETWEEN_TRANSACTIONS = 5.0
    TIME_BETWEEN_EACH_UPDATE = 5.0
    ALERT_THROTTLING_TIME = 60.0 * 60 * 2
    MIN_MINE_POINT = 60

    def __init__(
        self,
        user: str,
        config: UserConfig,
        from_sms_number: str,
        sms_client: Client,
        email_account: Email,
        log_dir: str,
        dry_run: bool,
    ) -> None:
        self.user = user
        self.config = config
        self.from_sms_number = from_sms_number
        self.sms = sms_client
        self.email = email_account
        self.log_dir = log_dir
        self.dry_run = dry_run

        self.time_since_last_alert = None

        self.crabada_w3 = T.cast(
            CrabadaWeb3Client,
            (
                CrabadaWeb3Client()
                .set_credentials(config["address"], config["private_key"])
                .set_node_uri(AvalancheCWeb3Client.AVAX_NODE_URL)
                .set_dry_run(dry_run)
            ),
        )
        self.crabada_w2 = CrabadaWeb2Client()

        self.address = self.config["address"]
        self.game_stats = NULL_GAME_STATS
        self.updated_game_stats = True
        self.avax_price_usd = 0.0
        self.reinforcement_strategy = self.config["reinforcement_strategy"](
            self.address,
            self.crabada_w2,
            self.config["reinforcing_crabs"],
            self.config["max_reinforcement_price_tus"],
        )


        if not dry_run and not os.path.isfile(get_lifetime_stats_file(user, self.log_dir)):
            write_game_stats(self.user, self.log_dir, self.game_stats)
        else:
            self.game_stats = get_game_stats(self.user, self.log_dir)
        logger.print_ok_blue(f"Adding bot for user {self.user} with address {self.address}")

        self._print_out_config()

    def _print_out_config(self) -> None:
        logger.print_bold(f"{self.user} Configuration\n")
        for config_item, value in self.config.items():
            if config_item == "private_key":
                continue
            logger.print_normal(f"\t{config_item}: {value}")
        logger.print_normal("")

    def _send_status_update(
        self, do_send_sms: bool, do_send_email: bool, custom_message: str
    ) -> None:

        if self.dry_run:
            return

        content = f"Action: {custom_message}\n\n"

        content += f"Explorer: https://snowtrace.io/address/{self.config['address']}\n\n"
        content += "---\U0001F579  GAME STATS\U0001F579  ---\n"
        for k, v in self.game_stats.items():
            if isinstance(v, float):
                content += f"{k.upper()}: {v:.3f}\n"
            else:
                content += f"{k.upper()}: {v}\n"

        content += "\n"

        try:
            if do_send_sms:
                sms_message = f"\U0001F980 Crabada Bot Alert \U0001F980\n\n"
                sms_message += content
                message = self.sms.messages.create(
                    body=sms_message, from_=self.from_sms_number, to=self.config["sms_number"]
                )
            if do_send_email:
                email_message = f"Hello {self.user}!\n"
                email_message += content
                send_email(
                    self.email,
                    self.config["email"],
                    f"\U0001F980 Crabada Bot Update",
                    email_message,
                )
        except:
            logger.print_fail("Failed to send email/sms alert")

    def _update_bot_stats(self, team: Team, mine: IdleGame) -> None:
        if mine["winner_team_id"] == team["team_id"]:
            self.game_stats["game_wins"] += 1
        else:
            self.game_stats["game_losses"] += 1

        self.game_stats["game_win_percent"] = (
            100.0
            * float(self.game_stats["game_wins"])
            / (self.game_stats["game_wins"] + self.game_stats["game_losses"])
        )

        self.game_stats["tus_gross"] += wei_to_tus_raw(mine["miner_tus_reward"])
        self.game_stats["cra_net"] += wei_to_cra_raw(mine["miner_cra_reward"])
        self.game_stats["tus_net"] += wei_to_tus_raw(mine["miner_tus_reward"])

        commission_tus = wei_to_tus_raw(mine["miner_tus_reward"]) * (
            self.config["commission_percent_per_mine"] / 100.0
        )
        self.game_stats["commission_tus"] += commission_tus
        self.game_stats["tus_net"] -= commission_tus

        if not self.dry_run:
            write_game_stats(self.user, self.log_dir, self.game_stats)
        self.updated_game_stats = True

    def _print_bot_stats(self) -> None:
        logger.print_normal("\n")
        logger.print_bold("--------\U0001F579  GAME STATS\U0001F579  ------")
        logger.print_normal(f"Explorer: https://snowtrace.io/address/{self.config['address']}\n\n")
        for k, v in self.game_stats.items():
            if isinstance(v, float):
                logger.print_ok_blue(f"{k.upper()}: {v:.3f}")
            else:
                logger.print_ok_blue(f"{k.upper()}: {v}")
        logger.print_bold("------------------------------\n")

    def _send_out_of_gas_sms(self):
        now = time.time()
        if (
            self.time_since_last_alert
            and now - self.time_since_last_alert < self.ALERT_THROTTLING_TIME
        ):
            return

        message = f"Unable to complete bot transaction due to insufficient gas \U000026FD!\n"
        message += f"Please add AVAX to your wallet ASAP to avoid delay in mining!\n"
        self._send_status_update(
            self.config["get_sms_updates"], self.config["get_email_updates"], message
        )
        self.time_since_last_alert = now

    def _calculate_and_log_gas_price(self, tx_receipt: TxReceipt) -> None:
        avax_gas = wei_to_tus_raw(self.crabada_w3.get_gas_cost_of_transaction_wei(tx_receipt))
        if avax_gas is None:
            return

        avax_gas_usd = self.avax_price_usd * avax_gas
        if not avax_gas_usd:
            return
        self.game_stats["avax_gas_usd"] += avax_gas_usd
        logger.print_bold(f"Paid {avax_gas} AVAX (${avax_gas_usd:.2f}) in gas")

    def _print_mine_status(self) -> None:
        open_mines = self.crabada_w2.list_my_open_mines((self.address))
        team_to_mines = {mine["game_id"]: mine for mine in open_mines}

        open_mines_str = " ".join([str(m["game_id"]) for m in open_mines])
        formatted_date = time.strftime("%A, %Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        logger.print_normal(f"Mines ({formatted_date})")

        for mine in open_mines:
            logger.print_normal(
                "\t{}\t\tround {}\t\t{}\t{}".format(
                    mine["game_id"],
                    mine["round"],
                    self.crabada_w2.get_remaining_time_formatted(mine),
                    "under attack" if mine.get("attack_team_id", "") else "safe",
                )
            )
        logger.print_normal("\n")

    def _is_gas_too_high(self, margin: int = 0) -> bool:
        gas_price_gwei = self.crabada_w3.get_gas_price_gwei()
        if gas_price_gwei is not None and (
            int(gas_price_gwei) > self.config["max_gas_price_gwei"] + margin
        ):
            logger.print_warn(
                f"Warning: High Gas ({gas_price_gwei}) > {self.config['max_gas_price_gwei']}!"
            )
            return True
        return False

    def _reinforce_with_crab(
        self, team: Team, mine: IdleGame, reinforcement_crab: CrabForLending
    ) -> bool:
        if reinforcement_crab is None:
            logger.print_warn(f"Mine[{mine['game_id']}: Unable to find suitable reinforcement...")
            return

        price_tus = wei_to_tus_raw(reinforcement_crab["price"])
        battle_points = reinforcement_crab["battle_point"]
        mine_points = reinforcement_crab["mine_point"]
        crabada_id = reinforcement_crab["crabada_id"]

        logger.print_normal(
            f"Mine[{mine['game_id']}]: Found reinforcement crabada {crabada_id} for {price_tus} Tus [BP {battle_points} | MP {mine_points}]"
        )

        with web3_transaction("insufficient funds for gas", self._send_out_of_gas_sms):
            tx_hash = self.crabada_w3.reinforce_defense(
                team["game_id"], crabada_id, reinforcement_crab["price"]
            )
            tx_receipt = self.crabada_w3.get_transaction_receipt(tx_hash)

            self._calculate_and_log_gas_price(tx_receipt)

            if tx_receipt["status"] != 1:
                logger.print_fail_arrow(
                    f"Error reinforcing mine {team['game_id']}: {tx_receipt['status']}"
                )
            else:
                logger.print_ok_arrow(f"Successfully reinforced mine {team['game_id']}")
                self.time_since_last_alert = None
                self.game_stats["tus_net"] -= price_tus
                self.game_stats["tus_reinforcement"] += price_tus
                self.updated_game_stats = True
                return True

        return False

    def _close_mine(self, team: Team, mine: IdleGame) -> None:
        logger.print_normal(f"Attempting to close game {team['game_id']}")

        with web3_transaction("insufficient funds for gas", self._send_out_of_gas_sms):
            tx_hash = self.crabada_w3.close_game(team["game_id"])
            tx_receipt = self.crabada_w3.get_transaction_receipt(tx_hash)

            self._calculate_and_log_gas_price(tx_receipt)

            if tx_receipt["status"] != 1:
                logger.print_fail_arrow(
                    f"Error closing mine {team['game_id']}: {tx_receipt['status']}"
                )
                return

        outcome = (
            "won \U0001F389"
            if mine.get("winner_team_id", -1) == team["team_id"]
            else "lost \U0001F915"
        )
        message = f"Successfully closed mine {team['game_id']}, we {outcome}"
        self._send_status_update(
            self.config["get_sms_updates"], self.config["get_email_updates"], message
        )
        self.time_since_last_alert = None
        self._update_bot_stats(team, mine)
        logger.print_ok_arrow(message)

    def _start_mine(self, team: Team) -> None:
        logger.print_normal(f"Attemting to start new mine with team {team['team_id']}!")

        with web3_transaction("insufficient funds for gas", self._send_out_of_gas_sms):
            tx_hash = self.crabada_w3.start_game(team["team_id"])
            tx_receipt = self.crabada_w3.get_transaction_receipt(tx_hash)

            self._calculate_and_log_gas_price(tx_receipt)

            if tx_receipt["status"] != 1:
                logger.print_fail(
                    f"Error starting mine for team {team['team_id']}: {tx_receipt['status']}"
                )
                return

        logger.print_ok_arrow(f"Successfully started mine for team {team['team_id']}")
        self.time_since_last_alert = None

    def _is_team_allowed_to_mine(self, team: Team) -> bool:
        teams_specified_to_mine = [m["team_id"] for m in self.config["mining_teams"]]
        return team["team_id"] in teams_specified_to_mine

    def _is_team_allowed_to_loot(self, team: Team) -> bool:
        teams_specified_to_loot = [m["team_id"] for m in self.config["looting_teams"]]
        return team["team_id"] in teams_specified_to_loot

    def _check_and_maybe_start_mines(self) -> None:
        available_teams = self.crabada_w2.list_available_teams(self.address)
        for team in available_teams:
            if not self._is_team_allowed_to_mine(team):
                logger.print_warn(f"Skipping team {team['team_id']} for mining...")
                continue

            if self._is_gas_too_high(margin=10):
                logger.print_warn(
                    f"Skipping closing of Mine[{mine['game_id']}] due to high gas cost"
                )
                continue

            self._start_mine(team)

    def _check_and_maybe_reinforce(self) -> None:
        if not self.config["should_reinforce"]:
            return

        teams = self.crabada_w2.list_teams(self.address)

        for team in teams:
            mine = self.crabada_w2.get_mine(team["game_id"])

            if mine is None:
                continue

            if not self.crabada_w2.mine_needs_reinforcement(mine):
                continue

            if not self._is_team_allowed_to_mine(team):
                logger.print_warn(f"Skipping team {team['team_id']} for mine reinforcing...")
                continue

            if self._is_gas_too_high() and not have_reinforced_mine_at_least_once(
                self.crabada_w2, team
            ):
                logger.print_warn(
                    f"Skipping reinforcement of Mine[{mine['game_id']}] due to high gas cost"
                )
                continue

            reinforcement_search_backoff = 0
            for _ in range(2):
                if not self.reinforcement_strategy.should_reinforce(mine):
                    break
                reinforcement_crab = self.reinforcement_strategy.get_reinforcement_crab(
                    team, mine, reinforcement_search_backoff
                )
                if self._reinforce_with_crab(team, mine, reinforcement_crab):
                    break
                logger.print_warn(f"Mine[{mine['game_id']}]: retrying reinforcement with backoff")
                # back off by 5 in the tavern every failure
                reinforcement_search_backoff += 5
                time.sleep(1.0)

    def _check_and_maybe_close_mines(self) -> None:
        teams = self.crabada_w2.list_teams(self.address)
        for team in teams:
            if team["game_id"] is None and team["game_type"] != "mining":
                continue

            if not self._is_team_allowed_to_mine(team):
                logger.print_warn(f"Skipping team {team['team_id']} for closing...")
                continue

            mine = self.crabada_w2.get_mine(team["game_id"])
            if not self.crabada_w2.mine_is_finished(mine):
                continue

            if self._is_gas_too_high(margin=10):
                logger.print_warn(
                    f"Skipping closing of Mine[{mine['game_id']}] due to high gas cost"
                )
                continue

            self._close_mine(team, mine)

    def get_lifetime_stats(self) -> T.Dict[str, T.Any]:
        return self.game_stats

    def update_avax_price(self, avax_price_usd: T.Optional[float]) -> None:
        if avax_price_usd is None:
            return
        self.avax_price_usd = avax_price_usd

    def run(self) -> None:
        logger.print_normal("=" * 60)

        logger.print_ok(f"User: {self.user.upper()}")

        gas_price_gwei = self.crabada_w3.get_gas_price_gwei()
        gas_price_gwei = "UNKNOWN" if gas_price_gwei is None else gas_price_gwei
        logger.print_ok(f"AVAX/USD: ${self.avax_price_usd:.2f}, Gas: {gas_price_gwei:.2f}")

        self._print_mine_status()
        self._check_and_maybe_close_mines()
        time.sleep(1.0)
        self._check_and_maybe_start_mines()
        time.sleep(1.0)
        self._check_and_maybe_reinforce()

        if self.updated_game_stats:
            self.updated_game_stats = False
            self._print_bot_stats()

        time.sleep(self.TIME_BETWEEN_EACH_UPDATE)

    def end(self) -> None:
        logger.print_fail(f"Exiting bot for {self.user}...")
        if not self.dry_run:
            write_game_stats(self.user, self.log_dir, self.game_stats)
        self._print_bot_stats()
