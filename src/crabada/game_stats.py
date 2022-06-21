import copy
import datetime
import deepdiff
import json
import os
import typing as T
from eth_typing import Address

from utils import logger
from utils.csv_logger import CsvLogger
from utils.game_stats import LifetimeGameStatsLogger
from utils.general import TIMESTAMP_FORMAT
from utils.price import Prices, wei_to_cra_raw, wei_to_tus_raw
from utils.user import get_alias_from_user
from crabada.profitability import CrabadaTransaction, GameStats, MineOption, Result, NULL_STATS
from crabada.types import IdleGame, MineOption, Team


class MineLootGameStats(T.TypedDict):
    tus_gross: T.Dict[str, float]
    cra_net: T.Dict[str, float]
    tus_net: T.Dict[str, float]
    cra_gross: T.Dict[str, float]
    game_wins: T.Dict[str, float]
    game_losses: T.Dict[str, float]
    game_win_percent: T.Dict[str, float]
    tus_reinforcement: T.Dict[str, float]


class LifetimeGameStats(T.TypedDict):
    commission_tus: float
    avax_gas_usd: float
    gas_tus: float
    MINE: MineLootGameStats
    LOOT: MineLootGameStats


NULL_GAME_STATS = LifetimeGameStats(
    MINE=MineLootGameStats(
        cra_gross=0.0,
        tus_gross=0.0,
        cra_net=0.0,
        tus_net=0.0,
        game_wins=0.0,
        game_losses=0.0,
        game_win_percent=0.0,
        tus_reinforcement=0.0,
    ),
    LOOT=MineLootGameStats(
        cra_gross=0.0,
        tus_gross=0.0,
        cra_net=0.0,
        tus_net=0.0,
        game_wins=0,
        game_losses=0,
        game_win_percent=0.0,
        tus_reinforcement=0.0,
    ),
    commission_tus=dict(),
    avax_gas_usd=0.0,
    gas_tus=0.0,
)


def get_daily_stats_message(user: str, csv: CsvLogger, target_date: datetime.datetime) -> str:
    profit_usd = 0.0
    total_tus = 0.0
    total_cra = 0.0
    wins = {
        MineOption.LOOT: 0,
        MineOption.MINE: 0,
    }
    losses = {
        MineOption.LOOT: 0,
        MineOption.MINE: 0,
    }
    miners_revenge = 0.0
    total_mrs = 0

    message = ""

    rows = csv.read()

    for row in csv.read():
        if len(row) < len(csv.get_col_map().keys()):
            continue

        timestamp = row[csv.get_col_map()["timestamp"]]

        if not timestamp:
            continue

        try:
            date = datetime.datetime.strptime(timestamp.strip(), TIMESTAMP_FORMAT)
        except:
            continue

        if target_date != date.date():
            continue

        p = row[csv.get_col_map()["profit_usd"]]
        if p:
            profit_usd += float(p)

        game_type = row[csv.get_col_map()["game_type"]]

        r = row[csv.get_col_map()["outcome"]]
        if r:
            wins[game_type] += 1 if r.upper() == Result.WIN else 0
            losses[game_type] += 1 if r.upper() == Result.LOSE else 0

        c = row[csv.get_col_map()["reward_cra"]]
        if c:
            total_cra += float(c)

        t = row[csv.get_col_map()["reward_tus"]]
        if t:
            total_tus += float(t)

        if game_type == MineOption.LOOT:
            continue

        m = row[csv.get_col_map()["miners_revenge"]]
        if m and float(m) > 0.0 and float(m) < 100.0:
            miners_revenge += min(float(m), 40.0)
            total_mrs += 1

    if total_mrs > 0:
        miners_revenge = miners_revenge / total_mrs

    date_pretty = target_date.strftime("%m/%d/%Y")
    message += f"------------{user}'s Stats For {date_pretty}------------\n\n"
    message += f"Net Profit USD: ${profit_usd:.2f}\n"
    message += f"Gross TUS: {total_tus:.2f} TUS\n"
    message += f"Gross CRA: {total_cra:.2f} CRA\n"
    for gt in wins.keys():
        if wins[gt] + losses[gt] > 0:
            win_percent = (wins[gt] / float(wins[gt] + losses[gt])) * 100.0
        else:
            win_percent = 0.0
        message += f"[{gt.upper()}] Wins: {wins[gt]} Losses: {losses[gt]}\n"
        message += f"[{gt.upper()}] Win Percent: {win_percent:.2f}%\n"
    message += f"[MINE] Avg Miners Revenge: {miners_revenge:.2f}%\n"
    return message


