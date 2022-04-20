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
    "0x2b255855ef74882b7b48300bc7778dbd7b81e55e",
    "0xed6e6a787fcfab544592cedab8ed477295927e0f",
    "0x426fF99B3F0c22dC130179656385bB4a4a4A0f3f",
    "0xb14b8b1e6ef554a4643b359d04188982cc4bd32c",
]

UNVALIDATED_ADDRESSES = [
    "0xe7679a598b476af9bbf61fa22d9e4edbf74a6c1f",
    "0xc7037680db9bc95dccf7616cf413ad798ddf9d86",
    "0x1c1ecf896340f69626d926d5426ae4686a5576e0",
    "0xab5c80ca5139482abaf546755e294da6986512f8",
    "0xf603bd3789c5787c0bc78a19bfb96d4651561ad8",
    "0x9ae1273678a3f4ab9d9fd5b51808c1cd7a6ba946",
    "0x92b6d8881153763ed6d8bade2ba1b073bdc4fbee",
    "0xae580287c02bb5455a3e680c88040921893751de",
    "0x74dc71b8ff1377891f730ae0a205034f4acdc9f6",
    "0xb43e226669a2b9af39afe869f6357194c1d1cb82",
    "0x1e79dbcbb7eadf462fbb3f5812eb59e0808c8b04",
    "0x69a4b86f6f8f3bfd0e79ec8ca554af9751770606",
    "0xb87abaf428a6c16757a497180cdfe4b0df563433",
    "0xe6f8e10a344f37fb986bb9f6da9e70586bf66bca",
    "0xfbc8938a58cf13f179961f0e8a30b0188d3b3dfc",
    "0xca663017d99db8f9f23bfadd5ee6d2cde5b5c665",
    "0xfbc8938a58cf13f179961f0e8a30b0188d3b3dfc",
    "0x8a0e11751d45da6d0377d4ad53ccbf71144d960f",
    "0xb43e226669a2b9af39afe869f6357194c1d1cb82",
    "0x74dc71b8ff1377891f730ae0a205034f4acdc9f6",
    "0xae580287c02bb5455a3e680c88040921893751de",
    "0x92b6d8881153763ed6d8bade2ba1b073bdc4fbee",
    "0xb4f821c2ec6da5ea9577497129a6c400f183950a",
    "0xfff827f8f80bbdd5b3d3f4fd62af2d12377b9094",
    "0xddae761f963ccbc77ed33e89bc6b0e0022dc9ec0",
    "0x791f4cb9354f21c9ae5d7a8153e411a1854facfd",
    "0xbb3c82459015497ffcf18ce01f2cb302d11b8b6c",
    "0xc47e328be8960c86df0126f019c883947b862281",
    "0xfcfa6885830f508f6efb78bdfad1e299cb56d022",
]


def get_available_loots(user_address: Address, verbose: bool = False) -> T.List[T.Any]:
    web2 = CrabadaWeb2Client()

    available_loots = []
    for page in range(1, 100):
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

    return available_loots


def find_loot_snipe(
    user_address: Address, verbose: bool = False
) -> T.Tuple[T.Dict[int, int], T.List[T.Any]]:
    web2 = CrabadaWeb2Client()

    loot_list = []
    for address in TARGET_ADDRESSES:
        mines = [m["game_id"] for m in web2.list_my_mines(address)]
        loot_list.extend(mines)

    available_loots = get_available_loots(user_address, verbose)

    target_pages = {}
    for inx, mine in enumerate(available_loots):
        page = int((inx + 9) / 9)
        faction = mine["faction"].upper()
        if mine["game_id"] in loot_list:
            data = {"page": page, "faction": faction}
            target_pages[mine["game_id"]] = data

            if verbose:
                logger.normal(
                    f"Found target {mine['game_id']} on page {data['page']} faction {data['faction']}"
                )
    logger.print_ok_arrow(f"Found {len(target_pages.keys())} snipes")
    return target_pages, [m["game_id"] for m in available_loots]


class LootSnipes:
    LOOTING_URL = "https://play.crabada.com/mine/start-looting"

    def __init__(self, webhook_url: str, dry_run: bool = False):
        self.dry_run = dry_run
        self.loot_snipes = {}
        self.webhook_url = webhook_url
        self.sent_webhooks = {}

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
                context = f"MINE: {mine} Faction: {mine_faction} Page: {page}\n"
                context += f"Loot with: {' '.join(attack_factions)}\n"
                logger.print_bold(context)

                if not self.dry_run:
                    webhook = DiscordWebhook(url=self.webhook_url)
                    embed = DiscordEmbed(
                        title=f"MINE {mine}",
                        description=f"Page: {page}\n",
                        color=FACTION_COLORS[mine_faction].value,
                    )
                    embed.add_embed_field(name="Mine", value=mine_faction.upper())
                    embed.add_embed_field(name="Attack", value=", ".join(attack_factions))
                    embed.set_thumbnail(url=FACTION_ICON_URLS[mine_faction])
                    webhook.add_embed(embed)
                    self.sent_webhooks[mine] = webhook.execute()
                time.sleep(1.0)

        self.loot_snipes.update(update_loot_snipes)

        mark_for_delete = [mine for mine in self.loot_snipes.keys() if mine not in available_loots]

        for mine in mark_for_delete:
            logger.print_normal(f"Deleting mine {mine} from cache")
            webhook = DiscordWebhook(url=self.webhook_url)
            webhook.delete(self.sent_webhooks[mine])
            del self.sent_webhooks[mine]
            del self.loot_snipes[mine]
