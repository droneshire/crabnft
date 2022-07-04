import copy
import datetime
import json
import logging
import math
import os
import time
import typing as T
from eth_account import Account, messages
from twilio.rest import Client
from web3.types import Address

from config_crabada import ADMIN_EMAIL, GAME_BOT_STRING
from crabada.config_manager_firebase import ConfigManagerFirebase
from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.crabada_web3_client import CrabadaWeb3Client
from crabada.factional_advantage import get_faction_adjusted_battle_points_from_teams
from crabada.game_stats import CrabadaLifetimeGameStatsLogger, NULL_GAME_STATS, Result
from crabada.game_stats import (
    get_daily_stats_message,
    update_game_stats_after_close,
)
from crabada.loot_sniping import LootSnipes
from crabada.miners_revenge import calc_miners_revenge, miners_revenge
from crabada.profitability import CrabadaTransaction, GameStats, NULL_STATS
from crabada.profitability import get_actual_game_profit, is_profitable_to_take_action
from crabada.strategies.strategy import GameStage, Strategy
from crabada.strategies.strategy_selection import STRATEGY_SELECTION, strategy_to_game_type
from crabada.types import CrabForLending, IdleGame, Team, MineOption
from utils import logger
from utils.config_types import UserConfig, SmsConfig
from utils.csv_logger import CsvLogger
from utils.email import Email, send_email
from utils.general import dict_sum, get_pretty_seconds, TIMESTAMP_FORMAT
from utils.math import Average
from utils.price import Prices, DEFAULT_GAS_USED
from utils.price import is_gas_too_high, wei_to_tus, wei_to_cra_raw, wei_to_tus_raw
from utils.user import get_alias_from_user
from web3_utils.swimmer_network_web3_client import SwimmerNetworkClient
from web3_utils.tus_swimmer_web3_client import TusSwimmerWeb3Client
from web3_utils.web3_client import web3_transaction


