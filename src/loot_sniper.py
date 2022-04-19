import time
import typing as T

from config import USERS
from crabada.loot_sniping import LootSnipes
from utils.discord import get_discord_hook


def main() -> None:
    webhooks = {
        "LOOT_SNIPE": get_discord_hook("LOOT_SNIPE"),
    }
    sniper = LootSnipes(webhooks)
    while True:
        sniper.check_and_alert(USERS["ROSS"]["address"])
        time.sleep(60.0)


if __name__ == "__main__":
    main()
