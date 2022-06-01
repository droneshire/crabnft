import datetime
import os
import typing as T
import textwrap

from eth_typing import Address

from crabada.types import Team, CrabadaClass, MineOption, CRABADA_ID_TO_CLASS
from crabada.crabada_web3_client import CrabadaWeb3Client
from utils import csv_logger, logger
from utils.general import TIMESTAMP_FORMAT
from utils.price import Prices, wei_to_tus_raw, wei_to_tus_raw

NORMALIZED_TIME = 4.0

CRA_MULTIPLIER = 1.0
IDLE_MULTIPLIER = 0.7


class Result:
    WIN = "WIN"
    LOSE = "LOSE"
    UNKNOWN = "UNKNOWN"


class GameStage:
    START = "START"
    CLOSE = "CLOSE"
    REINFORCE = "REINFORCE"


class CrabadaTransaction:
    def __init__(
        self,
        tx_hash: str,
        game_type: T.Literal["LOOT", "MINE"],
        tus: float,
        cra: float,
        did_succeed: bool,
        result: Result,
        gas: float,
        tx_gas_used: float,
    ):
        self.tx_hash = tx_hash
        self.tus_rewards = tus
        self.cra_rewards = cra
        self.did_succeed = did_succeed
        self.result = result
        self.gas = gas
        self.game_type = game_type
        self.tx_gas_used = tx_gas_used


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
    outcome: T.Literal[Result.WIN, Result.LOSE]
    team_id: int
    profit_usd: float
    miners_revenge: float


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
    outcome=Result.UNKNOWN,
    team_id=0,
    profit_usd=0.0,
    miners_revenge=0.0,
)

STATIC_WIN_PERCENTAGES = {
    "MINE": 40.0,
    "LOOT": 60.0,
}


class Scenarios:
    Loot = "LOOT"
    LootAndSelfReinforce = "LOOT & SELF REINFORCE"
    LootAndNoReinforce = "LOOT & NO REINFORCE"
    LootWithNoContest = "LOOT w/ NO CONTEST"
    MineAndReinforce = "MINE & REINFORCE"
    MineTenPercentAndReinforce = "MINE +10% & REINFORCE"
    MineTenPercentAndSelfReinforce = "MINE +10% & SELF REINFORCE"
    MineAndNoReinforce = "MINE & NO REINFORCE"
    MineAndSelfReinforce = "MINE & SELF REINFORCE"
    MineTenPercentAndNoReinforce = "MINE +10% & NO REINFORCE"
    MineWithNoContest = "MINE w/ NO CONTEST"
    MineTenPercentWithNoContest = "MINE +10% w/ NO CONTEST"
    TavernThreeMpCrabs = "TAVERN 3 MP CRABS"


NO_CONTEST_SCENARIOS = [
    Scenarios.LootWithNoContest,
    Scenarios.MineWithNoContest,
    Scenarios.MineTenPercentWithNoContest,
]

LOOT_SCENARIOS = [
    Scenarios.Loot,
    Scenarios.LootAndSelfReinforce,
    Scenarios.LootWithNoContest,
    Scenarios.LootAndNoReinforce,
]

MINE_SCENARIOS = [
    Scenarios.MineAndReinforce,
    Scenarios.MineTenPercentAndReinforce,
    Scenarios.MineTenPercentAndSelfReinforce,
    Scenarios.MineAndNoReinforce,
    Scenarios.MineAndSelfReinforce,
    Scenarios.MineTenPercentAndNoReinforce,
    Scenarios.MineWithNoContest,
    Scenarios.MineTenPercentWithNoContest,
]

TEN_PERCENT_MINE_SCENARIOS = [
    Scenarios.MineTenPercentAndReinforce,
    Scenarios.MineTenPercentAndSelfReinforce,
    Scenarios.MineTenPercentAndNoReinforce,
]

SELF_REINFORCE_SCENARIOS = [
    Scenarios.LootAndSelfReinforce,
    Scenarios.MineTenPercentAndSelfReinforce,
    Scenarios.MineAndSelfReinforce,
]

