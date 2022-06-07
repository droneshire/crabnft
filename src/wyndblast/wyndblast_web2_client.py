import copy
import json
import requests
import time
import typing as T

from eth_account import Account, messages
from eth_typing import Address

from utils import logger
from wyndblast.api_headers import (
    MORALIS_SERVER_TIME_HEADERS,
    MORALIS_USER_AUTH_HEADERS,
    WYNDBLAST_AUTHORIZATION_HEADER_KEY_FORMAT,
    WYNDBLAST_HEADERS,
)


class WyndblastWeb2Client:
    """Access api endpoints of Wyndblast Game"""

    DAILY_ACTIVITY_BASE_URL = "https://api.wyndblast.com/daily-activity"
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

    WYNDBLAST_NFT_CONTRACT_ADDRESS = "0x4b3903952a25961b9e66216186efd9b21903aed3"

    def __init__(self, private_key: str, user_address: Address) -> None:
        self.private_key = private_key
        self.user_address = user_address

        self.session_token = None
        self.object_id = None
        self.username = None

    def _get_request(self, url: str, params: T.Dict[str, T.Any] = {}) -> T.Any:
        try:
            return requests.request(
                "GET", url, params=params, headers=self.BROWSER_HEADERS, timeout=5.0
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
    ) -> T.Any:
        try:
            return requests.request(
                "POST", url, json=json_data, params=params, headers=headers, timeout=5.0
            ).json()
        except KeyboardInterrupt:
            raise
        except:
            return {}

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
        res = self._get_server_time_raw(headers=MORALIS_SERVER_TIME_HEADERS, params=params)
        if not res:
            return 0
        try:
            return int(res["result"]["dateTime"])
        except:
            return 0

    def _authorize_user_raw(
        self, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.MORALIS_BASE_URL + "/users"

        payload = self._get_moralis_auth_payload()
        return self._post_request(url, json_data=payload, headers=headers, params=params)

    def authorize_user(self) -> None:
        res = self._authorize_user_raw(headers=MORALIS_USER_AUTH_HEADERS)
        if not res:
            return
        try:
            self.session_token = res["sessionToken"]
            self.object_id = res["objectId"]
            self.username = res["username"]
            logger.print_ok(
                f"Successfully authorized user {self.user_address}:\nToken: {self.session_token}\nUser: {self.username}"
            )
        except:
            logger.print_fail(f"Failed to authorize user {self.user_address}:\n{res}")

    def _update_account_raw(
        self, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.MORALIS_BASE_URL + f"/classes/_User/{self.object_id}"

        payload = self._get_moralis_login_payload()
        return self._post_request(url, json_data=payload, headers=headers, params=params)

    def update_account(self) -> None:
        res = self._update_account_raw(headers=MORALIS_USER_AUTH_HEADERS)
        if not res:
            return
        try:
            logger.print_ok(f"Successful update for {self.user_address} at {res['updatedAt']}")
        except:
            logger.print_fail(f"Failed to update {self.object_id}:\n{res}")
