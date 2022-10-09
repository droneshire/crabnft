import copy
import datetime
import json
import requests
import time
import typing as T
from eth_typing import Address
from web3 import Web3

from utils import logger
from pumpskin.types import Pumpskin

TIMESTAMP_FORMAT = "%Y-%m-%d"


class PumpskinWeb2Client:
    """Access api endpoints of Pumpskin Game"""

    BASE_URL = "https://gateway.ipfscdn.io/ipfs"

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

    def _get_pumpskin_info_raw(
        self, token_id: int, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = self.BASE_URL + f"/QmY1Fccg5JrnpbyzNJBekPPPMQsPFm1Cxx9MJSeArpwTdP/{token_id}"
        return self._get_request(url, headers=headers, params=params)

    def get_pumpskin_info(self, token_id: int, params: T.Dict[str, T.Any] = {}) -> Pumpskin:
        try:
            res = self._get_pumpskin_info_raw(token_id=token_id, params=params)
            return res
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get pumpskin info:\n{res if res else ''}")
            return {}

    def get_pumpskin_image(self, token_id: int, params: T.Dict[str, T.Any] = {}) -> Pumpskin:
        try:
            res = self._get_pumpskin_info_raw(token_id=token_id, params=params)
            image_path = res["image"].split("://")[1]
            return self.BASE_URL + "/" + image_path
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get pumpskin image:\n{res if res else ''}")
            return {}
