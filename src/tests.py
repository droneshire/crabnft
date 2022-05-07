import deepdiff
import getpass
import json
import math
import os
import time

from eth_typing import Address

from config import GMAIL
from crabada.miners_revenge import calc_miners_revenge
from crabada.config_manager import ConfigManager
from crabada.config_manager_sheets import ConfigManagerSheets
from crabada.config_manager_firebase import ConfigManagerFirebase
from crabada.profitability import get_scenario_profitability, is_profitable_to_take_action
from crabada.types import CrabadaClass, Team
from utils import email, logger, security
from utils.config_types import UserConfig
from utils.price import Prices
from crabada.types import CrabForLending
from utils import logger

TEST_CONFIG = UserConfig(
    group=1,
    crabada_key="OzNlfYgu2jDLbjUBsNFmfPySz/QwRO3lbx+DjVmR7IQ=",  # deadbeef
    address=Address("0xae55967c2c5fae2cf2529b12f5a7344e99037656"),
    mining_teams={
        28201: 0,
        28203: 0,
    },
    looting_teams={
        28199: 0,
    },
    reinforcing_crabs={
        7777: 0,
        8888: 10,
    },
    breed_crabs=[],
    mining_strategy="PreferOwnMpCrabsAndDelayReinforcement",
    looting_strategy="PreferOwnBpCrabsAndDelayReinforcement",
    max_gas_price_gwei=95.0,
    max_reinforcement_price_tus=24.0,
    commission_percent_per_mine={
        "": 10.0,
    },
    sms_number="",
    email="info.crabada.bot@gmail.com",
    discord_handle="",
    get_sms_updates=False,
    get_sms_updates_loots=False,
    get_sms_updates_alerts=False,
    get_email_updates=True,
    should_reinforce=True,
)


def test_miners_revenge() -> None:
    expected_miners_revenge = 42.25
    this_dir = os.path.dirname(os.path.realpath(__file__))
    mine_file = os.path.join(this_dir, "crabada", "test_mines", "example_mine.json")
    with open(mine_file, "r") as infile:
        mine = json.load(infile)["result"]

    miners_revenge = calc_miners_revenge(mine, is_looting=False, additional_crabs=[], verbose=True)
    assert math.isclose(
        expected_miners_revenge, miners_revenge, abs_tol=0.01
    ), f"Expected: {expected_miners_revenge} Actual: {miners_revenge}"

    miners_revenge = calc_miners_revenge(mine, is_looting=True, additional_crabs=[], verbose=True)
    assert math.isclose(
        expected_miners_revenge, miners_revenge, abs_tol=0.01
    ), f"Expected: {expected_miners_revenge} Actual: {miners_revenge}"

    expected_miners_revenge = 37.15
    mine_file = os.path.join(this_dir, "crabada", "test_mines", "example_mine1.json")
    with open(mine_file, "r") as infile:
        mine = json.load(infile)["result"]

    miners_revenge = calc_miners_revenge(mine, is_looting=False, additional_crabs=[], verbose=True)
    assert math.isclose(
        expected_miners_revenge, miners_revenge, abs_tol=0.01
    ), f"Expected: {expected_miners_revenge} Actual: {miners_revenge}"

    mine_file = os.path.join(this_dir, "crabada", "test_mines", "example_mine2.json")
    with open(mine_file, "r") as infile:
        mine = json.load(infile)["result"]
    additional_crab = [
        CrabForLending(
            {
                "crabada_id": 7985,
                "crabada_class": 3,
                "photo": "7985.png",
                "hp": 113,
                "speed": 29,
                "armor": 27,
                "damage": 58,
                "critical": 42,
                "is_origin": 0,
                "is_genesis": 0,
                "legend_number": 0,
            }
        )
    ]

    miners_revenge = calc_miners_revenge(
        mine, is_looting=False, additional_crabs=additional_crab, verbose=True
    )
    assert math.isclose(
        expected_miners_revenge, miners_revenge, abs_tol=0.01
    ), f"Expected: {expected_miners_revenge} Actual: {miners_revenge}"

    mine_file = os.path.join(this_dir, "crabada", "test_mines", "example_mine3.json")
    with open(mine_file, "r") as infile:
        mine = json.load(infile)["result"]

    additional_crab = [
        CrabForLending(
            {
                "crabada_id": 73896,
                "crabada_class": 4,
                "photo": "73896.png",
                "hp": 148,
                "speed": 27,
                "armor": 35,
                "damage": 54,
                "critical": 39,
                "is_origin": 0,
                "is_genesis": 0,
                "legend_number": 0,
            }
        )
    ]

    miners_revenge = calc_miners_revenge(
        mine, is_looting=True, additional_crabs=additional_crab, verbose=True
    )
    assert math.isclose(
        expected_miners_revenge, miners_revenge, abs_tol=0.01
    ), f"Expected: {expected_miners_revenge} Actual: {miners_revenge}"


