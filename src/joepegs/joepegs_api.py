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
from utils.price import wei_to_token
from joepegs.types import Activity, ListFilters

TIMESTAMP_FORMAT = "%Y-%m-%d"

BASE_URL = "https://api.joepegs.dev/"
HEADERS = {
    "x-joepegs-api-key": JOEPEGS_API_KEY,
}


JOEPEGS_URL = "https://joepegs.com/item/{}/"
JOEPEGS_ITEM_URL = "https://joepegs.com/item/avalanche/{}/{}"
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

    def get_item(
        self,
        address: Address,
        token_id: int,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        try:
            return self._joepegs_api(f"/collections/{address}/tokens/{token_id}", params=params)
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get item {token_id}\n{res if res else ''}")
            return {}

    def get_collection(
        self, address: Address, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        try:
            return self._joepegs_api(f"collections/{address}", params=params)
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get collection {address}\n{res if res else ''}")
            return {}

    def get_listings(
        self, address: Address, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        actual_params = {
            "filters": ListFilters.BUY_NOW,
            "pageSize": 100,
            "pageNum": 1,
            "collectionAddress": address,
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

    def get_activities(
        self, address: Address, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.List[Activity]:
        actual_params = {
            "pageSize": 100,
            "pageNum": 1,
        }
        actual_params.update(params)
        extension = f"activities/{address}"
        try:
            return self._joepegs_api(extension, params=actual_params)
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get activities:\n{res if res else ''}")
            return []

    def get_sales(
        self, address: Address, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.List[Activity]:
        activities = self.get_activities(address, params=params)
        return [a for a in activities if type(a) == dict and a["activityType"] == "sale"]

    def get_floor_avax(
        self, address: Address, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> float:
        collection = self.get_collection(address, params=params)
        if not collection:
            logger.print_fail(f"Failed to get floor info")
            return -1.0
        if "floor" not in collection:
            logger.print_fail(f"Failed to get floor: {collection}")
            return -1.0
        return wei_to_token(int(collection["floor"]))

    def purchase_item(
        self,
        address: Address,
        token_id: int,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> str:
        actual_params = {
            "pageSize": 100,
            "pageNum": 1,
            "collection": address,
            "tokenId": token_id,
            "orderBy": "price_desc",
            "includeCollectionBids": False,
        }
        actual_params.update(params)
        extension = f"maker-orders"
        try:
            return self._joepegs_api(extension, params=actual_params)
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get maker orders:\n{res if res else ''}")
            return []
