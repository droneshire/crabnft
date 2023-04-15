import argparse
import getpass
import json
import logging
import os
import time

from web3 import Web3

import config_admin
import config_wyndblast, config_pumpskin, config_pat
from database.account import AccountDb
from database.connect import init_database
from database.models.account import Account, AccountSchema
from database.models.commission_percents import CommissionPercents
from plantatree.database.models.game_config import PatGameConfig
from pumpskin.database.models.game_config import (
    PumpskinsGameConfig,
    SpecialPumpskins,
)
from wyndblast.database.models.game_config import WyndblastGameConfig
from utils import file_util, logger
from utils.user import get_alias_from_user


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    log_dir = logger.get_logging_dir("p2e")
    parser.add_argument(
        "--log-level",
        choices=["INFO", "DEBUG", "ERROR", "NONE"],
        default="INFO",
    )
    parser.add_argument("--log-dir", default=log_dir)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def convert_pat(verbose: bool = False) -> None:
    for user, config in config_pat.USERS.items():
        alias = get_alias_from_user(user)
        address = Web3.toChecksumAddress(config["address"])
        AccountDb.add_account(alias, config["email"], config["discord_handle"])
        AccountDb.add_wallet(alias, address, config["private_key"])
        AccountDb.add_game_config(address, config["game"], PatGameConfig)
        db = AccountDb(alias)

        with db.wallet(address) as wallet:
            wallet.commission_percents = []
            for k, v in config["commission_percent_per_mine"].items():
                commission = CommissionPercents(address=k, percent=v)
                wallet.commission_percents.append(commission)

        with db.game_config(config["game"], address) as game_config:
            game_config.time_between_plants = config["game_specific_configs"][
                "time_between_plants"
            ]

        with db.account() as account:
            account_json = AccountSchema().dump(account)
        logger.print_ok_blue(f"{json.dumps(account_json, indent=4)}")


def convert_pumpskins(verbose: bool = False) -> None:
    for user, config in config_pumpskin.USERS.items():
        alias = get_alias_from_user(user)
        address = Web3.toChecksumAddress(config["address"])
        AccountDb.add_account(alias, config["email"], config["discord_handle"])
        AccountDb.add_wallet(alias, address, config["private_key"])
        AccountDb.add_game_config(address, config["game"], PumpskinsGameConfig)
        db = AccountDb(alias)

        with db.wallet(address) as wallet:
            wallet.commission_percents = []
            for k, v in config["commission_percent_per_mine"].items():
                commission = CommissionPercents(address=k, percent=v)
                wallet.commission_percents.append(commission)

        with db.game_config(config["game"], address) as game_config:
            for k, v in config["game_specific_configs"].items():
                if k == "special_pumps":
                    game_config.special_pumps = []
                    for pump, level in v.items():
                        special = SpecialPumpskins(
                            max_level=level, pumpkin_id=pump
                        )
                        game_config.special_pumps.append(special)
                else:
                    setattr(game_config, k, v)

        with db.account() as account:
            account_json = AccountSchema().dump(account)
        logger.print_ok_blue(f"{json.dumps(account_json, indent=4)}")


def convert_wyndblast(verbose: bool = False) -> None:
    for user, config in config_wyndblast.USERS.items():
        alias = get_alias_from_user(user)
        address = Web3.toChecksumAddress(config["address"])
        AccountDb.add_account(alias, config["email"], config["discord_handle"])
        AccountDb.add_wallet(alias, address, config["private_key"])
        AccountDb.add_game_config(address, config["game"], WyndblastGameConfig)
        db = AccountDb(alias)

        with db.wallet(address) as wallet:
            wallet.commission_percents = []
            for k, v in config["commission_percent_per_mine"].items():
                commission = CommissionPercents(
                    address=k, percent=v, wallet_id=wallet.address
                )
                wallet.commission_percents.append(commission)

        with db.account() as account:
            account_json = AccountSchema().dump(account)
        logger.print_ok_blue(f"{json.dumps(account_json, indent=4)}")


def main() -> None:
    args = parse_args()

    logger.setup_log(args.log_level, args.log_dir, "db_convert")

    init_database(args.log_dir, f"{config_admin.USER_CONFIGS_DB}", Account)

    convert_pat(args.verbose)
    convert_pumpskins(args.verbose)
    convert_wyndblast(args.verbose)


if __name__ == "__main__":
    main()
