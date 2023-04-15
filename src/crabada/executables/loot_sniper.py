import logging
import os
import time
import typing as T

from config_crabada import USERS
from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.loot_sniping import LootSnipes
from utils import logger, circuit_breaker
from utils.discord import DISCORD_WEBHOOK_URL


def main() -> None:
    logger.setup_log("INFO", logger.get_logging_dir("crabada"), "loot_sniper")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    sniper = LootSnipes(
        os.path.join(this_dir, "gspread_credentials.json"),
        CrabadaWeb2Client(),
        verbose=True,
    )
    cb = circuit_breaker.CircuitBreaker(15.0)
    while True:
        for _, config in USERS.items():
            cb.start()
            try:
                sniper.hunt(config["address"])
            except KeyboardInterrupt:
                sniper.end()
            except:
                pass
            cb.end()
            time.sleep(1.0)


if __name__ == "__main__":
    main()
