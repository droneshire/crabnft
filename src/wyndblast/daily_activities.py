import json
import typing as T

from utils import logger
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

    def __init__(self, wynd_w2: WyndblastWeb2Client):
        self.wynd_w2 = wynd_w2
        self.stats = stats = {
            "wins": 0,
            "losses": 0,
            "win_percent": 0.0,
            "chro": 0.0,
            "wams": 0.0,
            "elemental_stones": 0.0,
        }

    def run_activity(self) -> None:
        account_overview = self.wynd_w2.get_account_overview()
        total = account_overview["count_nfts"]["all"]

        available_wynds = account_overview["count_nfts"]["game"]["daily_activity"]["idle"]

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
                    logger.print_warn(f"Unable to proceed to next round")
                    self.stats["losses"] += 1
                    break
                else:
                    self.stats["wins"] += 1

        logger.print_bold(f"Activity Stats:\n")
        logger.print_ok_blue(f"Wins: {self.stats['wins']}")
        logger.print_ok_blue(f"Losses: {self.stats['losses']}")
        logger.print_ok_blue(f"CHRO: {self.stats['chro']}")
        logger.print_ok_blue(f"WAMS: {self.stats['wams']}")
        logger.print_ok_blue(f"Stones: {self.stats['elemental_stones']}")

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

        self.stats["chro"] += rewards["chro"]
        self.stats["wams"] += rewards["wams"]
        self.stats["elemental_stones"] += (
            rewards["elemental_stones"] if rewards["elemental_stones"] is not None else 0
        )

        if level < 3:
            logger.print_ok_blue(f"Finished round {level}")
            logger.print_ok_blue_arrow(
                f"CHRO: {rewards['chro']} WAMS: {rewards['wams']} ELEMENTAL STONES: {rewards['elemental_stones']}"
            )
            return did_succeed

        rewards = result["stage"]["rewards"]
        outcome_emoji = "\U0001F389" if did_succeed else "\U0001F915"
        logger.print_ok(f"Finished round, we {'won!' if did_succeed else 'lost.'} {outcome_emoji}")
        logger.print_ok_arrow(
            f"CHRO: {rewards['chro']} WAMS: {rewards['wams']} ELEMENTAL STONES: {rewards['elemental_stones']}"
        )
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
