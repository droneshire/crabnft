import copy
import datetime
import json
import requests
import time
import typing as T
from eth_typing import Address
from web3 import Web3

from config_admin import JOEPEGS_API_KEY
from utils import logger

TIMESTAMP_FORMAT = "%Y-%m-%d"

BASE_URL = "https://api.joepegs.dev/"
HEADERS = {
    "x-joepegs-api-key": JOEPEGS_API_KEY,
}


class ListFilters:
    BUY_NOW = "buy_now"
    HAS_OFFERS = "has_offers"
    ON_AUCTION = "on_auction"
    UNLISTED = "unlisted"


JOEPEGS_URL = "https://joepegs.com/item/0x0a27e02fdaf3456bd8843848b728ecbd882510d1/"
JOEPEGS_ICON_URL = "https://drive.google.com/uc?export=view&id=1mLBMY7-XPtLbSZrWRpCujFCc6cIJ_VIE"


class JoePegsClient:
    """Access api endpoints of JoePegs"""

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

    def _joepegs_api(
        self, endpoint: str, headers: T.Dict[str, T.Any] = HEADERS, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        url = f"{BASE_URL}v2/{endpoint}"
        return self._get_request(url, headers=headers, params=params)

    def get_collection(
        self, address: Address, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        try:
            return self._joepegs_api(f"collections/{address}")
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get collection\n{res if res else ''}")
            return {}

    def list_items_for_sale(
        self, address: Address, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        actual_params = {
            "filters": ListFilters.BUY_NOW,
            "pageSize": 100,
            "pageNum": 1,
            "collectionAddress": address,
            "orderBy": "rarity_desc",
        }
        actual_params.update(params)
        try:
            ret = self._joepegs_api(f"items", params=actual_params)
            return ret
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get list items:\n{res if res else ''}")
            return {}
