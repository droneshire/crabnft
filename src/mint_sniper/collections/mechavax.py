import json
import os
import time
import typing as T

from eth_typing import Address
from eth_typing.encoding import HexStr
from web3 import Web3

from config_admin import ADMIN_ADDRESS
from joepegs.joepegs_api import JoePegsClient
from mechavax.mechavax_web3client import MechContractWeb3Client
from mint_sniper.rarity import NftCollectionAnalyzerBase
from utils import logger
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.web3_client import Web3Client


class MechavaxMint(NftCollectionAnalyzerBase):
    ATTRIBUTES: T.Dict[str, T.Dict[T.Any, T.Any]] = {
        "Background": {},
        "Arms": {},
        "Body": {},
        "Legs": {},
        "Weapon": {},
        "Helmet": {},
        "Element": {},
        "Wings": {},
        "Aura": {},
        "Custom": {},
        "1/1": {},
        "Artist": {},
    }
    CUSTOM_INFO: T.Dict[str, int] = {
        "emission_multiple": -1,
        "token_id": -1,
    }
    TOKEN_ID_KEY = "edition"
    MAX_TOTAL_SUPPLY = 4500
    DISCORD_WEBHOOK = "DEEP_ALPHA_MINT_MINER"
    CONTRACT_ADDRESS: Address = "0xB68f42c2c805b81DaD78d2f07244917431c7F322"

    def __init__(self, force: bool = False):
        super().__init__("mechavax", force, try_all_mints=True)
        self.w3: MechContractWeb3Client = T.cast(
            MechContractWeb3Client,
            (
                MechContractWeb3Client()
                .set_credentials(ADMIN_ADDRESS, "")
                .set_node_uri(AvalancheCWeb3Client.NODE_URL)
                .set_contract()
            ),
        )

        self.collection_uri = self.w3.get_base_uri()
        self.jp_api = JoePegsClient()
        self.collection_map = self.map_tokens_to_name(use_cache=not force)

    def map_tokens_to_name(self, use_cache: bool = False) -> T.Dict[int, int]:
        data = {}
        collection_dir = os.path.dirname(self.files["rarity"])
        filename = os.path.join(collection_dir, "token_to_name_map.json")
        if os.path.isfile(filename):
            with open(filename) as infile:
                data = json.load(infile)

        if use_cache:
            return data

        return self.get_data(data, filename)

    def get_data(
        self, collection: T.Dict[int, int], filename: str
    ) -> T.Dict[int, int]:
        fails = 0
        try:
            for token_id in range(self.MAX_TOTAL_SUPPLY):

                jp_id = None

                if token_id in collection.values():
                    logger.print_ok_blue(
                        f"Already have {token_id}, skipping..."
                    )
                    continue

                for i in range(1, 5):
                    item = self.jp_api.get_item(self.CONTRACT_ADDRESS, token_id)

                    if "detail" in item:
                        logger.print_warn(f"No data for {token_id}")
                        break

                    if item and "metadata" in item:
                        break
                    else:
                        logger.print_warn(f"No data for {token_id}")
                        time.sleep(i * 20.0)
                        continue

                if item and "metadata" in item and item["metadata"] is None:
                    continue

                try:
                    jp_id = os.path.basename(
                        item["metadata"]["tokenUri"]
                    ).split(".")[0]
                except:
                    logger.print_fail(f"Failed to parse ids {item}")

                if jp_id:
                    logger.print_normal(f"Found {token_id}")
                    collection[jp_id] = token_id
        finally:
            with open(filename, "w") as outfile:
                json.dump(collection, outfile, indent=4)

        return collection

    def get_token_uri(self, token_id: int) -> str:
        """
        Should be overridden by derived class to query the contract for the ipfs-like base URI
        """
        return f"{self.collection_uri}{token_id}.json"

    def custom_nft_info(self, token_id: int) -> T.Dict[str, T.Any]:
        real_token_id = self.collection_map.get(str(token_id), -1)
        self.CUSTOM_INFO["emission_multiple"] = self.w3.get_mech_multiplier(
            real_token_id
        )
        self.CUSTOM_INFO["token_id"] = real_token_id
        return self.CUSTOM_INFO
