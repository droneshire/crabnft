import copy
import json
import random
import time
import typing as T

from yaspin import yaspin

from wyndblast.game_stats import WyndblastLifetimeGameStatsLogger
from wyndblast.game_stats import NULL_GAME_STATS
from wyndblast import types
from wyndblast.wyndblast_web2_client import PveWyndblastWeb2Client
from wyndblast.wyndblast_web3_client import WyndblastGameWeb3Client
from utils import logger
from utils.config_types import UserConfig
from utils.email import Email

MISSION_PREFIX = "M1S"

TIME_BETWEEN_BATTLES = 5.0

LEVEL_TO_NUM_ENEMIES = {
    f"{MISSION_PREFIX}1:1": 2,
    f"{MISSION_PREFIX}1:2": 3,
    f"{MISSION_PREFIX}1:3": 4,
    f"{MISSION_PREFIX}2:1": 3,
    f"{MISSION_PREFIX}2:2": 3,
    f"{MISSION_PREFIX}2:3": 4,
    f"{MISSION_PREFIX}3:1": 3,
    f"{MISSION_PREFIX}3:2": 5,
    f"{MISSION_PREFIX}3:3": 6,
    f"{MISSION_PREFIX}4:1": 4,
    f"{MISSION_PREFIX}4:2": 6,
    f"{MISSION_PREFIX}4:3": 6,
    f"{MISSION_PREFIX}5:1": 4,
    f"{MISSION_PREFIX}5:2": 6,
    f"{MISSION_PREFIX}5:3": 9,
    f"{MISSION_PREFIX}6:1": 6,
    f"{MISSION_PREFIX}6:2": 9,
    f"{MISSION_PREFIX}6:3": 9,
}

LEVEL_HIERARCHY = {
    ":E": 3,
    ":M": 2,
    ":H": 1,
}

BATTLE_ENEMY_DNAS = [
    "W0000000000WSW000002WE00004:W0000000000WSW000009WE00004:W0000000000WSW000015WE00004:W0000000000WSW000021WE00004:W0000000000D00000000WE00004:W0000000000D00000000WE00004:W0000000000D00000000WE00004:W0000000000D00000000WE00004:0xA000000B000000000C0002092022D00000080004:80004",
    "W0000000000WSW000003WE00017:W0000000000WSW000010WE00017:W0000000000WSW000016WE00017:W0000000000WSW000022WE00017:W0000000000D00000000WE00017:W0000000000D00000000WE00017:W0000000000D00000000WE00017:W0000000000D00000000WE00017:0xA000000B000000000C0002092022D00000080040:80040",
    "W0000000000WSW000050WE00005:W0000000000WSW000058WE00005:W0000000000WSW000062WE00005:W0000000000WSW000068WE00005:W0000000000D00000000WE00005:W0000000000D00000000WE00005:W0000000000D00000000WE00005:W0000000000D00000000WE00005:0xA000000B000000000C0002092022D00000080028:80028",
    "W0000000000WSW000052WE00017:W0000000000WSW000055WE00017:W0000000000WSW000063WE00017:W0000000000WSW000067WE00017:W0000000000D00000000WE00017:W0000000000D00000000WE00017:W0000000000D00000000WE00017:W0000000000D00000000WE00017:0xA000000B000000000C0002092022D00000080048:80048",
    "W0000000000DSW000030W000158:W0000000000WSW000039W000153:W0000000000WSW000033W000020:W0000000000WSW000029W000129:W0000000000DSW000048W000129:W0000000000DSW000025W000155:W0000000000WSW000042W000155:W0000000000DSW000040W000153:0x4B3903952A25961B9E66216186Efd9B21903AEd3:13728",
    "W0000000000DSW000045W000133:W0000000000WSW000027W000036:W0000000000DSW000028W000133:W0000000000DSW000044W000124:W0000000000DSW000043W000148:W0000000000WSW000038W000148:W0000000000WSW000040W000132:W0000000000WSW000036W000133:0x4B3903952A25961B9E66216186Efd9B21903AEd3:11118",
    "W0000000000WSW000002WE00004:W0000000000WSW000009WE00004:W0000000000WSW000015WE00004:W0000000000WSW000021WE00004:W0000000000D00000000WE00004:W0000000000D00000000WE00004:W0000000000D00000000WE00004:W0000000000D00000000WE00004:0xA000000B000000000C0002092022D00000080005:80005",
    "W0000000000WSW000004WE00010:W0000000000WSW000007WE00010:W0000000000WSW000014WE00010:W0000000000WSW000019WE00010:W0000000000D00000000WE00010:W0000000000D00000000WE00010:W0000000000D00000000WE00010:W0000000000D00000000WE00010:0xA000000B000000000C0002092022D00000080011:80011",
    "W0000000000WSW000003WE00007:W0000000000WSW000010WE00007:W0000000000WSW000016WE00007:W0000000000WSW000022WE00007:W0000000000D00000000WE00007:W0000000000D00000000WE00007:W0000000000D00000000WE00007:W0000000000D00000000WE00007:0xA000000B000000000C0002092022D00000080008:80008",
    "W0000000000WSW000001WE00002:W0000000000WSW000008WE00002:W0000000000WSW000013WE00002:W0000000000WSW000020WE00002:W0000000000D00000000WE00002:W0000000000D00000000WE00002:W0000000000D00000000WE00002:W0000000000D00000000WE00002:0xA000000B000000000C0002092022D00000080002:80002",
    "W0000000000WSW000002WE00004:W0000000000WSW000009WE00004:W0000000000WSW000015WE00004:W0000000000WSW000021WE00004:W0000000000D00000000WE00004:W0000000000D00000000WE00004:W0000000000D00000000WE00004:W0000000000D00000000WE00004:0xA000000B000000000C0002092022D00000080005:80005",
]


