import copy
import datetime
import enum
import json
import random
import time
import typing as T
from discord import Color
from discord_webhook import DiscordEmbed, DiscordWebhook
from yaspin import yaspin

from config_wyndblast import COMMISSION_WALLET_ADDRESS
from utils import discord
from utils import logger
from utils.config_types import UserConfig
from utils.email import Email
from utils.general import get_pretty_seconds
from utils.price import wei_to_token
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.chro_web3_client import ChroWeb3Client
from wyndblast.assets import WYNDBLAST_ASSETS
from wyndblast.game_stats import WyndblastLifetimeGameStatsLogger
from wyndblast.game_stats import NULL_GAME_STATS
from wyndblast import types
from wyndblast.pve_web2_client import PveWyndblastWeb2Client
from wyndblast.wyndblast_web3_client import WyndblastGameWeb3Client

MAP_1 = "M1S"
MAP_2 = "M2S"
MAP_3 = "M3S"

ALLOWED_MAPS = [MAP_1, MAP_2, MAP_3]


class Difficulty(enum.Enum):
    EASY = ":E"
    MEDIUM = ":M"
    HARD = ":H"


LEVEL_HIERARCHY = {
    Difficulty.EASY.value: 3,
    Difficulty.MEDIUM.value: 2,
    Difficulty.HARD.value: 1,
}


@yaspin(text="Resting between battles...")
def wait(wait_time) -> None:
    time.sleep(wait_time)


