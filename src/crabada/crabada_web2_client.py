import typing as T
import math
import requests
import time

from eth_typing import Address

from crabada.factional_advantage import get_faction_adjusted_battle_point, get_bp_mp_from_team
from crabada.miners_revenge import calc_miners_revenge
from crabada.types import Crab, CrabadaClass, CrabForLending, IdleGame, LendingCategories, Team
from crabada.types import CRABADA_ID_TO_CLASS
from utils import logger
from utils.general import first_or_none, n_or_better_or_none, get_pretty_seconds
from utils.price import wei_to_tus, Tus


class CrabadaWeb2Client:
    """
    Access the HTTP endpoints of the Crabada P2E game.

    All endpoints have a 'raw' parameter that you can set to true
    in order to get the full JSON response. By default it is false,
    which means you only get the data contained in the response (a
    list for list endpoints, a dict for specific endpoints)
    """

    BASE_URL = "https://idle-game-api.crabada.com/public/idle"

    BROWSER_HEADERS = {
        "authority": "idle-game-api.crabada.com",
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "origin": "https://idle.crabada.com",
        "pragma": "no-cache",
        "referer": "https://idle.crabada.com/",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "sec-gpc": "1",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
    }

    # reinforcement stuff
    N_CRAB_PERCENT = 37.0
    REINFORCE_TIME_WINDOW = 60 * (30 - 1)  # 30 minute window + 1 minute buffer

    # game facts
    TIME_PER_MINING_ACTION = 60.0 * 30
    MIN_LOOT_GAME_TIME = 60.0 * 60.0 * 1

    # api request limits (scale with teams/crabs)
    TEAM_AND_MINE_LIMIT = 50
    CRAB_LIMIT = 75

    MAX_BP_NORMAL_CRAB = 237

    def __init__(self) -> None:
        self.requests = requests

    def _get_request(self, url: str, params: T.Dict[str, T.Any] = {}) -> T.Any:
        try:
            return self.requests.request(
                "GET", url, params=params, headers=self.BROWSER_HEADERS, timeout=5.0
            ).json()
        except KeyboardInterrupt:
            raise
        except:
            return {}

    def get_crabs(self, user_address: Address, params: T.Dict[str, T.Any] = {}) -> T.List[Crab]:
        res = self.list_crabs_in_game_raw(user_address, params)
        try:
            return res["result"]["data"] or []
        except KeyboardInterrupt:
            raise
        except:
            return []

    def get_crab_classes(
        self, user_address: Address, params: T.Dict[str, T.Any] = {}
    ) -> T.Dict[int, str]:
        crab_classes = {}
        res = self.list_crabs_in_game_raw(user_address, params)
        try:
            return {
                c.get("crabada_id", -1): c.get("class_name", "UNKNOWN")
                for c in res["result"]["data"]
            }
        except KeyboardInterrupt:
            raise
        except:
            return {}

    def get_team_compositions_and_mp(
        self, user_address: Address, params: T.Dict[str, T.Any] = {}
    ) -> T.Dict[int, T.Tuple[T.List[CrabadaClass], int]]:
        teams = self.list_teams(user_address)
        team_composition = {}
        for team in teams:
            if team is None or team["crabada_id_1"] is None or team["crabada_id_2"] is None or team["crabada_id_3"] is None:
                continue
            comp = []
            for i in range(1, 4):
                if f"crabada_{i}_class" not in team:
                    break
                comp.append(CRABADA_ID_TO_CLASS[team[f"crabada_{i}_class"]])
            _, mp = get_bp_mp_from_team(team)
            if len(comp) == 3:
                team_composition[team["team_id"]] = (comp, mp)

        return team_composition

    def get_mine(self, mine_id: int, params: T.Dict[str, T.Any] = {}) -> IdleGame:
        """Get information from the given mine"""
        res = self.get_mine_raw(mine_id, params)
        if res:
            return res.get("result", None) or {}
        else:
            return {}

    def get_mine_raw(self, mine_id: int, params: T.Dict[str, T.Any] = {}) -> T.Any:
        url = self.BASE_URL + "/mine/" + str(mine_id)
        return self._get_request(url, params)

    def list_mines(self, params: T.Dict[str, T.Any] = {}) -> T.List[IdleGame]:
        """
        Get all mines.

        If you want only the open mines, pass status=open in the params.
        If you want only a certain user's mines, use the user_address param.
        """
        res = self.list_mines_raw(params)
        try:
            return res["result"]["data"] or []
        except KeyboardInterrupt:
            raise
        except:
            return []

    def list_my_available_crabs_for_reinforcement(
        self, user_address: Address, params: T.Dict[str, T.Any] = {}
    ) -> T.List[Crab]:
        res = self.list_crabs_in_game_raw(user_address, params)
        try:
            return [c for c in res["result"]["data"] if c.get("crabada_status", "") == "AVAILABLE"]
        except KeyboardInterrupt:
            raise
        except:
            return []

    def list_can_join_game_raw(
        self, user_address: Address, params: T.Dict[str, T.Any] = {}
    ) -> T.List[Crab]:
        url = self.BASE_URL + "/crabadas/can-join-team"
        actual_params = {
            "user_address": user_address,
            "page": 1,
            "limit": self.CRAB_LIMIT,
        }
        actual_params.update(params)
        return self._get_request(url, actual_params)

    def list_crabs_in_game_raw(
        self, user_address: Address, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.BASE_URL + "/crabadas/in-game"
        actual_params = {
            "limit": self.CRAB_LIMIT,
            "page": 1,
            "user_address": user_address,
            "order": "desc",
        }
        actual_params.update(params)
        return self._get_request(url, actual_params)

    def list_my_mines(
        self, user_address: Address, params: T.Dict[str, T.Any] = {}
    ) -> T.List[IdleGame]:
        """
        Get all mines that belong to the given user address
        """
        params["user_address"] = user_address
        return self.list_mines(params)

    def list_my_open_mines(
        self, user_address: Address, params: T.Dict[str, T.Any] = {}
    ) -> T.List[IdleGame]:
        """
        Get all mines that belong to the given user address
        and that are open
        """
        params["user_address"] = user_address
        params["status"] = "open"
        return self.list_mines(params)

    def list_my_open_loots(
        self, looter_address: Address, params: [str, T.Any] = {}
    ) -> T.List[IdleGame]:
        """
        Get all mines that are being looted by the given looter address
        and that are open
        """
        params.pop("user_address", None)
        params["looter_address"] = looter_address
        params["status"] = "open"
        return self.list_mines(params)

    def list_available_loots(
        self,
        user_address: Address,
        params: T.Dict[str, T.Any] = {},
    ) -> T.List[IdleGame]:
        actual_params = {
            "can_loot": 1,
            "looter_address": user_address,
            "status": "open",
        }
        actual_params.update(params)
        return self.list_mines(params=actual_params)

    def list_mines_raw(self, params: T.Dict[str, T.Any] = {}) -> T.Any:
        url = self.BASE_URL + "/mines"
        actual_params = {
            "limit": self.TEAM_AND_MINE_LIMIT,
            "page": 1,
        }
        actual_params.update(params)
        return self._get_request(url, actual_params)

    def get_team(self) -> None:
        raise Exception("The team route does not exit on the server!")

    def list_teams(self, user_address: Address, params: T.Dict[str, T.Any] = {}) -> T.List[Team]:
        """
        Get all teams of a given user address.

        If you want only the available teams, pass is_team_available=1
        in the params.
        It is currently not possible to list all users' teams, you can
        only see the teams of a specific user.
        """
        res = self.list_teams_raw(user_address, params)
        try:
            return res["result"]["data"] or []
        except KeyboardInterrupt:
            raise
        except:
            return []

    def list_available_teams(
        self, user_address: Address, params: T.Dict[str, T.Any] = {}
    ) -> T.List[Team]:
        """
        Get all available teams of a given user address.
        """
        actual_params = {"is_team_available": 1}
        actual_params.update(params)
        return self.list_teams(user_address, actual_params)

    def list_teams_raw(self, user_address: Address, params: T.Dict[str, T.Any] = {}) -> T.Any:
        url = self.BASE_URL + "/teams"
        actual_params = {"limit": self.TEAM_AND_MINE_LIMIT, "page": 1, "user_address": user_address}
        actual_params.update(params)
        return self._get_request(url, actual_params)

    def list_high_mp_crabs_for_lending(
        self, params: T.Dict[str, T.Any] = {}
    ) -> T.List[CrabForLending]:
        params["limit"] = 100
        params["orderBy"] = "mine_point"
        params["order"] = "desc"
        return self.list_crabs_for_lending(params)

    def list_high_bp_crabs_for_lending(
        self, params: T.Dict[str, T.Any] = {}
    ) -> T.List[CrabForLending]:
        params["limit"] = 100
        params["orderBy"] = "battle_point"
        params["order"] = "desc"
        return self.list_crabs_for_lending(params)

    def list_crabs_for_lending(self, params: T.Dict[str, T.Any] = {}) -> T.List[CrabForLending]:
        """
        Get all crabs available for lending as reinforcements; you can use
        sortBy and sort parameters, default is orderBy": 'price' and
        "order": 'asc'

        IMPORTANT: The price is expressed as the TUS price multiplied by
        10^18 (like with Weis), which means that price=100000000000000000
        (18 zeros) is just 1 TUS
        """
        res = self.list_crabs_for_lending_raw(params)
        try:
            return res["result"]["data"] or []
        except KeyboardInterrupt:
            raise
        except:
            return []

    def get_num_mine_reinforcements(self, mine: IdleGame) -> int:
        mine = self.get_mine(mine.get("game_id", None))
        if mine is None:
            return 0

        process = mine.get("process", [])
        return len([p for p in process if p["action"] == "reinforce-defense"])

    def get_num_loot_reinforcements(self, mine: IdleGame) -> int:
        mine = self.get_mine(mine.get("game_id", None))
        if mine is None:
            return 0

        process = mine.get("process", [])
        if process is None:
            return 0
        return len([p for p in process if p["action"] == "reinforce-attack"])

    def get_cheapest_best_crab_from_list_for_lending(
        self,
        crabs: T.List[CrabForLending],
        max_tus: Tus,
        reinforcement_search_backoff: int,
        lending_category: LendingCategories,
    ) -> CrabForLending:
        """
        From a list of crabs, pick the one with the best characteristic for the
        cheapest price
        """
        affordable_crabs = [c for c in crabs if wei_to_tus(c.get("price", max_tus)) < max_tus]
        sorted_affordable_crabs = sorted(
            affordable_crabs, key=lambda c: (-c[lending_category], c.get("price", max_tus))
        )
        if len(affordable_crabs) < 25:
            nth_crab = len(affordable_crabs) - 1
        else:
            nth_crab = int(math.ceil(self.N_CRAB_PERCENT / 100.0 * len(affordable_crabs)))
            nth_crab += reinforcement_search_backoff
        nth_crab = min(len(affordable_crabs), nth_crab)
        logger.print_ok_blue(f"Crab list: {nth_crab}/{len(affordable_crabs)}")
        return n_or_better_or_none(nth_crab, sorted_affordable_crabs)

    def get_best_high_mp_crab_for_lending(
        self, mine: IdleGame, max_tus: Tus, reinforcement_search_backoff: int
    ) -> T.Optional[CrabForLending]:
        cached_high_mp_crab = None
        for class_id in [
            CrabadaClass.PRIME,
            CrabadaClass.RUINED,
            CrabadaClass.CRABOID,
            CrabadaClass.SUNKEN,
            CrabadaClass.ORGANIC,
        ]:
            params = {
                "class_ids[]": class_id,
            }
            high_mp_crabs = self.list_high_mp_crabs_for_lending(params=params)
            high_mp_crab = self.get_cheapest_best_crab_from_list_for_lending(
                high_mp_crabs, max_tus, reinforcement_search_backoff, "mine_point"
            )

            if high_mp_crab is None:
                continue

            if cached_high_mp_crab is None:
                cached_high_mp_crab = high_mp_crab

            miners_revenge_before = min(
                calc_miners_revenge(mine, is_looting=False, verbose=False), 40.0
            )
            miners_revenge_after = min(
                calc_miners_revenge(
                    mine, is_looting=False, additional_crabs=[high_mp_crab], verbose=False
                ),
                40.0,
            )

            logger.print_normal(
                f"MR before: {miners_revenge_before:.2f}% MR after: {miners_revenge_after:.2f}%"
            )

            if miners_revenge_after < miners_revenge_before:
                continue

            return high_mp_crab

        return cached_high_mp_crab

    def get_best_high_bp_crab_for_lending(
        self, mine: IdleGame, max_tus: Tus, reinforcement_search_backoff: int
    ) -> T.Optional[CrabForLending]:
        cached_high_bp_crab = None
        for class_id in [
            CrabadaClass.BULK,
            CrabadaClass.GEM,
            CrabadaClass.SURGE,
        ]:
            params = {
                "class_ids[]": class_id,
            }
            high_bp_crabs = self.list_high_bp_crabs_for_lending(params=params)
            high_bp_crab = self.get_cheapest_best_crab_from_list_for_lending(
                high_bp_crabs, max_tus, reinforcement_search_backoff, "battle_point"
            )

            if high_bp_crab is None:
                continue

            if cached_high_bp_crab is None:
                cached_high_bp_crab = high_bp_crab

            miners_revenge_before = min(
                calc_miners_revenge(mine, is_looting=True, verbose=False), 40.0
            )
            miners_revenge_after = min(
                calc_miners_revenge(
                    mine, is_looting=True, additional_crabs=[high_bp_crab], verbose=False
                ),
                40.0,
            )
            logger.print_normal(
                f"MR before: {miners_revenge_before:.2f}% MR after: {miners_revenge_after:.2f}%"
            )

            if miners_revenge_after > miners_revenge_before:
                continue

        return cached_high_bp_crab

    def get_my_best_mp_crab_for_lending(self, user_address: Address, reinforcement_list: T.List[int],) -> T.Optional[CrabForLending]:
        return self.get_my_best_crab_for_lending(user_address, reinforcement_list, params={"orderBy": "mine_point"})

    def get_my_best_bp_crab_for_lending(self, user_address: Address, reinforcement_list: T.List[int],) -> T.Optional[CrabForLending]:
        return self.get_my_best_crab_for_lending(user_address, reinforcement_list, params={"orderBy": "battle_point"})

    def get_my_best_crab_for_lending(
        self,
        user_address: Address,
        reinforcement_list: T.List[int],
        params: T.Dict[str, T.Any] = {}
    ) -> T.Optional[CrabForLending]:
        my_crabs = self.list_my_available_crabs_for_reinforcement(user_address, params)
        if not my_crabs:
            return None

        my_crabs = [c for c in my_crabs if c in reinforcement_list]

        logger.print_normal(f"Found {len(my_crabs)} of own crabs that can reinforce")
        point_type = params.get("orderBy", "mine_point")

        sorted_crabs = sorted(my_crabs, key=lambda c: c[point_type])
        best_crab = sorted_crabs[0]
        best_crab["price"] = 0
        return best_crab

    def get_reinforcement_crabs(self, mine: IdleGame) -> T.List[int]:
        return [m["crabada_id"] for m in mine.get("defense_team_info", [])][3:]

    def list_crabs_for_lending_raw(self, params: T.Dict[str, T.Any] = {}) -> T.Any:
        url = self.BASE_URL + "/crabadas/lending"
        actual_params = {
            "limit": self.CRAB_LIMIT,
            "page": 1,
            "orderBy": "price",
            "order": "asc",
        }
        actual_params.update(params)
        return self._get_request(url, actual_params)

    def _get_battle_points(self, mine: IdleGame) -> T.Tuple[int, int]:
        defense_battle_point = get_faction_adjusted_battle_point(
            mine, is_looting=False, verbose=False
        )
        attack_battle_point = get_faction_adjusted_battle_point(
            mine, is_looting=True, verbose=False
        )

        return (defense_battle_point, attack_battle_point)

    def _can_loot_reinforcement_win(self, mine: IdleGame) -> bool:
        defense_battle_point, attack_battle_point = self._get_battle_points(mine)
        return attack_battle_point + self.MAX_BP_NORMAL_CRAB > defense_battle_point

    def loot_is_winning(self, mine: IdleGame) -> bool:
        """
        Determines if attack looter has won the battle
        """
        try:
            if mine.get("winner_team_id", -1) == mine["attack_team_id"]:
                return True
        except KeyboardInterrupt:
            raise
        except:
            return False
        defense_battle_point, attack_battle_point = self._get_battle_points(mine)
        return attack_battle_point > defense_battle_point

    def mine_is_winning(self, mine: IdleGame) -> bool:
        """
        Determines if defense miner has won the battle
        """
        try:
            if mine.get("winner_team_id", -1) == mine["team_id"]:
                return True
        except KeyboardInterrupt:
            raise
        except:
            return False
        defense_battle_point, attack_battle_point = self._get_battle_points(mine)

        if defense_battle_point is None:
            return False

        if attack_battle_point is None:
            return True

        return defense_battle_point >= attack_battle_point

    def mine_has_been_attacked(self, mine: IdleGame) -> bool:
        """
        Return True if, in the given game, the miner (the defense) has
        been attacked
        """
        if not mine:
            return False

        return mine.get("attack_team_id", None) is not None

    def mine_needs_reinforcement(self, mine: IdleGame) -> bool:
        """
        Return True if, in the given game, the miner (the defense) needs
        to reinforce the mine from an attacker
        """
        if not mine:
            return False

        if not self.mine_is_open(mine):
            return False

        if self.mine_is_finished(mine):
            return False

        if self.mine_is_settled(mine):
            return False

        if not self.mine_has_been_attacked(mine):
            return False

        process = mine["process"]
        actions = [p["action"] for p in process]
        if actions[-1] not in ["attack", "reinforce-attack"]:
            return False

        if actions.count("reinforce-defense") >= 2:
            return False

        if self.mine_is_winning(mine):
            return False

        attack_start_time = process[-1]["transaction_time"]
        return time.time() - attack_start_time < self.REINFORCE_TIME_WINDOW

    def loot_needs_reinforcement(self, mine: IdleGame) -> bool:
        """
        Return True if, in the given game, the looter (the offense) needs
        to attack the mine of a miner
        """
        if not mine:
            return False

        if not self.mine_is_open(mine):
            return False

        if self.mine_is_finished(mine):
            return False

        if self.mine_is_settled(mine):
            return False

        process = mine["process"]
        actions = [p["action"] for p in process]
        if actions[-1] not in ["reinforce-defense"]:
            return False

        num_reinforcements = len([a for a in actions if "reinforce-attack" in a])
        if num_reinforcements >= 2:
            return False

        if self.loot_is_winning(mine):
            return False

        # make sure we don't reinforce to a legendary when we can't win
        if not self._can_loot_reinforcement_win(mine):
            logger.print_warn(f"Not reinforcing mine {mine['game_id']} due to LEGENDARY reinforcement")
            return False

        defense_start_time = process[-1]["transaction_time"]
        return time.time() - defense_start_time < self.REINFORCE_TIME_WINDOW

    def mine_is_open(self, mine: IdleGame) -> bool:
        """
        Return True if the given game is open
        """
        if not mine:
            return False

        return mine.get("status", "") == "open"

    def mine_is_settled(self, mine: IdleGame) -> bool:
        """
        Return True if the given game is settled
        """
        if not mine:
            return False

        return self.get_remaining_time(mine) < 7000 or mine.get("winner_team_id", None) is not None

    def mine_is_finished(self, mine: IdleGame) -> bool:
        """
        Return true if the given game is past its end_time
        """
        return self.get_remaining_time(mine) <= 0

    def loot_past_settle_time(self, mine: IdleGame) -> bool:
        return self.get_remaining_loot_time(mine) < 0

    def loot_is_able_to_be_settled(self, mine: IdleGame) -> bool:
        """
        Return true if the given loot is able to be settled
        """
        if not self.loot_past_settle_time(mine):
            return False

        if self.loot_needs_reinforcement(mine):
            return False

        actions = [p["action"] for p in mine["process"]]

        if actions.count("reinforce-attack") >= 2:
            return True

        if actions[-1] in ["attack", "reinforce-attack"]:
            margin = 60.0 * 3
            is_past_action_time = (
                self.get_time_since_last_action(mine) > self.TIME_PER_MINING_ACTION + margin
            )
            return is_past_action_time

        return True

    def mine_is_closed(self, mine: IdleGame) -> bool:
        """
        Return true if the given game is closed (meaning the
        game has been settled and the reward has been claimed)
        """
        return mine.get("status", "") == "close"

    def get_remaining_time(self, game: IdleGame) -> int:
        """
        Seconds to the end of the given game
        """
        now = time.time()
        return int(game.get("end_time", now) - now)

    def get_total_mine_time(self, game: IdleGame) -> int:
        """
        Seconds total mine start to end
        """
        return int(game.get("end_time", 0) - game.get("start_time", 0))

    def get_total_mine_time_formatted(self, game: IdleGame) -> int:
        return get_pretty_seconds(self.get_total_mine_time(game))

    def get_remaining_loot_time(self, game: IdleGame) -> int:
        """
        Seconds to the end of the given loot before can settle
        """
        now = time.time()

        start_time = game.get("start_time", now)
        if game is None or game.get("process") is None:
            return now + self.MIN_LOOT_GAME_TIME * 1.1

        for p in game.get("process", []):
            if p["action"] == "attack":
                start_time = p["transaction_time"]

        end_time = start_time + self.MIN_LOOT_GAME_TIME
        return int(end_time - now)

    def get_remaining_loot_time_formatted(self, game: IdleGame) -> str:
        return get_pretty_seconds(self.get_remaining_loot_time(game))

    def get_time_since_last_action(self, game: IdleGame) -> int:
        """
        Seconds since last game action
        """
        now = time.time()
        transaction_time = game["process"][-1]["transaction_time"]
        return int(now - transaction_time)

    def get_time_since_last_action_formatted(self, game: IdleGame) -> str:
        """
        Hours, minutes and seconds to the end of the current action
        """
        return get_pretty_seconds(self.get_time_since_last_action(game))

    def get_remaining_time_for_action(self, game: IdleGame) -> int:
        now = time.time()
        last_transaction_time = game["process"][-1]["transaction_time"]
        return int(last_transaction_time + self.TIME_PER_MINING_ACTION - now)

    def get_remaining_time_for_action_formatted(self, game: IdleGame) -> str:
        """
        Hours, minutes and seconds to the end of the current action
        """
        return get_pretty_seconds(self.get_remaining_time_for_action(game))

    def get_remaining_time_formatted(self, game: IdleGame) -> str:
        """
        Hours, minutes and seconds to the end of the given game
        """
        return get_pretty_seconds(self.get_remaining_time(game))

    def get_next_mine_to_finish(self, games: T.List[IdleGame]) -> IdleGame:
        """Given a list of games, return the mine that is open and
        next to finish; returns None if there are no unfinished games
        (finished=past the 4th our, regardless of whether the reward
        has been claimed)

        If a game is already finished, it won't be considered"""
        unfinished_games = [g for g in games if not mine_is_finished(g)]
        return first_or_none(sorted(unfinished_games, key=lambda g: g.get("end_time", 10e20)))

    def get_last_mine_start_time(self, user_address: Address) -> int:
        last_mine_start = 0
        for mine in self.list_my_open_mines(user_address):
            last_mine_start = max(last_mine_start, mine.get("start_time", 0))
        return last_mine_start
