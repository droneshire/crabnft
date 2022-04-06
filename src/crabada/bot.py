import json
import logging
import math
import os
import time
import typing as T
from twilio.rest import Client
from web3.types import Address, TxReceipt

from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.crabada_web3_client import CrabadaWeb3Client
from crabada.strategies.strategy import Strategy
from crabada.strategies.looting import LootingStrategy
from crabada.strategies.strategy_selection import STRATEGY_SELECTION
from crabada.types import CrabForLending, IdleGame, Team
from utils import logger
from utils.config_types import UserConfig, SmsConfig
from utils.email import Email, send_email
from utils.game_stats import LifetimeGameStats, NULL_GAME_STATS
from utils.game_stats import get_game_stats, get_lifetime_stats_file, write_game_stats
from utils.general import get_pretty_seconds
from utils.math import Average
from utils.price import wei_to_tus, wei_to_cra_raw, wei_to_tus_raw, Prices
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.tus_web3_client import TusWeb3Client
from web3_utils.web3_client import web3_transaction


class CrabadaMineBot:
    TIME_BETWEEN_TRANSACTIONS = 5.0
    TIME_BETWEEN_EACH_UPDATE = 0.0
    ALERT_THROTTLING_TIME = 60.0 * 30.0
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
        self.lifetime_game_stats: LifetimeGameStats = NULL_GAME_STATS
        self.updated_game_stats: bool = True
        self.prices: Prices = Prices(0.0, 0.0, 0.0)
        self.avg_gas_avax: Average = Average()

        self.mining_strategy = STRATEGY_SELECTION[self.config["mining_strategy"]](
            self.address,
            self.crabada_w2,
            self.crabada_w3,
            self.config,
        )
        self.looting_strategy = STRATEGY_SELECTION[self.config["looting_strategy"]](
            self.address,
            self.crabada_w2,
            self.crabada_w3,
            self.config,
        )
        self.reinforcement_search_backoff: int = 0
        self.avg_reinforce_tus: Average = Average(20.0)
        self.last_mine_start: T.Optional[float] = None

        if not dry_run and not os.path.isfile(get_lifetime_stats_file(user, self.log_dir)):
            write_game_stats(self.user, self.log_dir, self.lifetime_game_stats)
        else:
            self.lifetime_game_stats = get_game_stats(self.user, self.log_dir)
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
        for k, v in self.lifetime_game_stats.items():
            if isinstance(v, dict):
                v = sum([c for _, c in v.items()])

            if isinstance(v, float):
                content += f"{k.upper()}: {v:.3f}\n"
            else:
                content += f"{k.upper()}: {v}\n"

        content += "\n"

        try:
            if do_send_sms and self.from_sms_number:
                sms_message = f"\U0001F980 Crabada Bot Alert \U0001F980\n\n"
                sms_message += content
                message = self.sms.messages.create(
                    body=sms_message, from_=self.from_sms_number, to=self.config["sms_number"]
                )
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail("Failed to send sms alert")

        try:
            if do_send_email and self.config["email"]:
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
            logger.print_fail("Failed to send email alert")

    def _update_bot_stats(self, team: Team, mine: IdleGame) -> None:
        if mine.get("winner_team_id", "") == team["team_id"]:
            self.lifetime_game_stats["game_wins"] += 1
        else:
            self.lifetime_game_stats["game_losses"] += 1

        self.lifetime_game_stats["game_win_percent"] = (
            100.0
            * float(self.lifetime_game_stats["game_wins"])
            / (self.lifetime_game_stats["game_wins"] + self.lifetime_game_stats["game_losses"])
        )

        if mine.get("winner_team_id", "") == team["team_id"]:
            tus_reward = wei_to_tus_raw(mine.get("miner_tus_reward",0.0))
            cra_reward = wei_to_cra_raw(mine.get("miner_cra_reward",0.0))
            game_type = "MINE"
        else:
            tus_reward = wei_to_tus_raw(mine.get("looter_tus_reward",0.0))
            cra_reward = wei_to_cra_raw(mine.get("looter_cra_reward",0.0))
            game_type = "LOOT"

        self.lifetime_game_stats["tus_gross"][game_type] = self.lifetime_game_stats["tus_gross"].get(game_type, 0.0) + tus_reward
        self.lifetime_game_stats["cra_gross"][game_type] = self.lifetime_game_stats["cra_gross"].get(game_type, 0.0) + cra_reward
        self.lifetime_game_stats["tus_net"][game_type] = self.lifetime_game_stats["tus_net"].get(game_type, 0.0) + tus_reward
        self.lifetime_game_stats["cra_net"][game_type] = self.lifetime_game_stats["cra_net"].get(game_type, 0.0) + cra_reward

        for address, commission in self.config["commission_percent_per_mine"].items():
            commission_tus = tus_reward * (commission / 100.0)
            commission_cra = cra_reward * (commission / 100.0)
            # convert cra -> tus and add to tus commission, we dont take direct cra commission
            commission_tus += self.prices.cra_to_tus(commission_cra)
            self.lifetime_game_stats["commission_tus"][address] = (
                self.lifetime_game_stats["commission_tus"].get(address, 0.0) + commission_tus
            )

            self.lifetime_game_stats["tus_net"][game_type] -= commission_tus
            self.lifetime_game_stats["cra_net"][game_type] -= commission_cra

        if not self.dry_run:
            write_game_stats(self.user, self.log_dir, self.lifetime_game_stats)
        self.updated_game_stats = True

    def _print_bot_stats(self) -> None:
        logger.print_normal("\n")
        logger.print_bold("--------\U0001F579  GAME STATS\U0001F579  ------")
        logger.print_normal(f"Explorer: https://snowtrace.io/address/{self.config['address']}\n\n")
        for k, v in self.lifetime_game_stats.items():
            if isinstance(v, float):
                logger.print_ok_blue(f"{k.upper()}: {v:.3f}")
            else:
                logger.print_ok_blue(f"{k.upper()}: {v}")
        logger.print_bold("------------------------------\n")

    def _send_out_of_gas_sms(self):
        now = time.time()
        if (
            self.time_since_last_alert is not None
            and now - self.time_since_last_alert < self.ALERT_THROTTLING_TIME
        ):
            return

        message = f"Unable to complete bot transaction due to insufficient gas \U000026FD!\n"
        message += f"Please add AVAX to your wallet ASAP to avoid delay in mining!\n"
        logger.print_fail(message)
        self._send_status_update(True, True, message)
        self.time_since_last_alert = now

    def _calculate_and_log_gas_price(self, tx_receipt: TxReceipt) -> None:
        avax_gas = wei_to_tus_raw(self.crabada_w3.get_gas_cost_of_transaction_wei(tx_receipt))
        if avax_gas is None:
            return

        avax_gas_usd = self.prices.avax_usd * avax_gas
        if not avax_gas_usd:
            return
        self.lifetime_game_stats["avax_gas_usd"] += avax_gas_usd
        self.avg_gas_avax.update(avax_gas)
        logger.print_bold(f"Paid {avax_gas} AVAX (${avax_gas_usd:.2f}) in gas")

    def _print_mine_loot_status(self) -> None:
        self._print_stats(self.crabada_w2.list_my_open_mines(self.address), True)
        self._print_stats(self.crabada_w2.list_my_open_loots(self.address), False)

    def _print_stats(self, mines: T.List[IdleGame], is_mine: bool = True) -> None:
        formatted_date = time.strftime("%A, %Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        header = "{:4s}{:10s}{:6s}{:10s}{:20s}{:25s}{:15s}{:15s}{:12s}\t{:25s}\n".format(
            "#",
            "Team",
            "Group",
            "Mine",
            "Round",
            "Progress",
            "Time Left",
            "Reinforce #",
            "Status",
            "Reinforcements",
        )
        header += len(header) * "_"

        if is_mine:
            logger.print_normal(f"Mines ({formatted_date})")
            last_mine_start_formatted = get_pretty_seconds(
                int(time.time() - self.crabada_w2.get_last_mine_start_time(self.address))
            )
            logger.print_normal(f"Last Mine Start: {last_mine_start_formatted}")
        else:
            logger.print_normal(f"Loots ({formatted_date})")

        if mines:
            logger.print_normal(header)
        else:
            logger.print_normal(f"No {'mines' if is_mine else 'loots'}")

        PROGRESS_SLOTS = 20
        for inx, mine in enumerate(mines):
            mine_data = self.crabada_w2.get_mine(mine["game_id"])

            if is_mine:
                team_id = "team_id"
                num_reinforcements = self.crabada_w2.get_num_mine_reinforcements(mine_data)
                is_winning = self.crabada_w2.mine_is_winning(mine_data)
                total_time = self.crabada_w2.get_total_mine_time(mine_data) + 1
                remaining_time = self.crabada_w2.get_remaining_time(mine_data)
            else:
                team_id = "attack_team_id"
                num_reinforcements = self.crabada_w2.get_num_loot_reinforcements(mine_data)
                is_winning = self.crabada_w2.loot_is_winning(mine_data)
                total_time = self.looting_strategy.LOOTING_DURATION
                remaining_time = self.crabada_w2.get_remaining_loot_time(mine_data)

            percent_done = (total_time - remaining_time) / total_time
            progress = (
                math.ceil(percent_done * PROGRESS_SLOTS) if remaining_time > 0 else PROGRESS_SLOTS
            )

            reinforments_used_str = logger.format_normal("[")
            for crab in self.crabada_w2.get_reinforcement_crabs(mine_data):
                if crab in self.config["reinforcing_crabs"].keys():
                    reinforments_used_str += logger.format_ok_blue(f"{crab} ")
                else:
                    reinforments_used_str += logger.format_normal(f"{crab} ")
            reinforments_used_str += logger.format_normal("]")

            logger.print_normal(
                "#{:3s}{:10s}{:6s}{:10s}{:20s}{:25s}{:15s}{:15s}{:20s}\t{:25s}".format(
                    str(inx + 1),
                    str(mine[team_id]),
                    str(self.config["mining_teams"].get(mine[team_id])),
                    str(mine["game_id"]),
                    mine["process"][-1]["action"],
                    "|{}{}|".format("#" * progress, " " * (PROGRESS_SLOTS - progress)),
                    get_pretty_seconds(remaining_time),
                    f"reinforced {num_reinforcements}x",
                    logger.format_ok("winning") if is_winning else logger.format_fail("losing"),
                    reinforments_used_str,
                )
            )
        logger.print_normal("\n")

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

        reinforce_margin = 0
        if strategy._have_reinforced_at_least_once(team):
            reinforce_margin = 30
        if isinstance(strategy, LootingStrategy):
            reinforce_margin = 50

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
        self.avg_reinforce_tus.update(price_tus)

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
                game_type = "LOOT" if isinstance(strategy, LootingStrategy) else "MINE"
                self.lifetime_game_stats["tus_net"][game_type] -= price_tus
                self.lifetime_game_stats["tus_reinforcement"][game_type] += price_tus
                self.updated_game_stats = True
                return True

        return False

    def _close_mine(self, team: Team, mine: IdleGame, strategy: Strategy) -> bool:
        if self._is_gas_too_high(margin=strategy.get_gas_margin()):
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
        # TODO: tell win/loss from tx_receipt on loots, this is a hack
        if isinstance(strategy, LootingStrategy):
            time.sleep(5.0)
            mine = self.crabada_w2.get_mine(mine)
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

        logger.print_ok_arrow(f"Successfully started mine for team {team['team_id']}")
        self.time_since_last_alert = None

        return True

    def _is_team_allowed_to_mine(self, team: Team) -> bool:
        return team["team_id"] in self.config["mining_teams"].keys()

    def _is_team_allowed_to_loot(self, team: Team) -> bool:
        return team["team_id"] in self.config["looting_teams"]

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

        groups_started = []

        for team in available_teams:
            if not self._is_team_allowed_to_mine(team):
                logger.print_warn(f"Skipping team {team['team_id']} for mining...")
                continue

            if self._is_gas_too_high(margin=self.mining_strategy.get_gas_margin()):
                logger.print_warn(
                    f"Skipping open of mine for team {team['team_id']} due to high gas cost"
                )
                continue

            if not self.mining_strategy.should_start(team):
                continue

            # only start one team from group at a time in case there's some staggering
            # that needs to happen
            team_group = self.config["mining_teams"].get(team["team_id"], -1)
            if team_group in groups_started:
                continue

            if self._start_mine(team):
                groups_started.append(team_group)

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
        return self.lifetime_game_stats

    def update_prices(
        self,
        avax_usd: T.Optional[float],
        tus_usd: T.Optional[float],
        cra_usd: T.Optional[float],
    ) -> None:
        self.prices.update(avax_usd, tus_usd, cra_usd)

    def set_backoff(self, reinforcement_backoff: int) -> None:
        self.reinforcement_search_backoff = reinforcement_backoff

    def get_backoff(self) -> int:
        return self.reinforcement_search_backoff

    def get_avg_gas_avax(self) -> float:
        return self.avg_gas_avax.get_avg()

    def get_avg_reinforce_tus(self) -> float:
        return self.avg_reinforce_tus.get_avg()

    def run(self) -> None:
        logger.print_normal("=" * 60)

        logger.print_ok(f"User: {self.user.upper()}")

        gas_price_gwei = self.crabada_w3.get_gas_price_gwei()
        gas_price_gwei = "UNKNOWN" if gas_price_gwei is None else gas_price_gwei
        logger.print_ok(
            f"AVAX: ${self.prices.avax_usd:.3f}, TUS: ${self.prices.tus_usd:.3f}, CRA: ${self.prices.cra_usd:.3f}, Gas: {gas_price_gwei:.2f}"
        )

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
            write_game_stats(self.user, self.log_dir, self.lifetime_game_stats)
        self._print_bot_stats()