class PveGame:
    MAX_WYNDS_PER_BATTLE = 2
    MIN_GAME_DURATION = 10
    MAX_GAME_DURATION = 29
    MAX_REPLAYS_PER_CYCLE = 5  # based on a daily reward that is 20x battles per week

    TIME_BETWEEN_CLAIM_QUEST = 60.0 * 60.0 * 6
    TIME_BETWEEN_LEVEL_UP = 60.0 * 5.0
    MARGIN_AFTER_MIDNIGHT_SECONDS = 60.0 * 60.0 * 1.5

    def __init__(
        self,
        user: str,
        config: UserConfig,
        email_accounts: T.List[Email],
        wynd_w2: PveWyndblastWeb2Client,
        wynd_w3: WyndblastGameWeb3Client,
        stats_logger: WyndblastLifetimeGameStatsLogger,
        stages_info: T.List[types.LevelsInformation],
        account_info: T.List[types.AccountLevels],
        human_mode: bool,
        ignore_utc_time: bool = False,
    ) -> None:
        self.user = user
        self.config = config
        self.email_accounts = email_accounts
        self.wynd_w2 = wynd_w2
        self.wynd_w3 = wynd_w3
        self.stats_logger = stats_logger
        self.human_mode = human_mode
        self.is_deactivated = False
        self.ignore_utc_time = ignore_utc_time

        self.min_game_duration = self.MIN_GAME_DURATION if human_mode else self.MIN_GAME_DURATION
        self.max_game_duration = (
            self.MAX_GAME_DURATION * 3 if human_mode else self.MAX_GAME_DURATION
        )

        self.chro_w3: ChroWeb3Client = T.cast(
            ChroWeb3Client,
            (
                ChroWeb3Client()
                .set_credentials(config["address"], config["private_key"])
                .set_node_uri(AvalancheCWeb3Client.NODE_URL)
                .set_contract()
                .set_dry_run(False)
            ),
        )
        self.current_stats = copy.deepcopy(NULL_GAME_STATS)

        self.last_level_up = 0.0
        self.last_quest_claim = 0.0
        self.num_replays = 0

        self.last_mission = None

        self.stages_info: T.List[types.LevelsInformation] = stages_info
        self.account_info: T.List[types.AccountLevels] = account_info

        self.sorted_levels = []
        for difficulty in LEVEL_HIERARCHY.keys():
            levels = self._get_all_levels_from_cache(exclude_difficulty=True)
            self.sorted_levels.extend([l + difficulty for l in levels])

        self.completed = set(
            self.stats_logger.lifetime_stats["pve_game"]["levels_completed"].get(
                self.config["address"], []
            )
        )

        self.did_tutorial = len(self.completed) > 0

        logger.print_ok_blue(f"\nStarting PVE game for user {user}...")

    def _is_just_past_midnight_utc(self) -> bool:
        if self.ignore_utc_time:
            return True
        now = datetime.datetime.now(datetime.timezone.utc)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        time_delta = now - midnight
        return time_delta.total_seconds() < self.MARGIN_AFTER_MIDNIGHT_SECONDS

    def _get_level_five_exp(self) -> int:
        INVALID_EXP = 1000000
        for level in self.account_info:
            if level.get("level", -1) == 5:
                return level.get("total_exp", INVALID_EXP)
        return INVALID_EXP

    def _get_all_levels_from_cache(self, exclude_difficulty: bool = False) -> T.List[str]:
        levels = []
        for stages in self.stages_info:
            for stage in stages.get("stages", []):
                if exclude_difficulty:
                    stage_id = stage.get("id", "")
                    if stage_id:
                        levels.append(stage_id)
                else:
                    for difficulty, stage_difficulty_info in stage.get("difficulties", {}).items():
                        stage_id = stage_difficulty_info.get("id", "")
                        if stage_id:
                            levels.append(stage_id)

        return sorted(levels)

    def _get_stage_info_from_cache(self, mission: str) -> types.StageDifficulty:
        stages = []

        for stages in self.stages_info:
            if stages.get("id", "") in mission:
                stages = stages.get("stages", [])
                break

        level_info: types.StageInfo = types.StageInfo()
        for stage in stages:
            if stage.get("id", "") in mission:
                level_info = stage
                break

        for difficulty, stage_difficulty_info in level_info.get("difficulties", {}).items():
            if stage_difficulty_info.get("id", "") in mission:
                return stage_difficulty_info

        return {}

    def _get_num_enemies_for_mission(self, mission: str) -> int:
        if mission[:3] not in ALLOWED_MAPS:
            logger.print_warn(f"{mission} not in allowed maps [{ALLOWED_MAPS}]")
            return 0

        return len(self._get_enemy_lineup(mission))

    def _get_enemy_lineup(self, mission: str) -> T.List[types.BattleUnit]:
        enemies: T.List[types.BattleUnit] = []

        stage_info: types.StageDifficulty = self._get_stage_info_from_cache(mission)

        enemies_info = stage_info.get("enemy", {})
        for enemy_type, category in enemies_info.items():
            for status, info in category.items():
                units = info.get("units", [])
                for enemy_unit in units:
                    unit = types.BattleUnit = {
                        "equipment_dna": enemy_unit.get("equipment", ""),
                        "rider_dna": enemy_unit.get("rider", ""),
                        "wynd_dna": enemy_unit.get("wynd", ""),
                    }
                    enemies.append(unit)

        return enemies

    def _get_product_id(self, nft_data: types.PveNfts) -> str:
        units: T.List[types.BattleUnit] = []
        if not nft_data:
            logger.print_warn(f"Could not get nft data for product id")
            return ""

        wynds: T.List[types.PveWynd] = nft_data["wynd"]
        if not wynds:
            logger.print_warn(f"No wynds in user data! not setting presets")
            return ""

        product_id = wynds[0].get("product_id", "")
        return product_id

    def _get_player_lineup(
        self, num_players: int, our_units: types.PveNfts
    ) -> T.List[types.BattleUnit]:
        units: T.List[types.BattleUnit] = []
        if not our_units:
            logger.print_warn(f"Could not get nft data for player lineup creation")
            return []

        wynds: T.List[types.PveWynd] = our_units["wynd"]

        num_players = min(len(wynds), num_players)

        used_dnas_inx = []
        index = 0
        for _ in range(num_players):
            if len(used_dnas_inx) >= len(wynds):
                logger.print_warn(f"Unable to find enough wynds to play with. Found {len(units)}")
                return units

            while index in used_dnas_inx:
                index = random.randrange(num_players)

            used_dnas_inx.append(index)

            dna_string = wynds[index].get("metadata", {}).get("dna", {}).get("all", "")
            product_id = wynds[index].get("product_id", "")
            cooldown_time = wynds[index].get("cooldown_time", 1)

            if cooldown_time > 0:
                logger.print_warn(
                    f"Not using {product_id} since cooldown is {get_pretty_seconds(cooldown_time)}"
                )
                continue

            if not dna_string:
                logger.print_warn(f"Could not get DNA string for ID: {product_id}")
                continue

            unit = types.BattleUnit = {
                "equipment_dna": "",
                "rider_dna": "",
                "wynd_dna": dna_string,
            }
            units.append(unit)

        logger.print_normal(f"Using {len(units)} wynds in battle")

        return units

    def _get_next_stage(self) -> str:
        if self.last_mission is None:
            return self._get_next_stage_from_api()
        else:
            index = self.sorted_levels.index(self.last_mission) + 1
            if index >= len(self.sorted_levels):
                return self._get_next_stage_from_api()

        proposed_stage = self.sorted_levels[index]
        if proposed_stage in self.completed:
            for level in self.sorted_levels:
                if level not in self.completed:
                    return level
            return self._get_next_stage_from_api()

        return self.sorted_levels[index]

    def _get_next_stage_from_api(self) -> str:
        stages: types.PveStages = self.wynd_w2.get_stages()
        if not stages:
            logger.print_warn(f"No level data obtained")
            return ""
        for s in stages["completed"]:
            self.completed.add(s)
        if self.completed:
            self.did_tutorial = True

        self.stats_logger.lifetime_stats["pve_game"]["levels_completed"][
            self.config["address"]
        ] = list(self.completed)

        unlocked = stages["unlocked"]
        next_stages = [s for s in unlocked if s not in list(self.completed)]
        if len(next_stages) == 0:
            logger.print_normal(f"Not playing b/c no stages left to play!")
            return ""

        available_indices = [self.sorted_levels.index(v) for v in next_stages]
        if available_indices:
            stage_id = self.sorted_levels[min(available_indices)]
        else:
            return ""
        return stage_id if any([s for s in ALLOWED_MAPS if stage_id.startswith(s)]) else ""

    def _get_stamina_for_level(self, mission: str) -> int:
        stage_info: types.StageDifficulty = self._get_stage_info_from_cache(mission)
        return stage_info.get("stamina_cost", 10000)

    def _get_stamina(self) -> int:
        return self.wynd_w2.get_stamina()

    def _send_pve_update(self, account_exp: int) -> None:
        webhook = DiscordWebhook(
            url=discord.DISCORD_WEBHOOK_URL["WYNDBLAST_PVE_ACTIVITY"], rate_limit_retry=True
        )
        embed = DiscordEmbed(
            title=f"PVE ACTIVITIES",
            description=f"Finished for {self.config['discord_handle'].upper()}\n",
            color=Color.purple().value,
        )

        chro_won = self.current_stats["chro"]
        levels_completed = len(
            self.current_stats["pve_game"]["levels_completed"].get(self.config["address"], [])
        )
        if levels_completed < 1 and chro_won <= 0:
            return
        embed.add_embed_field(name=f"Account Exp", value=f"{account_exp}", inline=False)
        embed.add_embed_field(name=f"CHRO Earned", value=f"{chro_won:.2f}", inline=False)
        embed.add_embed_field(name=f"Levels Won", value=f"{levels_completed}", inline=True)

        embed.set_thumbnail(url=WYNDBLAST_ASSETS["wynd"], height=100, width=100)
        webhook.add_embed(embed)
        webhook.execute()

    def _send_summary_email(self) -> None:
        # TODO: do we want email updates?
        pass

    def _update_stats(self, account_exp: int) -> None:
        for k, v in self.current_stats.items():
            if type(v) != type(self.stats_logger.lifetime_stats.get(k)):
                logger.print_warn(
                    f"Mismatched stats:\n{self.current_stats}\n{self.stats_logger.lifetime_stats}"
                )
                continue

            if k in ["commission_chro"]:
                continue

            if isinstance(v, list):
                new_set = set(self.stats_logger.lifetime_stats[k])
                for i in v:
                    new_set.add(i)
                self.stats_logger.lifetime_stats[k] = new_set
            elif isinstance(v, dict):
                for i, j in self.stats_logger.lifetime_stats[k].items():
                    if "levels_completed" in i:
                        for address, levels in self.stats_logger.lifetime_stats[k][i].items():
                            new_stats = set(self.current_stats[k][i].get(address, []))
                            if not new_stats:
                                continue
                            total_stats = set(list(new_stats).extend(levels))
                            self.stats_logger.lifetime_stats[k][i][address] = list(total_stats)
                    elif "account_exp" in i:
                        for address, levels in self.stats_logger.lifetime_stats[k][i].items():
                            new_stats = self.current_stats[k][i].get(address, 0)
                            self.stats_logger.lifetime_stats[k][i][address] = (
                                self.stats_logger.lifetime_stats[k][i].get(address, 0) + new_stats
                            )
                    else:
                        self.stats_logger.lifetime_stats[k][i] += self.current_stats[k][i]
            else:
                self.stats_logger.lifetime_stats[k] += v

        self.stats_logger.lifetime_stats["commission_chro"] = self.stats_logger.lifetime_stats.get(
            "commission_chro", {COMMISSION_WALLET_ADDRESS: 0.0}
        )

        chro_rewards = self.current_stats["chro"]
        for address, commission_percent in self.config["commission_percent_per_mine"].items():
            commission_chro = chro_rewards * (commission_percent / 100.0)

            self.stats_logger.lifetime_stats["commission_chro"][address] = (
                self.stats_logger.lifetime_stats["commission_chro"].get(address, 0.0)
                + commission_chro
            )

            logger.print_ok(
                f"Added {commission_chro} CHRO for {address} in commission ({commission_percent}%)!"
            )

        self._send_pve_update(account_exp)

        self.current_stats = copy.deepcopy(NULL_GAME_STATS)

        logger.print_ok_blue(
            f"Lifetime Stats for {self.user.upper()}\n"
            f"{json.dumps(self.stats_logger.lifetime_stats, indent=4)}"
        )

    def _check_and_level_units(self, our_units: types.PveNfts) -> None:
        """
        Try to level up all of our units!
        """
        now = time.time()
        if now - self.last_level_up > self.TIME_BETWEEN_LEVEL_UP:
            logger.print_normal("Pinging realtime...")
            self.wynd_w2.ping_realtime()

            wynds: T.List[types.PveWynd] = our_units.get("wynd", [])

            for player in wynds:
                product_id = player.get("product_id", "")
                logger.print_normal(f"Attempting to level up wynd {product_id}...")
                if self.wynd_w2.level_up_wynd(product_id):
                    logger.print_ok_arrow(f"Leveled up wynd {product_id}!")
                else:
                    logger.print_normal(f"Unable to level up wynd {product_id}")
            self.last_level_up = now

    def _check_and_claim_quest_list(self) -> None:
        """
        Claim any quest achievements that have occurred (daily/weekly/level/story)
        """
        now = time.time()

        if now - self.last_quest_claim < self.TIME_BETWEEN_CLAIM_QUEST:
            logger.print_normal(f"Skipping quest claim, not time yet...")
            return

        self.last_quest_claim = now

        self.wynd_w2.ping_realtime()

        logger.print_ok_blue(f"Attempting to claim daily quests")
        res: types.ClaimQuests = self.wynd_w2.claim_daily()

        if res:
            logger.print_ok(f"Successfully claimed daily rewards! +{res['exp']} exp")
            self.current_stats["pve_game"]["account_exp"][self.config["address"]] = (
                self.current_stats["pve_game"]["account_exp"].get(self.config["address"], 0)
                + res["exp"]
            )

            if res["is_level_up"]:
                logger.print_ok_arrow(f"Leveled up our Profile!")

        logger.print_ok_blue(f"Attempting to claim weekly quests")
        res: types.ClaimQuests = self.wynd_w2.claim_weekly()

        if res:
            logger.print_ok(f"Successfully claimed weekly rewards! EXP[{res['exp']}]")

            if res["is_level_up"]:
                logger.print_ok_arrow(f"Leveled up our Profile!")

    def _check_and_do_standard_quest_list(self, nft_data: types.PveNfts) -> None:
        """
        Do the Quest List for non-story related items
        """
        product_id = self._get_product_id(nft_data)
        if not product_id:
            return

        logger.print_bold(f"Setting unit presets...")
        self.wynd_w2.preset_unit(product_id)

        logger.print_bold(f"Setting team presets...")
        self.wynd_w2.preset_team([product_id])

    def _get_levels_at_difficulty(self, difficulty: Difficulty) -> T.List[str]:
        return [l for l in self.sorted_levels if difficulty.value in l]

    def _get_next_level(self, countdown: types.Countdown) -> str:
        stage_id = self._get_next_stage()

        user_data: types.PveUser = {}

        if not stage_id:
            user_data = self.wynd_w2.get_user_profile()
            if not user_data:
                return ""

            if countdown:
                daily_countdown_seconds = countdown.get("daily_countdown_second", 0)
            else:
                daily_countdown_seconds = 0

            if (
                user_data.get("exp", self._get_level_five_exp()) < self._get_level_five_exp()
                and self.num_replays < self.MAX_REPLAYS_PER_CYCLE
                and daily_countdown_seconds < 60 * 60 * 3
            ):
                # only play "extra" rounds if we are within 3 hours of the end of dailies
                # so that we can get the daily exp towards our level up and weekly level up
                # otherwise no need to play since it only helps with wynd leveling which we don't
                # care about
                logger.print_bold(f"We've beat the full map, but still need more exp, replaying...")
                easy_levels = self._get_levels_at_difficulty(difficulty=Difficulty.EASY)
                stage_id = easy_levels[random.randrange(len(easy_levels))]
                self.num_replays += 1
            elif user_data.get("exp", self._get_level_five_exp()) >= self._get_level_five_exp():
                self.num_replays = 0
                logger.print_bold(f"Beat game, no need to play anymore!")
                return ""
            else:
                self.num_replays = 0
                logger.print_bold(f"Waiting for EXP boosts, no way to do that now so not playing")
                return ""

        needed_stamina = self._get_stamina_for_level(stage_id)
        current_stamina = self._get_stamina()
        if self.human_mode and current_stamina < needed_stamina:
            logger.print_normal(
                f"Not playing more since we're behaving and respecting "
                f"stamina...Have: {current_stamina} Need: {needed_stamina}"
            )
            return ""

        return stage_id

    def _check_and_play_story(self, nft_data: types.PveNfts, countdown: types.Countdown) -> bool:
        if not self._is_just_past_midnight_utc():
            logger.print_warn(f"Not within midnight window, waiting to play game...")
            return False

        stage_id = self._get_next_level(countdown)

        if not stage_id:
            return False

        num_enemies = self._get_num_enemies_for_mission(stage_id)

        logger.print_ok_blue(f"We will be battling {num_enemies} enemies in stage {stage_id}...")
        battle_setup: types.BattleSetup = types.BattleSetup()
        battle_setup["enemy"] = self._get_enemy_lineup(stage_id)
        battle_setup["player"] = self._get_player_lineup(self.MAX_WYNDS_PER_BATTLE, nft_data)

        if not battle_setup["player"]:
            logger.print_warn(f"No players available to battle")
            return False

        RETRY_ATTEMPTS = 6
        did_succeed = False
        difficulty_adjustment = LEVEL_HIERARCHY[stage_id[-2:]]
        for attempt in range(RETRY_ATTEMPTS):
            duration = random.randint(self.min_game_duration, self.max_game_duration)
            result = (
                "win"
                if random.randint(
                    1, RETRY_ATTEMPTS - difficulty_adjustment if self.human_mode else 1
                )
                == 1
                else "lose"
            )
            should_win = result == "win"

            logger.print_normal(f"Getting stamina...")
            needed_stamina = self._get_stamina_for_level(stage_id)
            current_stamina = self._get_stamina()
            logger.print_normal(f"Stamina, Have: {current_stamina} Need: {needed_stamina}")

            logger.print_normal(f"Pinging realtime...")
            self.wynd_w2.ping_realtime()

            did_succeed = False

            if current_stamina < needed_stamina:
                logger.print_warn("Not enough stamina not attempting battle...")
                break

            if self.wynd_w2.battle(stage_id, battle_setup, duration=duration, result=result):
                if result == "win":
                    logger.print_ok(f"We {result.upper()}! \U0001F389")
                else:
                    logger.print_warn(f"We {result.upper()} \U0001F62D")
                did_succeed = True
                self.did_tutorial = True

            if did_succeed:
                if result == "lose" and attempt + 1 < RETRY_ATTEMPTS:
                    logger.print_normal(f"Since we lost, let's retry here shortly...")
                    wait(10.0)
                elif result == "win":
                    self.completed.add(stage_id)
                    levels_completed = set(
                        self.current_stats["pve_game"]["levels_completed"].get(
                            self.config["address"], []
                        )
                    )
                    levels_completed.add(stage_id)
                    self.current_stats["pve_game"]["levels_completed"][
                        self.config["address"]
                    ] = list(levels_completed)
                    self.last_mission = stage_id
                    break
            elif attempt + 1 >= RETRY_ATTEMPTS:
                logger.print_fail(f"Failed to submit battle")
            else:
                logger.print_warn(f"Failed to submit battle, retrying...")
                wait(5.0 * attempt)

        if not did_succeed:
            return False

        if self.num_replays >= self.MAX_REPLAYS_PER_CYCLE:
            self.num_replays = 0
            return False

        return True

    def check_and_claim_if_needed(self, exp: int) -> bool:
        chro_rewards: types.PveRewards = self.wynd_w2.get_chro_rewards()
        unclaimed_chro = chro_rewards.get("claimable", 0)
        logger.print_ok(f"Unclaimed CHRO Rewards: {unclaimed_chro} CHRO")

        if unclaimed_chro <= 0.0:
            logger.print_normal(f"Nothing to claim!")
            return False

        if exp < self._get_level_five_exp():
            logger.print_normal(f"Waiting till level 5 to claim rewards ({unclaimed_chro} CHRO)")
            return False

        logger.print_ok(f"Sending rewards to the contract: {unclaimed_chro} CHRO...")
        ret = self.wynd_w2.claim_chro()

        if not ret:
            logger.print_warn(f"Failed to set rewards. Trying to claim anyways...")
        else:
            logger.print_ok_arrow(f"Success!")

        chro_before = self.chro_w3.get_balance()

        logger.print_ok(f"Claiming rewards! {unclaimed_chro} CHRO")
        tx_hash = self.wynd_w3.claim_rewards()
        tx_receipt = self.wynd_w3.get_transaction_receipt(tx_hash)
        gas = wei_to_token(self.wynd_w3.get_gas_cost_of_transaction_wei(tx_receipt))
        logger.print_bold(f"Paid {gas} AVAX in gas")

        self.stats_logger.lifetime_stats["avax_gas"] += gas

        if tx_receipt.get("status", 0) != 1:
            logger.print_warn(f"Failed to claim CHRO!")
            return False
        else:
            logger.print_ok(f"Successfully claimed CHRO")
            logger.print_normal(f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n")

        chro_after = self.chro_w3.get_balance()

        if chro_after > chro_before:
            delta_chro = chro_after - chro_before
            self.current_stats["chro"] += delta_chro
            logger.print_ok_arrow(f"Adding {delta_chro} CHRO to stats...")

        return True

    def check_and_auth_account(self) -> bool:
        if self.wynd_w2.update_account():
            self.is_deactivated = False
            return self.is_deactivated

        if not self.wynd_w2.authorize_user():
            self.is_deactivated = True
            return self.is_deactivated

        if not self.wynd_w2.update_account():
            self.is_deactivated = True
            return self.is_deactivated

        if not self.wynd_w2.refresh_auth():
            self.is_deactivated = True
            return self.is_deactivated

        self.wynd_w2.ping_realtime()

        self.is_deactivated = False
        return self.is_deactivated

    def _check_and_try_tutorial(self) -> bool:
        logger.print_normal("Attempting tutorial...")
        if not self.wynd_w2.complete_opening():
            return False
        time.sleep(5.0)
        if not self.wynd_w2.complete_novel_before_main1():
            return False
        time.sleep(5.0)
        if not self.wynd_w2.complete_novel_stage1():
            return False

        logger.print_ok_arrow("Completed tutorial!")
        return True

    def play_game(self) -> None:
        if self.is_deactivated:
            logger.print_warn(f"Skipping {self.user} since we have been deactivated!")
            return

        if not self.did_tutorial:
            if not self._check_and_try_tutorial():
                logger.print_fail_arrow(f"Failed to complete tutorial...")

        nft_data: types.PveNfts = self.wynd_w2.get_nft_data()
        if nft_data.get("error_code", "") == "ERR:AUTH:FORBIDDEN_ACCESS":
            self.is_deactivated = True
            logger.print_warn(f"Detected deactivated account!")
            return

        user_data: types.PveUser = self.wynd_w2.get_user_profile()
        chro_rewards: types.PveRewards = self.wynd_w2.get_chro_rewards()
        user_exp = user_data.get("exp", 0)

        self._check_and_do_standard_quest_list(nft_data)

        countdown: types.Countdown = self.wynd_w2.get_countdown()

        if countdown:
            daily_reset_left = get_pretty_seconds(countdown.get("daily_countdown_second", -1))
            logger.print_ok_blue(f"Daily quests reset in {daily_reset_left}")

            weekly_reset_left = get_pretty_seconds(countdown.get("weekly_countdown_second", -1))
            logger.print_ok_blue(f"Weekly quests reset in {weekly_reset_left}")

        logger.print_ok_blue_arrow(f"User exp: {user_exp}")
        logger.print_ok_blue_arrow(f"User stamina: {self._get_stamina()}")

        while self._check_and_play_story(nft_data, countdown):
            wait(random.randint(30, 70 if self.human_mode else 50))
            self.check_and_auth_account()
            logger.print_normal(f"Playing next stage...")

        self._check_and_claim_quest_list()
        self._check_and_level_units(nft_data)

        self.check_and_auth_account()

        self.check_and_claim_if_needed(user_exp)

        if self.is_deactivated:
            logger.print_warn(f"Detected deactivated account!")

        self._send_summary_email()
        self._update_stats(user_exp)