@yaspin(text="Resting between battles...")
def wait(wait_time) -> None:
    time.sleep(wait_time)


class PveGame:
    MAX_WYNDS_PER_BATTLE = 2
    MIN_GAME_DURATION = 10
    MAX_GAME_DURATION = 29

    def __init__(
        self,
        user: str,
        config: UserConfig,
        email_accounts: T.List[Email],
        wynd_w2: PveWyndblastWeb2Client,
        wynd_w3: WyndblastGameWeb3Client,
        stats_logger: WyndblastLifetimeGameStatsLogger,
    ) -> None:
        self.user = user
        self.config = config
        self.email_accounts = email_accounts
        self.wynd_w2 = wynd_w2
        self.wynd_w3 = wynd_w3
        self.stats_logger = stats_logger

        self.current_stats = copy.deepcopy(NULL_GAME_STATS)

        logger.print_ok_blue(f"\nStarting PVE game for user {user}...")

    def _get_num_enemies_for_mission(self, mission: str) -> int:
        if not mission.startswith(MISSION_PREFIX):
            return 0

        # strip off the difficulty part since all difficulties are same num enemies
        mission_stage = mission[:-2]
        return LEVEL_TO_NUM_ENEMIES.get(mission_stage, 0)

    def _get_enemy_lineup(self, num_enemies: int) -> T.List[types.BattleUnit]:
        enemies: T.List[types.BattleUnit] = []
        for i in range(num_enemies):
            unit = types.BattleUnit = {
                "equipment_dna": "",
                "rider_dna": "",
                "wynd_dna": BATTLE_ENEMY_DNAS[i],
            }
            enemies.append(unit)

        return enemies

    def _get_player_lineup(
        self, num_players: int, our_units: types.PveNfts
    ) -> T.List[types.BattleUnit]:
        units: T.List[types.BattleUnit] = []
        if not our_units:
            logger.print_warn(f"Could not get nft data for player lineup creation")
            return []

        wynds: T.List[types.PveWynd] = our_units["wynd"]

        if len(wynds) < num_players:
            logger.print_warn(
                f"Not enough ({len(wynds)}) wynds for requested num of players. Wanted: {num_players}"
            )

        num_players = min(len(wynds), num_players)

        for i in range(num_players):
            dna_string = wynds[i].get("metadata", {}).get("dna", {}).get("all", "")
            product_id = wynds[i].get("product_id", "")
            if not dna_string:
                logger.print_warn(f"Could not get DNA string for ID: {product_id}")
                return []

            unit = types.BattleUnit = {
                "equipment_dna": "",
                "rider_dna": "",
                "wynd_dna": dna_string,
            }
            units.append(unit)

        return units

    def _check_and_claim_quest_list(self) -> None:
        """
        Claim any quest achievements that have occurred (daily/weekly/level/story)
        """
        logger.print_ok_blue(f"Attempting to claim daily quests")
        res: types.ClaimQuests = self.wynd_w2.claim_daily()

        if res:
            logger.print_ok(f"Successfully claimed daily rewards! EXP[{res['exp']}]")

            if res["is_level_up"]:
                logger.print_ok_arrow(f"Leveled up our Profile!")

        logger.print_ok_blue(f"Attempting to claim weekly quests")
        res: types.ClaimQuests = self.wynd_w2.claim_weekly()

        if res:
            logger.print_ok(f"Successfully claimed weekly rewards! EXP[{res['exp']}]")

            if res["is_level_up"]:
                logger.print_ok_arrow(f"Leveled up our Profile!")

    def _check_and_claim_rewards(self) -> None:
        """
        Claim CHRO rewards from the game
        """
        pass

    def _check_and_do_standard_quest_list(self) -> None:
        """
        Do the Quest List for non-story related items
        """

    def _check_and_play_story(self, nft_data: types.PveNfts) -> bool:
        stages: types.PveStages = self.wynd_w2.get_stages()
        if not stages:
            logger.print_warn(f"No level data obtained")
            return False
        completed = stages["completed"]
        unlocked = stages["unlocked"]
        next_stages = sorted([s for s in unlocked if s not in completed])
        if len(next_stages) == 0:
            logger.print_normal(f"Not playing b/c no stages left to play!")
            return

        stage_id = next_stages[0]

        num_enemies = self._get_num_enemies_for_mission(stage_id)

        logger.print_ok_blue(f"We will be battling {num_enemies} enemies in stage {stage_id}...")
        battle_setup: types.BattleSetup = types.BattleSetup()
        battle_setup["enemy"] = self._get_enemy_lineup(num_enemies)
        battle_setup["player"] = self._get_player_lineup(self.MAX_WYNDS_PER_BATTLE, nft_data)

        if not battle_setup["player"]:
            logger.print_fail(f"No players available to battle!")
            return False

        logger.print_normal(f"Using following lineup:\n{json.dumps(battle_setup, indent=4)}")

        duration = random.randint(self.MIN_GAME_DURATION, self.MAX_GAME_DURATION)
        if self.wynd_w2.battle(stage_id, battle_setup, duration=duration):
            logger.print_ok(f"We WON")
        else:
            logger.print_warn(f"Failed to submit battle")
            return False

        for player in battle_setup["player"]:
            dna = player.get("wynd_dna", "")
            if not dna:
                continue
            dna_split = dna.split(":")
            product_id = ":".join(dna_split[-2:])
            logger.print_normal(f"Attempting to level up wynd {product_id}...")
            if self.wynd_w2.level_up_wynd(dna):
                logger.print_ok_arrow(f"Leveled up wynd {product_id}!")

        return True

    def play_game(self) -> None:
        nft_data: types.PveNfts = self.wynd_w2.get_nft_data()
        while self._check_and_play_story(nft_data):
            wait(TIME_BETWEEN_BATTLES)
            logger.print_normal(f"Playing next stage...")

        # self._check_and_do_standard_quest_list()
        # self._check_and_claim_quest_list()
        # self._check_and_claim_rewards()
