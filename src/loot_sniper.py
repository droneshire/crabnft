import time
import typing as T

from config import USERS
from crabada.loot_sniping import LootSnipes
from utils.discord import DISCORD_WEBHOOK_URL


def main() -> None:
    sniper = LootSnipes(webhook_url=DISCORD_WEBHOOK_URL["LOOT_SNIPE"])
    while True:
        try:
            sniper.check_and_alert(USERS["ROSS"]["address"])
        finally:
            sniper.delete_all_messages()
        time.sleep(20.0)


if __name__ == "__main__":
    main()