def update_game_stats_after_close(
    tx: CrabadaTransaction,
    team: Team,
    mine: IdleGame,
    lifetime_stats: LifetimeGameStats,
    game_stats: GameStats,
    prices: Prices,
    commission: T.Dict[Address, float],
) -> None:
    tus_rewards = 0.0 if tx.tus_rewards is None else tx.tus_rewards
    cra_rewards = 0.0 if tx.cra_rewards is None else tx.cra_rewards

    team_id = team["team_id"]

    game_stats[team_id]["reward_tus"] = tus_rewards
    game_stats[team_id]["reward_cra"] = cra_rewards
    game_stats[team_id]["game_type"] = tx.game_type

    stats = lifetime_stats[tx.game_type]

    did_win = tx.result == Result.WIN or mine.get("winner_team_id", "") == team_id

    if did_win:
        stats["game_wins"] += 1
        game_stats[team_id]["outcome"] = Result.WIN
    else:
        stats["game_losses"] += 1
        game_stats[team_id]["outcome"] = Result.LOSE

    stats["game_win_percent"] = (
        100.0 * float(stats["game_wins"]) / (stats["game_wins"] + stats["game_losses"])
    )

    logger.print_normal(f"Earned {tus_rewards} TUS, {cra_rewards} CRA")

    stats["tus_gross"] = stats["tus_gross"] + tus_rewards
    stats["cra_gross"] = stats["cra_gross"] + cra_rewards
    stats["tus_net"] = stats["tus_net"] + tus_rewards
    stats["cra_net"] = stats["cra_net"] + cra_rewards

    for address, commission in commission.items():
        commission_tus = tus_rewards * (commission / 100.0)
        commission_cra = cra_rewards * (commission / 100.0)
        # convert cra -> tus and add to tus commission, we dont take direct cra commission
        commission_tus += prices.cra_to_tus(commission_cra)

        logger.print_ok(f"Added {commission_tus} TUS for {address} in commission ({commission}%)!")

        game_stats[team_id]["commission_tus"] = commission_tus

        lifetime_stats["commission_tus"][address] = (
            lifetime_stats["commission_tus"].get(address, 0.0) + commission_tus
        )

        stats["tus_net"] -= commission_tus
        stats["cra_net"] -= commission_cra

    game_stats[team_id]["avax_usd"] = prices.avax_usd
    game_stats[team_id]["tus_usd"] = prices.tus_usd
    game_stats[team_id]["cra_usd"] = prices.cra_usd

    lifetime_stats[tx.game_type] = copy.deepcopy(stats)


def update_lifetime_stats_format(game_stats: LifetimeGameStats) -> LifetimeGameStats:
    new_game_stats = LifetimeGameStats()
    new_game_stats[MineOption.MINE] = MineLootGameStats()
    new_game_stats[MineOption.LOOT] = MineLootGameStats()

    if "gas_tus" in game_stats:
        return game_stats

    new_game_stats = copy.deepcopy(game_stats)
    new_game_stats["gas_tus"] = 0.0
    logger.print_normal(f"Old:\n{json.dumps(game_stats, indent=4)}")
    logger.print_bold(f"New:\n{json.dumps(new_game_stats, indent=4)}")
    return new_game_stats


