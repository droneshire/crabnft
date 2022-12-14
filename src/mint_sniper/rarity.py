import os
import json
import typing as T

from eth_typing import Address
from eth_typing.encoding import HexStr
from web3 import Web3
from web3.types import TxParams, Wei

from utils import logger
from utils.discord import DISCORD_WEBHOOK_URL
from utils.file_util import make_sure_path_exists




class NftCollectionAnalyzerBase:
    ATTRIBUTES_FILE = "attributes.json"
    COLLECTION_FILE = "collection.json"
    RARITY_FILE = "rarity.json"
    ATTRIBUTES = {}

    def __init__(
        self,
        collection_name: str,
        address: Address,
        discord_webhook: str,
        attributes_dict: T.Dict[str, T.Dict[T.Any, T.Any]],
    ):
        self.collection_name = collection_name
        self.address = address
        self.discord_webhook = DISCORD_WEBHOOK_URL[discord_webhook]

        this_dir = os.path.dirname(os.path.abspath(__file__))
        collection_dir = os.path.join(this_dir, "collections", collection_name)

        self.files = {
            "attributes": os.path.join(collection_dir, f"{collection_name}_{ATTRIBUTES_FILE}"),
            "collection": os.path.join(collection_dir, f"{collection_name}_{COLLECTION_FILE}"),
            "rarity": os.path.join(collection_dir, f"{collection_name}_{RARITY_FILE}"),
        }

        for path in self.files.keys():
            make_sure_path_exists(path)

    def get_collection_uri(self) -> str:
        raise NotImplementedError

    def update_nft_collection_attributes(
        self,
        attributes_file: str,
        pumpskin_collection: str,
    ) -> T.Dict[int, float]:
        pumpskin_w2: PumpskinWeb2Client = PumpskinWeb2Client()
        pumpskins_info = {}
        pumpskins_stats = copy.deepcopy(self.ATTRIBUTES)

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
        self,
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

    def calculate_rarity_from_query(self, token_id: int, attributes_file: str) -> Rarity:
        pumpskin_w2: PumpskinWeb2Client = PumpskinWeb2Client()
        pumpskin_info = pumpskin_w2.get_pumpskin_info(token_id)

        with open(attributes_file, "r") as infile:
            pumpskin_stats = json.load(infile)

        return calculate_rarity(token_id, pumpskin_info, pumpskin_stats)

    def calculate_rarity_for_collection(
        self,
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
