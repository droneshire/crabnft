import time
import typing as T

from config import USERS
from crabada.loot_sniping import LootSnipes
from utils.discord import DISCORD_WEBHOOK_URL


def main() -> None:
    sniper = LootSnipes(webhook_url=DISCORD_WEBHOOK_URL["LOOT_SNIPE"], verbose=True)
    while True:
        for _, config in USERS.items():
            try:
                sniper.hunt(config["address"])
            except KeyboardInterrupt:
                sniper.delete_all_messages()
                return
            except:
                pass
            time.sleep(10.0)


if __name__ == "__main__":
    main()
