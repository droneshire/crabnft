import copy
import json
import typing as T

from utils import logger
from utils.config_types import UserConfig
from utils.email import Email, send_email
from wyndblast.game_stats import NULL_GAME_STATS
from wyndblast.types import (
    Action,
    AccountOverview,
    ActivityResult,
    ActivitySelection,
    DailyActivity,
    DailyActivitySelection,
    DayLog,
    Stage,
    ProductMetadata,
    WyndStatus,
)
from wyndblast.wyndblast_web2_client import WyndblastWeb2Client


class DailyActivitiesGame:
    MAX_NUM_ROUNDS = 3

    def __init__(
        self,
        user: str,
        config: UserConfig,
        email_accounts: T.List[Email],
        wynd_w2: WyndblastWeb2Client,
    ):
        self.user = user
        self.config_mgr = config
        self.email_accounts = email_accounts
        self.wynd_w2 = wynd_w2

        self.current_stats = copy.deepcopy(NULL_GAME_STATS)

        self.lifetime_stats = copy.deepcopy(NULL_GAME_STATS)

        logger.print_ok_blue(f"\nStarting for user {user}...")

    def run_activity(self) -> None:
        account_overview = self.wynd_w2.get_account_overview()

        try:
            total = account_overview["count_nfts"]["all"]

            available_wynds = account_overview["count_nfts"]["game"]["daily_activity"]["idle"]
        except:
            logger.print_fail(f"Failed to process account overview")
            return

        if available_wynds <= 0:
            logger.print_warn(f"No wynds available for daily activities...")
            return

        logger.print_bold(f"Found {available_wynds} Wynds available for daily activities\n\n")

        wynds: T.List[WyndStatus] = self.wynd_w2.get_all_wynds_activity()

        for wynd in wynds:
            wynd_id = int(wynd["product_id"].split(":")[1])
            wynd_faction = wynd["product_metadata"]["faction"]
            wynd_element = wynd["product_metadata"]["element"]
            wynd_class = wynd["product_metadata"]["class"]

            most_recent_activity: DayLog = wynd["days"][-1]
            if most_recent_activity["round_completed"]:
                logger.print_normal(
                    f"Skipping {wynd_id} for daily activities b/c already completed..."
                )
                continue

            logger.print_bold(f"Wynd[{wynd_id}] starting daily activities")
            stats_fmt = logger.format_ok_blue(f"Faction: {wynd_faction.upper()}\t")
            stats_fmt += logger.format_normal(f"Class: {wynd_class} Element: {wynd_element}\n")
            logger.print_normal("{}".format(stats_fmt))

            rounds_remaining = self._get_rounds_remaining(day_log=most_recent_activity)

            logger.print_normal(f"{rounds_remaining} rounds left to play...")

            if rounds_remaining == 0:
                continue

            activities_completed = most_recent_activity.get("activities")

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
                    logger.print_warn(f"We lost, unable to proceed to next round")
                    break

        self._send_summary_email()
        self._update_stats()

    def _update_stats(self) -> None:
        for k, v in self.current_stats.items():
            if isinstance(v, list):
                self.lifetime_stats[k].extend(v)
            else:
                self.lifetime_stats[k] += v

        self.current_stats = copy.deepcopy(NULL_GAME_STATS)

    def _send_summary_email(self) -> None:
        content = f"Activity Stats for {self.user.upper()}:\n"
        content += f"Wins: {self.current_stats['wins']}\n"
        content += f"Losses: {self.current_stats['losses']}\n"
        content += f"CHRO: {self.current_stats['chro']}\n"
        content += f"WAMS: {self.current_stats['wams']}\n"
        content += f"Stones: {' '.join(self.current_stats['elemental_stones'])}\n"

        logger.print_bold(content)

        send_email(
            self.email_accounts, self.config_mgr["email"], "Wyndblast Daily Activities", content
        )

    def _play_round(self, wynd_id: int, current_stage: int, wynd_info: ProductMetadata) -> bool:
        options: DailyActivitySelection = self.wynd_w2.get_activity_selection(wynd_id)
        if current_stage > 1:
            actions: Action = options["selection_detail"]
        else:
            faction_options = options["selection_detail"][wynd_info["faction"]]
            actions: Action = faction_options[0]

        selection: ActivitySelection = self._get_best_action(current_stage, actions, wynd_info)

        selection["product_ids"] = [self.wynd_w2._get_product_id(wynd_id)]

        logger.print_normal(f"Selecting: {json.dumps(selection, indent=4)}")

        result: ActivityResult = self.wynd_w2.do_activity(selection)

        did_succeed = result["stage"]["success"]

        level = result["stage"]["level"]
        rewards = result["stage"]["rewards"]

        self.current_stats["chro"] += rewards["chro"]
        self.current_stats["wams"] += rewards["wams"]
        if rewards["elemental_stones"] is not None:
            self.current_stats["elemental_stones"].append(rewards["elemental_stones"])

        outcome_emoji = "\U0001F389" if did_succeed else "\U0001F915"

        if level < 3:
            logger.print_ok_blue(f"Finished round {level}")
            logger.print_ok_blue_arrow(
                f"CHRO: {rewards['chro']} WAMS: {rewards['wams']} ELEMENTAL STONES: {rewards['elemental_stones']}"
            )
            if not did_succeed:
                logger.print_ok(f"Finished round, we lost {outcome_emoji}")
        else:
            logger.print_ok(
                f"Finished round, we {'won!' if did_succeed else 'lost.'} {outcome_emoji}"
            )
            logger.print_ok_arrow(
                f"CHRO: {rewards['chro']} WAMS: {rewards['wams']} ELEMENTAL STONES: {rewards['elemental_stones']}"
            )
            if did_succeed:
                self.current_stats["wins"] += 1
            else:
                self.current_stats["losses"] += 1

        return did_succeed

    def _get_best_action(
        self, current_stage: int, actions: Action, wynd_info: ProductMetadata
    ) -> ActivitySelection:
        best_percent = 0.0
        wynd_class = wynd_info["class"]
        wynd_element = wynd_info["element"]

        selection: ActivitySelection = ActivitySelection(
            faction=wynd_info["faction"],
            stage=current_stage,
        )

        best_score = 0
        for action, info in actions["variations"].items():
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
