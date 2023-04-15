import copy
import json
import random
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
    Stamina,
    StaminaBuy,
    TeamPreset,
    Units,
    UnitPreset,
    WyndLevelUpResponse,
)
from wyndblast.wyndblast_web2_client import WyndblastWeb2Client


class PveWyndblastWeb2Client(WyndblastWeb2Client):
    PVE_LOBBY_ID = "TESTING"

    def __init__(
        self,
        private_key: str,
        user_address: Address,
        base_url: str,
        dry_run: bool = False,
    ) -> None:
        super().__init__(
            private_key,
            user_address,
            base_url,
            rate_limit_delay=3.5,
            use_proxy=False,
            dry_run=dry_run,
        )

    def _get_pve_headers(
        self, api_key: str = API_KEYS["pve"]
    ) -> T.Dict[str, str]:
        headers = copy.deepcopy(WYNDBLAST_PVE_HEADERS)
        headers[
            "authorization"
        ] = WYNDBLAST_AUTHORIZATION_HEADER_KEY_FORMAT.format(self.session_token)
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
            logger.print_fail(f"Failed to get pve countdown!")
            if res:
                logger.print_normal(f"{res}")
            return {}

    def _get_level_quests_raw(
        self,
        level: str,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.PVE_BASE_URL + f"/quest/{level}"
        return self._get_request(url, headers=headers, params=params)

    def get_level_quests(self, level: str) -> T.List[LevelQuests]:
        try:
            res = self._get_level_quests_raw(
                level, headers=self._get_pve_headers()
            )
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get pve level quests!")
            if res:
                logger.print_normal(f"{res}")
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
            logger.print_fail(f"Failed to get pve stages!")
            if res:
                logger.print_normal(f"{res}")
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
            logger.print_fail(f"Failed to get pve chro rewards!")
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
            logger.print_fail(f"Failed to get pve user profile!")
            if res:
                logger.print_normal(f"{res}")
            return res

    def _get_nft_data_raw(
        self, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.PVE_BASE_URL + f"/nft"
        return self._get_request(
            url, headers=headers, params=params, timeout=20.0
        )

    def get_nft_data(self) -> PveNfts:
        try:
            res = self._get_nft_data_raw(headers=self._get_pve_headers())
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get pve nft data!")
            if res:
                logger.print_normal(f"{res}")
            return {}

    def _get_stamina_raw(
        self, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.PVE_BASE_URL + f"/stamina"
        return self._get_request(
            url, headers=headers, params=params, timeout=20.0
        )

    def get_stamina(self) -> int:
        try:
            res = self._get_stamina_raw(headers=self._get_pve_headers())
            return res["result"]["current"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get stamina!")
            if res:
                logger.print_normal(f"{res}")
            return 0

    def _refresh_auth_raw(
        self, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.PVE_BASE_URL + f"/stamina"
        return self._get_request(
            url, headers=headers, params=params, timeout=20.0
        )

    def refresh_auth(self) -> bool:
        try:
            res = self._refresh_auth_raw(headers=self._get_pve_headers())
            return res.get("status", False)
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to refresh pve authorization!")
            if res:
                logger.print_normal(f"{res}")
            return False

    def _level_up_wynd_raw(
        self,
        product_id: str,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.PVE_BASE_URL + f"/rewards/wynd/claim/{product_id}"
        return self._post_request(
            url, json_data={}, headers=headers, params=params
        )

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

    def level_up_wynd(self, product_id: str) -> bool:
        try:
            res = self._level_up_wynd_raw(
                product_id, headers=self._get_pve_headers()
            )
            return res["result"]["is_level_up"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to level up wynd!")
            if res:
                logger.print_normal(f"{res}")
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

    def battle(
        self,
        stage_id: str,
        battle_setup: BattleSetup,
        duration: int = 28,
        result: str = "win",
    ) -> bool:
        payload: BattlePayload = BattlePayload()
        payload["duration"] = duration
        payload["setup"] = battle_setup
        payload["stage_id"] = stage_id
        payload["lobby_id"] = self.PVE_LOBBY_ID
        payload["result"] = result
        payload["survived"] = {
            "player": battle_setup["player"] if result == "win" else [],
            "enemy": battle_setup["enemy"][
                : random.randint(1, len(battle_setup["enemy"]))
            ]
            if result == "lose"
            else [],
        }
        try:
            res = self._battle_raw(
                payload=json.loads(json.dumps(payload)),
                headers=self._get_pve_headers(api_key=API_KEYS["internal"]),
            )
            if not res.get("status", False):
                logger.print_fail_arrow(f"{res}")
            return res["status"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to battle!")
            if res:
                logger.print_normal(f"{res}")
            return False

    def _claim_daily_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.PVE_BASE_URL + "/rewards/quest/daily/claim"
        return self._post_request(
            url, json_data={}, headers=headers, params=params, timeout=15.0
        )

    def claim_daily(self) -> ClaimQuests:
        try:
            res = self._claim_daily_raw(headers=self._get_pve_headers())
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to claim dailies!")
            if res:
                logger.print_normal(f"{res}")
            return {}

    def _claim_weekly_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.PVE_BASE_URL + "/rewards/quest/weekly/claim"
        return self._post_request(
            url, json_data={}, headers=headers, params=params, timeout=15.0
        )

    def claim_weekly(self) -> ClaimQuests:
        try:
            res = self._claim_weekly_raw(headers=self._get_pve_headers())
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to claim weeklies!")
            if res:
                logger.print_normal(f"{res}")
            return {}

    def _claim_chro_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.PVE_BASE_URL + "/rewards/chro/claim"
        return self._post_request(
            url, json_data={}, headers=headers, params=params, timeout=15.0
        )

    def claim_chro(self) -> T.Dict[T.Any, T.Any]:
        try:
            res = self._claim_chro_raw(headers=self._get_pve_headers())
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to claim chro!")
            if res:
                logger.print_normal(f"{res}")
            return {}

    def _preset_unit_raw(
        self,
        payload: T.Dict[T.Any, T.Any],
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.PVE_BASE_URL + f"/preset/unit"
        return self._post_request(
            url, json_data=payload, headers=headers, params=params, timeout=10.0
        )

    def preset_unit(self, product_id: str) -> bool:
        payload: UnitPreset = UnitPreset()
        payload["name"] = "TEST"
        payload["unit"] = {
            "equipment_product_id": "",
            "rider_product_id": "",
            "wynd_product_id": product_id,
        }
        try:
            res = self._preset_unit_raw(
                payload=json.loads(json.dumps(payload)),
                headers=self._get_pve_headers(),
            )
            return res["result"]["is_active"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to preset unit!")
            if res:
                logger.print_normal(f"{res}")
            return False

    def _preset_team_raw(
        self,
        payload: T.Dict[T.Any, T.Any],
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.PVE_BASE_URL + f"/preset/team"
        return self._post_request(
            url, json_data=payload, headers=headers, params=params, timeout=10.0
        )

    def preset_team(self, product_ids: T.List[str]) -> bool:
        payload: TeamPreset = TeamPreset()
        payload["name"] = "1"
        payload["units"] = []
        for i in product_ids:
            unit: Units = Units()
            unit["equipment_product_id"] = ""
            unit["rider_product_id"] = ""
            unit["wynd_product_id"] = i
            unit["position"] = {"x": 521.592468, "y": 400.443848}
            payload["units"].append(unit)
        try:
            res = self._preset_team_raw(
                payload=json.loads(json.dumps(payload)),
                headers=self._get_pve_headers(),
            )
            return res["result"]["is_active"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to preset team!")
            if res:
                logger.print_normal(f"{res}")
            return False

    def _ping_realtime_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.PVE_BASE_URL + "/ws/realtime"
        return self._post_request(
            url, json_data={}, headers=headers, params=params, timeout=15.0
        )

    def ping_realtime(self) -> T.Dict[str, str]:
        try:
            res = self._ping_realtime_raw(headers=self._get_pve_headers())
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to ping realtime!")
            if res:
                logger.print_normal(f"{res}")
            return {}

    def _complete_opening_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.PVE_BASE_URL + "/opening"
        return self._post_request(
            url, json_data={}, headers=headers, params=params, timeout=15.0
        )

    def complete_opening(self) -> bool:
        try:
            res = self._complete_opening_raw(headers=self._get_pve_headers())
            return res["status"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to complete_opening!")
            if res:
                logger.print_normal(f"{res}")
            return False

    def _complete_novel_stage1_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.PVE_BASE_URL + "/visual-novel/Selecting_Stage_1_1"
        return self._post_request(
            url, json_data={}, headers=headers, params=params, timeout=15.0
        )

    def complete_novel_stage1(self) -> bool:
        try:
            res = self._complete_novel_stage1_raw(
                headers=self._get_pve_headers()
            )
            return res["status"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to complete_novel_stage1!")
            if res:
                logger.print_normal(f"{res}")
            return False

    def _complete_novel_before_main1_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.PVE_BASE_URL + "/visual-novel/Before_Main_Map_1"
        return self._post_request(
            url, json_data={}, headers=headers, params=params, timeout=15.0
        )

    def complete_novel_before_main1(self) -> bool:
        try:
            res = self._complete_novel_before_main1_raw(
                headers=self._get_pve_headers()
            )
            return res["status"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to complete_novel_before_main1!")
            if res:
                logger.print_normal(f"{res}")
            return False

    def _request_stamina_buy_raw(
        self,
        stamina: int,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.PVE_BASE_URL + "/stamina/buy"
        data = {
            "amount": stamina,
        }
        return self._post_request(
            url, json_data=data, headers=headers, params=params, timeout=20.0
        )

    def request_stamina_buy(self, stamina: int) -> StaminaBuy:
        try:
            res = self._request_stamina_buy_raw(
                stamina, headers=self._get_pve_headers()
            )
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to request_stamina_buy_raw!")
            if res:
                logger.print_normal(f"{res}")
            return {}
