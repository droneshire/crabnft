import json
import os
import typing as T

from utils import logger
from wyndblast.pve_google_storage_web2_client import PveGoogleStorageWeb2Client
from wyndblast.types import AccountLevels, LevelsInformation, WyndLevelsStats, Skills
from wyndblast.wyndblast_web2_client import WyndblastWeb2Client


def get_cache_info(
    log_dir: str,
) -> T.Tuple[
    T.List[LevelsInformation], T.List[AccountLevels], T.Any, WyndLevelsStats, T.List[Skills]
]:
    google_w2: PveGoogleStorageWeb2Client = PveGoogleStorageWeb2Client(
        "",
        "",
        dry_run=False,
    )

    json_file = os.path.join(log_dir, "stages_info.json")
    if os.path.isfile(json_file):
        with open(json_file) as infile:
            stages_info: T.List[LevelsInformation] = json.load(infile)["data"]
    else:
        logger.print_normal("Caching stages info...")
        stages_info: T.List[LevelsInformation] = google_w2.get_level_data()
        with open(json_file, "w") as outfile:
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

    json_file = os.path.join(log_dir, "enemy_info.json")
    if os.path.isfile(json_file):
        with open(json_file) as infile:
            enemy_info: T.Any = json.load(infile)["data"]
    else:
        logger.print_normal("Caching enemy data info...")
        enemy_info: T.Any = google_w2.get_enemy_data()
        with open(json_file, "w") as outfile:
            data = {"data": enemy_info}
            json.dump(data, outfile, indent=4)

    json_file = os.path.join(log_dir, "skills_info.json")
    if os.path.isfile(json_file):
        with open(json_file) as infile:
            skills_info: WyndLevelsStats = json.load(infile)["data"]
    else:
        logger.print_normal("Caching skills info...")
        skills_info: WyndLevelsStats = google_w2.get_skill_data()
        with open(json_file, "w") as outfile:
            data = {"data": skills_info}
            json.dump(data, outfile, indent=4)

    json_file = os.path.join(log_dir, "wynd_level_info.json")
    if os.path.isfile(json_file):
        with open(json_file) as infile:
            wynd_info: T.List[Skills] = json.load(infile)["data"]
    else:
        logger.print_normal("Caching wynd level info...")
        wynd_info: T.List[Skills] = google_w2.get_wynd_level_stats_data()
        with open(json_file, "w") as outfile:
            data = {"data": wynd_info}
            json.dump(data, outfile, indent=4)

    return stages_info, account_info, enemy_info, skills_info, wynd_info
