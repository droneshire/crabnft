import copy
import json
import os
import requests
import typing as T

from eth_typing import Address

from utils import logger
from utils.discord import DISCORD_WEBHOOK_URL
from utils.file_util import make_sure_path_exists


class NftCollectionAnalyzerBase:
    ATTRIBUTES: T.Dict[str, T.Dict[T.Any, T.Any]] = {}
    MAX_TOTAL_SUPPLY = 0
    DISCORD_WEBHOOK = ""
    CONTRACT_ADDRESS: Address = ""

    def __init__(
        self,
        collection_name: str,
    ):
        self.collection_name = collection_name
        self.address = self.CONTRACT_ADDRESS
        self.discord_webhook = DISCORD_WEBHOOK_URL[self.DISCORD_WEBHOOK]

        this_dir = os.path.dirname(os.path.abspath(__file__))
        collection_dir = os.path.join(this_dir, "collections", collection_name)

        self.files = {
            "attributes": os.path.join(collection_dir, f"{collection_name}_attributes.json"),
            "collection": os.path.join(collection_dir, f"{collection_name}_collection.json"),
            "rarity": os.path.join(collection_dir, f"{collection_name}_rarity.json"),
        }

        for path in self.files.values():
            make_sure_path_exists(path)

    def _get_collection_info(self, token_id: int) -> T.Dict[T.Any, T.Any]:
        info = {}
        url = self.get_collection_uri(token_id)
        return self._get_request(url)

    def _get_request(
        self, url: str, headers: T.Dict[str, T.Any] = {}, params: T.Dict[str, T.Any] = {}
    ) -> T.Any:
        try:
            return requests.request("GET", url, params=params, headers=headers, timeout=5.0).json()
        except KeyboardInterrupt:
            raise
        except:
            return {}

    def get_collection_uri(self) -> str:
        """
        Should be overridden by derived class to query the contract for the ipfs-like base URI
        """
        raise NotImplementedError

    def save_nft_collection_attributes(self) -> None:
        collection_info = {}
        collection_stats = copy.deepcopy(self.ATTRIBUTES)

        for nft in range(self.MAX_TOTAL_SUPPLY):
            collection_info[nft] = self._get_collection_info(nft)
            logger.print_normal(f"Processing nft {nft}...")
            for attribute in collection_info[nft].get("attributes", []):
                if attribute["trait_type"] not in collection_stats:
                    logger.print_fail(f"Unknown attribute: {attribute['trait_type']}")
                    continue
                trait_type = attribute["trait_type"]
                trait_value = attribute["value"]
                collection_stats[trait_type][trait_value] = (
                    collection_stats[trait_type].get(trait_value, 0) + 1
                )

        with open(self.files["attributes"], "w") as outfile:
            json.dump(
                collection_stats,
                outfile,
                indent=4,
                sort_keys=True,
            )
        with open(self.files["collection"], "w") as outfile:
            json.dump(
                collection_info,
                outfile,
                indent=4,
                sort_keys=True,
            )

    def calculate_rarity(
        self,
        token_id: int,
        nft_info: T.Dict[str, T.List[T.Dict[str, str]]],
        collection_stats: T.Dict[str, T.Any],
    ) -> T.Dict[str, T.Dict[T.Any, T.Any]]:
        """
        Given the individual nft's attributes and the full collection stats,
        calculate the attributes rarity of said nft
        """
        nft_rarity = {k: 0.0 for k in collection_stats.keys()}
        nft_traits = {k: 0.0 for k in collection_stats.keys()}

        if "attributes" not in nft_info:
            return {}

        for attribute in nft_info["attributes"]:
            nft_traits[attribute["trait_type"]] = attribute["value"]

        total_trait_count = 0
        for trait, values in collection_stats.items():
            total_count = 0
            pumpkin_trait_count = 0
            for value, count in values.items():
                total_count += count
                if value == nft_traits[trait]:
                    pumpkin_trait_count = count
                    total_trait_count += count

            rarity = float(pumpkin_trait_count) / total_count
            nft_rarity[trait] = {"trait": nft_traits[trait], "rarity": rarity}

        nft_rarity["Overall"] = {
            "trait": None,
            "rarity": float(total_trait_count) / (total_count * len(collection_stats.keys())),
        }

        return nft_rarity

    def get_rarity_from_query(self, token_id: int) -> T.Dict[str, T.Dict[T.Any, T.Any]]:
        """
        Download info from the web source for a particular nft in the collection
        and get its attributes rarity
        """
        nft_info = self._get_collection_info(token_id)

        with open(self.files["attributes"], "r") as infile:
            collection_stats = json.load(infile)

        return self.calculate_rarity(token_id, nft_info, collection_stats)

    def get_full_collection_rarity(
        self,
        save_to_disk: bool = False,
    ) -> T.Dict[int, float]:
        """
        Use cached collection stats and collection attributes to calculate rarity
        for the entire collection and optionally save that to disk.

        Returns the cached rarity map for the entire collection
        """
        collection_rarity = {}

        if not os.path.isfile(self.files["attributes"]):
            raise ValueError("missing attributes file")

        with open(self.files["attributes"], "r") as infile:
            collection_stats = json.load(infile)

        if not os.path.isfile(self.files["attributes"]):
            raise ValueError("missing collections file")

        with open(self.files["collection"], "r") as infile:
            collection_traits = json.load(infile)

        for nft in range(self.MAX_TOTAL_SUPPLY):
            collection_rarity[nft] = self.calculate_rarity(
                nft, collection_traits[str(nft)], collection_stats
            )

        sorted_collection_rarity = dict(
            sorted(
                collection_rarity.items(),
                key=lambda y: y[1].get("Overall", {"rarity": 1000.0})["rarity"],
            )
        )

        if save_to_disk and self.files["rarity"] is not None:
            with open(self.files["rarity"], "w") as outfile:
                json.dump(
                    sorted_collection_rarity,
                    outfile,
                    indent=4,
                )

        return sorted_collection_rarity
