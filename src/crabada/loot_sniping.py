import copy
import typing as T

from eth_typing import Address

from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.factional_advantage import FACTIONAL_ADVANTAGE
from utils import logger

TARGET_ADDRESSES = [
    "0x9DA9FEB8fad6a9A98594825d14F13cdE3CA8fD3e",
    "0xDEf7CB0eAA0DB7aF60DFe90E2B1665441a44d7C1",
    "0xd42a401d2762d8b22dba1bada7f9970457bcfac6",
    "0xd1090cfccaf7381db44b06a937a90780d2c61304",
    "0x0e9CEb3Ea6C16D7CC0Ad00927e6f038FB3B95525",
    "0x07b6228E674Ed8875A9B57DB8C06f5bcEa9F3F15",
    "0x01d778e7de7e05b541b8c596fb579030ce4db291",
    "0xb5a943ab656bd34c8715c74ad14c63554ca74b84",
    "0x558afda5dd07d0898691cef304682c5f87d8bcf2",
]


def find_loot_snipe(user_address: Address, verbose: bool = False) -> T.Dict[int, int]:
    web2 = CrabadaWeb2Client()

    loot_list = []
    for address in TARGET_ADDRESSES:
        mines = [m["game_id"] for m in web2.list_my_mines(address)]
        loot_list.extend(mines)

    params = {
        "limit": 500,
    }
    available_loots = web2.list_available_loots(user_address, params=params)
    target_pages = {}
    for inx, mine in enumerate(available_loots):
        page = (inx + 1) % 8
        faction = mine["faction"].upper()
        if mine["game_id"] in loot_list:
            data = {"page": page, "faction": faction}
            target_pages[mine["game_id"]] = data

            if verbose:
                logger.print_bold(
                    f"Found target {mine['game_id']} on page {data['page']} faction {data['faction']}"
                )

    return target_pages


class LootSnipes:
    LOOTING_URL = "https://play.crabada.com/mine/start-looting"

    def __init__(self, webhooks: T.Dict[str, T.Any], dry_run: bool = False):
        self.dry_run = dry_run
        self.webhooks = webhooks
        self.loot_snipes = {}

    def check_and_alert(self, address: str) -> None:
        logger.print_ok_blue("Hunting for loot snipes...")
        update_loot_snipes = find_loot_snipe(address, verbose=False)
        for mine, data in update_loot_snipes.items():
            if mine not in self.loot_snipes.keys():
                page = data["page"]
                mine_faction = data["faction"]
                attack_factions = [f for f, a in FACTIONAL_ADVANTAGE.items() if f in a]
                webhook_text = f"**Found new loot snipe!**\n"
                webhook_text += f"Mine: {mine} Faction: {mine_faction} Page: {page}\n"
                webhook_text += f"Loot with: {' '.join(attack_factions)}\n"
                logger.print_bold(webhook_text)
                if not self.dry_run:
                    self.webhooks["LOOT_SNIPE"].send(webhook_text)
        self.loot_snipes = copy.deepcopy(update_loot_snipes)
