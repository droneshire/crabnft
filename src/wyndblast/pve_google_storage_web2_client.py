import copy
import json
import time
import typing as T

from eth_typing import Address

from config_admin import ADMIN_ADDRESS
from utils import logger
from wyndblast.api_headers import (
    WYNDBLAST_PVE_GOOGLESTORAGE_HEADERS,
    GOOGLE_STORAGE_X_CLIENT_DATA_KEYS,
)
from wyndblast.types import AccountLevels, LevelsInformation, PveWynd, Skills, WyndLevelsStats
from wyndblast.wyndblast_web2_client import WyndblastWeb2Client


class PveGoogleStorageWeb2Client(WyndblastWeb2Client):
    def __init__(self, dry_run: bool = False) -> None:
        super().__init__(
            "dummy",
            ADMIN_ADDRESS,
            WyndblastWeb2Client.GOOGLE_STORAGE_URL,
            rate_limit_delay=0.0,
            use_proxy=False,
            dry_run=dry_run,
        )

    def _get_google_pve_headers(
        self, x_client: str = GOOGLE_STORAGE_X_CLIENT_DATA_KEYS["pve"]
    ) -> T.Dict[str, str]:
        headers = copy.deepcopy(WYNDBLAST_PVE_GOOGLESTORAGE_HEADERS)
        headers["x-client-data"] = x_client
        return headers

    def _get_all_enemies_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.base_url + f"/PvE-enemy.json"
        default_params = {
            "v": self._get_server_time(),
        }
        default_params.update(params)

        return self._get_request(url, headers=headers, params=default_params, timeout=10.0)

    def get_all_enemies(self) -> T.List[PveWynd]:
        try:
            res = self._get_all_enemies_raw(headers=self._get_google_pve_headers())
            return res
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get enemies list!")
            if res:
                logger.print_normal(f"{res}")
            return False

    def _get_account_stats_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.base_url + f"/account-stats.json"
        default_params = {
            "v": self._get_server_time(),
        }
        default_params.update(params)

        return self._get_request(url, headers=headers, params=default_params, timeout=10.0)

    def get_account_stats(self) -> T.List[AccountLevels]:
        try:
            res = self._get_account_stats_raw(headers=self._get_google_pve_headers())
            return res
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get account stats list!")
            if res:
                logger.print_normal(f"{res}")
            return False

    def _get_level_data_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.base_url + f"/PvE-stages.json"
        default_params = {
            "v": self._get_server_time(),
        }
        default_params.update(params)

        return self._get_request(url, headers=headers, params=default_params, timeout=10.0)

    def get_level_data(self) -> T.List[LevelsInformation]:
        try:
            res = self._get_level_data_raw(headers=self._get_google_pve_headers())
            return res
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get level stats list!")
            if res:
                logger.print_normal(f"{res}")
            return False

    def _get_enemy_data_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.base_url + f"/PvE-enemy.json"
        default_params = {
            "v": self._get_server_time(),
        }
        default_params.update(params)

        return self._get_request(url, headers=headers, params=default_params, timeout=10.0)

    def get_enemy_data(self) -> T.Any:
        try:
            res = self._get_level_data_raw(headers=self._get_google_pve_headers())
            return res
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get level stats list!")
            if res:
                logger.print_normal(f"{res}")
            return False

    def _get_wynd_level_stats_data_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.base_url + "wynd-level-stats.json"
        default_params = {
            "v": self._get_server_time(),
        }
        default_params.update(params)

        return self._get_request(url, headers=headers, params=default_params, timeout=10.0)

    def get_wynd_level_stats_data(self) -> WyndLevelsStats:
        try:
            res = self._get_level_data_raw(headers=self._get_google_pve_headers())
            return res
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get level stats list!")
            if res:
                logger.print_normal(f"{res}")
            return False

    def _get_skills_data_raw(
        self,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
    ) -> T.Any:
        url = self.base_url + "skills.json"
        default_params = {
            "v": self._get_server_time(),
        }
        default_params.update(params)

        return self._get_request(url, headers=headers, params=default_params, timeout=10.0)

    def get_skill_data(self) -> T.List[Skills]:
        try:
            res = self._get_level_data_raw(headers=self._get_google_pve_headers())
            return res
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"Failed to get level stats list!")
            if res:
                logger.print_normal(f"{res}")
            return False
