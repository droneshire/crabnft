import copy
import datetime
import json
import requests
import time
import typing as T


from eth_account import Account, messages
from eth_typing import Address
from web3 import Web3
from yaspin import yaspin

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


@yaspin(text="Waiting...")
def wait(wait_time) -> None:
    time.sleep(wait_time)


class WyndblastWeb2Client:
    """Access api endpoints of Wyndblast Game"""

    DAILY_ACTIVITY_BASE_URL = "https://api.wyndblast.com/daily-activity"
    GOOGLE_STORAGE_URL = "https://storage.googleapis.com/wyndblast-dev.appspot.com/public/json"
    MORALIS_BASE_URL = "https://qheky5jm92sj.usemoralis.com:2053/server/"
    PVE_BASE_URL = "https://wyndblast-pve-api-26nte4kk3a-ey.a.run.app"

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
        self.user_address = Web3.toChecksumAddress(user_address) if user_address else ""

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
        delay: float = 5.0,
    ) -> T.Any:
        if delay > 0.0:
            wait(delay)
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
        delay: float = 5.0,
    ) -> T.Any:
        if self.dry_run:
            return {}

        if delay > 0.0:
            wait(delay)

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
        if not self.user_address:
            return {}
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
        if not self.user_address:
            logger.print_warn("Cannot use moralis, no key pairs provided")
            return {}
        payload = self._get_moralis_base_payload()
        payload["_method"] = "PUT"
        payload["_SessionToken"] = self.session_token
        payload["ethAddress"] = self.user_address.lower()
        payload["ACL"] = {self.object_id: {"read": True, "write": True}}
        payload["accounts"] = {"__op": "AddUnique", "objects": [self.user_address.lower()]}
        return json.loads(json.dumps(payload))

    def _get_login_signature(self) -> (str, int):
        if not self.user_address:
            logger.print_warn("Cannot use moralis, no key pairs provided")
            return "", 0
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

    def authorize_user(self) -> bool:
        try:
            res = self._authorize_user_raw(headers=self._get_moralis_headers())
            self.session_token = res["sessionToken"]
            self.object_id = res["objectId"]
            self.username = res["username"]
            logger.print_normal(
                f"Successfully authorized user {self.user_address}:\nToken: {self.session_token}\nUser: {self.username}"
            )
            return True
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(
                f"Failed to authorize user {self.user_address}:\n{res if res else ''}"
            )
            return False

    def _update_account_raw(
        self, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.MORALIS_BASE_URL + f"/classes/_User/{self.object_id}"

        payload = self._get_moralis_login_payload()
        return self._post_request(url, json_data=payload, headers=headers, params=params)

    def update_account(self) -> bool:
        if self.session_token is None:
            return False
        try:
            res = self._update_account_raw(headers=self._get_moralis_headers())
            logger.print_normal(f"Successful update for {self.user_address} at {res['updatedAt']}")
            return True
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to update {self.object_id}:\n{res if res else ''}")
            return False