def delta_game_stats(
    user_a_stats: LifetimeGameStats, user_b_stats: LifetimeGameStats, verbose: bool = False
) -> LifetimeGameStats:
    diff = deepdiff.DeepDiff(user_a_stats, user_b_stats)
    if not diff:
        return NULL_GAME_STATS

    diffed_stats = copy.deepcopy(NULL_GAME_STATS)

    for item in ["avax_gas_usd", "gas_tus"]:
        if item not in user_a_stats or item not in user_b_stats:
            diffed_stats[item] = 0.0
        else:
            diffed_stats[item] = user_a_stats[item] - user_b_stats[item]

    for item in ["commission_tus"]:
        for k, v in user_a_stats[item].items():
            diffed_stats[item][k] = v

        for k, v in user_b_stats[item].items():
            diffed_stats[item][k] = diffed_stats[item].get(k, 0.0) - v

    for game_type in [MineOption.MINE, MineOption.LOOT]:
        for k, v in user_a_stats[game_type].items():
            diffed_stats[game_type][k] = v

        for k, v in user_b_stats[game_type].items():
            diffed_stats[game_type][k] = diffed_stats[game_type].get(k, 0.0) - v

    if verbose:
        logger.print_bold("Subtracting game stats:")
        logger.print_normal(json.dumps(diffed_stats, indent=4))
    return diffed_stats


def merge_game_stats(
    user_a_stats: str, user_b_stats: str, log_dir: str, verbose
) -> LifetimeGameStats:
    diff = deepdiff.DeepDiff(user_a_stats, user_b_stats)
    if not diff:
        return user_a_stats

    merged_stats = copy.deepcopy(NULL_GAME_STATS)

    for item in ["avax_gas_usd", "gas_tus"]:
        merged_stats[item] = merged_stats.get(item, 0.0) + user_a_stats.get(item, 0.0)
        merged_stats[item] = merged_stats.get(item, 0.0) + user_b_stats.get(item, 0.0)

    for item in ["commission_tus"]:
        for k, v in user_a_stats[item].items():
            merged_stats[item][k] = merged_stats[item].get(k, 0.0) + v

        for k, v in user_b_stats[item].items():
            merged_stats[item][k] = merged_stats[item].get(k, 0.0) + v

    for game_type in [MineOption.MINE, MineOption.LOOT]:
        for k, v in user_a_stats[game_type].items():
            merged_stats[game_type][k] += v

        for k, v in user_b_stats[game_type].items():
            merged_stats[game_type][k] += v

    if verbose:
        logger.print_bold("Merging game stats:")
        logger.print_normal(json.dumps(merged_stats, indent=4))
    return merged_stats


class CrabadaLifetimeGameStatsLogger(LifetimeGameStatsLogger):
    def __init__(
        self,
        user: str,
        null_game_stats: T.Dict[T.Any, T.Any],
        log_dir: str,
        backup_stats: T.Dict[T.Any, T.Any],
        dry_run: bool = False,
        verbose: bool = False,
    ):
        super().__init__(user, null_game_stats, log_dir, backup_stats, dry_run, verbose)

    def write(self) -> None:
        delta_stats = delta_game_stats(
            self.lifetime_stats, self.last_lifetime_stats, verbose=self.verbose
        )
        file_stats = self.read()
        combined_stats = merge_game_stats(
            delta_stats, file_stats, self.log_dir, verbose=self.verbose
        )

        if self.verbose:
            logger.print_bold(f"Writing stats for {self.user} [alias: {self.alias}]")

        self.write_game_stats(combined_stats, dry_run=self.dry_run)
        self.last_lifetime_stats = copy.deepcopy(self.lifetime_stats)

    def read(self) -> T.Dict[T.Any, T.Any]:
        if self.verbose:
            logger.print_bold(f"Reading stats for {self.user} [alias: {self.alias}]")

        return self.get_game_stats()
