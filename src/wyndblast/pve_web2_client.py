import copy
import json
import typing as T

from eth_typing import Address

from utils import logger
from wyndblast.api_headers import (
    API_KEYS,
    WYNDBLAST_AUTHORIZATION_HEADER_KEY_FORMAT,
    WYNDBLAST_PVE_HEADERS,
)
from wyndblast.types import (
    BattlePayload,
    BattleSetup,
    ClaimQuests,
    Countdown,
    LevelQuests,
    PveNfts,
    PveRewards,
    PveUser,
    PveStages,
    WyndLevelUpResponse,
)
from wyndblast.wyndblast_web2_client import WyndblastWeb2Client


class PveWyndblastWeb2Client(WyndblastWeb2Client):
    PVE_LOBBY_ID = "TESTING"

    def __init__(
        self, private_key: str, user_address: Address, base_url: str, dry_run: bool = False
    ) -> None:
        super().__init__(private_key, user_address, base_url, dry_run=dry_run)

    def _get_pve_headers(self, api_key: str = API_KEYS["pve"]) -> T.Dict[str, str]:
        headers = copy.deepcopy(WYNDBLAST_PVE_HEADERS)
        headers["authorization"] = WYNDBLAST_AUTHORIZATION_HEADER_KEY_FORMAT.format(
            self.session_token
        )
        headers["x-api-key"] = api_key
        return headers

    def _get_countdown_raw(
        self, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.PVE_BASE_URL + "/countdown"
        return self._get_request(url, headers=headers, params=params)

    def get_countdown(self) -> Countdown:
        try:
            res = self._get_countdown_raw(headers=self._get_pve_headers())
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get pve countdown!\n{res}")
            return {}

    def _get_level_quests_raw(
        self, level: str, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.PVE_BASE_URL + f"/quest/{level}"
        return self._get_request(url, headers=headers, params=params)

    def get_level_quests(self, level: str) -> T.List[LevelQuests]:
        try:
            res = self._get_level_quests_raw(level, headers=self._get_pve_headers())
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get pve level quests!\n{res}")
            return {}

    def _get_stages_raw(
        self, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.PVE_BASE_URL + f"/stage"
        return self._get_request(url, headers=headers, params=params)

    def get_stages(self) -> PveStages:
        try:
            res = self._get_stages_raw(headers=self._get_pve_headers())
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get pve stages!\n{res}")
            return {}

    def _get_chro_rewards_raw(
        self, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.PVE_BASE_URL + f"/rewards/chro/"
        return self._get_request(url, headers=headers, params=params)

    def get_chro_rewards(self) -> PveRewards:
        try:
            res = self._get_chro_rewards_raw(headers=self._get_pve_headers())
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get pve chro rewards!\n{res}")
            return {}

    def _get_user_profile_raw(
        self, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.PVE_BASE_URL + f"/user"
        return self._get_request(url, headers=headers, params=params)

    def get_user_profile(self) -> PveUser:
        try:
            res = self._get_user_profile_raw(headers=self._get_pve_headers())
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get pve user profile!\n{res}")
            return {}

    def _get_nft_data_raw(
        self, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.PVE_BASE_URL + f"/nft"
        return self._get_request(url, headers=headers, params=params, timeout=20.0)

    def get_nft_data(self) -> PveNfts:
        try:
            res = self._get_nft_data_raw(headers=self._get_pve_headers())
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get pve nft data!\n{res}")
            return {}

    def _level_up_wynd_raw(
        self, dna_string: str, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.PVE_BASE_URL + f"/rewards/wynd/claim/{dna_string}"
        return self._post_request(url, json_data={}, headers=headers, params=params)

    def get_wynd_dna_str(self, product_id: str) -> str:
        nft: PveNfts = self.get_nft_data()
        if not nft:
            logger.print_fail(f"No NFT stats!")
            return ""

        wynds = nft.get("wynd", [])

        if not wynds:
            logger.print_fail(f"No wynds in NFT stats!")
            return ""

        for wynd in wynds:
            if wynd["product_id"] == product_id:
                return wynd.get("metadata", {}).get("dna", {}).get("all", "")

        return ""

    def level_up_wynd(self, dna_string: str) -> bool:
        try:
            res = self._level_up_wynd_raw(dna_string, headers=self._get_pve_headers())
            return res["result"]["is_level_up"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to level up wynd!\n{res}")
            return False

    def _battle_raw(
        self,
        payload: T.Dict[T.Any, T.Any],
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.PVE_BASE_URL + f"/internal/battle"
        return self._post_request(
            url, json_data=payload, headers=headers, params=params, timeout=10.0
        )

    def battle(self, stage_id: str, battle_setup: BattleSetup, duration: int = 28) -> bool:
        payload: BattlePayload = BattlePayload()
        payload["duration"] = duration
        payload["setup"] = battle_setup
        payload["stage_id"] = stage_id
        payload["lobby_id"] = self.PVE_LOBBY_ID
        payload["result"] = "win"
        payload["survived"] = {
            "player": battle_setup["player"],
            "enemy": [],
        }
        try:
            res = self._battle_raw(
                payload=json.loads(json.dumps(payload)),
                headers=self._get_pve_headers(api_key=API_KEYS["internal"]),
            )
            return res["result"]["won"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to battle!\n{res}")
            return False

    def _claim_daily_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.PVE_BASE_URL + "/rewards/quest/daily/claim"
        return self._post_request(url, json_data={}, headers=headers, params=params, timeout=15.0)

    def claim_daily(self) -> ClaimQuests:
        try:
            res = self._claim_daily_raw(headers=self._get_pve_headers())
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to claim dailies!\n{res}")
            return {}

    def _claim_weekly_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.PVE_BASE_URL + "/rewards/quest/weekly/claim"
        return self._post_request(url, json_data={}, headers=headers, params=params, timeout=15.0)

    def claim_weekly(self) -> ClaimQuests:
        try:
            res = self._claim_weekly_raw(headers=self._get_pve_headers())
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to claim weeklies!\n{res}")
            return {}

    def _claim_chro_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.PVE_BASE_URL + "/rewards/chro/claim"
        return self._post_request(url, json_data={}, headers=headers, params=params, timeout=15.0)

    def claim_chro(self) -> T.Dict[T.Any, T.Any]:
        try:
            res = self._claim_chro_raw(headers=self._get_pve_headers())
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to claim weeklies!\n{res}")
            return {}
