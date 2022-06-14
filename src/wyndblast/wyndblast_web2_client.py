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
    MORALIS_SERVER_TIME_HEADERS,
    MORALIS_USER_AUTH_HEADERS,
    WYNDBLAST_AUTHORIZATION_HEADER_KEY_FORMAT,
    WYNDBLAST_HEADERS,
)
from wyndblast.types import (
    AccountOverview,
    ActivityResult,
    ActivitySelection,
    DailyActivitySelection,
    Rewards,
    WyndNft,
    WyndStatus,
)

TIMESTAMP_FORMAT = "%Y-%m-%d"


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

    WYNDBLAST_NFT_CONTRACT_ADDRESS = "0x4B3903952A25961B9E66216186Efd9B21903AEd3"

    def __init__(self, private_key: str, user_address: Address) -> None:
        self.private_key = private_key
        self.user_address = Web3.toChecksumAddress(user_address)

        self.session_token = None
        self.object_id = None
        self.username = None

    def _get_request(
        self, url: str, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        try:
            return requests.request("GET", url, params=params, headers=headers, timeout=5.0).json()
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

    def _get_product_id(self, nft_id: int) -> str:
        return ":".join([self.WYNDBLAST_NFT_CONTRACT_ADDRESS, str(nft_id)])

    def _get_daily_activity_headers(self) -> T.Dict[str, str]:
        headers = copy.deepcopy(WYNDBLAST_HEADERS)
        headers["authorization"] = WYNDBLAST_AUTHORIZATION_HEADER_KEY_FORMAT.format(
            self.session_token
        )
        return headers

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
        try:
            res = self._get_server_time_raw(headers=MORALIS_SERVER_TIME_HEADERS, params=params)
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

    def authorize_user(self) -> None:
        try:
            res = self._authorize_user_raw(headers=MORALIS_USER_AUTH_HEADERS)
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
            res = self._update_account_raw(headers=MORALIS_USER_AUTH_HEADERS)
            logger.print_normal(f"Successful update for {self.user_address} at {res['updatedAt']}")
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to update {self.object_id}:\n{res if res else ''}")

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
            "limit": "100",
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
        url = self.DAILY_ACTIVITY_BASE_URL + "/balance"

        return self._get_request(url, headers=headers, params=params)

    def get_unclaimed_balances(self, user_address: Address) -> Rewards:
        try:
            res = self._get_balances_raw(headers=self._get_daily_activity_headers())
            return res["result"]
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to read unclaimed balances!\n{res}")
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
            try:
                date_str = res["result"]["last_claim_datetime"].split("T")[0]
                return datetime.datetime.strptime(date_str, TIMESTAMP_FORMAT)
            except:
                return None
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to read last claim time!\n{res}")
            return None
