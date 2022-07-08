"""
Update config to db from local config file
"""

import argparse
import datetime
import getpass


from config_crabada import USERS
from crabada.config_manager_firebase import ConfigManagerFirebase
from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.types import MineOption
from utils import logger
from utils.user import get_alias_from_user


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", choices=sorted(list(USERS.keys())) + ["ALL"], default="ALL")
    parser.add_argument(
        "--from-crabada", action="store_true", help="setup teams by querying address"
    )
    parser.add_argument(
        "--force-erase", action="store_true", help="erase existing config regardless of alias"
    )
    return parser.parse_args()


def update_firebase_db() -> None:
    args = parse_args()

    if args.user == "ALL":
        users = list(USERS.keys())
    else:
        users = [args.user]

    aliases = set([get_alias_from_user(u) for u in USERS])

    for user in users:
        cm = ConfigManagerFirebase(user, USERS[user], [], "", "", CrabadaWeb2Client())
        if args.from_crabada:
            erase_configs = args.force_erase or get_alias_from_user(user) == user
            cm.update_user_from_crabada(user, erase_configs)
        else:
            cm.update_user_from_local_config(user)


if __name__ == "__main__":
    update_firebase_db()
