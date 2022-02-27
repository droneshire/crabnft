from typing import Any, List, Tuple

import requests
from eth_typing import Address

from utils.general import firstOrNone, secondOrNone, getPrettySeconds
from crabada.types import CrabForLending, IdleGame, Team


class CrabadaWeb2Client:
    """
    Access the HTTP endpoints of the Crabada P2E game.

    All endpoints have a 'raw' parameter that you can set to true
    in order to get the full JSON response. By default it is false,
    which means you only get the data contained in the response (a
    list for list endpoints, a dict for specific endpoints)
    """

    BASE_URL = 'https://idle-api.crabada.com/public/idle'

    def getMine(self, mineId: int, params: dict[str, Any] = {}) -> IdleGame:
        """Get information from the given mine"""
        res = self.getMine_Raw(mineId, params)
        return res['result']

    def getMine_Raw(self, mineId: int, params: dict[str, Any] = {}) -> Any:
        url = self.BASE_URL + '/mine/' + str(mineId)
        return requests.request("GET", url, params=params).json()

    def listMines(self, params: dict[str, Any] = {}) -> List[IdleGame]:
        """
        Get all mines.

        If you want only the open mines, pass status=open in the params.
        If you want only a certain user's mines, use the user_address param.
        """
        res = self.listMines_Raw(params)
        try:
            return res['result']['data'] or []
        except:
            return []

    def listMyOpenMines(self, userAddress: Address, params: dict[str, Any] = {}) -> List[IdleGame]:
        """
        Get all mines that belong to the given user address
        and that are open
        """
        params['user_address'] = userAddress
        params['status'] = 'open'
        return self.listMines(params)

    def listMyOpenLoots(self, looterAddress: Address, params: dict[str, Any] = {}) -> List[IdleGame]:
        """
        Get all mines that are being looted by the given looter address
        and that are open
        """
        params.pop('user_address', None)
        params['looter_address'] = looterAddress
        params['status'] = 'open'
        return self.listMines(params)

    def listMines_Raw(self, params: dict[str, Any] = {}) -> Any:
        url = self.BASE_URL + '/mines'
        defaultParams = {
            "limit": 5,
            "page": 1,
        }
        actualParams = defaultParams | params
        return requests.request("GET", url, params=actualParams).json()

    def getTeam(self) -> None:
        raise Exception("The team route does not exit on the server!")

    def listTeams(self, userAddress: Address, params: dict[str, Any] = {}) -> List[Team]:
        """
        Get all teams of a given user address.

        If you want only the available teams, pass is_team_available=1
        in the params.
        It is currently not possible to list all users' teams, you can
        only see the teams of a specific user.
        """
        res = self.listTeams_Raw(userAddress, params)
        try:
            return res['result']['data'] or []
        except:
            return []

    def listAvailableTeams(self, userAddress: Address, params: dict[str, Any] = {}) -> List[Team]:
        """
        Get all available teams of a given user address.
        """
        actualParams = params | {'is_team_available': 1}
        return self.listTeams(userAddress, actualParams)

    def listTeams_Raw(self, userAddress: Address, params: dict[str, Any] = {}) -> Any:
        url = self.BASE_URL + '/teams'
        defaultParams = {
            "limit": 5,
            "page": 1,
        }
        actualParams = defaultParams | params
        actualParams['user_address'] = userAddress
        return requests.request("GET", url, params=actualParams).json()

    def listCrabsForLending(self, params: dict[str, Any] = {}) -> List[CrabForLending]:
        """
        Get all crabs available for lending as reinforcements; you can use
        sortBy and sort parameters, default is orderBy": 'price' and
        "order": 'asc'

        IMPORTANT: The price is expressed as the TUS price multiplied by
        10^18 (like with Weis), which means that price=100000000000000000
        (18 zeros) is just 1 TUS
        """
        res = self.listCrabsForLending_Raw(params)
        try:
            return res['result']['data'] or []
        except:
            return []

    def getCheapestCrabForLending(self, params: dict[str, Any] = {}) -> CrabForLending:
        """
        Return the cheapest crab on the market available for lending,
        or None if no crab is found
        """
        params["limit"] = 1
        params["orderBy"] = 'price'
        params["order"] = 'asc'
        return firstOrNone(self.listCrabsForLending(params))

    def getSecondCheapestCrabForLending(self, params: dict[str, Any] = {}) -> CrabForLending:
        """
        Return the second cheapest crab on the market available for lending,
        or None if no crab is found
        """
        params["limit"] = 2
        params["orderBy"] = 'price'
        params["order"] = 'asc'
        return secondOrNone(self.listCrabsForLending(params))

    def listCrabsForLending_Raw(self, params: dict[str, Any] = {}) -> Any:
        url = self.BASE_URL + '/crabadas/lending'
        defaultParams = {
            "limit": 10,
            "page": 1,
            "orderBy": 'price',
            "order": 'asc',
        }
        actualParams = defaultParams | params
        return requests.request("GET", url, params=actualParams).json() # type: ignore

    @staticmethod()
    def mineHasBeenAttacked(mine: IdleGame) -> bool:
        """
        Return True if, in the given game, the miner (the defense) has
        been attacked
        """
        return mine['attack_team_id'] is not None

    @staticmethod()
    def mineIsOpen(mine: IdleGame) -> bool:
        """
        Return True if the given game is open
        """
        return mine['status'] == 'open'

    @staticmethod()
    def mineIsSettled(mine: IdleGame) -> bool:
        """
        Return True if the given game is settled
        """
        # TODO: Update to account for the situation where the looting team has less
        # BP than the mining team since the beginning, in which case you get a weird
        # situation where the mine['winner_team_id'] is None. Maybe use process?
        # Example:
        # [{'game_id': 787426, 'start_time': 1643482620, 'end_time': 1643497020, 'cra_reward': 3750000000000000000, 'tus_reward': 303750000000000000000, 'miner_cra_reward': 3750000000000000000, 'miner_tus_reward': 303750000000000000000, 'looter_cra_reward': 300000000000000000, 'looter_tus_reward': 24300000000000000000, 'estimate_looter_win_cra': 2737500000000000000, 'estimate_looter_win_tus': 221737500000000000000, 'estimate_looter_lose_cra': 300000000000000000, 'estimate_looter_lose_tus': 24300000000000000000, 'estimate_miner_lose_cra': 1312500000000000000, 'estimate_miner_lose_tus': 106312500000000000000, 'estimate_miner_win_cra': 3750000000000000000, 'estimate_miner_win_tus': 303750000000000000000, 'round': 0, 'team_id': 6264, 'owner': '0x7ee27ef2ba8535f83798c930255d7bb5d04aeae8', 'defense_point': 711, 'defense_mine_point': 198, 'attack_team_id': 4476, 'attack_team_owner': '0x5818a5f1ff6df3b7f5dad8ac66e100cce9e33e8e', 'attack_point': 647, 'winner_team_id': None, 'status': 'open', 'process': [{'action': 'create-game', 'transaction_time': 1643482620}, {'action': 'attack', 'transaction_time': 1643482627}], 'crabada_id_1': 18953, 'crabada_id_2': 18955, 'crabada_id_3': 16969, 'mine_point_modifier': 0, 'crabada_1_photo': '18953.png', 'crabada_2_photo': '18955.png', 'crabada_3_photo': '16969.png', 'defense_crabada_number': 3}]
        return getRemainingTime(mine) < 7000 or mine['winner_team_id'] is not None

    @staticmethod()
    def mineIsFinished(game: IdleGame) -> bool:
        """
        Return true if the given game is past its end_time
        """
        return self.getRemainingTime(game) <= 0

    @staticmethod()
    def mineIsClosed(game: IdleGame) -> bool:
        """
        Return true if the given game is closed (meaning the
        game has been settled and the reward has been claimed)
        """
        return game['status'] == 'close'

    @staticmethod()
    def getRemainingTime(game: IdleGame) -> int:
        """
        Seconds to the end of the given game
        """
        return int(game['end_time'] - time())

    @staticmethod()
    def getRemainingTimeFormatted(game: IdleGame) -> str:
        """
        Hours, minutes and seconds to the end of the given game
        """
        return self.getPrettySeconds(getRemainingTime(game))

    @staticmethod()
    def getNextMineToFinish(games: List[IdleGame]) -> IdleGame:
        """Given a list of games, return the mine that is open and
        next to finish; returns None if there are no unfinished games
        (finished=past the 4th our, regardless of whether the reward
        has been claimed)

        If a game is already finished, it won't be considered"""
        unfinishedGames = [ g for g in games if not mineIsFinished(g) ]
        return firstOrNone(sorted(unfinishedGames, key=lambda g: g['end_time']))
