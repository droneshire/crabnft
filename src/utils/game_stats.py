import copy
import json
import os
import typing as T
from eth_typing import Address

from utils import logger
from utils.price import Prices, wei_to_cra_raw, wei_to_tus_raw
from crabada.profitability import Result
from crabada.strategies.strategy import CrabadaTransaction
from crabada.types import IdleGame, Team


class GameStats(T.TypedDict):
    reinforce1: float
    reinforce2: float
    gas_start: float
    gas_reinforce1: float
    gas_reinforce2: float
    gas_close: float
    game_type: T.Literal["MINE", "LOOT"]
    reward_tus: float
    reward_cra: float
    avax_usd: float
    tus_usd: float
    cra_usd: float
    commission_tus: float
    outcome: T.Literal["WIN", "LOSE"]


NULL_STATS = GameStats(
    reinforce1=0.0,
    reinforce2=0.0,
    gas_start=0.0,
    gas_reinforce1=0.0,
    gas_reinforce2=0.0,
    gas_close=0.0,
    game_type="MINE",
    reward_tus=0.0,
    reward_cra=0.0,
    avax_usd=0.0,
    tus_usd=0.0,
    cra_usd=0.0,
    commission_tus=0.0,
    outcome="WIN",
)


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
)


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
    if team_id in game_stats:
        game_stats[team_id]["reward_tus"] = tus_rewards
        game_stats[team_id]["reward_cra"] = cra_rewards
        game_stats[team_id]["game_type"] = tx.game_type

    stats = lifetime_stats[tx.game_type]

    did_win = tx.result == Result.WIN or mine.get("winner_team_id", "") == team_id

    if did_win:
        stats["game_wins"] += 1
        if team_id in game_stats:
            game_stats[team_id]["outcome"] = Result.WIN
    else:
        stats["game_losses"] += 1
        if team_id in game_stats:
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

        if team_id in game_stats:
            game_stats[team_id]["commission_tus"] = commission_tus

        lifetime_stats["commission_tus"][address] = (
            lifetime_stats["commission_tus"].get(address, 0.0) + commission_tus
        )

        stats["tus_net"] -= commission_tus
        stats["cra_net"] -= commission_cra

    if team_id in game_stats:
        game_stats[team_id]["avax_usd"] = prices.avax_usd
        game_stats[team_id]["tus_usd"] = prices.tus_usd
        game_stats[team_id]["cra_usd"] = prices.cra_usd

    lifetime_stats[tx.game_type] = copy.deepcopy(stats)


def update_lifetime_stats_format(game_stats: LifetimeGameStats) -> LifetimeGameStats:
    new_game_stats = LifetimeGameStats()
    new_game_stats["MINE"] = MineLootGameStats()
    new_game_stats["LOOT"] = MineLootGameStats()

    if "MINE" in game_stats or "LOOT" in game_stats:
        return game_stats

    for k, v in game_stats.items():
        if k in ["commission_tus", "avax_gas_usd"]:
            new_game_stats[k] = v
        elif k not in NULL_GAME_STATS["MINE"].keys():
            continue
        elif isinstance(v, (float, int)):
            new_game_stats["MINE"][k] = v
            new_game_stats["LOOT"][k] = 0.0
        else:
            return game_stats
    logger.print_normal(f"Old:\n{json.dumps(game_stats, indent=4)}")
    logger.print_bold(f"New:\n{json.dumps(new_game_stats, indent=4)}")
    return new_game_stats


def get_lifetime_stats_file(user: str, log_dir: str) -> str:
    return os.path.join(log_dir, user.lower() + "_lifetime_game_bot_stats.json")


def get_game_stats(user: str, log_dir: str) -> T.Dict[str, T.Any]:
    game_stats_file = get_lifetime_stats_file(user, log_dir)
    if not os.path.isfile(game_stats_file):
        return NULL_GAME_STATS
    with open(game_stats_file, "r") as infile:
        return json.load(infile)


def write_game_stats(user: str, log_dir: str, game_stats: LifetimeGameStats, dry_run=False) -> None:
    if dry_run:
        return

    game_stats_file = get_lifetime_stats_file(user, log_dir)
    with open(game_stats_file, "w") as outfile:
        json.dump(
            game_stats,
            outfile,
            indent=4,
            sort_keys=True,
        )
