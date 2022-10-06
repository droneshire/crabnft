import argparse
import getpass
import logging
import os
import time
from yaspin import yaspin

from config_pumpskin import GMAIL, USERS, USER_GROUPS
from utils import logger
from utils.email import Email, get_email_accounts_from_password
from utils.security import decrypt_secret
from pumpskin.pumpskin_bot import PumpskinBot

TIME_BETWEEN_PLAYERS = 60.0
TIME_BETWEEN_RUNS = 3.0 * 60.0 * 60.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    log_dir = logger.get_logging_dir("pumpskin")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument("--quiet", action="store_true", help="Disable alerts")
    parser.add_argument("--log-level", choices=["INFO", "DEBUG", "ERROR", "NONE"], default="INFO")
    parser.add_argument("--log-dir", default=log_dir)
    parser.add_argument("--groups", nargs="+", default=USER_GROUPS)
    return parser.parse_args()


def setup_log(log_level: str, log_dir: str, id_string: str) -> None:
    if log_level == "NONE":
        return

    log_name = (
        time.strftime("%Y_%m_%d__%H_%M_%S", time.localtime(time.time()))
        + f"_pumpskin_{id_string}.log"
    )

    log_dir = os.path.join(log_dir, "bot")

    if not os.path.isdir(log_dir):
        os.mkdir(log_dir)

    log_file = os.path.join(log_dir, log_name)

    logging.basicConfig(
        filename=log_file,
        level=logging.getLevelName(log_level),
        format="[%(levelname)s][%(asctime)s][%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        filemode="w",
    )


@yaspin(text="Waiting...")
def wait(wait_time) -> None:
    time.sleep(wait_time)


def run_bot() -> None:
    args = parse_args()

    setup_log(args.log_level, args.log_dir, "the_den")

    encrypt_password = ""
    email_accounts = []

    if not args.dry_run:
        encrypt_password = getpass.getpass(prompt="Enter decryption password: ")
        email_accounts = get_email_accounts_from_password(encrypt_password, GMAIL)

    bots = []
    for user, config in USERS.items():
        private_key = decrypt_secret(encrypt_password, config["private_key"])
        config["private_key"] = private_key

        bot = PumpskinBot(
            user,
            config,
            email_accounts,
            encrypt_password,
            args.log_dir,
            dry_run=args.dry_run,
        )
        bot.init()
        bots.append(bot)

    try:
        while True:
            for bot in bots:
                bot.run()
                logger.print_normal(f"Waiting before next user...")
                wait(TIME_BETWEEN_PLAYERS)
            logger.print_normal(f"Waiting for next round of botting...")
            wait(TIME_BETWEEN_RUNS)

    finally:
        for bot in bots:
            bot.end()


if __name__ == "__main__":
    run_bot()
