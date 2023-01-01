import json
import os
import typing as T

from utils import logger
from wyndblast.pve_google_storage_web2_client import PveGoogleStorageWeb2Client
from wyndblast.types import AccountLevels, LevelsInformation
from wyndblast.wyndblast_web2_client import WyndblastWeb2Client


def get_cache_info(
    log_dir: str,
) -> T.Tuple[T.List[LevelsInformation], T.List[AccountLevels]]:
    google_w2: PveGoogleStorageWeb2Client = PveGoogleStorageWeb2Client(
        "",
        "",
        WyndblastWeb2Client.GOOGLE_STORAGE_URL,
        dry_run=False,
    )

    stages_info_file = os.path.join(log_dir, "stages_info.json")
    if os.path.isfile(stages_info_file):
        with open(stages_info_file) as infile:
            stages_info: T.List[LevelsInformation] = json.load(infile)["data"]
    else:
        logger.print_normal("Caching stages info...")
        stages_info: T.List[LevelsInformation] = google_w2.get_level_data()
        with open(stages_info_file, "w") as outfile:
            data = {"data": stages_info}
            json.dump(data, outfile, indent=4)

    account_info_file = os.path.join(log_dir, "account_info.json")
    if os.path.isfile(account_info_file):
        with open(account_info_file) as infile:
            account_info: T.List[AccountLevels] = json.load(infile)["data"]
    else:
        logger.print_normal("Caching account info...")
        account_info: T.List[AccountLevels] = google_w2.get_account_stats()
        with open(account_info_file, "w") as outfile:
            data = {"data": account_info}
            json.dump(data, outfile, indent=4)

    return stages_info, account_info
