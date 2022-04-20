import copy
import time
import typing as T

from discord_webhook import DiscordEmbed, DiscordWebhook
from eth_typing import Address

from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.factional_advantage import FACTIONAL_ADVANTAGE, FACTION_ICON_URLS, FACTION_COLORS
from crabada.types import Faction
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
    "0x93e1465c361531eca2998f6270c87660f18e81d8",
    "0xd5d412a38c5f4be5278860d4820782d4bb9c6351",
    "0x93e1465c361531eca2998f6270c87660f18e81d8",
    "0xd5d412a38c5f4be5278860d4820782d4bb9c6351",
    "0xbd238cdC4aE0285ED90f1c027E6BCe4FcfBcb640",
    "0xbaD22EE016e19F99c918712D06f399C0B12da1E0",
    "0x0198B604c13E1ccA07A6cd31c5dC4CDE68bDdf7E",
    "0x05e428A8640Ac0a21cb6945857B8377F2F6016c2",
    "0x32564dF03f74B481cF133e89091a513B411495D9",
]


def find_loot_snipe(user_address: Address, verbose: bool = False) -> T.Tuple[T.Dict[int, int], T.List[T.Any]]:
    web2 = CrabadaWeb2Client()

    loot_list = []
    for address in TARGET_ADDRESSES:
        mines = [m["game_id"] for m in web2.list_my_mines(address)]
        loot_list.extend(mines)

    available_loots = []
    for page in range(1,100):
        params = {
            "page": page,
            "limit": 100,
        }
        time.sleep(2.0)
        loots = web2.list_available_loots(user_address, params=params)

        if not loots:
            break

        if verbose:
            logger.print_normal(f"Searching through {len(loots)} mines...")

        available_loots.extend(loots)

    target_pages = {}
    for inx, mine in enumerate(available_loots):
        page = int((inx + 9) / 9)
        faction = mine["faction"].upper()
        if mine["game_id"] in loot_list:
            data = {"page": page, "faction": faction}
            target_pages[mine["game_id"]] = data

            if verbose:
                logger.print_bold(
                    f"Found target {mine['game_id']} on page {data['page']} faction {data['faction']}"
                )
    logger.print_ok_arrow(f"Found {len(target_pages.keys())} snipes")
    return target_pages, available_loots


class LootSnipes:
    LOOTING_URL = "https://play.crabada.com/mine/start-looting"

    def __init__(self, webhook_url: str, dry_run: bool = False):
        self.dry_run = dry_run
        self.webhook_url = webhook_url
        self.loot_snipes = {}

    def check_and_alert(self, address: str) -> None:
        logger.print_ok_blue("Hunting for loot snipes...")
        update_loot_snipes, available_loots = find_loot_snipe(address, verbose=True)
        for mine, data in update_loot_snipes.items():
            if mine not in self.loot_snipes.keys():
                page = data["page"]
                mine_faction = data["faction"]
                if mine_faction == Faction.NO_FACTION:
                    attack_factions = list(
                        [k for k in FACTIONAL_ADVANTAGE.keys() if k != Faction.NO_FACTION]
                    )
                else:
                    attack_factions = [
                        f for f, a in FACTIONAL_ADVANTAGE.items() if mine_faction in a
                    ]
                webhook_text = f"Faction: {mine_faction} Page: {page}\n"
                webhook_text += f"Loot with: **{' '.join(attack_factions)}**\n"
                logger.print_bold(webhook_text)
                if not self.dry_run:
                    webhook = DiscordWebhook(url=self.webhook_url)
                    embed = DiscordEmbed(title=f"MINE {mine}", description=f"Page: {page}\n", color=FACTION_COLORS[mine_faction].value)
                    embed.add_embed_field(name="Mine", value=mine_faction.upper())
                    embed.add_embed_field(name="Attack", value=', '.join(attack_factions))
                    webhook.add_embed(embed)
                    webhook.execute()

        self.loot_snipes = copy.deepcopy(update_loot_snipes)

        mark_for_delete = [mine for mine in self.loot_snipes.keys() if mine not in available_loots]

        for mine in mark_for_delete:
            logger.print_normal(f"Deleting mine {mine} from cache")
            del self.loot_snipes[mine]
