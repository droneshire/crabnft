import getpass
import json
import os

from eth_typing import Address

from config import GMAIL
from crabada.miners_revenge import calc_miners_revenge
from crabada.config_manager import ConfigManager
from utils import email, logger, security
from utils.config_types import UserConfig

TEST_CONFIG = UserConfig(
        group=1,
        crabada_key="deadbeef",
        address=Address("0xfoobar"),
        mining_teams={
            1234: 1,
            8765: 1,
            5678: 2,
            4321: 2,
        },
        looting_teams={
            9999: 20,
            1111: 20,
        },
        reinforcing_crabs={
            7777: 1,
            8888: 20,
        },
        breed_crabs=[],
        mining_strategy="PreferOwnMpCrabsAndDelayReinforcement",
        looting_strategy="PreferOwnBpCrabsAndDelayReinforcement",
        max_gas_price_gwei=95,
        max_reinforcement_price_tus=24,
        max_reinforce_bp_delta=10,
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
    mine_file = os.path.join(this_dir, "crabada", "example_mine.json")
    with open(mine_file, "r") as infile:
        mine = json.load(infile)["result"]

    miners_revenge = calc_miners_revenge(mine)
    assert (
        expected_miners_revenge == miners_revenge
    ), f"Expected: {expected_miners_revenge} Actual: {miners_revenge}"

def test_config_manager() -> None:
    email_accounts = []
    encrypt_password = getpass.getpass(prompt="Enter decryption password: ")

    for email_account in GMAIL:
        email_password = security.decrypt(
            str.encode(encrypt_password), email_account["password"]
        ).decode()
        email_accounts.append(
            email.Email(address=email_account["user"], password=email_password)
        )
    cm = ConfigManager("TEST", TEST_CONFIG, email_accounts)

    cm.write_updated_config()


if __name__ == "__main__":
    test_config_manager()
    test_miners_revenge()
