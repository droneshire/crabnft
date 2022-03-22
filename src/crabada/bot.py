import json
import logging
import os
import time
import typing as T
from twilio.rest import Client
from web3.types import Address, TxReceipt

from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.crabada_web3_client import CrabadaWeb3Client
from crabada.factional_advantage import get_faction_adjusted_battle_point
from crabada.strategies.mining import PreferOwnMpCrabs, PreferOwnMpCrabsAndDelayReinforcement
from crabada.strategies.strategy import Strategy
from crabada.types import CrabForLending, IdleGame, Team
from utils import logger
from utils.config_types import UserConfig, SmsConfig
from utils.email import Email, send_email
from utils.game_stats import GameStats, NULL_GAME_STATS
from utils.game_stats import get_game_stats, get_lifetime_stats_file, write_game_stats
from utils.general import get_pretty_seconds
from utils.price import tus_to_wei, wei_to_tus, wei_to_cra_raw, wei_to_tus_raw
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.tus_web3_client import TusWeb3Client
from web3_utils.web3_client import web3_transaction


class CrabadaMineBot:
    TIME_BETWEEN_TRANSACTIONS = 5.0
    TIME_BETWEEN_EACH_UPDATE = 2.0
    ALERT_THROTTLING_TIME = 60.0 * 30.0
    MIN_MINE_POINT = 60
    MIN_TIME_BETWEEN_MINES = 60.0 * 31.0

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
        self.user: str = user
        self.config: UserConfig = config
        self.from_sms_number: str = from_sms_number
        self.sms: Client = sms_client
        self.email: Email = email_account
        self.log_dir: str = log_dir
        self.dry_run: bool = dry_run

        self.time_since_last_alert: T.Optional[float] = None

        self.crabada_w3: CrabadaWeb3Client = T.cast(
            CrabadaWeb3Client,
            (
                CrabadaWeb3Client()
                .set_credentials(config["address"], config["private_key"])
                .set_node_uri(AvalancheCWeb3Client.AVAX_NODE_URL)
                .set_dry_run(dry_run)
            ),
        )
        self.tus_w3: TusWeb3Client = T.cast(
            TusWeb3Client,
            (
                TusWeb3Client()
                .set_credentials(self.config["address"], config["private_key"])
                .set_node_uri(AvalancheCWeb3Client.AVAX_NODE_URL)
                .set_dry_run(dry_run)
            ),
        )
        self.crabada_w2: CrabadaWeb2Client = CrabadaWeb2Client()

        self.address: Address = self.config["address"]
        self.game_stats: GameStats = NULL_GAME_STATS
        self.updated_game_stats: bool = True
        self.avax_price_usd: float = 0.0

        self.mining_strategy = self.config["mining_strategy"](
            self.address,
            self.crabada_w2,
            self.crabada_w3,
            self.config["reinforcing_crabs"],
            self.config["max_reinforcement_price_tus"],
        )
        self.looting_strategy = self.config["looting_strategy"](
            self.address,
            self.crabada_w2,
            self.crabada_w3,
            self.config["reinforcing_crabs"],
            self.config["max_reinforcement_price_tus"],
        )
        self.reinforcement_search_backoff: int = 0
        self.last_mine_start: T.Optional[float] = None

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
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail("Failed to send email/sms alert")

    def _update_bot_stats(self, team: Team, mine: IdleGame) -> None:
        if mine.get("winner_team_id", "") == team["team_id"]:
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
            and now - self.time_since_last_alert > self.ALERT_THROTTLING_TIME
        ):
            return

        message = f"Unable to complete bot transaction due to insufficient gas \U000026FD!\n"
        message += f"Please add AVAX to your wallet ASAP to avoid delay in mining!\n"
        self._send_status_update(True, True, message)
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

    def _print_mine_loot_status(self) -> None:
        open_mines = self.crabada_w2.list_my_open_mines(self.address)
        open_loots = self.crabada_w2.list_my_open_loots(self.address)

        formatted_date = time.strftime("%A, %Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        logger.print_normal(f"Mines ({formatted_date})")
        last_mine_start_formatted = get_pretty_seconds(
            int(time.time() - self._get_last_mine_start_time())
        )
        logger.print_normal(f"Last Mine Start: {last_mine_start_formatted}")

        if not open_mines:
            logger.print_normal("NO MINES")

        for inx, mine in enumerate(open_mines):
            mine_data = self.crabada_w2.get_mine(mine["game_id"])
            logger.print_normal(
                "#{}\t{:9d}\t{:18s}\t{:18s}\t{:14s}{:14s}\t{:10s}".format(
                    inx + 1,
                    mine["game_id"],
                    mine["process"][-1]["action"],
                    self.crabada_w2.get_remaining_time_formatted(mine_data),
                    f"reinforced {self.crabada_w2.get_num_loot_reinforcements(mine_data)}x",
                    f"[{', '.join([str(c) for c in self.crabada_w2.get_reinforcement_crabs(mine_data)])}]",
                    "winning" if self.crabada_w2.mine_is_winning(mine_data) else "losing",
                )
            )

        logger.print_normal(f"Loots ({formatted_date})")

        if not open_loots:
            logger.print_normal("NO LOOTS")

        for inx, loot in enumerate(open_loots):
            loot_data = self.crabada_w2.get_mine(loot["game_id"])
            logger.print_normal(
                "#{}\t{}\t\tround {}\t\t{}\t[{}]".format(
                    inx + 1,
                    loot["game_id"],
                    loot["round"],
                    self.crabada_w2.get_remaining_loot_time_formatted(loot),
                    "winning" if self.crabada_w2.loot_is_winning(loot_data) else "losing",
                )
            )

        logger.print_normal("\n")

    def _get_last_mine_start_time(self) -> float:
        # TODO(ross): dedupe all these api calls
        mines = self.crabada_w2.list_my_open_mines(self.address)
        now = time.time()
        last_mine_start = 0
        for mine in mines:
            last_mine_start = max(last_mine_start, mine.get("start_time", 0))
        return last_mine_start

    def _is_gas_too_high(self, margin: int = 0) -> bool:
        gas_price_gwei = self.crabada_w3.get_gas_price_gwei()
        gas_price_limit = self.config["max_gas_price_gwei"] + margin
        if gas_price_gwei is not None and (int(gas_price_gwei) > int(gas_price_limit)):
            logger.print_warn(f"Warning: High Gas ({gas_price_gwei}) > {gas_price_limit}!")
            return True
        return False

    def _reinforce_loot_or_mine(
        self,
        team: Team,
        mine: IdleGame,
        strategy: Strategy,
    ) -> None:
        if not strategy.should_reinforce(mine):
            return

        reinforce_margin = 30 if strategy._have_reinforced_at_least_once(team) else 0
        if self._is_gas_too_high(margin=reinforce_margin):
            logger.print_warn(
                f"Skipping reinforcement of Mine[{mine['game_id']}] due to high gas cost"
            )
            return

        for _ in range(2):
            reinforcement_crab = strategy.get_reinforcement_crab(
                team, mine, self.reinforcement_search_backoff
            )
            if self._reinforce_with_crab(
                team,
                mine,
                reinforcement_crab,
                strategy,
            ):
                last_reinforcement_search_backoff = self.reinforcement_search_backoff
                self.reinforcement_search_backoff = max(0, self.reinforcement_search_backoff - 2)
                if last_reinforcement_search_backoff != self.reinforcement_search_backoff:
                    logger.print_ok_blue(
                        f"Reinforcement backoff: {last_reinforcement_search_backoff}->{self.reinforcement_search_backoff}"
                    )
                return

            self.reinforcement_search_backoff = self.reinforcement_search_backoff + 5
            logger.print_ok_blue(
                f"Adjusting reinforcement backoff to {self.reinforcement_search_backoff}"
            )
            # back off by 5 in the tavern every failure
            time.sleep(1.0)

    def _reinforce_with_crab(
        self,
        team: Team,
        mine: IdleGame,
        reinforcement_crab: CrabForLending,
        strategy: Strategy,
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

        available_tus = float(self.tus_w3.get_balance())
        if available_tus < price_tus:
            logger.print_warn(
                f"Insufficient TUS to purchase reinforcement! Balance: {available_tus}, Needed: {price_tus}"
            )
            return True

        with web3_transaction("insufficient funds for gas", self._send_out_of_gas_sms):
            tx_receipt = strategy.reinforce(
                team["game_id"], crabada_id, reinforcement_crab["price"]
            )

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

    def _close_mine(self, team: Team, mine: IdleGame, strategy: Strategy) -> bool:
        if self._is_gas_too_high(margin=0):
            logger.print_warn(
                f"Skipping closing of Game[{mine.get('game_id', '')}] due to high gas cost"
            )
            return False

        with web3_transaction("insufficient funds for gas", self._send_out_of_gas_sms):
            tx_receipt = strategy.close(team["game_id"])

            self._calculate_and_log_gas_price(tx_receipt)

            if tx_receipt["status"] != 1:
                logger.print_fail_arrow(
                    f"Error closing game {team['game_id']}: {tx_receipt['status']}"
                )
                return False

        self.time_since_last_alert = None
        self._update_bot_stats(team, mine)

        return True

    def _start_mine(self, team: Team) -> bool:
        logger.print_normal(f"Attemting to start new mine with team {team['team_id']}!")

        with web3_transaction("insufficient funds for gas", self._send_out_of_gas_sms):
            tx_receipt = self.mining_strategy.start(team["team_id"])

            self._calculate_and_log_gas_price(tx_receipt)

            if tx_receipt["status"] != 1:
                logger.print_fail(
                    f"Error starting mine for team {team['team_id']}: {tx_receipt['status']}"
                )
                return False

        return True

        logger.print_ok_arrow(f"Successfully started mine for team {team['team_id']}")
        self.time_since_last_alert = None

    def _is_team_allowed_to_mine(self, team: Team) -> bool:
        teams_specified_to_mine = [m["team_id"] for m in self.config["mining_teams"]]
        return team["team_id"] in teams_specified_to_mine

    def _is_team_allowed_to_loot(self, team: Team) -> bool:
        teams_specified_to_loot = [m["team_id"] for m in self.config["looting_teams"]]
        return team["team_id"] in teams_specified_to_loot

    def _check_and_maybe_reinforce_loots(self, team: Team, mine: IdleGame) -> None:
        if not self._is_team_allowed_to_loot(team):
            logger.print_warn(f"Skipping team {team['team_id']} for loot reinforcing...")
            return

        self._reinforce_loot_or_mine(
            team,
            mine,
            self.looting_strategy,
        )

    def _check_and_maybe_reinforce_mines(self, team: Team, mine: IdleGame) -> None:
        if not self._is_team_allowed_to_mine(team):
            logger.print_warn(f"Skipping team {team['team_id']} for mine reinforcing...")
            return

        self._reinforce_loot_or_mine(
            team,
            mine,
            self.mining_strategy,
        )

    def _check_and_maybe_close_loots(self, team: Team, mine: IdleGame) -> None:
        if not self.crabada_w2.loot_is_able_to_be_settled(mine):
            return

        if not self._is_team_allowed_to_loot(team):
            logger.print_warn(f"Skipping team {team['team_id']} for settling...")
            return

        if self._close_mine(team, mine, self.looting_strategy):
            message = f"\U0001F980 Crabada Bot Alert \U0001F980\n\n"
            message += f"Closed up looting of mine {mine['game_id']}, let's start another!"
            self._send_status_update(True, True, message)

    def _check_and_maybe_close_mines(self, team: Team, mine: IdleGame) -> None:
        if not self.crabada_w2.mine_is_finished(mine):
            return

        if not self._is_team_allowed_to_mine(team):
            logger.print_warn(f"Skipping team {team['team_id']} for closing...")
            return

        if self._close_mine(team, mine, self.mining_strategy):
            outcome = (
                "won \U0001F389"
                if mine.get("winner_team_id", -1) == team["team_id"]
                else "lost \U0001F915"
            )
            message = f"Successfully closed mine {team['game_id']}, we {outcome}"
            self._send_status_update(
                self.config["get_sms_updates"], self.config["get_email_updates"], message
            )
            logger.print_ok(message)

    def _check_and_maybe_start_mines(self) -> None:
        available_teams = self.crabada_w2.list_available_teams(self.address)
        last_mine_start = self._get_last_mine_start_time()
        for team in available_teams:
            if not self._is_team_allowed_to_mine(team):
                logger.print_warn(f"Skipping team {team['team_id']} for mining...")
                continue

            if self._is_gas_too_high(margin=10):
                logger.print_warn(
                    f"Skipping open of mine for team {team['team_id']} due to high gas cost"
                )
                continue

            now = time.time()
            if (
                isinstance(
                    self.mining_strategy, (PreferOwnMpCrabs, PreferOwnMpCrabsAndDelayReinforcement)
                )
            ) and now - last_mine_start + self.mining_strategy.get_reinforcement_delay() < self.MIN_TIME_BETWEEN_MINES:
                time_before_start_formatted = get_pretty_seconds(
                    int(
                        last_mine_start
                        + self.MIN_TIME_BETWEEN_MINES
                        - self.mining_strategy.get_reinforcement_delay()
                        - now
                    )
                )
                logger.print_normal(f"Waiting to start mine in {time_before_start_formatted}")
                continue

            if self._start_mine(team):
                last_mine_start = now

    def _check_and_maybe_reinforce(self) -> None:
        if not self.config["should_reinforce"]:
            return

        teams = self.crabada_w2.list_teams(self.address)
        loots = [l["game_id"] for l in self.crabada_w2.list_my_open_loots(self.address)]
        mines = [m["game_id"] for m in self.crabada_w2.list_my_mines(self.address)]
        for team in teams:
            mine = self.crabada_w2.get_mine(team["game_id"])

            if mine is None:
                continue

            if mine.get("game_id", -1) in loots:
                self._check_and_maybe_reinforce_loots(team, mine)
                continue

            if mine.get("game_id", -1) in mines:
                self._check_and_maybe_reinforce_mines(team, mine)
                continue

    def _check_and_maybe_close(self) -> None:
        teams = self.crabada_w2.list_teams(self.address)
        loots = [l["game_id"] for l in self.crabada_w2.list_my_open_loots(self.address)]
        mines = [m["game_id"] for m in self.crabada_w2.list_my_mines(self.address)]
        for team in teams:
            if team["game_id"] is None and team["game_type"] != "mining":
                continue

            mine = self.crabada_w2.get_mine(team["game_id"])
            if mine is None:
                continue

            if mine.get("game_id", "") in loots:
                self._check_and_maybe_close_loots(team, mine)

            if mine.get("game_id", "") in mines:
                self._check_and_maybe_close_mines(team, mine)

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

        self._print_mine_loot_status()
        self._check_and_maybe_close()
        self._check_and_maybe_start_mines()
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
