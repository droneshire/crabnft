import copy
import deepdiff
import json
import os
import time
import tqdm
import typing as T

from discord_webhook import DiscordEmbed, DiscordWebhook
from eth_typing import Address

from config_crabada import USERS
from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.factional_advantage import FACTIONAL_ADVANTAGE, FACTION_ICON_URLS, FACTION_COLORS
from crabada.factional_advantage import get_faction_adjusted_battle_point, get_bp_mp_from_mine
from crabada.miners_revenge import calc_miners_revenge
from crabada.types import Faction, IdleGame, TeamMember
from utils import logger
from utils.discord import DISCORD_WEBHOOK_URL
from utils.google_sheets import GoogleSheets

MAX_PAGE_DEPTH = 50
MIN_MINERS_REVENGE = 36.0
MIN_MP_THRESHOLD = 225
MIN_PAGE_THRESHOLD = 3

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


class LootSnipes:
    LOOTING_URL = "https://play.crabada.com/mine/start-looting"
    MAX_LOOT_STALE_TIME = 60.0 * 9.0
    ADDRESS_GSHEET = "No Reinforce List"
    UPDATE_TIME_DELTA = 60.0 * 5.0
    SEARCH_ADDRESSES_PER_ITERATION = 50

    def __init__(
        self,
        credentials: str,
        verbose: bool = False,
        update_from_sheet: bool = True,
        log_name_suffix: str = "",
    ):
        self.verbose = verbose
        self.urls = DISCORD_WEBHOOK_URL
        self.snipes = {}
        self.gsheet = (
            GoogleSheets(self.ADDRESS_GSHEET, credentials, []) if update_from_sheet else None
        )
        self.last_update = 0.0
        self.web2 = CrabadaWeb2Client()
        self.search_index: T.Dict[str, int] = {
            "verified": 0,
            "unverified": 0,
        }
        self.sheets_update_delta = self.UPDATE_TIME_DELTA

        self.hit_rate = {}
        if update_from_sheet:
            self.log_file = os.path.join(
                logger.get_logging_dir("crabada"),
                "sniper",
                f"hit_rates{'_' + log_name_suffix if log_name_suffix else ''}.json",
            )
            self.addresses: T.Dict[str, list] = {"verified": [], "unverified": [], "blocklist": []}
            self.hit_rate = self._read_log()
        else:
            self.log_file = os.path.join(
                logger.get_logging_dir("crabada"),
                "sniper",
                f"no_reinforce{'_' + log_name_suffix if log_name_suffix else ''}.json",
            )
            data = self._read_log()
            if not data:
                self.addresses: T.Dict[str, list] = {
                    "verified": [],
                    "unverified": [],
                    "blocklist": [],
                }
            else:
                self.addresses: T.Dict[str, list] = data

    def consolidate_snipes(self) -> None:
        sniper_dir = os.path.dirname(self.log_file)
        snipe_data = self._read_log()

        log_files = [
            f for f in os.listdir(sniper_dir) if os.path.isfile(os.path.join(sniper_dir, f))
        ]
        for log_file in log_files:
            if not log_file.startswith("no_reinforce"):
                continue
            if log_file == self.log_file:
                continue
            data = self._read_log(log_file)
            snipe_data.update(data)
        self._write_log(snipe_data)

    def delete_all_messages(self) -> None:
        logger.print_fail("Deleting all messages")
        for _, hook in self.snipes.items():
            try:
                hook["webhook"].delete(hook["sent"])
                time.sleep(0.2)
            except:
                pass

        self._write_log(self.hit_rate)

        self.snipes = {}

    def hunt(self, address: str) -> None:
        self._update_addresses_from_sheet()
        available_loots = self.get_available_loots(address, 1, 9, False)

        if len(self.addresses["verified"]) > 0:
            addresses_to_search = self._update_address_search_circ_buffer(
                "verified", self.addresses["verified"]
            )
            logger.print_ok_blue("Hunting for verified loot snipes...")
            self._hunt_no_reinforce_mines(address, addresses_to_search, available_loots, True)

        if len(self.addresses["unverified"]) > 0:
            addresses_to_search = self._update_address_search_circ_buffer(
                "unverified", self.addresses["unverified"]
            )
            logger.print_ok_blue("Hunting for suspected loot snipes...")
            self._hunt_no_reinforce_mines(
                address, self.addresses["unverified"], available_loots, False
            )
        logger.print_ok_blue("Hunting for low MP loot snipes...")
        self._hunt_low_mp_teams(address, available_loots)

    def _read_log(self, log_file: str = "") -> T.Dict[str, int]:
        if not log_file:
            log_file = self.log_file
        if not os.path.isfile(log_file):
            return {}

        with open(log_file, "r") as infile:
            return json.load(infile)

    def _write_log(self, data: T.Dict[str, int]) -> None:
        with open(self.log_file, "w") as outfile:
            json.dump(data, outfile, indent=4)

    def get_available_loots(
        self, user_address: Address, start_page: int = 1, max_pages: int = 8, verbose: bool = False
    ) -> T.List[IdleGame]:

        available_loots = []
        pb = tqdm.tqdm(total=max_pages - start_page)
        logger.print_ok_blue(f"Searching for available mines...")
        for page in range(start_page, start_page + max_pages):
            params = {
                "page": page,
                "limit": 100,
            }
            pb.update(1)
            loots = self.web2.list_available_loots(user_address, params=params)

            if not loots:
                break

            if verbose:
                logger.print_normal(f"Searching through {len(loots)} mines...")

            available_loots.extend(loots)
        pb.close()

        return available_loots

    def _update_address_search_circ_buffer(
        self, list_name: str, address_list: T.List[str]
    ) -> T.List[str]:
        search_this_time = []
        start = self.search_index[list_name]
        end = start + self.SEARCH_ADDRESSES_PER_ITERATION
        if self.SEARCH_ADDRESSES_PER_ITERATION > len(address_list):
            search_this_time = address_list
        elif end > len(address_list):
            end = end - len(address_list)
            search_this_time = address_list[start:] + address_list[0:end]
        else:
            search_this_time = address_list[start:end]
        logger.print_normal(f"Searching through address list index {start}->{end}")

        self.search_index[list_name] = end

        logger.print_normal(f"Updated {list_name} search index: {self.search_index[list_name]}")
        return search_this_time

    def add_no_reinforce_address(self, mine: IdleGame) -> None:
        user_address = mine.get("owner", "")
        if user_address in self.addresses["verified"]:
            return
        logger.print_ok(f"Found a new no-reinforce snipe {mine['owner']} to list")
        self.addresses["verified"].append(user_address)
        self._write_log(self.addresses)

    def remove_no_reinforce_address(self, mine: IdleGame) -> None:
        user_address = mine.get("owner", "")
        if user_address not in self.addresses["verified"]:
            return
        logger.print_ok(f"Removing previous no-reinforce snipe {mine['owner']} from list")
        self.addresses["verified"].remove(user_address)
        self._write_log(self.addresses)

    def find_loot_snipe(
        self,
        user_address: Address,
        address_list: T.List[str],
        available_loots: T.List[IdleGame],
        verbose: bool = False,
    ) -> T.Dict[int, T.Any]:

        bot_user_addresses = [v["address"] for _, v in USERS.items()]

        if verbose:
            logger.print_normal(f"Searching through addresses...")

        if not address_list:
            address_list = self.addresses["verified"]
            address_list.extend(self.addresses["unverified"])

        pb = tqdm.tqdm(total=len(address_list))
        loot_list = {}
        for address in address_list:
            if address in bot_user_addresses:
                logger.print_fail_arrow(f"Snipe was a bot holder user: {address}...skipping")
                continue
            if address in self.addresses["blocklist"]:
                logger.print_warn(f"Owner ({address}) is on blocklist...skipping")
                continue
            mines = {m["game_id"]: address for m in self.web2.list_my_mines(address)}
            loot_list.update(mines)
            pb.update(1)
        pb.close()

        if verbose:
            logger.print_normal(f"Checking against {len(loot_list)} no-reinforce mines...")

        target_pages = {}
        for inx, mine in enumerate(available_loots):
            page = int((inx + 9) / 9)
            faction = mine["faction"].upper()
            if mine["game_id"] in loot_list.keys():

                if mine["owner"] in self.addresses["blocklist"]:
                    logger.print_warn(
                        f"Skipping low mp mine b/c owner ({mine['owner']}) is on blocklist"
                    )
                    continue

                address = loot_list[mine["game_id"]]

                self.hit_rate[address] = self.hit_rate.get(address, 0) + 1

                bp, mp = get_bp_mp_from_mine(mine, is_looting=False, verbose=False)

                data = {
                    "page": page,
                    "faction": faction,
                    "defense_battle_point": bp,
                    "defense_mine_point": mp,
                    "address": address,
                }
                target_pages[mine["game_id"]] = data

                if verbose:
                    logger.print_normal(
                        f"Found target {mine['game_id']} on page {data['page']} faction {data['faction']}"
                    )
        logger.print_ok_arrow(f"Found {len(target_pages.keys())} snipes")
        return target_pages

    def _create_fake_team(self, loot_team: str, mine: IdleGame) -> IdleGame:
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

    def find_low_mr_teams(
        self,
        user_address: Address,
        available_loots: T.List[IdleGame],
        mp_threshold: int = MIN_MP_THRESHOLD,
        min_page_threshold: int = MIN_PAGE_THRESHOLD,
        verbose: bool = False,
    ) -> T.Dict[int, T.Any]:
        target_pages = {}
        bot_user_addresses = [v["address"] for _, v in USERS.items()]
        for inx, mine in enumerate(available_loots):

            if mine["owner"] in bot_user_addresses:
                logger.print_fail_arrow(
                    f"Snipe added for bot holder user: {mine['owner']}...skipping"
                )
                continue

            faction = mine["faction"].upper()

            MINE_PER_PAGE = 8
            page = int((inx + MINE_PER_PAGE) / MINE_PER_PAGE)
            bp, mp = get_bp_mp_from_mine(mine, is_looting=False, verbose=False)

            if mp > mp_threshold or page < min_page_threshold:
                continue

            if mine["owner"] in self.addresses["blocklist"]:
                logger.print_warn(
                    f"Skipping low mp mine b/c owner ({mine['owner']}) is on blocklist"
                )
                continue

            data = {
                "page": page,
                "faction": faction,
                "defense_mine_point": mp,
                "defense_battle_point": bp,
                "address": mine["owner"],
            }
            target_pages[mine["game_id"]] = data

        logger.print_ok_arrow(f"Found {len(target_pages.keys())} low MP snipes")
        return target_pages

    def _update_addresses_from_sheet(self) -> None:
        if not self.gsheet:
            return

        now = time.time()
        if now - self.last_update < self.sheets_update_delta:
            return

        self.last_update = now

        old_addresses = copy.deepcopy(self.addresses)

        try:
            self.addresses = {
                "verified": list(set(self.gsheet.read_column(1)[1:])),
                "unverified": list(set(self.gsheet.read_column(3)[1:])),
                "blocklist": list(set(self.gsheet.read_column(4)[1:])),
            }
            self.sheets_update_delta = self.UPDATE_TIME_DELTA
        except:
            self.sheets_update_delta = self.sheets_update_delta * 2

        diff = deepdiff.DeepDiff(old_addresses, self.addresses)
        if diff:
            logger.print_bold(f"Updating from spreadsheet...")
            logger.print_bold(f"{len(self.addresses['verified'])} verified addresses")
            logger.print_bold(f"{len(self.addresses['unverified'])} unverified addresses")
            logger.print_bold(f"{len(self.addresses['blocklist'])} blocklist addresses")
            logger.print_normal(f"{diff}")

    def _get_address_snipe_embed(
        self,
        attack_factions: T.List[str],
        mine_faction: str,
        mine: int,
        page: int,
        battle_point: int,
        verified: bool,
        address: str,
    ) -> DiscordEmbed:
        embed = DiscordEmbed(
            title=f"MINE {mine}",
            description=f"{', '.join(attack_factions)}\n",
            color=FACTION_COLORS[mine_faction].value,
        )
        embed.add_embed_field(name="Mine", value=mine_faction.upper(), inline=True)
        embed.add_embed_field(name="Page", value=page, inline=True)
        embed.add_embed_field(name="BP", value=battle_point, inline=False)
        embed.add_embed_field(name="Verified", value="True" if verified else "False", inline=True)
        embed.add_embed_field(name="Address", value=address[:8], inline=True)
        embed.add_embed_field(name="Address Hit Count", value=self.hit_rate[address], inline=False)

        embed.set_thumbnail(url=FACTION_ICON_URLS[mine_faction])
        return embed

    def _get_low_mp_snipe_embed(
        self,
        attack_factions: T.List[str],
        mine_faction: str,
        mine: int,
        page: int,
        battle_point: int,
        mine_point: int,
    ) -> DiscordEmbed:
        embed = DiscordEmbed(
            title=f"MINE {mine}",
            description=f"{', '.join(attack_factions)}\n",
            color=FACTION_COLORS[mine_faction].value,
        )
        embed.add_embed_field(name="Mine", value=mine_faction.upper(), inline=True)
        embed.add_embed_field(name="Page", value=page, inline=True)
        embed.add_embed_field(name="BP", value=battle_point, inline=False)
        embed.add_embed_field(name="MP", value=mine_point, inline=True)
        embed.set_thumbnail(url=FACTION_ICON_URLS[mine_faction])
        return embed

    def _hunt_low_mp_teams(self, address: str, available_loots: T.List[IdleGame]) -> None:
        update_loot_snipes = self.find_low_mr_teams(address, available_loots, verbose=True)

        def get_embed(mine: int, data: T.Dict[str, T.Any]) -> DiscordEmbed:
            page = data["page"]
            mine_faction = data["faction"]
            battle_point = data["defense_battle_point"]
            mine_point = data["defense_mine_point"]

            if mine_faction == Faction.NO_FACTION:
                attack_factions = ["ANY"]
            else:
                attack_factions = [f for f, a in FACTIONAL_ADVANTAGE.items() if mine_faction in a]

            context = f"MINE: {mine} Faction: {mine_faction} Page: {page}\n"
            context += f"Loot with: {' '.join(attack_factions)}\n"
            context += f"MP: {data['defense_mine_point']}\n"
            logger.print_normal(context)

            return self._get_low_mp_snipe_embed(
                attack_factions, mine_faction, mine, page, battle_point, mine_point
            )

        open_loots = [m["game_id"] for m in available_loots]
        self._update_discord(
            update_loot_snipes, open_loots, "LOW_MR_LOOT_SNIPE", embed_handle=get_embed
        )

    def _hunt_no_reinforce_mines(
        self,
        address: str,
        address_list: T.List[str],
        available_loots: T.List[IdleGame],
        verified: bool,
    ) -> None:
        update_loot_snipes = self.find_loot_snipe(
            address, address_list, available_loots, verbose=self.verbose
        )

        def get_embed(mine: int, data: T.Dict[str, T.Any]) -> DiscordEmbed:
            page = data["page"]
            mine_faction = data["faction"]
            battle_point = data["defense_battle_point"]
            address = data["address"]

            if mine_faction == Faction.NO_FACTION:
                attack_factions = ["ANY"]
            else:
                attack_factions = [f for f, a in FACTIONAL_ADVANTAGE.items() if mine_faction in a]

            context = f"MINE: {mine} Faction: {mine_faction} Page: {page}\n"
            context += f"Loot with: {' '.join(attack_factions)}\n"
            logger.print_bold(context)

            return self._get_address_snipe_embed(
                attack_factions, mine_faction, mine, page, battle_point, verified, address
            )

        open_loots = [m["game_id"] for m in available_loots]
        self._update_discord(update_loot_snipes, open_loots, "LOOT_SNIPE", embed_handle=get_embed)

    def _get_mines_to_delete(self, available_loots: T.List[int]) -> T.List[int]:
        mark_for_delete = []
        for mine in self.snipes.keys():
            if mine not in available_loots:
                mark_for_delete.append(mine)
                continue

            if time.time() - self.snipes[mine].get("start_time", 0.0) > self.MAX_LOOT_STALE_TIME:
                mark_for_delete.append(mine)
                continue

            if self.snipes[mine].get("fail_count", 0) > 3:
                mark_for_delete.append(mine)
                continue

        return mark_for_delete

    def _update_discord(
        self,
        update_loot_snipes: T.Dict[int, T.Dict[str, T.Any]],
        available_loots: T.List[int],
        discord_channel: str,
        embed_handle: T.Callable[[int, T.Dict[str, T.Any]], DiscordEmbed],
    ) -> None:
        info = []
        for mine, data in update_loot_snipes.items():
            page = data["page"]
            mine_faction = data["faction"]
            info.append((page, mine_faction, mine))

        snipes = sorted(info, key=lambda d: (d[1], -d[0], d[2]))
        for page, mine_faction, mine in snipes:
            data = update_loot_snipes[mine]
            battle_point = data["defense_battle_point"]

            if mine in self.snipes.keys():
                old_page = self.snipes[mine]["page"]
                if page == old_page:
                    logger.print_ok_blue(f"Skipping {mine} since already in cache")
                    continue

                logger.print_normal(f"Updating page for mine {mine}, {old_page} -> {page}")
                self.snipes[mine]["webhook"].remove_embeds()
                self.snipes[mine]["webhook"].add_embed(embed_handle(mine, data))
                try:
                    self.snipes[mine]["sent"] = self.snipes[mine]["webhook"].edit(
                        self.snipes[mine]["sent"]
                    )
                    self.snipes[mine]["page"] = page
                    self.snipes[mine]["fail_count"] = 0
                except:
                    logger.print_warn("failed to edit webhook, deleting webhook...")
                    self.snipes[mine]["fail_count"] += 1
                continue

            self.snipes[mine] = {}
            self.snipes[mine]["webhook"] = DiscordWebhook(
                url=self.urls[discord_channel], rate_limit_retry=True
            )
            self.snipes[mine]["webhook"].add_embed(embed_handle(mine, data))
            try:
                self.snipes[mine]["sent"] = self.snipes[mine]["webhook"].execute()
                self.snipes[mine]["page"] = page
                self.snipes[mine]["start_time"] = time.time()
                self.snipes[mine]["fail_count"] = 0
            except:
                logger.print_warn("failed to send webhook")
                self.snipes[mine]["fail_count"] += 1

            time.sleep(1.0)

        mark_for_delete = self._get_mines_to_delete(available_loots)

        for mine in mark_for_delete:
            logger.print_normal(f"Deleting mine {mine} from cache")
            try:
                self.snipes[mine]["webhook"].delete(self.snipes[mine]["sent"])
                del self.snipes[mine]
            except:
                logger.print_fail("failed to delete webhook")

        logger.print_normal(f"DB: {','.join([str(k) for k in self.snipes.keys()])}")

        self._write_log(self.hit_rate)
