import copy
import datetime
import json
import typing as T

from eth_typing import Address

from utils import logger
from wyndblast.api_headers import (
    WYNDBLAST_AUTHORIZATION_HEADER_KEY_FORMAT,
    WYNDBLAST_DAILY_ACTIVITIES_HEADERS,
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
from wyndblast.wyndblast_web2_client import WyndblastWeb2Client


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
