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
    "0xd5d412a38c5f4be5278860d4820782d4bb9c6351",
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
    # UNVALIDATED_ADDRESSES
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
    "0xbb3c82459015497ffcf18ce01f2cb302d11b8b6c",
    "0xc47e328be8960c86df0126f019c883947b862281",
    "0xfcfa6885830f508f6efb78bdfad1e299cb56d022",
    "0x9f1920a809b07f2748075e5eac216264c74ad647",
    "0xf95132048b0f642f45d400aab08d2f6c86d63d98",
    "0x40f5402277e83a8a0ba902e255883f3f5142978a",
    "0x49fff1e342921f89d9bab94d95dd159c641d8a0b",
    "0x5a538c794d056a2b3e437bf8c563e1dc195e1393",
    "0xa8c153f9441913a5cf28fd5149d2287822d0535f",
    "0xfe1315dafd9624e59c9a257d457215bafe8dc67c",
    "0xf2aafffa10eeb133b6bda8b40aba2b5068c7d633",
    "0x2e2530d185f299a7c88862d34a490e253953c07c",
    "0x223a2a1884868decd14bf63afd247962819a6f2a",
    "0x2e2530d185f299a7c88862d34a490e253953c07c",
    "0xb8cc9ca72f12ad16352917ccf769a5de5c2df007",
    "0xc049082f2fa3f142c987cf31054f67a2e2577bc5",
    "0xc016ef5cb8c874c1da0fe0dc160770e063bb4d74",
    "0x6e7609bbc3701f42ea56e068841cdc0955e7feec",
    "0x1ab93c4e10995aa1d94b265949a247e2c1db8251",
    "0xbd1c769b9678cb795b213d6d8a417a38d77a905e",
    "0x1b309d8d43aa5d9d719bd65f73fdb8cdf3f839d9",
    "0xba23023f3edfa5501faa5d70ef8b7103a80fcad6",
    "0xd7f1fce99d88301707035dcf8196819318b7f4d1",
    "0x85b5edb52e17b9e9f789b69dca2e83ca624a7ece",
    "0x6e6a61b04c1a0c2f81a0df6a43fe8eccbd635547",
    "0x115d023a655e8d70a1153302b41a641b080eb81f",
    "0x1d0c32ed8225e6173fc043442706a6c8661ac045",
    "0x3969a1b3be0cb3024ebda6778ba72c4f72e1423a",
    "0x2e2530d185f299a7c88862d34a490e253953c07c",
    "0x0445d01f3f467c1661ff9267fd7592e6f6801576",
    "0x6212a5e86f46841e4ccc44e8a3a763efcd9b3fcc",
    "0x7d9291fb57822031977a983dbbf7d0157c016c60",
    "0x337a52a3f0d42303eb73d228e6b43544f8261671",
    "0x833c29e720ceaee0681a12721dd51f5e513a1dca",
    "0x9ae1273678a3f4ab9d9fd5b51808c1cd7a6ba946",
    "0x4c0f4f0268fe1d86b3745cf6d9243cdb081265cc",
]

MAX_PAGE_DEPTH = 50


def get_available_loots(user_address: Address, verbose: bool = False) -> T.List[T.Any]:
    web2 = CrabadaWeb2Client()

    available_loots = []
    for page in range(1, 8):
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

    if verbose:
        logger.print_normal(f"Checking against {len(loot_list)} suspected no reinforce mines...")

    target_pages = {}
    for inx, mine in enumerate(available_loots):
        page = int((inx + 9) / 9)
        faction = mine["faction"].upper()
        if mine["game_id"] in loot_list:
            data = {"page": page, "faction": faction}
            target_pages[mine["game_id"]] = data

            if verbose:
                logger.print_normal(
                    f"Found target {mine['game_id']} on page {data['page']} faction {data['faction']}"
                )
    logger.print_ok_arrow(f"Found {len(target_pages.keys())} snipes")
    return target_pages, [m["game_id"] for m in available_loots]


class LootSnipes:
    LOOTING_URL = "https://play.crabada.com/mine/start-looting"

    def __init__(self, webhook_url: str, verbose: bool = False):
        self.verbose = verbose
        self.url = webhook_url
        self.snipes = {}

    def delete_all_messages(self) -> None:
        logger.print_fail("Deleting all messages")
        for _, hook in self.snipes.items():
            try:
                hook["webhook"].delete(hook["sent"])
                time.sleep(1.0)
            except:
                pass
        self.snipes = {}

    def _get_embed(
        self, attack_factions: T.List[str], mine_faction: str, mine: int, page: int
    ) -> None:
        embed = DiscordEmbed(
            title=f"MINE {mine}",
            description=f"{', '.join(attack_factions)}\n",
            color=FACTION_COLORS[mine_faction].value,
        )
        embed.add_embed_field(name="Mine", value=mine_faction.upper())
        embed.add_embed_field(name="Page", value=page)
        embed.set_thumbnail(url=FACTION_ICON_URLS[mine_faction])
        return embed

    def check_and_alert(self, address: str) -> None:
        logger.print_ok_blue("Hunting for loot snipes...")
        update_loot_snipes, available_loots = find_loot_snipe(address, verbose=self.verbose)
        for mine, data in update_loot_snipes.items():
            page = data["page"]
            mine_faction = data["faction"]

            if mine_faction == Faction.NO_FACTION:
                attack_factions = ["ANY"]
            else:
                attack_factions = [f for f, a in FACTIONAL_ADVANTAGE.items() if mine_faction in a]

            if mine in self.snipes.keys():
                old_page = self.snipes[mine]["page"]
                if page == old_page:
                    logger.print_ok_blue(f"Skipping {mine} since already in cache")
                    continue

                logger.print_normal(f"Updating page for mine {mine}, {old_page} -> {page}")
                self.snipes[mine]["webhook"].remove_embeds()
                self.snipes[mine]["webhook"].add_embed(
                    self._get_embed(attack_factions, mine_faction, mine, page)
                )
                try:
                    self.snipes[mine]["sent"] = self.snipes[mine]["webhook"].edit(
                        self.snipes[mine]["sent"]
                    )
                    self.snipes[mine]["page"] = page
                except:
                    logger.print_warn("failed to edit webhook, deleting webhook...")
                    self.snipes[mine]["webhook"].delete(self.snipes[mine]["sent"])
                    del self.snipes[mine]
                time.sleep(1.0)
                continue

            context = f"MINE: {mine} Faction: {mine_faction} Page: {page}\n"
            context += f"Loot with: {' '.join(attack_factions)}\n"
            logger.print_bold(context)

            self.snipes[mine] = {}
            self.snipes[mine]["webhook"] = DiscordWebhook(url=self.url, rate_limit_retry=True)
            self.snipes[mine]["webhook"].add_embed(
                self._get_embed(attack_factions, mine_faction, mine, page)
            )
            try:
                self.snipes[mine]["sent"] = self.snipes[mine]["webhook"].execute()
                self.snipes[mine]["page"] = page
                self.snipes[mine]["faction"] = mine_faction
            except:
                logger.print_warn("failed to send webhook")

            time.sleep(4.0)

        mark_for_delete = [mine for mine in self.snipes.keys() if mine not in available_loots]

        for mine in mark_for_delete:
            logger.print_normal(f"Deleting mine {mine} from cache")
            self.snipes[mine]["webhook"].delete(self.snipes[mine]["sent"])
            del self.snipes[mine]
