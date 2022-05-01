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
from utils import email, logger, security
from utils.config_types import UserConfig
from crabada.types import CrabForLending
from utils import logger

TEST_CONFIG = UserConfig(
    group=1,
    crabada_key="deadbeef",
    address=Address("0xfoobar"),
    mining_teams={
        1234: 0,
        8765: 0,
        5678: 0,
        4321: 0,
    },
    looting_teams={
        9999: 10,
        1111: 10,
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
    email="ryeager12@gmail.com",
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


def test_config_manager() -> None:
    dry_run = True
    email_accounts = []

    if not dry_run:
        encrypt_password = getpass.getpass(prompt="Enter decryption password: ")

        for email_account in GMAIL:
            email_password = security.decrypt(
                str.encode(encrypt_password), email_account["password"]
            ).decode()
            email_accounts.append(
                email.Email(address=email_account["user"], password=email_password)
            )

    cm = ConfigManager("TEST", TEST_CONFIG, email_accounts, dry_run=dry_run)
    cm._delete_sheet()
    cm._create_sheet_if_needed()
    time.sleep(4.0)
    new_config = cm.check_for_updated_config()

    diff = deepdiff.DeepDiff(TEST_CONFIG, new_config)
    if diff:
        logger.print_normal(f"{diff}")
        assert False, "unexpected change in configuration"


if __name__ == "__main__":
    test_config_manager()
    test_miners_revenge()