class CrabadaMineBot:
    TIME_BETWEEN_TRANSACTIONS = 5.0
    ALERT_THROTTLING_TIME = 60.0 * 120.0
    MIN_MINE_POINT = 60

    def __init__(
        self,
        user: str,
        config: UserConfig,
        from_sms_number: str,
        sms_client: Client,
        email_accounts: T.List[Email],
        encrypt_password: str,
        log_dir: str,
        dry_run: bool,
    ) -> None:
        self.user: str = user
        self.from_sms_number: str = from_sms_number
        self.sms: Client = sms_client
        self.emails: T.List[Email] = email_accounts
        self.log_dir: str = log_dir
        self.dry_run: bool = dry_run
        self.address: Address = config["address"]

        self.crabada_w3: CrabadaWeb3Client = T.cast(
            CrabadaWeb3Client,
            (
                CrabadaWeb3Client()
                .set_credentials(config["address"], config["private_key"])
                .set_node_uri(SwimmerNetworkClient.NODE_URL)
                .set_dry_run(dry_run)
            ),
        )
        self.tus_w3: TusSwimmerWeb3Client = T.cast(
            TusSwimmerWeb3Client,
            (
                TusSwimmerWeb3Client()
                .set_credentials(config["address"], config["private_key"])
                .set_node_uri(SwimmerNetworkClient.NODE_URL)
                .set_dry_run(dry_run)
            ),
        )
        self.crabada_w2: CrabadaWeb2Client = CrabadaWeb2Client()

        self.game_stats: T.Dict[int, GameStat] = dict()
        self.updated_game_stats: bool = True
        self.reinforcement_search_backoff: int = 0
        self.last_mine_start: T.Optional[float] = None
        self.last_date = datetime.date.today()
        self.time_since_last_alert: T.Optional[float] = None
        self.fraud_detection_tracker: T.Set[int] = set()
        self.reinforcement_skip_tracker: T.Set[int] = set()

        self.prices: Prices = Prices(0.0, 0.0, 0.0)
        self.avg_gas_used: Average = Average()
        self.fast_avg_gas_used: Average = Average()
        self.avg_reinforce_tus: Average = Average(15.0)
        self.avg_gas_gwei: Average = Average(60.0)

        self.config_mgr = ConfigManagerFirebase(
            user,
            config,
            email_accounts,
            encrypt_password,
            log_dir,
            dry_run=dry_run,
            verbose=True,
        )
        self.config_mgr.init()

        if not self.config_mgr.config["game_specific_configs"].get("authorization", ""):
            self._authorize_user()

        self.mining_strategy = STRATEGY_SELECTION[
            config["game_specific_configs"]["mining_strategy"]
        ](
            self.address,
            self.crabada_w2,
            self.crabada_w3,
            self.config_mgr,
        )
        self.looting_strategy = STRATEGY_SELECTION[
            config["game_specific_configs"]["looting_strategy"]
        ](
            self.address,
            self.crabada_w2,
            self.crabada_w3,
            self.config_mgr,
        )

        self.alias = get_alias_from_user(self.user)
        self.stats_logger = CrabadaLifetimeGameStatsLogger(
            self.alias,
            self.log_dir,
            self.config_mgr.get_lifetime_stats(),
            self.dry_run,
            verbose=True,
        )
        csv_header = ["timestamp"] + [k for k in NULL_STATS.keys()] + ["team_id"]
        csv_file = self.stats_logger.get_lifetime_stats_file().split(".")[0] + ".csv"
        self.csv = CsvLogger(csv_file, csv_header, dry_run)

        # TODO(ross): known race condition if multiple bots write to same file at same time
        # however, we are running all bots in single loop now so don't need a lock until/if we
        # ever have multiple bots running again on the same system
        self.loot_sniper: LootSnipes = LootSnipes("", False, False)

        logger.print_ok_blue(f"Adding bot for user {self.alias} with address {self.address}")

    def _authorize_user(self) -> str:
        address = self.address.lower()
        timestamp = str(int(time.time() * 1000))
        to_sign = f"{address}_{timestamp}"
        signable = messages.encode_defunct(text=to_sign)
        signed = Account.sign_message(signable, private_key=self.config_mgr.config["private_key"])
        logger.print_normal(f"Signing authorization and getting auth token....")
        auth_token = self.crabada_w2.get_auth_token(self.address, signed.signature.hex(), timestamp)
        if not auth_token:
            logger.print_warn(f"Failed to auth user!")
            return ""

        logger.print_ok(f"Successfully authorized user: {auth_token}")
        self.config_mgr.config["game_specific_configs"]["authorization"] = auth_token
        return auth_token

    def _check_calc_and_send_daily_update_message(self) -> None:
        today = datetime.date.today()
        if today == self.last_date:
            return

        self.last_date = today
        yesterday = today - datetime.timedelta(days=1)

        message = get_daily_stats_message(self.alias, self.csv, yesterday)

        logger.print_normal(message)

        if self.dry_run:
            return

        yesterday_pretty = yesterday.strftime("%m/%d/%Y")
        subject = f"\U0001F4C8 Crabada Daily Bot Stats for {yesterday_pretty}"

        if self.config_mgr.config["email"]:
            send_email(
                self.emails,
                self.config_mgr.config["email"],
                subject,
                message,
            )

    def _send_status_update(
        self,
        do_send_sms: bool,
        do_send_email: bool,
        custom_message: str,
        tx_hash: str = None,
        subject: str = f"{GAME_BOT_STRING} Update",
    ) -> None:

        if self.dry_run:
            return

        content = f"Action: {custom_message}\n\n"

        if tx_hash is None:
            explorer_content = f"Explorer: https://explorer.swimmer.network/address/{self.config_mgr.config['address']}\n\n"
        else:
            explorer_content = f"Explorer: https://explorer.swimmer.network/tx/{tx_hash}\n\n"

        logger.print_normal(explorer_content)

        content += explorer_content
        content += "---\U0001F579  GAME STATS\U0001F579  ---\n"

        for k, v in self.stats_logger.lifetime_stats.items():
            if k in [MineOption.MINE, MineOption.LOOT]:
                content += f"{k}:\n"
                for s, n in self.stats_logger.lifetime_stats[k].items():
                    content += f"\t{' '.join(s.lower().split('_'))}: {n:.3f}\n"
                content += "\n"
            else:
                if isinstance(v, dict):
                    content += f"{' '.join(k.upper().split('_'))}: {dict_sum(v):.3f}\n"
                else:
                    content += f"{' '.join(k.upper().split('_'))}: {v:.3f}\n"
                content += "\n"

        try:
            if do_send_sms and self.from_sms_number:
                sms_message = f"{GAME_BOT_STRING} Alert \U0001F980\n\n"
                sms_message += content
                message = self.sms.messages.create(
                    body=sms_message,
                    from_=self.from_sms_number,
                    to=self.config_mgr.config["sms_number"],
                )
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail("Failed to send sms alert")

        if do_send_email and self.config_mgr.config["email"]:
            email_message = f"Hello {self.alias}!\n"
            email_message += content
            send_email(
                self.emails,
                self.config_mgr.config["email"],
                subject,
                email_message,
            )

    def _update_bot_stats(self, tx: CrabadaTransaction, team: Team, mine: IdleGame) -> None:
        team_id = team["team_id"]
        if team_id not in self.game_stats:
            self.game_stats[team_id] = NULL_STATS

        update_game_stats_after_close(
            tx,
            team,
            mine,
            self.stats_logger.lifetime_stats,
            self.game_stats,
            self.prices,
            self.config_mgr.config["commission_percent_per_mine"],
        )

        outcome_emoji = "\U0001F389" if tx.result == Result.WIN else "\U0001F915"

        profit_tus, profit_usd = get_actual_game_profit(
            self.game_stats[team_id], with_commission=False
        )
        self.game_stats[team_id]["profit_tus"] = profit_tus
        self.game_stats[team_id]["profit_usd"] = profit_usd

        logger.print_bold(f"Profits: {profit_tus:.2f} TUS (${profit_usd:.2f})")

        profit_tus, profit_usd = get_actual_game_profit(
            self.game_stats[team_id], with_commission=True
        )

        logger.print_bold(f"Profits w/ commission: {profit_tus:.2f} TUS (${profit_usd:.2f})")

        message = f"Successfully closed {tx.game_type} {team['game_id']}, we {tx.result} {outcome_emoji}.\n"
        if team["team_id"] in self.reinforcement_skip_tracker:
            self.reinforcement_skip_tracker.discard(team["team_id"])
            message += f"**NOTE: we intentionally did not reinforce this mine due to sustained periods of negative expected profit or high gas!\n"
        logger.print_ok_arrow(message)

        message += f"Profits: {profit_tus:.2f} TUS [${profit_usd:.2f}]\n"

        self._send_status_update(
            False,
            self.config_mgr.config["get_email_updates"],
            message,
            tx_hash=tx.tx_hash,
        )

        self.stats_logger.write()

        now = datetime.datetime.now()
        self.game_stats[team_id]["timestamp"] = now.strftime(TIMESTAMP_FORMAT)
        self.game_stats[team_id]["team_id"] = team_id
        self.game_stats[team_id]["miners_revenge"] = calc_miners_revenge(
            mine, is_looting=tx.game_type == MineOption.LOOT
        )
        self.csv.write(self.game_stats[team_id])
        self.game_stats.pop(team_id)
        self.updated_game_stats = True

    def _print_bot_stats(self) -> None:
        logger.print_normal("\n")
        logger.print_bold("--------\U0001F579  GAME STATS\U0001F579  ------")
        logger.print_normal(
            f"Explorer: https://explorer.swimmer.network/address/{self.config_mgr.config['address']}\n\n"
        )
        for k, v in self.stats_logger.lifetime_stats.items():
            if k in [MineOption.MINE, MineOption.LOOT]:
                logger.print_ok_blue(f"{k}:")
                for s, n in self.stats_logger.lifetime_stats[k].items():
                    logger.print_ok_blue(f"  {' '.join(s.lower().split('_'))}: {n:.3f}")
            else:
                logger.print_ok_blue(f"{' '.join(k.upper().split('_'))}: {v}")
        logger.print_ok_blue("\n")
        logger.print_bold("------------------------------\n")

    def _send_out_of_gas_sms(self):
        now = time.time()
        if (
            self.time_since_last_alert is not None
            and now - self.time_since_last_alert < self.ALERT_THROTTLING_TIME
        ):
            return

        message = f"Unable to complete bot transaction due to insufficient gas \U000026FD!\n"
        message += f"Please add TUS to your wallet ASAP to avoid delay in mining!\n"
        logger.print_fail(message)

        # always send the email
        email_message = f"Hello {self.alias}!\n"
        email_message += message
        try:
            send_email(
                self.emails,
                self.config_mgr.config["email"],
                f"Bot: Out of Gas Notification!",
                email_message,
            )
        except:
            logger.print_warn(
                f"Failed to send out of gas email alert to {self.config_mgr.config['email']}"
            )

        if self.config_mgr.config["get_sms_updates_alerts"]:
            sms_message = f"\U0001F980 Out of Gas Alert \U0001F980\n\n"
            sms_message += message
            try:
                self.sms.messages.create(
                    body=sms_message,
                    from_=self.from_sms_number,
                    to=self.config_mgr.config["sms_number"],
                )
            except:
                logger.print_warn(
                    f"Failed to send out of gas sms alert to {self.config_mgr.config['sms_number']}"
                )

        self.time_since_last_alert = now

    def _get_gas_cost(self, gas_used: T.Optional[float]) -> T.Optional[float]:
        gas_price_wei = self.crabada_w3.get_gas_price("wei")
        if gas_used is None or gas_price_wei is None:
            return None
        return wei_to_tus_raw(gas_price_wei * gas_used)

    def _calculate_and_log_gas_price(self, tx: CrabadaTransaction) -> float:
        if tx.gas is None or self.prices.tus_usd is None:
            return 0.0

        self.avg_gas_used.update(tx.tx_gas_used)
        self.fast_avg_gas_used.update(tx.tx_gas_used)

        tus_gas_usd = self.prices.tus_usd * tx.gas

        self.stats_logger.lifetime_stats["gas_tus"] += tx.gas
        logger.print_bold(f"Paid {tx.gas} TUS (${tus_gas_usd:.2f}) in gas")
        return tx.gas

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

            if mine_data is None or mine is None:
                continue

            if is_mine:
                team_id = "team_id"
                num_reinforcements = self.crabada_w2.get_num_mine_reinforcements(mine_data)
                is_winning = self.crabada_w2.mine_is_winning(mine_data)
                total_time = self.crabada_w2.get_total_mine_time(mine_data) + 1
                remaining_time = self.crabada_w2.get_remaining_time(mine_data)
                group = self.config_mgr.config["game_specific_configs"]["mining_teams"].get(
                    mine_data.get(team_id, -1)
                )
            else:
                team_id = "attack_team_id"
                num_reinforcements = self.crabada_w2.get_num_loot_reinforcements(mine_data)
                is_winning = self.crabada_w2.loot_is_winning(mine_data)
                total_time = self.looting_strategy.LOOTING_DURATION
                remaining_time = self.crabada_w2.get_remaining_loot_time(mine_data)
                group = self.config_mgr.config["game_specific_configs"]["looting_teams"].get(
                    mine_data.get(team_id, -1)
                )

            percent_done = (total_time - remaining_time) / total_time
            progress = (
                math.ceil(percent_done * PROGRESS_SLOTS) if remaining_time > 0 else PROGRESS_SLOTS
            )

            reinforments_used_str = logger.format_normal("[")
            for crab in self.crabada_w2.get_reinforcement_crabs(mine_data):
                if (
                    crab
                    in self.config_mgr.config["game_specific_configs"]["reinforcing_crabs"].keys()
                ):
                    reinforments_used_str += logger.format_ok_blue(f"{crab} ")
                else:
                    reinforments_used_str += logger.format_normal(f"{crab} ")
            reinforments_used_str += logger.format_normal("]")

            if mine_data is not None and len(mine_data.get("process", [])) > 0:
                round_str = mine_data["process"][-1].get("action", "unknown")
                team_str = str(mine_data[team_id])
                game_str = str(mine["game_id"])
            else:
                round_str = "unknown"
                team_str = "unknown"
                game_str = "unknown"

            logger.print_normal(
                "#{:3s}{:10s}{:6s}{:10s}{:20s}{:25s}{:15s}{:15s}{:20s}\t{:25s}".format(
                    str(inx + 1),
                    team_str,
                    str(group),
                    game_str,
                    round_str,
                    "|{}{}|".format("#" * progress, " " * (PROGRESS_SLOTS - progress)),
                    get_pretty_seconds(remaining_time),
                    f"reinforced {num_reinforcements}x",
                    logger.format_ok("winning") if is_winning else logger.format_fail("losing"),
                    reinforments_used_str,
                )
            )
        logger.print_normal("\n")

    def _should_take_action(
        self, team: Team, game_stage: GameStage, strategy: Strategy, mine: T.Optional[IdleGame]
    ) -> bool:
        game_type = strategy_to_game_type(strategy)

        if game_stage == GameStage.START:
            stats = self.get_lifetime_stats()
            total_mine_games = (
                stats[MineOption.MINE]["game_wins"] + stats[MineOption.MINE]["game_losses"]
            )
            total_loot_games = (
                stats[MineOption.LOOT]["game_wins"] + stats[MineOption.LOOT]["game_losses"]
            )
            if (
                math.isclose(stats[MineOption.MINE]["game_win_percent"], 0.0, abs_tol=1.0)
                or total_mine_games < 50
            ):
                mine_win_percent = 40.0
            else:
                mine_win_percent = stats[MineOption.MINE]["game_win_percent"]

            if (
                math.isclose(stats[MineOption.LOOT]["game_win_percent"], 0.0, abs_tol=1.0)
                or total_loot_games < 50
            ):
                loot_win_percent = 60.0
            else:
                loot_win_percent = stats[MineOption.LOOT]["game_win_percent"]

            win_percentages = {
                MineOption.MINE: mine_win_percent,
                MineOption.LOOT: loot_win_percent,
            }

            if game_type == MineOption.MINE:
                group = self.config_mgr.config["game_specific_configs"]["mining_teams"].get(
                    team["team_id"], -1
                )
            else:
                group = self.config_mgr.config["game_specific_configs"]["looting_teams"].get(
                    team["team_id"], -1
                )

            does_have_self_reinforcements = any(
                [
                    c
                    for c, v in self.config_mgr.config["game_specific_configs"][
                        "reinforcing_crabs"
                    ].items()
                    if v == group
                ]
            )

            if self.fast_avg_gas_used.get_avg() is not None:
                avg_gas_price_tus = self._get_gas_cost(self.fast_avg_gas_used.get_avg())
            else:
                avg_gas_price_tus = 2.03

            if self.fast_avg_gas_used.count >= 5:
                self.fast_avg_gas_used.reset(self.fast_avg_gas_used.get_avg())

            if not is_profitable_to_take_action(
                team=team,
                prices=self.prices,
                avg_gas_price_tus=avg_gas_price_tus,
                avg_reinforce_tus=self.avg_reinforce_tus.get_avg(),
                win_percentages=win_percentages,
                commission_percent=dict_sum(self.config_mgr.config["commission_percent_per_mine"]),
                is_looting=game_type == MineOption.LOOT,
                is_reinforcing_allowed=self.config_mgr.config["game_specific_configs"][
                    "should_reinforce"
                ],
                can_self_reinforce=does_have_self_reinforcements,
                min_profit_threshold_tus=0.0,
                verbose=False,
            ):
                self.reinforcement_skip_tracker.add(team["team_id"])

                logger.print_warn(
                    f"Skipping {game_type} {game_stage} for team {team['team_id']} because it is unprofitable!"
                )
                return False

        elif is_gas_too_high(
            gas_price_gwei=self.crabada_w3.get_gas_price(),
            max_price_gwei=self.config_mgr.config["max_gas_price_gwei"],
            margin=strategy.get_gas_margin(game_stage=game_stage, mine=mine),
        ):
            self.reinforcement_skip_tracker.add(team["team_id"])

            logger.print_warn(
                f"Skipping {game_type} {game_stage} for team {team['team_id']} because of high gas!"
            )
            return False

        return True

    def _find_mine_to_loot(
        self,
        team: Team,
        available_loots: T.List[IdleGame],
    ) -> T.Optional[int]:
        mine_to_loot = None

        loot_candidates = self.loot_sniper.find_loot_snipe(self.address, [], available_loots)

        mine_to_loot, lowest_mr = self._find_best_loot(team, loot_candidates)

        if mine_to_loot is None:
            loot_candidates = self.loot_sniper.find_low_mr_teams(
                self.address, available_loots, verbose=True
            )

            mine_to_loot, lowest_mr = self._find_best_loot(team, loot_candidates)

        if mine_to_loot is not None:
            logger.print_normal(
                f"Loot[{mine_to_loot}]: Theirs: {loot_candidates[mine_to_loot]['faction']} Ours: {team['faction']}"
            )
            logger.print_normal(f"Miners Revenge: {lowest_mr:.2f}%")
            logger.print_normal(f"{json.dumps(loot_candidates[mine_to_loot], indent=4)}")

        return mine_to_loot

    def _find_best_loot(
        self, team: Team, loot_candidates: T.Dict[int, T.Any]
    ) -> T.Tuple[int, float]:
        mine_to_loot: int = None
        lowest_mr = 100.0
        highest_page = 0
        for loot, data in loot_candidates.items():
            mine_team: Team = Team(
                faction=data["faction"], battle_point=data["defense_battle_point"]
            )
            loot_points, mine_points = get_faction_adjusted_battle_points_from_teams(
                team, mine_team
            )
            mr = miners_revenge(
                mine_points, loot_points, data["defense_mine_point"], [], 3, False, False
            )
            if mr < lowest_mr or mr == lowest_mr and data["page"] > highest_page:
                mine_to_loot = loot
                lowest_mr = mr
                highest_page = data["page"]

        return mine_to_loot, lowest_mr

    def _reinforce_loot_or_mine(
        self,
        team: Team,
        mine: IdleGame,
        strategy: Strategy,
    ) -> None:
        if not strategy.should_reinforce(mine):
            return

        if not self._should_take_action(team, GameStage.REINFORCE, strategy, mine):
            return

        for _ in range(2):
            reinforcement_crab = strategy.get_reinforcement_crab(
                team, mine, self.reinforcement_search_backoff + strategy.get_backoff_margin()
            )
            if self._reinforce_with_crab(
                team,
                mine,
                reinforcement_crab,
                strategy,
            ):
                last_reinforcement_search_backoff = self.reinforcement_search_backoff
                self.reinforcement_search_backoff = max(0, self.reinforcement_search_backoff - 1)
                if last_reinforcement_search_backoff != self.reinforcement_search_backoff:
                    logger.print_ok_blue(
                        f"Reinforcement backoff: {last_reinforcement_search_backoff}->{self.reinforcement_search_backoff}"
                    )
                if team["team_id"] in self.reinforcement_skip_tracker:
                    self.reinforcement_skip_tracker.discard(team["team_id"])
                return

            self.reinforcement_search_backoff = self.reinforcement_search_backoff + 5
            logger.print_ok_blue(
                f"Adjusting reinforcement backoff to {self.reinforcement_search_backoff}"
            )

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

        have_reinforced = strategy.have_reinforced_at_least_once(mine)
        if team["team_id"] not in self.game_stats:
            self.game_stats[team["team_id"]] = NULL_STATS

        self.game_stats[team["team_id"]][
            "reinforce2" if have_reinforced else "reinforce1"
        ] = price_tus

        logger.print_normal(
            f"Mine[{mine['game_id']}]: Found reinforcement crabada {crabada_id} for {price_tus} Tus [BP {battle_points} | MP {mine_points}]"
        )

        if not math.isclose(price_tus, 0.0):
            self.avg_reinforce_tus.update(price_tus)

        available_tus = float(self.tus_w3.get_balance())
        if available_tus < price_tus:
            logger.print_warn(
                f"Insufficient TUS to purchase reinforcement! Balance: {available_tus}, Needed: {price_tus}"
            )
            return True

        with web3_transaction("insufficient funds for gas", self._send_out_of_gas_sms):
            tx = strategy.reinforce(team["game_id"], crabada_id, reinforcement_crab["price"])

            have_reinforced = strategy.have_reinforced_at_least_once(mine)
            gas_tus = self._calculate_and_log_gas_price(tx)
            self.game_stats[team["team_id"]][
                "gas_reinforce2" if have_reinforced else "gas_reinforce1"
            ] = gas_tus

            if tx.did_succeed:
                logger.print_ok_arrow(f"Successfully reinforced mine {team['game_id']}")
                self.time_since_last_alert = None
                self.stats_logger.lifetime_stats[tx.game_type]["tus_net"] -= price_tus
                self.stats_logger.lifetime_stats[tx.game_type]["tus_reinforcement"] += price_tus
                self.updated_game_stats = True
                return True

        logger.print_fail_arrow(f"Error reinforcing mine {team['game_id']}")
        return False

    def _close_mine(self, team: Team, mine: IdleGame, strategy: Strategy) -> bool:

        if not self._should_take_action(team, GameStage.CLOSE, strategy, mine):
            return False

        with web3_transaction("insufficient funds for gas", self._send_out_of_gas_sms):
            tx = strategy.close(team["game_id"])

            gas_tus = self._calculate_and_log_gas_price(tx)

            if tx.did_succeed:
                self.time_since_last_alert = None
                self._update_bot_stats(tx, team, mine)

                if team["team_id"] in self.fraud_detection_tracker:
                    self.fraud_detection_tracker.discard(team["team_id"])
                    logger.print_warn(f"Removing {team['team_id']} from fraud detection list")

                return True

            if team["team_id"] not in self.game_stats:
                self.game_stats[team["team_id"]] = NULL_STATS

            self.game_stats[team["team_id"]]["gas_close"] = gas_tus

        logger.print_fail_arrow(f"Error closing game {team['game_id']}")
        return False

    def _start_mine(self, team: Team) -> bool:
        logger.print_normal(f"Attemting to start new mine with team {team['team_id']}!")

        with web3_transaction("insufficient funds for gas", self._send_out_of_gas_sms):
            tx = self.mining_strategy.start(team["team_id"])

            gas_tus = self._calculate_and_log_gas_price(tx)

            if tx.did_succeed:
                self.time_since_last_alert = None
                self.game_stats[team["team_id"]] = copy.deepcopy(NULL_STATS)
                self.game_stats[team["team_id"]]["gas_start"] = gas_tus
                logger.print_ok_arrow(f"Successfully started mine for team {team['team_id']}")

                if team["team_id"] in self.fraud_detection_tracker:
                    content = f"Possible fraud detection from user {self.alias}.\n\n"
                    content += f"Started a mine with team {team['team_id']} that never was closed by the bot!"
                    send_email(self.emails, ADMIN_EMAIL, "Fraud Detection Alert!", content)
                else:
                    self.fraud_detection_tracker.add(team["team_id"])
                    logger.print_warn(f"Adding team {team['team_id']} to fraud detection list")

                return True

        logger.print_fail(f"Error starting mine for team {team['team_id']}")
        return False

    def _start_loot(self, team: Team, available_loots: T.List[IdleGame]) -> bool:
        mine_to_loot: T.Optional[IdleGame] = self._find_mine_to_loot(team, available_loots)

        if mine_to_loot is None:
            logger.print_warn(f"Failed to find a mine to loot!")
            return False

        logger.print_normal(
            f"Attemting to start loot of mine {mine_to_loot} with team {team['team_id']}!"
        )

        with web3_transaction("insufficient funds for gas", self._send_out_of_gas_sms):
            tx = self.looting_strategy.start(team["team_id"], mine_to_loot)

            gas_tus = self._calculate_and_log_gas_price(tx)

            if tx.did_succeed:
                self.time_since_last_alert = None
                self.game_stats[team["team_id"]] = copy.deepcopy(NULL_STATS)
                self.game_stats[team["team_id"]]["gas_start"] = gas_tus
                logger.print_ok_arrow(f"Successfully started loot for team {team['team_id']}")

                if team["team_id"] in self.fraud_detection_tracker:
                    content = f"Possible fraud detection from user {self.alias}.\n\n"
                    content += f"Started a loot with team {team['team_id']} that never was closed by the bot!"
                    send_email(self.emails, ADMIN_EMAIL, "Fraud Detection Alert!", content)
                else:
                    self.fraud_detection_tracker.add(team["team_id"])
                    logger.print_warn(f"Adding team {team['team_id']} to fraud detection list")

                # remove it from the available loots list
                for i, loot in enumerate(available_loots):
                    if loot["game_id"] != mine_to_loot:
                        continue

                    del available_loots[i]
                    break
                return True

        logger.print_fail(f"Error starting loot for team {team['team_id']}")
        self._authorize_user()
        return False

    def _is_team_allowed_to_mine(self, team: Team) -> bool:
        return team["team_id"] in self.config_mgr.config["game_specific_configs"][
            "mining_teams"
        ].keys() or self._is_team_allowed_to_loot(
            team
        )  # looting teams go back and forth between loot/mine

    def _is_team_allowed_to_loot(self, team: Team) -> bool:
        return (
            team["team_id"]
            in self.config_mgr.config["game_specific_configs"]["looting_teams"].keys()
            and self.config_mgr.config["game_specific_configs"]["authorization"]
        )

    def _check_and_maybe_reinforce_loots(self, team: Team, mine: IdleGame) -> None:
        self._reinforce_loot_or_mine(
            team,
            mine,
            self.looting_strategy,
        )

    def _check_and_maybe_reinforce_mines(self, team: Team, mine: IdleGame) -> None:
        self._reinforce_loot_or_mine(
            team,
            mine,
            self.mining_strategy,
        )

    def _check_and_maybe_close_loots(self, team: Team, mine: IdleGame) -> None:
        if not self.crabada_w2.loot_is_able_to_be_settled(mine):
            return

        if team["team_id"] in self.game_stats:
            # we don't do gas start for loots, so we don't track it
            self.game_stats[team["team_id"]]["gas_start"] = 0.0

        num_reinforcements = self.crabada_w2.get_num_mine_reinforcements(mine)
        if num_reinforcements == 0:
            self.loot_sniper.add_no_reinforce_address(mine)
        else:
            self.loot_sniper.remove_no_reinforce_address(mine)

        self._close_mine(team, mine, self.looting_strategy)

    def _check_and_maybe_start(self) -> None:
        available_teams = self.crabada_w2.list_available_teams(self.address)
        available_loots = []

        teams_to_mine = available_teams[:]
        for team in available_teams:
            if not self._is_team_allowed_to_loot(team):
                logger.print_warn(f"Skipping team {team['team_id']} for looting...")
                continue

            if not self._should_take_action(
                team, GameStage.START, self.looting_strategy, mine=None
            ):
                continue

            if not self.looting_strategy.should_start(team):
                continue

            if not available_loots:
                available_loots = self.loot_sniper.get_available_loots(self.address, 9, True)

            if self._start_loot(team, available_loots):
                teams_to_mine.remove(team)

        self._check_and_maybe_start_mines(teams_to_mine)

    def _check_and_maybe_close_mines(self, team: Team, mine: IdleGame) -> None:
        if not self.crabada_w2.mine_is_finished(mine):
            return

        self._close_mine(team, mine, self.mining_strategy)

    def _check_and_maybe_start_mines(self, teams_to_mine: T.List[Team]) -> None:
        groups_started = []

        for team in teams_to_mine:
            if not self._is_team_allowed_to_mine(team):
                logger.print_warn(f"Skipping team {team['team_id']} for mining...")
                continue

            if not self._should_take_action(team, GameStage.START, self.mining_strategy, mine=None):
                continue

            if not self.mining_strategy.should_start(team):
                continue

            # only start one team from group at a time in case there's some staggering
            # that needs to happen
            team_group = self.config_mgr.config["game_specific_configs"]["mining_teams"].get(
                team["team_id"], -1
            )

            if self._start_mine(team):
                groups_started.append(team_group)

    def _check_and_maybe_reinforce(self) -> None:
        if not self.config_mgr.config["game_specific_configs"].get("should_reinforce", True):
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
            if team["game_id"] is None or team["game_type"] is None:
                continue

            mine = self.crabada_w2.get_mine(team["game_id"])
            if mine is None:
                continue

            if mine.get("game_id", "") in loots:
                self._check_and_maybe_close_loots(team, mine)

            if mine.get("game_id", "") in mines:
                self._check_and_maybe_close_mines(team, mine)

    def get_lifetime_stats(self) -> T.Dict[str, T.Any]:
        return self.stats_logger.lifetime_stats

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

    def get_avg_gas_tus(self) -> T.Optional[float]:
        return self._get_gas_cost(self.avg_gas_used.get_avg())

    def get_avg_reinforce_tus(self) -> T.Optional[float]:
        return self.avg_reinforce_tus.get_avg()

    def get_avg_gas_gwei(self) -> T.Optional[float]:
        return self.avg_gas_gwei.get_avg()

    def get_config(self) -> UserConfig:
        return self.config_mgr.config

    def run(self) -> None:
        logger.print_normal("=" * 60)

        logger.print_ok(f"User: {self.alias.upper()}")

        gas_price_gwei = self.crabada_w3.get_gas_price()
        if gas_price_gwei is None:
            gas_price_gwei = -1.0
        self.avg_gas_gwei.update(gas_price_gwei)
        logger.print_ok(
            f"AVAX: ${self.prices.avax_usd:.3f}, TUS: ${self.prices.tus_usd:.4f}, CRA: ${self.prices.cra_usd:.4f}, Gas: {gas_price_gwei:.2f}"
        )

        self._check_calc_and_send_daily_update_message()

        self.config_mgr.check_for_config_updates()

        self._print_mine_loot_status()

        self._check_and_maybe_close()
        time.sleep(2.0)
        self._check_and_maybe_start()
        time.sleep(2.0)
        self._check_and_maybe_reinforce()
        time.sleep(2.0)

        if self.updated_game_stats:
            self.updated_game_stats = False
            self._print_bot_stats()

        self.stats_logger.write()

    def end(self) -> None:
        logger.print_fail(f"Exiting bot for {self.user}...")

        self.stats_logger.write()
        self.config_mgr.close()

        for team in self.game_stats.keys():
            self.game_stats[team]["team_id"] = team
        if self.game_stats:
            self.csv.write(self.game_stats)