def test_config_manager_firebase() -> None:
    email_accounts = []

    encrypt_password = getpass.getpass(prompt="Enter decryption password: ")


    cm = ConfigManagerFirebase("TEST", TEST_CONFIG, email_accounts, encrypt_password, dry_run=False)
    cm.update_all_users_from_local_config()
    # cm.check_for_config_updates()


def test_config_manager_sheets() -> None:
    dry_run = False
    email_accounts = []

    encrypt_password = ""
    cm = ConfigManagerSheets("TEST", TEST_CONFIG, email_accounts, encrypt_password, dry_run=False)
    cm._delete_sheet()
    cm._create_sheet_if_needed()
    new_config = cm._read_sheets_config()
    cm._delete_sheet()

    diff = deepdiff.DeepDiff(TEST_CONFIG, new_config)
    if diff:
        logger.print_normal(f"{diff}")
        assert False, "unexpected change in configuration"


def test_profitability_calc() -> None:
    """
    We're gonna test that we get the same results as here given different team inputs:

    **Profitability Update**
    **Avg Tx Gas ⛽**:              0.01712 AVAX
    **Avg Gas Price ⛽**:           92.290872 gwei
    **Avg Mining Win % 🏆**:        40.00%
    **Avg Looting Win % 💀**:       60.00%
    **Avg Reinforce Cost 💰**:      7.86 TUS

    **Prices**
    AVAX: $60.504, TUS: $0.021, CRA: $0.389

    **Expected Profit (EP)**
    *(normalized over a 4 hour window)*
    **LOOT**:
        -136.64 TUS,    $-2.93
    **LOOT & SELF REINFORCE**:
        -73.74 TUS,    $-1.58
    **MINE & REINFORCE**:
        17.89 TUS,    $0.38
    **MINE & SELF REINFORCE**:
        33.62 TUS,    $0.72
    **MINE +10% & REINFORCE**:
        55.07 TUS,    $1.18
    **MINE +10% & SELF REINFORCE**:
        70.80 TUS,    $1.52
    **MINE & NO REINFORCE**:
        33.54 TUS,    $0.72
    **MINE +10% & NO REINFORCE**:
        70.72 TUS,    $1.52
    **TAVERN 3 MP CRABS**:
        31.08 TUS,    $0.67
    """

    prices = Prices(60.504, 0.021, 0.389)
    avg_gas_price_avax = 0.01712
    avg_reinforce_tus = 7.86
    win_percentages = {
        "MINE": 40.0,
        "LOOT": 60.0,
    }
    test_team = Team(
        crabada_1_class=CrabadaClass.PRIME,
        crabada_2_class=CrabadaClass.CRABOID,
        crabada_3_class=CrabadaClass.CRABOID,
    )

    profit_tus = get_scenario_profitability(
        test_team,
        prices,
        avg_gas_price_avax,
        avg_reinforce_tus,
        win_percentages,
        0.0,
        is_looting=False,
        is_reinforcing_allowed=True,
        can_self_reinforce=False,
        verbose=False,
    )

    assert math.isclose(profit_tus, 311.88, abs_tol=0.1), "Failed MINE +10% NO CONTEST test"

    test_team = Team(
        crabada_1_class=CrabadaClass.PRIME,
        crabada_2_class=CrabadaClass.BULK,
        crabada_3_class=CrabadaClass.BULK,
    )

    avg_gas_price_avax = 0.005
    profit_tus = get_scenario_profitability(
        test_team,
        prices,
        avg_gas_price_avax,
        avg_reinforce_tus,
        win_percentages,
        0.0,
        is_looting=False,
        is_reinforcing_allowed=True,
        can_self_reinforce=False,
        verbose=False,
    )

    assert math.isclose(profit_tus, 191.64, abs_tol=0.1), "Failed MINE +10% REINFORCE test"

    profit_tus = get_scenario_profitability(
        test_team,
        prices,
        avg_gas_price_avax,
        avg_reinforce_tus,
        win_percentages,
        0.0,
        is_looting=False,
        is_reinforcing_allowed=True,
        can_self_reinforce=True,
        verbose=False,
    )
    assert math.isclose(profit_tus, 207.36, abs_tol=0.1), "Failed MINE +10% SELF REINFORCE test"

    avg_gas_price_avax = 0.01712
    profit_tus = get_scenario_profitability(
        test_team,
        prices,
        avg_gas_price_avax,
        avg_reinforce_tus,
        win_percentages,
        0.0,
        is_looting=False,
        is_reinforcing_allowed=True,
        can_self_reinforce=False,
        verbose=False,
    )

    # in this scenario, gas is high so we should result in NO REINFORCE
    assert math.isclose(profit_tus, 69.30, abs_tol=0.1), "Failed MINE +10% REINFORCE test"

    profit_tus = get_scenario_profitability(
        test_team,
        prices,
        avg_gas_price_avax,
        avg_reinforce_tus,
        win_percentages,
        0.0,
        is_looting=False,
        is_reinforcing_allowed=True,
        can_self_reinforce=True,
        verbose=False,
    )
    # in this scenario, gas is high so we should result in NO REINFORCE
    assert math.isclose(profit_tus, 69.30, abs_tol=0.1), "Failed MINE +10% SELF REINFORCE test"

    profit_tus = get_scenario_profitability(
        test_team,
        prices,
        avg_gas_price_avax,
        avg_reinforce_tus,
        win_percentages,
        0.0,
        is_looting=False,
        is_reinforcing_allowed=False,
        can_self_reinforce=True,
        verbose=False,
    )
    assert math.isclose(profit_tus, 69.29, abs_tol=0.1), "Failed MINE +10% NO REINFORCE test"

    profit_tus = get_scenario_profitability(
        test_team,
        prices,
        avg_gas_price_avax,
        avg_reinforce_tus,
        win_percentages,
        0.0,
        is_looting=False,
        is_reinforcing_allowed=False,
        can_self_reinforce=False,
        verbose=False,
    )
    assert math.isclose(profit_tus, 69.29, abs_tol=0.1), "Failed MINE +10% NO REINFORCE test"

    profit_tus = get_scenario_profitability(
        test_team,
        prices,
        avg_gas_price_avax,
        avg_reinforce_tus,
        win_percentages,
        0.0,
        is_looting=True,
        is_reinforcing_allowed=True,
        can_self_reinforce=True,
        verbose=False,
    )
    assert math.isclose(profit_tus, 173.79, abs_tol=0.1), "Failed LOOT SELF REINFORCE test"

    profit_tus = get_scenario_profitability(
        test_team,
        prices,
        avg_gas_price_avax,
        avg_reinforce_tus,
        win_percentages,
        0.0,
        is_looting=True,
        is_reinforcing_allowed=True,
        can_self_reinforce=False,
        verbose=False,
    )
    assert math.isclose(profit_tus, 173.79, abs_tol=0.1), "Failed LOOT test"

    profit_tus = get_scenario_profitability(
        test_team,
        prices,
        avg_gas_price_avax,
        avg_reinforce_tus,
        win_percentages,
        0.0,
        is_looting=True,
        is_reinforcing_allowed=True,
        can_self_reinforce=False,
        verbose=False,
    )
    assert math.isclose(profit_tus, 173.79, abs_tol=0.1), "Failed LOOT NO CONTEST test"


def test_config_manager() -> None:
    send_email_accounts = []
    encrypt_password = getpass.getpass(prompt="Enter decryption password: ")

    cm = ConfigManager("TEST", TEST_CONFIG, send_email_accounts, encrypt_password)
    cm._print_out_config()
    cm._send_email_config_if_needed()
    cm._save_config()


if __name__ == "__main__":
    test_config_manager()
    test_config_manager_firebase()
    test_config_manager_sheets()
    test_miners_revenge()
    test_profitability_calc()
