import copy
import datetime
import json
import requests
import time
import typing as T

from eth_account import Account, messages
from eth_typing import Address
from web3 import Web3

from utils import logger
from wyndblast.api_headers import (
    API_KEYS,
    MORALIS_HEADERS,
    WYNDBLAST_AUTHORIZATION_HEADER_KEY_FORMAT,
    WYNDBLAST_DAILY_ACTIVITIES_HEADERS,
    WYNDBLAST_PVE_HEADERS,
)
from wyndblast.types import (
    AccountOverview,
    ActivityResult,
    ActivitySelection,
    BattlePayload,
    BattleSetup,
    ClaimQuests,
    Countdown,
    DailyActivitySelection,
    LevelQuests,
    PveNfts,
    PveRewards,
    PveUser,
    Rewards,
    PveStages,
    WyndLevelUpResponse,
    WyndNft,
    WyndStatus,
)

TIMESTAMP_FORMAT = "%Y-%m-%d"


class WyndblastWeb2Client:
    """Access api endpoints of Wyndblast Game"""

    DAILY_ACTIVITY_BASE_URL = "https://api.wyndblast.com/daily-activity"
    PVE_BASE_URL = "https://wyndblast-pve-api-26nte4kk3a-ey.a.run.app"
    MORALIS_BASE_URL = "https://qheky5jm92sj.usemoralis.com:2053/server/"

    TO_SIGN = "WyndBlast Authentication\n\nId: lQBcMbRFdVKdFM2ToB0LZEjzhGEbXFilLikZY759:{}"

    MORALIS_BASE_PAYLOAD = {
        "_ApplicationId": "lQBcMbRFdVKdFM2ToB0LZEjzhGEbXFilLikZY759",
        "_ClientVersion": "js1.5.8",
        "_InstallationId": "51bc66ad-7a51-4c35-837b-125726261b76",
    }

    MORALIS_AUTH_PAYLOAD = {
        "authData": {
            "moralisEth": {
                "id": "",
                "signature": "",
                "data": "",
            }
        },
    }

    WYNDBLAST_NFT_CONTRACT_ADDRESS = "0x4B3903952A25961B9E66216186Efd9B21903AEd3"

    def __init__(
        self, private_key: str, user_address: Address, base_url: str, dry_run: bool = False
    ) -> None:
        self.private_key = private_key
        self.user_address = Web3.toChecksumAddress(user_address)

        self.session_token = None
        self.object_id = None
        self.username = None
        self.dry_run = dry_run
        self.base_url = base_url
        if dry_run:
            logger.print_warn("Web2 Client in dry run mode...")

    def _get_request(
        self,
        url: str,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
        timeout: float = 5.0,
    ) -> T.Any:
        try:
            return requests.request(
                "GET", url, params=params, headers=headers, timeout=timeout
            ).json()
        except KeyboardInterrupt:
            raise
        except:
            return {}

    def _post_request(
        self,
        url: str,
        json_data: T.Dict[str, T.Any] = {},
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
        timeout: float = 5.0,
    ) -> T.Any:
        if self.dry_run:
            return {}
        try:
            return requests.request(
                "POST", url, json=json_data, params=params, headers=headers, timeout=timeout
            ).json()
        except KeyboardInterrupt:
            raise
        except:
            return {}

    def _get_product_id(self, nft_id: int) -> str:
        return ":".join([self.WYNDBLAST_NFT_CONTRACT_ADDRESS, str(nft_id)])

    def _get_moralis_base_payload(self) -> T.Dict[str, T.Any]:
        payload = copy.deepcopy(self.MORALIS_BASE_PAYLOAD)
        return json.loads(json.dumps(payload))

    def _get_moralis_auth_payload(self) -> T.Dict[str, T.Any]:
        signature, timestamp = self._get_login_signature()

        payload = self._get_moralis_base_payload()
        payload.update(self.MORALIS_AUTH_PAYLOAD)
        payload["authData"]["moralisEth"]["id"] = self.user_address.lower()
        payload["authData"]["moralisEth"]["signature"] = signature
        payload["authData"]["moralisEth"]["data"] = self.TO_SIGN.format(timestamp)
        return json.loads(json.dumps(payload))

    def _get_moralis_logout_payload(self) -> T.Dict[str, T.Any]:
        payload = self._get_moralis_base_payload()
        return json.loads(json.dumps(payload))

    def _get_moralis_login_payload(self) -> T.Dict[str, T.Any]:
        payload = self._get_moralis_base_payload()
        payload["_method"] = "PUT"
        payload["_SessionToken"] = self.session_token
        payload["ethAddress"] = self.user_address.lower()
        payload["ACL"] = {self.object_id: {"read": True, "write": True}}
        payload["accounts"] = {"__op": "AddUnique", "objects": [self.user_address.lower()]}
        return json.loads(json.dumps(payload))

    def _get_login_signature(self) -> (str, int):
        server_time = self._get_server_time()
        signable = messages.encode_defunct(text=self.TO_SIGN.format(server_time))
        signed = Account.sign_message(signable, private_key=self.private_key)
        return signed.signature.hex(), server_time

    def _get_server_time_raw(
        self, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.MORALIS_BASE_URL + "/functions/getServerTime"
        payload = self._get_moralis_base_payload()
        return self._post_request(url, json_data=payload, headers=headers, params=params)

    def _get_server_time(self, params: T.Dict[str, T.Any] = {}) -> int:
        try:
            res = self._get_server_time_raw(headers=self._get_moralis_headers(), params=params)
            return int(res["result"]["dateTime"])
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get server time:\n{res if res else ''}")
            return 0

    def _authorize_user_raw(
        self, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.MORALIS_BASE_URL + "/users"

        payload = self._get_moralis_auth_payload()
        return self._post_request(url, json_data=payload, headers=headers, params=params)

    def _logout_user_raw(
        self, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.MORALIS_BASE_URL + "/logout"

        payload = self._get_moralis_logout_payload()
        return self._post_request(url, json_data=payload, headers=headers, params=params)

    def logout_user(self) -> None:
        try:
            res = self._logout_user_raw(headers=self._get_moralis_headers())
            logger.print_bold(f"Successfully logged out user {self.user_address}")
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to logout user {self.user_address}:\n{res if res else ''}")

    def _get_moralis_headers(self) -> T.Dict[str, T.Any]:
        headers = copy.deepcopy(MORALIS_HEADERS)
        headers["origin"] = self.base_url
        headers["referer"] = self.base_url
        return headers

    def authorize_user(self) -> None:
        try:
            res = self._authorize_user_raw(headers=self._get_moralis_headers())
            self.session_token = res["sessionToken"]
            self.object_id = res["objectId"]
            self.username = res["username"]
            logger.print_normal(
                f"Successfully authorized user {self.user_address}:\nToken: {self.session_token}\nUser: {self.username}"
            )
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(
                f"Failed to authorize user {self.user_address}:\n{res if res else ''}"
            )

    def _update_account_raw(
        self, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.MORALIS_BASE_URL + f"/classes/_User/{self.object_id}"

        payload = self._get_moralis_login_payload()
        return self._post_request(url, json_data=payload, headers=headers, params=params)

    def update_account(self) -> None:
        try:
            res = self._update_account_raw(headers=self._get_moralis_headers())
            logger.print_normal(f"Successful update for {self.user_address} at {res['updatedAt']}")
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to update {self.object_id}:\n{res if res else ''}")


class DailyActivitiesWyndblastWeb2Client(WyndblastWeb2Client):
    def __init__(
        self, private_key: str, user_address: Address, base_url: str, dry_run: bool = False
    ) -> None:
        super().__init__(private_key, user_address, base_url, dry_run=dry_run)

    def _get_daily_activity_headers(self) -> T.Dict[str, str]:
        headers = copy.deepcopy(WYNDBLAST_DAILY_ACTIVITIES_HEADERS)
        headers["authorization"] = WYNDBLAST_AUTHORIZATION_HEADER_KEY_FORMAT.format(
            self.session_token
        )
        return headers

    def _get_account_overview_raw(
        self, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.DAILY_ACTIVITY_BASE_URL + "/nft-overview"
        default_params = {
            "limit": "100",
            "page": "1",
        }
        default_params.update(params)

        return self._get_request(url, headers=headers, params=default_params)

    def get_account_overview(self) -> AccountOverview:
        try:
            res = self._get_account_overview_raw(headers=self._get_daily_activity_headers())
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed get nft overview")
            return {}

    def _get_nft_raw(
        self, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.DAILY_ACTIVITY_BASE_URL + "/nft"
        default_params = {
            "limit": "12",
            "page": "1",
        }
        default_params.update(params)
        return self._get_request(url, headers=headers, params=default_params)

    def get_all_wynds_activity(self, params: T.Dict[str, T.Any] = {}) -> T.List[WyndStatus]:
        try:
            res = self._get_nft_raw(headers=self._get_daily_activity_headers(), params=params)
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed get nft stats\n{res}")
            return []

    def _get_activity_selection_raw(
        self, nft_id: int, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.DAILY_ACTIVITY_BASE_URL + "/select"
        json_data = {"product_ids": [self._get_product_id(nft_id)]}
        headers = self._get_daily_activity_headers()

        return self._post_request(url, json_data=json_data, headers=headers, params=params)

    def get_activity_selection(self, nft_id: int) -> DailyActivitySelection:
        try:
            res = self._get_activity_selection_raw(
                nft_id=nft_id, headers=self._get_daily_activity_headers()
            )
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get activity options\n{res if res else ''}")
            return {}

    def _new_raw(
        self,
        selection: ActivitySelection,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.DAILY_ACTIVITY_BASE_URL + "/new"
        json_data = json.loads(json.dumps(selection))

        return self._post_request(url, json_data=json_data, headers=headers, params=params)

    def do_activity(self, selection: ActivitySelection) -> ActivityResult:
        try:
            res = self._new_raw(selection=selection, headers=self._get_daily_activity_headers())
            return res["result"][0]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to do activity!\n{res}")
            return {}

    def _get_balances_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.DAILY_ACTIVITY_BASE_URL + "/rewards"

        return self._get_request(url, headers=headers, params=params)

    def get_unclaimed_balances(self) -> Rewards:
        try:
            res = self._get_balances_raw(headers=self._get_daily_activity_headers())
            return res["result"]["total_rewards"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to read unclaimed rewards!\n{res}")
            return {}

    def _get_wynd_status_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.DAILY_ACTIVITY_BASE_URL + "/nft/owned"

        default_params = {
            "limit": "50",
            "page": "1",
        }
        default_params.update(params)

        return self._get_request(url, headers=headers, params=default_params)

    def get_wynd_status(self) -> T.List[WyndNft]:
        try:
            res = self._get_wynd_status_raw(headers=self._get_daily_activity_headers())
            return res["result"]["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to read wynd status!\n{res}")
            return []

    def _get_last_claim_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.DAILY_ACTIVITY_BASE_URL + "/last-claim"

        return self._get_request(url, headers=headers, params=params)

    def get_last_claim(self) -> T.Optional[datetime.datetime]:
        try:
            res = self._get_last_claim_raw(headers=self._get_daily_activity_headers())
            last_claim = res["result"]["last_claim_datetime"]
            if last_claim is None:
                return None
            date_str = last_claim.split("T")[0]
            return datetime.datetime.strptime(date_str, TIMESTAMP_FORMAT)
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to read last claim time!\n{res}")
            return None


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
        url = self.PVE_BASE_URL + "/cooldown"
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

    def _get_wynd_dna_str(self, product_id: str) -> str:
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
            dna_string = self._get_wynd_dna_str(product_id)
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
        url = self.PVE_BASE_URL + "rewards/quest/daily/claim"
        return self._post_request(url, json_data={}, headers=headers, params=params)

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
        url = self.PVE_BASE_URL + "rewards/quest/weekly/claim"
        return self._post_request(url, json_data={}, headers=headers, params=params)

    def claim_weekly(self) -> ClaimQuests:
        try:
            res = self._claim_weekly_raw(headers=self._get_pve_headers())
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to claim weeklies!\n{res}")
            return {}
