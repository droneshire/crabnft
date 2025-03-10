import copy
import datetime
import json
import random
import time
import typing as T
from discord import Color
from discord_webhook import DiscordEmbed, DiscordWebhook

from config_wyndblast import COMMISSION_WALLET_ADDRESS
from utils import discord
from utils import logger
from utils.config_types import UserConfig
from utils.email import Email, send_email
from utils.price import wei_to_token
from wyndblast.assets import WYNDBLAST_ASSETS
from wyndblast.database.models.daily_activities import (
    DailyActivities,
    DailyActivitiesSchema,
    ElementalStones,
    ElementalStonesSchema,
    WinLoss,
    WinLossSchema,
)
from wyndblast.game_stats import NULL_GAME_STATS
from wyndblast.game_stats import WyndblastLifetimeGameStats
from wyndblast.types import (
    Action,
    AccountOverview,
    ActivityResult,
    ActivitySelection,
    DailyActivity,
    DailyActivitySelection,
    DayLog,
    Rewards,
    Stage,
    ProductMetadata,
    WyndNft,
    WyndStatus,
)
from wyndblast.daily_activities_web2_client import (
    DailyActivitiesWyndblastWeb2Client,
)
from wyndblast.wyndblast_web3_client import WyndblastGameWeb3Client


class DailyActivitiesGame:
    MAX_NUM_ROUNDS = 3
    MIN_CLAIM_CHRO = 400
    DAYS_BETWEEN_CLAIM = 1

    def __init__(
        self,
        user: str,
        config: UserConfig,
        email_accounts: T.List[Email],
        wynd_w2: DailyActivitiesWyndblastWeb2Client,
        wynd_w3: WyndblastGameWeb3Client,
        stats: WyndblastLifetimeGameStats,
        allow_deactivate: bool,
    ):
        self.user = user
        self.config = config
        self.email_accounts = email_accounts
        self.wynd_w2 = wynd_w2
        self.wynd_w3 = wynd_w3
        self.stats = stats
        self.is_deactivated = False
        self.allow_deactivate = allow_deactivate

        self.current_stats = copy.deepcopy(NULL_GAME_STATS)

        logger.print_ok_blue(f"\nStarting for user {user}...")

    def check_and_claim_if_needed(self) -> bool:
        rewards_unclaimed: Rewards = self.wynd_w2.get_unclaimed_balances()

        unclaimed_chro = int(rewards_unclaimed.get("chro", 0))
        if unclaimed_chro < self.MIN_CLAIM_CHRO:
            logger.print_normal(
                f"Not enough CHRO to claim rewards ({unclaimed_chro} CHRO)"
            )
            return False

        date: datetime.datetime = self.wynd_w2.get_last_claim()
        if date is not None:
            time_delta: datetime.date = (
                datetime.datetime.now().date() - date.date()
            )

            if time_delta.days < self.DAYS_BETWEEN_CLAIM:
                return False

        logger.print_ok(f"Claiming rewards! {unclaimed_chro} CHRO")
        tx_hash = self.wynd_w3.claim_rewards()
        tx_receipt = self.wynd_w3.get_transaction_receipt(tx_hash)
        gas = wei_to_token(
            self.wynd_w3.get_gas_cost_of_transaction_wei(tx_receipt)
        )
        logger.print_bold(f"Paid {gas} AVAX in gas")

        with self.stats.user() as user:
            user.gas_avax += gas

        if tx_receipt.get("status", 0) != 1:
            logger.print_fail(f"Failed to claim CHRO!")
        else:
            logger.print_ok(f"Successfully claimed CHRO")
            logger.print_normal(
                f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n"
            )

        return True

    def check_and_auth_account(self) -> bool:
        if not self.allow_deactivate:
            self.is_deactivated = False
            return False

        if self.wynd_w2.update_account():
            self.is_deactivated = False
            return self.is_deactivated

        if not self.wynd_w2.authorize_user():
            self.is_deactivated = True
            return self.is_deactivated

        if not self.wynd_w2.update_account():
            self.is_deactivated = True
            return self.is_deactivated

        self.is_deactivated = False
        return self.is_deactivated

    def run_activity(self) -> None:
        account_overview = self.wynd_w2.get_account_overview()

        if not account_overview:
            self.check_and_auth_account()
            return

        try:
            total = account_overview["count_nfts"]["all"]

            available_wynds = account_overview["count_nfts"]["game"][
                "daily_activity"
            ]["idle"]
        except:
            logger.print_fail(f"Failed to process account overview")
            return

        if available_wynds <= 0:
            logger.print_warn(
                f"0/{total} wynds available for daily activities..."
            )
            return

        logger.print_bold(
            f"Found {available_wynds}/{total} Wynds available for daily activities\n\n"
        )

        wynds: T.List[WyndStatus] = []
        ITEMS_PER_PAGE = 5
        total_pages = int((total + ITEMS_PER_PAGE) / ITEMS_PER_PAGE)
        logger.print_normal(f"Searching through {total_pages} pages of NFTs...")
        for page in range(1, total_pages + 2):
            params = {"page": page, "limit": ITEMS_PER_PAGE}
            new_wynds = self.wynd_w2.get_all_wynds_activity(params=params)
            if not new_wynds:
                logger.print_warn(f"Didn't find any new winds on page {page}")
            wynds.extend(new_wynds)

        if not wynds:
            self.check_and_auth_account()
            return

        rounds_completed = 0
        for wynd in wynds:
            wynd_id = int(wynd["product_id"].split(":")[1])
            wynd_faction = wynd["product_metadata"]["faction"]
            wynd_element = wynd["product_metadata"]["element"]
            wynd_class = wynd["product_metadata"]["class"]

            most_recent_activity: DayLog = wynd["days"][-1]

            rounds_remaining = self._get_rounds_remaining(
                day_log=most_recent_activity
            )

            if most_recent_activity["round_completed"] or rounds_remaining == 0:
                logger.print_normal(
                    f"Skipping {wynd_id} for daily activities b/c already completed..."
                )
                continue

            logger.print_normal(
                f"\nWynd[{wynd_id}]: {rounds_remaining} rounds left to play..."
            )

            logger.print_bold(f"Wynd[{wynd_id}]: starting daily activities")
            stats_fmt = logger.format_ok_blue(
                f"Faction: {wynd_faction.upper()}\t"
            )
            stats_fmt += logger.format_normal(
                f"Class: {wynd_class} Element: {wynd_element}\n"
            )
            logger.print_normal("{}".format(stats_fmt))

            activities_completed = most_recent_activity.get("activities")

            rounds_completed += 1

            if len(activities_completed) > 0:
                stage = activities_completed[-1]["stage"]["level"]
            else:
                stage = 0

            for attempt in range(rounds_remaining, 0, -1):
                stage += 1

                if not self._play_round(
                    wynd_id,
                    current_stage=stage,
                    wynd_info=wynd["product_metadata"],
                ):
                    logger.print_warn(
                        f"We lost, unable to proceed to next round"
                    )
                    break

        if rounds_completed <= 0:
            return

        self.check_and_auth_account()

        self.check_and_claim_if_needed()

        self._send_summary_email(len(wynds))
        self._update_stats()

    def _send_close_game_discord_activity_update(self) -> None:
        webhook = DiscordWebhook(
            url=discord.DISCORD_WEBHOOK_URL["WYNDBLAST_ACTIVITY"],
            rate_limit_retry=True,
        )
        embed = DiscordEmbed(
            title=f"DAILY ACTIVITIES",
            description=f"Finished for {self.config['discord_handle'].upper()}\n",
            color=Color.red().value,
        )
        totals = {
            "wins": 0,
            "losses": 0,
        }
        for stage in range(1, 4):
            with self.stats.winloss(stage) as winloss:
                totals["wins"] += winloss.wins
                totals["losses"] += winloss.losses

        total_games = float(totals["losses"] + totals["wins"])
        if total_games > 0:
            win_percent = totals["wins"] / total_games * 100.0
        else:
            win_percent = 0.0

        embed.add_embed_field(
            name=f"Win %", value=f"{win_percent:.2f}%", inline=False
        )
        embed.add_embed_field(
            name=f"CHRO",
            value=f"{int(self.current_stats['chro'])}",
            inline=True,
        )
        embed.add_embed_field(
            name=f"WAMS",
            value=f"{int(self.current_stats['wams'])}",
            inline=True,
        )
        embed.add_embed_field(
            name=f"ESTONES",
            value=f"{int(self.current_stats['elemental_stones']['elemental_stones_qty'])}",
            inline=True,
        )

        try:
            wynds: T.List[WyndNft] = self.wynd_w2.get_wynd_status()
            embed.set_image(url=wynds[random.randrange(len(wynds))]["image"])
        except:
            embed.set_thumbnail(
                url=WYNDBLAST_ASSETS["wynd"], height=100, width=100
            )

        webhook.add_embed(embed)
        webhook.execute()

    def _update_stats(self) -> None:
        chro_rewards = self.current_stats["chro"]

        for address, commission_percent in self.config[
            "commission_percent_per_mine"
        ].items():
            commission_chro = chro_rewards * (commission_percent / 100.0)

            with self.stats.commission(address) as commission:
                commission.amount += commission_chro

            logger.print_ok(
                f"Added {commission_chro} CHRO for {address} in commission ({commission_percent}%)!"
            )

        self._send_close_game_discord_activity_update()

        self.current_stats = copy.deepcopy(NULL_GAME_STATS)

        with self.stats.daily() as da:
            stats_json = DailyActivitiesSchema().dump(da)
            logger.print_ok_blue(
                f"Lifetime Stats for {self.user.upper()}\n"
                f"{json.dumps(stats_json, indent=4)}"
            )

    def _send_summary_email(self, active_nfts: int) -> None:
        content = f"Activity Stats for {self.user.upper()}:\n"
        content += f"Active NFTs: {active_nfts}\n"
        for stage in range(1, 4):
            stage_str = f"Stage {stage}" if stage != 3 else "All Stages"
            key = f"stage_{stage}"
            content += (
                f"Completed {stage_str}: {self.current_stats[key]['wins']}\n\n"
            )
        content += f"REWARDS:"
        content += f"CHRO: {self.current_stats['chro']}\n"
        content += f"WAMS: {self.current_stats['wams']}\n"
        if isinstance(self.current_stats["elemental_stones"], dict):
            content += f"Elemental Stones:\n"
            for stone, count in self.current_stats["elemental_stones"].items():
                if stone == "elemental_stones_qty":
                    continue
                content += f"{stone}: {count}\n"

        logger.print_bold(content)

        send_email(
            self.email_accounts,
            self.config["email"],
            "Wyndblast Daily Activities",
            content,
        )

    def _play_round(
        self,
        wynd_id: int,
        current_stage: int,
        wynd_info: ProductMetadata,
        verbose: bool = False,
    ) -> bool:
        options: DailyActivitySelection = self.wynd_w2.get_activity_selection(
            wynd_id
        )

        if not options or not isinstance(options, dict):
            self.check_and_auth_account()
            return False

        if current_stage > 1:
            actions: Action = options["selection_detail"]
        else:
            faction_options: T.List[Action] = options.get(
                "selection_detail", {}
            ).get(wynd_info.get("faction", ""), [])

            if not faction_options:
                return False

            actions: Action = faction_options[0]

        selection: ActivitySelection = self._get_best_action(
            current_stage, actions, wynd_info
        )

        if not selection:
            return False

        selection["product_ids"] = [self.wynd_w2._get_product_id(wynd_id)]

        if verbose:
            logger.print_normal(f"Selecting: {json.dumps(selection, indent=4)}")

        result: ActivityResult = self.wynd_w2.do_activity(selection)

        if not result:
            self.check_and_auth_account()
            return False

        did_succeed = result["stage"]["success"]

        level = int(result["stage"]["level"])
        rewards = result["stage"]["rewards"]

        with self.stats.user() as user:
            self.current_stats["chro"] += rewards["chro"]
            user.chro += rewards["chro"]
            self.current_stats["wams"] += rewards["wams"]
            user.wams += rewards["wams"]
            if rewards["elemental_stones"] is not None:
                with self.stats.daily() as da:
                    self.current_stats["elemental_stones"][
                        rewards["elemental_stones"]
                    ] += 1
                    self.current_stats["elemental_stones"][
                        "elemental_stones_qty"
                    ] += 1
                    previous_value = getattr(
                        da.elemental_stones[0],
                        rewards["elemental_stones"].lower(),
                    )
                    setattr(
                        da.elemental_stones[0],
                        rewards["elemental_stones"].lower(),
                        previous_value + 1,
                    )

        outcome_emoji = "\U0001F389" if did_succeed else "\U0001F915"

        if level < 3:
            logger.print_ok_blue(f"Finished stage {level}")
            logger.print_ok_blue_arrow(
                f"CHRO: {rewards['chro']} WAMS: {rewards['wams']}\nELEMENTAL STONES:\n{rewards['elemental_stones']}"
            )
            if not did_succeed:
                logger.print_ok(f"Finished stage, we lost {outcome_emoji}")
        else:
            logger.print_ok(
                f"Finished round, we {'won!' if did_succeed else 'lost.'} {outcome_emoji}"
            )
            logger.print_ok_arrow(
                f"CHRO: {rewards['chro']} WAMS: {rewards['wams']}\nELEMENTAL STONES:\n {rewards['elemental_stones']}"
            )

        stage_key = f"stage_{level}"
        with self.stats.winloss(level) as winloss:
            if did_succeed:
                self.current_stats[stage_key]["wins"] += 1
                winloss.wins += 1
            else:
                self.current_stats[stage_key]["losses"] += 1
                winloss.losses += 1

        return did_succeed

    def _get_best_action(
        self,
        current_stage: int,
        actions: Action,
        wynd_info: ProductMetadata,
        verbose: bool = False,
    ) -> ActivitySelection:
        best_percent = 0.0
        wynd_class = wynd_info["class"]
        wynd_element = wynd_info["element"]

        selection: ActivitySelection = ActivitySelection(
            faction=wynd_info["faction"],
            stage=current_stage,
        )

        best_score = 0
        if "variations" not in actions:
            logger.print_warn(f"Failed to get variation in actions:\n{actions}")
            return None

        for action, info in actions.get("variations", {}).items():
            score = 0

            success_rate = int(info["success_rate"].strip("%"))

            if success_rate > best_percent:
                score += success_rate

            if wynd_element == info["element_requirement"]:
                score += 10.0

            if wynd_class == info["class_requirement"]:
                score += 10.0

            if score > best_score:
                best_score = score
                selection["class_requirement"] = info["class_requirement"]
                selection["element_requirement"] = info["element_requirement"]
                selection["variation"] = action

            if verbose:
                logger.print_normal(
                    f"Analyzing: {action} has {success_rate}% success rate [score={score}]"
                )

        return selection

    def _get_rounds_remaining(self, day_log: DayLog) -> int:
        attempted_rounds = len(day_log["activities"])
        if attempted_rounds == 0:
            return self.MAX_NUM_ROUNDS

        stage: Stage = day_log["activities"][-1]["stage"]

        # completed all rounds already
        if stage["level"] == self.MAX_NUM_ROUNDS:
            return 0

        # we failed so we can't continue
        if not stage["success"]:
            return 0

        return max(self.MAX_NUM_ROUNDS - attempted_rounds, 0)
