import logging
import os
import time
import typing as T

from config import USERS
from crabada.loot_sniping import LootSnipes
from utils import logger
from utils.discord import DISCORD_WEBHOOK_URL


def setup_log(log_level: str, log_dir: str, id_string: str) -> None:
    if log_level == "NONE":
        return

    log_name = (
        time.strftime("%Y_%m_%d__%H_%M_%S", time.localtime(time.time()))
        + f"_crabada_{id_string}.log"
    )
    log_file = os.path.join(log_dir, log_name)
    logging.basicConfig(
        filename=log_file,
        level=logging.getLevelName(log_level),
        format="[%(levelname)s][%(asctime)s][%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        filemode="w",
    )


def main() -> None:
    setup_log("INFO", logger.get_logging_dir(), "loot_sniper")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    sniper = LootSnipes(os.path.join(this_dir, "credentials.json"), verbose=True)
    while True:
        for _, config in USERS.items():
            sniper.hunt(config["address"])
            time.sleep(1.0)


if __name__ == "__main__":
    main()