REINFORCE_SCENARIOS = [
    Scenarios.MineAndReinforce,
    Scenarios.MineTenPercentAndReinforce,
    Scenarios.Loot,
    Scenarios.LootAndSelfReinforce,
    Scenarios.MineTenPercentAndSelfReinforce,
    Scenarios.MineAndSelfReinforce,
]

NO_REINFORCE_PAY_SCENARIOS = (
    [
        Scenarios.LootAndNoReinforce,
        Scenarios.MineAndNoReinforce,
        Scenarios.MineTenPercentAndNoReinforce,
    ]
    + NO_CONTEST_SCENARIOS
    + SELF_REINFORCE_SCENARIOS
)

REWARDS_TUS: T.Dict[str, T.Dict[str, float]] = {
    Scenarios.Loot: {
        Result.WIN: {
            "TUS": 155.21625 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        Result.LOSE: {
            "TUS": 17.01 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        "time_normalized": 1.0,
    },
    Scenarios.LootAndSelfReinforce: {
        Result.WIN: {
            "TUS": 155.21625 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        Result.LOSE: {
            "TUS": 17.01 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        "time_normalized": 1.0,
    },
    Scenarios.LootAndNoReinforce: {
        Result.WIN: {
            "TUS": 155.21625 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        Result.LOSE: {
            "TUS": 17.01 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        "time_normalized": 1.0,
    },
    Scenarios.LootWithNoContest: {
        Result.WIN: {
            "TUS": 155.21625 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        Result.LOSE: {
            "TUS": 155.21625 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        "time_normalized": 1.0,
    },
    Scenarios.MineAndReinforce: {
        Result.WIN: {
            "TUS": 212.625 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        Result.LOSE: {
            "TUS": 74.4188 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        "time_normalized": 4.0,
    },
    Scenarios.MineAndSelfReinforce: {
        Result.WIN: {
            "TUS": 212.625 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        Result.LOSE: {
            "TUS": 74.4188 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        "time_normalized": 4.0,
    },
    Scenarios.MineTenPercentAndReinforce: {
        Result.WIN: {
            "TUS": 233.8875 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        Result.LOSE: {
            "TUS": 95.6812 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        "time_normalized": 4.0,
    },
    Scenarios.MineTenPercentAndSelfReinforce: {
        Result.WIN: {
            "TUS": 233.8875 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        Result.LOSE: {
            "TUS": 95.6812 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        "time_normalized": 4.0,
    },
    Scenarios.MineAndNoReinforce: {
        Result.WIN: {
            "TUS": 74.4188 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        Result.LOSE: {
            "TUS": 74.4188 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        "time_normalized": 4.0,
    },
    Scenarios.MineTenPercentAndNoReinforce: {
        Result.WIN: {
            "TUS": 95.6812 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        Result.LOSE: {
            "TUS": 95.6812 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        "time_normalized": 4.0,
    },
    Scenarios.MineWithNoContest: {
        Result.WIN: {
            "TUS": 212.625 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        Result.LOSE: {
            "TUS": 212.625 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        "time_normalized": 4.0,
    },
    Scenarios.MineTenPercentWithNoContest: {
        Result.WIN: {
            "TUS": 233.8875 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        Result.LOSE: {
            "TUS": 233.8875 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        "time_normalized": 4.0,
    },
    Scenarios.TavernThreeMpCrabs: {
        Result.WIN: {
            "TUS": 0.0 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        Result.LOSE: {
            "TUS": 0.0 * IDLE_MULTIPLIER,
            "CRA": 0.0 * CRA_MULTIPLIER,
        },
        "time_normalized": 2.0,
    },
}


def get_expected_tus(game_type: Scenarios, prices: Prices, win_percent: float) -> float:
    win_decimal = win_percent / 100.0
    winnings_tus = REWARDS_TUS[game_type][Result.WIN]["TUS"]
    winnings_cra = REWARDS_TUS[game_type][Result.WIN]["CRA"]
    winnings_tus += prices.cra_to_tus(winnings_cra)

    losings_tus = REWARDS_TUS[game_type][Result.LOSE]["TUS"]
    losings_cra = REWARDS_TUS[game_type][Result.LOSE]["CRA"]
    losings_tus += prices.cra_to_tus(losings_cra)

    return win_decimal * winnings_tus + (1 - win_decimal) * losings_tus


def get_expected_game_profit(
    game_type: str,
    prices: Prices,
    avg_gas_price_tus: float,
    avg_reinforce_tus: float,
    win_percent: float,
    commission_percent: float,
    do_reinforce: bool,
    verbose: bool = False,
) -> float:
    revenue_tus = get_expected_tus(game_type, prices, win_percent)
    avg_gas_per_game_tus = avg_gas_price_tus * (4 if do_reinforce else 2)
    reinforcement_per_game_tus = 2.0 * avg_reinforce_tus if do_reinforce else 0.0
    commission_tus = (commission_percent / 100.0) * revenue_tus

    profit_tus = revenue_tus - avg_gas_per_game_tus - reinforcement_per_game_tus - commission_tus
    if verbose:
        logger.print_normal(
            f"[{game_type}]: Win %: {win_percent:.2f}%, AVAX: ${prices.avax_usd:.2f}, TUS: ${prices.tus_usd:.2f}, CRA: ${prices.cra_usd:.2f}"
        )
        logger.print_normal(
            f"[{game_type}]: Revenue: {revenue_tus:.2f}, Gas: {avg_gas_per_game_tus:.2f}, Commission: {commission_tus:.2f}, Reinforce: {reinforcement_per_game_tus:.2f}, Profit: {profit_tus:.2f}\n"
        )
    return profit_tus


def get_actual_game_profit(
    game_stats: GameStats,
    with_commission: bool,
    verbose: bool = False,
) -> T.Tuple[float, float]:
    prices = Prices(game_stats["avax_usd"], game_stats["tus_usd"], game_stats["cra_usd"])
    if game_stats["reward_tus"] is None or game_stats["reward_cra"] is None:
        return 0.0, 0.0
    revenue_tus = game_stats["reward_tus"] + prices.cra_to_tus(game_stats["reward_cra"])

    gas_used_tus = sum(
        [game_stats[g] for g in ["gas_close", "gas_start", "gas_reinforce1", "gas_reinforce2"]]
    )

    reinforcement_used_tus = game_stats["reinforce1"] + game_stats["reinforce2"]

    commission_tus = game_stats["commission_tus"]
    if not with_commission:
        commission_tus = 0.0

    profit_tus = revenue_tus - gas_used_tus - reinforcement_used_tus - commission_tus
    profit_usd = prices.tus_usd * profit_tus
    if verbose:
        logger.print_normal(
            f"[{game_type}]: Revenue: {revenue_tus}, Gas: {gas_used_tus}, Reinforce: {reinforcement_used_tus}, Profit: {profit_tus} TUS, Profit: ${profit_usd:.2f}"
        )
    return profit_tus, profit_usd


def get_rewards_from_tx_receipt(tx_receipt: T.Any) -> T.Tuple[T.Optional[float], T.Optional[float]]:
    DATA_SIZE = 64

    tus_rewards = None
    cra_rewards = 0.0

    logs = tx_receipt.get("logs", [])
    for log in logs:
        data_str = log.get("data", "")

        if not data_str.startswith("0x"):
            continue

        raw_data = data_str[len("0x") :]
        data = textwrap.wrap(raw_data, DATA_SIZE)

        if len(data) != 3:
            continue

        if int(data[0], 16) == int(CrabadaWeb3Client().contract_address.lower(), 16):
            tus_rewards = wei_to_tus_raw(int(data[2], 16))

    return (tus_rewards, cra_rewards)


def is_idle_game_transaction_profitable(
    game_type: str,
    prices: Prices,
    avg_gas_price_tus: float,
    avg_reinforce_tus: float,
    win_percent: float,
    commission_percent: float,
    do_reinforce: bool,
    verbose: bool = False,
) -> bool:
    return (
        get_expected_game_profit(
            game_type,
            prices,
            avg_gas_price_tus,
            avg_reinforce_tus,
            win_percent,
            commission_percent,
            do_reinforce,
            verbose=verbose,
        )
        > 0.0
    )


def get_scenario_profitability(
    team: Team,
    prices: Prices,
    avg_gas_price_tus: float,
    avg_reinforce_tus: float,
    win_percentages: T.Dict[MineOption, float],
    commission_percent: float,
    is_looting: bool,
    is_reinforcing_allowed: bool,
    can_self_reinforce: bool,
    verbose: bool = False,
) -> float:
    scenario = Scenarios.MineAndReinforce
    composition = []
    for i in range(1, 4):
        if f"crabada_{i}_class" not in team:
            break
        composition.append(team[f"crabada_{i}_class"])

    if verbose:
        comp_str = " ".join([CRABADA_ID_TO_CLASS[c] for c in composition])
        logger.print_normal(f"Team comp: {comp_str}")

    scenarios_to_check = [Scenarios.MineAndReinforce]

    if is_looting:
        # assume looters get snipes
        scenarios_to_check = [Scenarios.LootWithNoContest]
    else:
        # CCP teams lets use a no contest calculation
        if (
            composition.count(CrabadaClass.CRABOID) == 2
            and composition.count(CrabadaClass.PRIME) == 1
        ):
            scenarios_to_check = [Scenarios.MineTenPercentWithNoContest]

        elif CrabadaClass.PRIME in composition:
            scenarios_to_check = [Scenarios.MineTenPercentAndNoReinforce]

            if is_reinforcing_allowed:
                if can_self_reinforce:
                    scenarios_to_check.append(Scenarios.MineTenPercentAndSelfReinforce)
                else:
                    scenarios_to_check.append(Scenarios.MineTenPercentAndReinforce)
        else:
            scenarios_to_check = [Scenarios.MineAndNoReinforce]

            if is_reinforcing_allowed:
                if can_self_reinforce:
                    scenarios_to_check.append(Scenarios.MineAndSelfReinforce)
                else:
                    scenarios_to_check.append(Scenarios.MineAndReinforce)

    scenario_profits_tus = {}
    for scenario_to_check in scenarios_to_check:
        do_reinforce = scenario_to_check in REINFORCE_SCENARIOS
        dont_pay_for_reinforcements = scenario_to_check in NO_REINFORCE_PAY_SCENARIOS
        reinforce_tus = 0.0 if dont_pay_for_reinforcements else avg_reinforce_tus

        if verbose:
            logger.print_normal(f"Testing scenario: {scenario_to_check}")
            logger.print_normal(f"Do reinforce: {do_reinforce}")
            logger.print_normal(f"Gas: {avg_gas_price_tus}")
            logger.print_normal(f"Reinforce cost (TUS): {reinforce_tus:.2f}")

        profit_tus = get_expected_game_profit(
            scenario_to_check,
            prices,
            avg_gas_price_tus,
            reinforce_tus,
            win_percentages[MineOption.LOOT if is_looting else MineOption.MINE],
            commission_percent,
            do_reinforce,
            verbose=True,
        )
        scenario_profits_tus[profit_tus] = scenario_to_check

    max_profit_tus = max(scenario_profits_tus.keys())

    logger.print_normal(f"Most profitable scenario: {scenario_profits_tus[max_profit_tus]}")
    return max_profit_tus


def is_profitable_to_take_action(
    team: Team,
    prices: Prices,
    avg_gas_price_tus: float,
    avg_reinforce_tus: float,
    win_percentages: T.Dict[MineOption, float],
    commission_percent: float,
    is_looting: bool,
    is_reinforcing_allowed: bool,
    can_self_reinforce: bool,
    min_profit_threshold_tus: float = 0.0,
    verbose: bool = False,
) -> bool:
    profit_tus = get_scenario_profitability(
        team,
        prices,
        avg_gas_price_tus,
        avg_reinforce_tus,
        win_percentages,
        commission_percent,
        is_looting,
        is_reinforcing_allowed,
        can_self_reinforce,
        verbose=verbose,
    )
    return profit_tus > min_profit_threshold_tus


def get_profitability_message(
    prices: Prices,
    avg_gas_tus: float,
    gas_price_gwei: float,
    avg_reinforce_tus: float,
    win_percentages: T.Dict[str, float],
    commission_percent: float = 0.0,
    verbose: bool = False,
    use_static_percents: bool = True,
    log_stats: bool = True,
    group: T.Optional[int] = None,
) -> str:
    PROFIT_HYSTERESIS = 10

    data_points = {
        "avg_tx_gas_tus": avg_gas_tus,
        "avg_gas_price_gwei": gas_price_gwei,
        "avg_mining_win": win_percentages["MINE"],
        "avg_loot_win": win_percentages["LOOT"],
        "avg_reinforce_cost_tus": avg_reinforce_tus,
        "avax_usd": prices.avax_usd,
        "tus_usd": prices.tus_usd,
        "cra_usd": prices.cra_usd,
    }

    percentages = {}
    if use_static_percents:
        percentages = STATIC_WIN_PERCENTAGES
    else:
        percentages = win_percentages

    if prices.avax_usd is None or prices.tus_usd is None or prices.cra_usd is None:
        return ""

    message = "**Swimmer Profitability Update**\n"
    message += "{}\t\t{}\n".format(f"**Avg Tx Gas \U000026FD**:", f"{avg_gas_tus:.3f} TUS")
    message += "{}\t\t{}\n".format(
        f"**Avg Gas Price \U000026FD**:", f"{gas_price_gwei/1000.0:.2f} TUS"
    )
    message += "{}\t{}\n".format(f"**Avg Mining Win % \U0001F3C6**:", f"{percentages['MINE']:.2f}%")
    message += "{}\t{}\n".format(
        f"**Avg Looting Win % \U0001F480**:", f"{percentages['LOOT']:.2f}%"
    )
    message += "{}\t{}\n\n".format(
        f"**Avg Reinforce Cost \U0001F4B0**:", f"{avg_reinforce_tus:.2f} TUS"
    )

    message += f"**Prices**\n"
    message += (
        f"AVAX: ${prices.avax_usd:.2f}, TUS: ${prices.tus_usd:.4f}, CRA: ${prices.cra_usd:.4f}\n\n"
    )

    message += f"**Expected Profit (EP)**\n"
    message += f"*(normalized over a 4 hour window)*\n"

    if log_stats:
        csv_file = os.path.join(
            logger.get_logging_dir(),
            "profitability_stats{}.csv".format(str(group) if group is not None else ""),
        )

        profit_headers = []
        for scenario in REWARDS_TUS.keys():
            profit_headers.append(f"{scenario.lower()}_4hr_profit_tus")
            profit_headers.append(f"{scenario.lower()}_4hr_profit_usd")

        header = ["timestamp"] + list(data_points.keys()) + profit_headers
        csv = csv_logger.CsvLogger(csv_file, header)

    for game in REWARDS_TUS.keys():
        # hypothetical scenario that we use to estimate loot snipes
        if game == Scenarios.LootAndNoReinforce:
            continue

        if game in LOOT_SCENARIOS:
            win_percent = percentages["LOOT"]
        else:
            win_percent = percentages["MINE"]

        if game == Scenarios.TavernThreeMpCrabs:
            profit_tus = avg_reinforce_tus * 3 - avg_gas_tus / 6
        else:
            do_reinforce = game in REINFORCE_SCENARIOS
            dont_pay_for_reinforcements = game in NO_REINFORCE_PAY_SCENARIOS
            reinforce_tus = 0.0 if dont_pay_for_reinforcements else avg_reinforce_tus
            profit_tus = get_expected_game_profit(
                game,
                prices,
                avg_gas_tus,
                reinforce_tus,
                win_percent,
                commission_percent,
                do_reinforce,
            )

        games_per_4_hrs = NORMALIZED_TIME / REWARDS_TUS[game]["time_normalized"]
        profit_tus_4_hrs = profit_tus * games_per_4_hrs
        profit_usd_4_hrs = prices.tus_usd * profit_tus_4_hrs
        profit_emoji = "\U0001F4C8" if profit_tus_4_hrs > 0.0 else "\U0001F4C9"
        data_points[f"{game.lower()}_4hr_profit_tus"] = profit_tus_4_hrs
        data_points[f"{game.lower()}_4hr_profit_usd"] = profit_usd_4_hrs
        message += "{}\n    {} TUS,    ${}\n".format(
            f"**{game}**:", f"{profit_tus_4_hrs:.2f}", f"{profit_usd_4_hrs:.2f}"
        )

    now = datetime.datetime.now()
    data_points["timestamp"] = now.strftime(TIMESTAMP_FORMAT)
    if log_stats:
        csv.write(data_points)

    if verbose:
        logger.print_normal(message)

    return message
