import copy
import time
import typing as T

from discord_webhook import DiscordEmbed, DiscordWebhook
from eth_typing import Address

from crabada.loot_target_addresses import TARGET_ADDRESSES, UNVALIDATED_ADDRESSES
from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.factional_advantage import FACTIONAL_ADVANTAGE, FACTION_ICON_URLS, FACTION_COLORS
from crabada.factional_advantage import get_faction_adjusted_battle_point
from crabada.miners_revenge import calc_miners_revenge
from crabada.types import Faction, IdleGame, TeamMember
from utils import logger

MAX_PAGE_DEPTH = 50
MIN_MINERS_REVENGE = 0.35

PURE_LOOT_TEAM_IDLE_GAME_STATS = {
    "CCP": {
        "bp": 661,
        "mp": 245,
        "faction": Faction.MACHINE,
    },
    "SSP": {
        "bp": 665,
        "mp": 239,
        "faction": Faction.TRENCH,
    },
    "BBP": {
        "bp": 695,
        "mp": 213,
        "faction": Faction.ORE,
    },
    "RRP": {
        "bp": 665,
        "mp": 239,
        "faction": Faction.ABYSS,
    },
}


def get_available_loots(
    user_address: Address, max_pages: int = 8, verbose: bool = False
) -> T.List[IdleGame]:
    web2 = CrabadaWeb2Client()

    available_loots = []
    for page in range(1, max_pages):
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
    user_address: Address, address_list: T.List[str], verbose: bool = False
) -> T.Tuple[T.Dict[int, int], T.List[T.Any]]:
    web2 = CrabadaWeb2Client()

    loot_list = []
    for address in address_list:
        mines = [m["game_id"] for m in web2.list_my_mines(address)]
        loot_list.extend(mines)

    available_loots = get_available_loots(user_address, max_pages=8, verbose=verbose)

    if verbose:
        logger.print_normal(f"Checking against {len(loot_list)} suspected no reinforce mines...")

    target_pages = {}
    for inx, mine in enumerate(available_loots):
        page = int((inx + 9) / 9)
        faction = mine["faction"].upper()
        if mine["game_id"] in loot_list:
            battle_point = get_faction_adjusted_battle_point(mine, is_looting=False, verbose=True)
            data = {"page": page, "faction": faction, "defense_battle_point": battle_point}
            target_pages[mine["game_id"]] = data

            if verbose:
                logger.print_normal(
                    f"Found target {mine['game_id']} on page {data['page']} faction {data['faction']}"
                )
    logger.print_ok_arrow(f"Found {len(target_pages.keys())} snipes")
    return target_pages, [m["game_id"] for m in available_loots]


def create_fake_team(loot_team: str, mine: IdleGame) -> IdleGame:
    mine["attack_team_members"] = []
    for _ in range(2):
        crab = TeamMember(
            hp=0,
            damage=0,
            speed=0,
            critical=0,
            armor=0,
        )
        mine["attack_team_members"].append(crab)

    crab = TeamMember(
        hp=0,
        damage=0,
        speed=0,
        critical=PURE_LOOT_TEAM_IDLE_GAME_STATS[loot_team]["mp"],
        armor=PURE_LOOT_TEAM_IDLE_GAME_STATS[loot_team]["bp"],
    )

    mine["attack_team_members"].append(crab)
    mine["attack_point"] = PURE_LOOT_TEAM_IDLE_GAME_STATS[loot_team]["bp"]
    mine["attack_team_faction"] = PURE_LOOT_TEAM_IDLE_GAME_STATS[loot_team]["faction"]

    return mine


def find_low_mr_teams(user_address: Address, verbose: bool = False) -> None:
    available_loots = get_available_loots(user_address, max_pages=4, verbose=verbose)

    target_pages = {}
    for inx, mine in enumerate(available_loots):
        for team_type in PURE_LOOT_TEAM_IDLE_GAME_STATS.keys():
            mine = create_fake_team(team_type, mine)
            page = int((inx + 9) / 9)
            faction = mine["faction"].upper()
            miners_revenge = calc_miners_revenge(mine)
            print(miners_revenge * 100.0)
            if miners_revenge > MIN_MINERS_REVENGE or page <= 2:
                continue
            data = {"page": page, "faction": faction, "defense_battle_point": battle_point}
            target_pages[mine["game_id"]] = data

            if verbose:
                logger.print_normal(
                    f"Found target {mine['game_id']} with MR {miners_revenge * 100.0}% on page {data['page']} faction {data['faction']}"
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

    def hunt(self, address: str) -> None:
        logger.print_ok_blue("Hunting for verified loot snipes...")
        self._hunt_no_reinforce_mines(address, TARGET_ADDRESSES, True)
        logger.print_ok_blue("Hunting for suspected loot snipes...")
        self._hunt_no_reinforce_mines(address, UNVALIDATED_ADDRESSES, False)
        # logger.print_ok_blue("Hunting for low MP loot snipes...")
        # self.hunt_low_mp_teams()

    def _get_embed(
        self,
        attack_factions: T.List[str],
        mine_faction: str,
        mine: int,
        page: int,
        battle_point: int,
        verified: bool,
    ) -> None:
        embed = DiscordEmbed(
            title=f"MINE {mine}",
            description=f"{', '.join(attack_factions)}\n",
            color=FACTION_COLORS[mine_faction].value,
        )
        embed.add_embed_field(name="Mine", value=mine_faction.upper(), inline=True)
        embed.add_embed_field(name="Page", value=page, inline=True)
        embed.add_embed_field(name="BP", value=battle_point, inline=False)
        embed.add_embed_field(name="Verified", value="True" if verified else "False", inline=True)
        embed.set_thumbnail(url=FACTION_ICON_URLS[mine_faction])
        return embed

    def _hunt_no_reinforce_mines(
        self, address: str, address_list: T.List[str], verified: bool
    ) -> None:
        update_loot_snipes, available_loots = find_loot_snipe(
            address, address_list, verbose=self.verbose
        )
        self._update_discord(update_loot_snipes, available_loots, verified=verified)

    def _update_discord(
        self,
        update_loot_snipes: T.Dict[int, T.Dict[str, T.Any]],
        available_loots: T.List[int],
        verified: bool,
    ) -> None:
        for mine, data in update_loot_snipes.items():
            page = data["page"]
            mine_faction = data["faction"]
            battle_point = data["defense_battle_point"]

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
                    self._get_embed(
                        attack_factions, mine_faction, mine, page, battle_point, verified=verified
                    )
                )
                try:
                    self.snipes[mine]["sent"] = self.snipes[mine]["webhook"].edit(
                        self.snipes[mine]["sent"]
                    )
                    self.snipes[mine]["page"] = page
                except:
                    logger.print_warn("failed to edit webhook, deleting webhook...")
                time.sleep(1.0)
                continue

            context = f"MINE: {mine} Faction: {mine_faction} Page: {page}\n"
            context += f"Loot with: {' '.join(attack_factions)}\n"
            logger.print_bold(context)

            self.snipes[mine] = {}
            self.snipes[mine]["webhook"] = DiscordWebhook(url=self.url, rate_limit_retry=True)
            self.snipes[mine]["webhook"].add_embed(
                self._get_embed(
                    attack_factions, mine_faction, mine, page, battle_point, verified=verified
                )
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
            try:
                self.snipes[mine]["webhook"].delete(self.snipes[mine]["sent"])
                del self.snipes[mine]
            except:
                logger.print_fail("failed to delete webhook")
