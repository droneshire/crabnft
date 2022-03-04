import json
import logging
import os
import time
import typing as T
from twilio.rest import Client
from web3.types import TxReceipt

from crabada.web2_client import CrabadaWeb2Client
from crabada.web3_client import CrabadaWeb3Client
from crabada.factional_advantage import get_faction_adjusted_battle_point
from crabada.types import CrabForLending, GameStats, IdleGame, NULL_GAME_STATS, Team
from utils import logger
from utils.config_types import UserConfig, SmsConfig
from utils.price import get_avax_price_usd, tus_to_wei, wei_to_tus, wei_to_cra_raw, wei_to_tus_raw
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.web3_client import web3_transaction


class CrabadaBot:
    TIME_BETWEEN_TRANSACTIONS = 5.0
    TIME_BETWEEN_EACH_UPDATE = 30.0
    SMS_COST_PER_MESSAGE = 0.0075
    ALERT_THROTTLING_TIME = 60.0 * 5

    def __init__(
        self,
        user: str,
        config: UserConfig,
        from_sms_number: str,
        sms_client: Client,
        crypto_api_token: str,
        log_dir: str,
        dry_run: bool,
    ) -> None:
        self.user = user
        self.config = config
        self.from_sms_number = from_sms_number
        self.sms = sms_client
        self.api_token = crypto_api_token

        self.time_since_last_alert = 0.0

        self.crabada_w3 = T.cast(
            CrabadaWeb3Client,
            (
                CrabadaWeb3Client()
                .set_credentials(config["address"], config["private_key"])
                .set_node_uri(AvalancheCWeb3Client.AVAX_NODE_URL)
            ).set_dry_run(dry_run),
        )
        self.crabada_w2 = CrabadaWeb2Client()

        self.address = self.config["address"]
        self.game_stats = NULL_GAME_STATS
        self.game_stats_file = os.path.join(log_dir, user.lower() + "_lifetime_game_bot_stats.json")
        self.updated_game_stats = True
        self.have_reinforced_at_least_once: T.Dict[str, bool] = {}
        self.closed_mines = 0

        teams = self.crabada_w2.list_teams(self.address)
        for team in teams:
            team_mine = self.crabada_w2.get_mine(team["game_id"])
            if team_mine is None:
                continue
            self.have_reinforced_at_least_once[team["team_id"]] = team_mine.get("round", 0) > 1

        if not os.path.isfile(self.game_stats_file):
            with open(self.game_stats_file, "w") as outfile:
                json.dump(
                    NULL_GAME_STATS, outfile, indent=4, sort_keys=True,
                )
        else:
            with open(self.game_stats_file, "r") as infile:
                self.game_stats = json.load(infile)
        logger.print_ok_blue(f"Adding bot for user {self.user} with address {self.address}")

    def _send_status_update_sms(self, custom_message: str) -> None:
        if not self.config["get_sms_updates"]:
            return

        text_message = f"\U0001F980 Crabada Bot Alert \U0001F980\n\n"
        text_message += f"Action: {custom_message}\n\n"

        text_message += f"Explorer: https://snowtrace.io/address/{self.config['address']}\n\n"
        text_message += "---\U0001F579  GAME STATS\U0001F579  ---\n"
        for k, v in self.game_stats.items():
            if isinstance(v, float):
                text_message += f"{k.upper()}: {v:.3f}\n"
            else:
                text_message += f"{k.upper()}: {v}\n"

        text_message += "\n"

        try:
            message = self.sms.messages.create(
                body=text_message, from_=self.from_sms_number, to=self.config["sms_number"]
            )
            self.game_stats["sms_cost"] += self.SMS_COST_PER_MESSAGE
            self.game_stats["sms_sent"] += 1
        except:
            logger.print_fail("Failed to send SMS alert")
            pass

        game_logger = logging.getLogger()
        if game_logger:
            game_logger.debug(json.dumps(message.sid, indent=4, sort_keys=True))

    def _send_out_of_gas_sms(self):
        now = time.time()
        if (
            self.time_since_last_alert
            and now - self.time_since_last_alert < self.ALERT_THROTTLING_TIME
        ):
            return

        message = f"Unable to complete bot transaction due to insufficient gas \U000026FD!\n"
        message += f"Please add AVAX to your wallet ASAP to avoid delay in mining!\n"
        self._send_status_update_sms(message)
        self.time_since_last_alert = now

    def _calculate_and_log_gas_price(self, tx_receipt: TxReceipt) -> None:
        avax_gas = wei_to_tus_raw(self.crabada_w3.get_gas_cost_of_transaction_wei(tx_receipt))
        if avax_gas is None:
            return
        avax_gas_usd = get_avax_price_usd(self.api_token) * avax_gas
        self.game_stats["avax_gas_usd"] += avax_gas_usd
        logger.print_bold(f"Paid {avax_gas} AVAX (${avax_gas_usd:.2f}) in gas")

    def _print_mine_status(self) -> None:
        open_mines = self.crabada_w2.list_my_open_mines((self.address))
        team_to_mines = {mine["game_id"]: mine for mine in open_mines}

        open_mines_str = " ".join([str(m["game_id"]) for m in open_mines])
        formatted_date = time.strftime("%A, %Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        logger.print_warn(f"Mines ({formatted_date})")

        for mine in open_mines:
            logger.print_normal(
                f"\t{mine['game_id']}\t\tround {mine['round']}\t\t{self.crabada_w2.get_remaining_time_formatted(mine)}\t\t"
            )
        logger.print_normal("\n")

    def _check_and_maybe_start_mines(self) -> None:
        available_teams = self.crabada_w2.list_available_teams(self.address)
        for team in available_teams:

            teams_specified_to_mine = [m["team_id"] for m in self.config["mining_teams"]]
            if team["team_id"] not in teams_specified_to_mine:
                logger.print_warn(f"Skipping team {team['team_id']} for mining...")
                continue

            logger.print_normal(f"Attemting to start new mine with team {team['team_id']}!")

            with web3_transaction("insufficient funds for gas", self._send_out_of_gas_sms):
                tx_hash = self.crabada_w3.start_game(team["team_id"])
                tx_receipt = self.crabada_w3.get_transaction_receipt(tx_hash)

                self._calculate_and_log_gas_price(tx_receipt)

                if tx_receipt["status"] != 1:
                    logger.print_fail(f"Error starting mine for team {team['team_id']}")
                else:
                    logger.print_ok_arrow(f"Successfully started mine for team {team['team_id']}")
                    self.have_reinforced_at_least_once[team["team_id"]] = False

    def _check_and_maybe_reinforce_mines(self) -> None:
        if not self.config["should_reinforce"]:
            return

        teams = self.crabada_w2.list_teams(self.address)
        for team in teams:
            team_mine = self.crabada_w2.get_mine(team["game_id"])

            if team_mine is None:
                continue

            if not self.crabada_w2.mine_needs_reinforcement(team_mine):
                continue

            fee_per_gas_wei = self.crabada_w3.estimate_max_fee_per_gas_in_gwei()
            if (
                fee_per_gas_wei is not None
                and fee_per_gas_wei > self.self.config["max_fee_per_gas"]
            ):
                logger.print_warn(f"Warning: High Fee/Gas ({fee_per_gas_wei})!")
                if not self.have_reinforced_at_least_once.get(team["team_id"], True):
                    logger.print_warn(f"Skipping reinforcement due to high gas cost")
                    continue

            reinforcment_crab = None
            if (
                team_mine["attack_point"] - get_faction_adjusted_battle_point(team, team_mine)
                < self.config["max_reinforce_bp_delta"]
            ):
                logger.print_normal(
                    f"Mine[{team_mine['game_id']}]: using reinforcement strategy of highest bp"
                )
                reinforcment_crab = self.crabada_w2.get_best_high_bp_crab_for_lending(
                    self.config["max_reinforcement_price_tus"]
                )
            else:
                logger.print_normal(
                    f"Mine[{team_mine['game_id']}]: using reinforcement strategy of highest mp"
                )
                reinforcment_crab = self.crabada_w2.get_best_high_mp_crab_for_lending(
                    self.config["max_reinforcement_price_tus"]
                )

            if reinforcment_crab is None:
                logger.print_fail("Could not find affordable reinforcement!")
                continue

            price_tus = wei_to_tus_raw(reinforcment_crab["price"])
            battle_points = reinforcment_crab["battle_point"]
            mine_points = reinforcment_crab["mine_point"]
            crabada_id = reinforcment_crab["crabada_id"]

            logger.print_normal(
                f"Mine[{team_mine['game_id']}]: Found reinforcement crabada {crabada_id} for {price_tus} Tus [BP {battle_points} | MP {mine_points}]"
            )

            with web3_transaction("insufficient funds for gas", self._send_out_of_gas_sms):
                tx_hash = self.crabada_w3.reinforce_defense(
                    team["game_id"], crabada_id, reinforcment_crab["price"]
                )
                tx_receipt = self.crabada_w3.get_transaction_receipt(tx_hash)

                self._calculate_and_log_gas_price(tx_receipt)

                if tx_receipt["status"] != 1:
                    logger.print_fail_arrow(f"Error reinforcing mine {team['game_id']}")
                else:
                    logger.print_ok_arrow(f"Successfully reinforced mine {team['game_id']}")
                    self.game_stats["tus_net"] -= price_tus
                    self.game_stats["tus_reinforcement"] += price_tus
                    self.updated_game_stats = True
                    self.have_reinforced_at_least_once[team["team_id"]] = True

    def _check_and_maybe_close_mines(self) -> None:
        teams = self.crabada_w2.list_teams(self.address)
        for team in teams:
            if team["game_id"] is None and team["game_type"] != "mining":
                continue

            team_mine = self.crabada_w2.get_mine(team["game_id"])
            if not self.crabada_w2.mine_is_finished(team_mine):
                continue

            logger.print_normal(f"Attempting to close game {team['game_id']}")

            with web3_transaction("insufficient funds for gas", self._send_out_of_gas_sms):
                tx_hash = self.crabada_w3.close_game(team["game_id"])
                tx_receipt = self.crabada_w3.get_transaction_receipt(tx_hash)

                self._calculate_and_log_gas_price(tx_receipt)

                if tx_receipt["status"] != 1:
                    logger.print_fail_arrow(f"Error closing mine {team['game_id']}")
                else:
                    outcome = (
                        "won \U0001F389"
                        if team_mine["winner_team_id"] == team["team_id"]
                        else "lost \U0001F915"
                    )
                    logger.print_ok_arrow(
                        f"Successfully closed mine {team['game_id']}, we {outcome}"
                    )
                    self._update_bot_stats(team, team_mine)
                    self.closed_mines += 1

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

        self.game_stats["commission_tus"] += (
            wei_to_tus_raw(mine["miner_tus_reward"]) * self.config["commission_percent_per_mine"]
        )
        self.game_stats["tus_net"] -= self.game_stats["commission_tus"]

        with open(self.game_stats_file, "w") as outfile:
            json.dump(self.game_stats, outfile, indent=4, sort_keys=True)
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

    def run(self) -> None:
        logger.print_normal("=" * 60)

        logger.print_ok(f"User: {self.user.upper()}")

        avax_price_usd = get_avax_price_usd(self.api_token)
        avax_price_usd = "UNKNOWN" if avax_price_usd is None else f"{avax_price_usd:.2f}"
        fee_per_gas_wei = self.crabada_w3.estimate_max_fee_per_gas_in_gwei()
        fee_per_gas_wei = "UNKNOWN" if fee_per_gas_wei is None else fee_per_gas_wei
        logger.print_ok(f"AVAX/USD: ${avax_price_usd}, Est. Fee/Gas: {fee_per_gas_wei}")

        self._print_mine_status()
        self._check_and_maybe_start_mines()
        self._check_and_maybe_reinforce_mines()
        self._check_and_maybe_close_mines()

        if self.updated_game_stats:
            self.updated_game_stats = False
            self._print_bot_stats()

        if self.closed_mines >= len(self.config["mining_teams"]):
            self.closed_mines = 0
            self._send_status_update_sms(
                f"Successfully finished {self.closed_mines} mines! \U0001F389"
            )

        time.sleep(self.TIME_BETWEEN_EACH_UPDATE)

    def end(self) -> None:
        logger.print_fail(f"Exiting bot for {self.user}...")

        self._print_bot_stats()
        with open(self.game_stats_file, "w") as outfile:
            json.dump(self.game_stats, outfile, indent=4, sort_keys=True)
