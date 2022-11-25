import copy
import json
import os
import typing as T

from config_admin import ADMIN_ADDRESS
from pumpskin.pumpskin_web2_client import PumpskinWeb2Client
from pumpskin.types import Rarity, Tokens
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client

MAX_PUMPSKINS = 6666
MAX_TOTAL_SUPPLY = 6666

ATTRIBUTES_FILE = "attributes.json"
COLLECTION_FILE = "collection.json"
RARITY_FILE = "rarity.json"

PUMPSKIN_ATTRIBUTES = {
    "Background": {},
    "Frame": {},
    "Body": {},
    "Neck": {},
    "Eyes": {},
    "Head": {},
    "Facial": {},
    "Item": {},
}


def get_json_path(file_name: str) -> str:
    this_dir = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(this_dir, file_name)
    return file_path


def calc_potn_from_level(level: int) -> int:
    return 50 * level**2


def calc_cooldown_from_level(level: int) -> int:
    return level + 1


def calc_ppie_per_day_from_level(level: int) -> int:
    return level + 3


def calc_ppie_earned_per_day(pumpskins: T.Dict[int, T.Dict[int, T.Any]]) -> int:
    return sum([calc_ppie_per_day_from_level(p.get("kg", 0) / 100) for _, p in pumpskins.items()])


def calc_roi_from_mint(ppie_price_usd: float, avax_usd: float, pumpskin_price_avax: float) -> float:
    ppie_accumulations = {1: {"days": 2.1, Tokens.PPIE: 8, Tokens.POTN: 12}}
    for level in range(2, 101):
        ppie_accumulations[level] = {}

        potn_per_day = 3 * calc_ppie_per_day_from_level(level)
        ppie_accumulations[level][Tokens.POTN] = (
            ppie_accumulations[level - 1][Tokens.POTN] + potn_per_day
        )

        cost_to_level = calc_potn_from_level(level)
        days_to_level = cost_to_level / ppie_accumulations[level][Tokens.POTN]
        ppie_while_waiting_to_level = days_to_level * calc_ppie_per_day_from_level(level)
        ppie_accumulations[level][Tokens.PPIE] = (
            ppie_accumulations[level - 1][Tokens.PPIE] + ppie_while_waiting_to_level
        )
        ppie_accumulations[level]["days"] = ppie_accumulations[level - 1]["days"] + days_to_level

    pumpskin_price_usd = pumpskin_price_avax * avax_usd
    ppie_per_pumpskin = pumpskin_price_usd / ppie_price_usd

    roi_days = ppie_accumulations[100]["days"]
    for level, stats in ppie_accumulations.items():
        if stats[Tokens.PPIE] > ppie_per_pumpskin:
            roi_days = stats["days"]
            break
    return roi_days


def get_mint_stats() -> T.Tuple[int, int]:
    w3: PumpskinNftWeb3Client = (
        PumpskinNftWeb3Client()
        .set_credentials(ADMIN_ADDRESS, "")
        .set_node_uri(AvalancheCWeb3Client.NODE_URL)
        .set_contract()
        .set_dry_run(False)
    )
    minted = w3.get_total_pumpskins_minted()
    supply = MAX_PUMPSKINS
    return (minted, supply)


def update_nft_collection_attributes(
    attributes_file: str,
    pumpskin_collection: str,
) -> T.Dict[int, float]:
    pumpskin_w2: PumpskinWeb2Client = PumpskinWeb2Client()
    pumpskins_info = {}
    pumpskins_stats = copy.deepcopy(PUMPSKIN_ATTRIBUTES)

    for pumpskin in range(MAX_TOTAL_SUPPLY):
        pumpskins_info[pumpskin] = pumpskin_w2.get_pumpskin_info(pumpskin)
        logger.print_normal(f"Processing pumpskin {pumpskin}...")
        for attribute in pumpskins_info[pumpskin].get("attributes", []):
            if attribute["trait_type"] not in pumpskins_stats:
                logger.print_fail(f"Unknown attribute: {attribute['trait_type']}")
                continue
            trait_type = attribute["trait_type"]
            trait_value = attribute["value"]
            pumpskins_stats[trait_type][trait_value] = (
                pumpskins_stats[trait_type].get(trait_value, 0) + 1
            )

    with open(attributes_file, "w") as outfile:
        json.dump(
            pumpskins_stats,
            outfile,
            indent=4,
            sort_keys=True,
        )
    with open(pumpskin_collection, "w") as outfile:
        json.dump(
            pumpskins_info,
            outfile,
            indent=4,
            sort_keys=True,
        )


def calculate_rarity(
    token_id: int,
    pumpskin_info: T.Dict[str, T.List[T.Dict[str, str]]],
    pumpskin_stats: T.Dict[str, T.Any],
) -> Rarity:
    pumpskin_rarity = {k: 0.0 for k in pumpskin_stats.keys()}
    pumpskin_traits = {k: 0.0 for k in pumpskin_stats.keys()}

    if "attributes" not in pumpskin_info:
        return {}

    for attribute in pumpskin_info["attributes"]:
        pumpskin_traits[attribute["trait_type"]] = attribute["value"]

    total_trait_count = 0
    for trait, values in pumpskin_stats.items():
        total_count = 0
        pumpkin_trait_count = 0
        for value, count in values.items():
            total_count += count
            if value == pumpskin_traits[trait]:
                pumpkin_trait_count = count
                total_trait_count += count

        rarity = float(pumpkin_trait_count) / total_count
        pumpskin_rarity[trait] = {"trait": pumpskin_traits[trait], "rarity": rarity}

    pumpskin_rarity["Overall"] = {
        "trait": None,
        "rarity": float(total_trait_count) / (total_count * len(pumpskin_stats.keys())),
    }

    return pumpskin_rarity


def calculate_rarity_from_query(token_id: int, attributes_file: str) -> Rarity:
    pumpskin_w2: PumpskinWeb2Client = PumpskinWeb2Client()
    pumpskin_info = pumpskin_w2.get_pumpskin_info(token_id)

    with open(attributes_file, "r") as infile:
        pumpskin_stats = json.load(infile)

    return calculate_rarity(token_id, pumpskin_info, pumpskin_stats)


def calculate_rarity_for_collection(
    rarity_file: str = None,
    save_to_disk: bool = False,
) -> T.Dict[int, float]:
    pumpskins_rarity = {}

    attributes_file = get_json_path(ATTRIBUTES_FILE)
    with open(attributes_file, "r") as infile:
        pumpskin_stats = json.load(infile)

    collections_file = get_json_path(COLLECTION_FILE)
    with open(collections_file, "r") as infile:
        collection_traits = json.load(infile)

    for pumpskin in range(MAX_TOTAL_SUPPLY):
        pumpskins_rarity[pumpskin] = calculate_rarity(
            pumpskin, collection_traits[str(pumpskin)], pumpskin_stats
        )

    sorted_pumpskins_rarity = dict(
        sorted(
            pumpskins_rarity.items(),
            key=lambda y: y[1].get("Overall", {"rarity": 1000.0})["rarity"],
        )
    )

    if save_to_disk and rarity_file is not None:
        with open(rarity_file, "w") as outfile:
            json.dump(
                sorted_pumpskins_rarity,
                outfile,
                indent=4,
            )

    return sorted_pumpskins_rarity
