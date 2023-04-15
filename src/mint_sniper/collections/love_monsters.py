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
from mint_sniper.constants import IPFS_BASE_URL
from mint_sniper.rarity import NftCollectionAnalyzerBase
from utils import logger
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.web3_client import Web3Client


class LoveMonstersWeb3Client(AvalancheCWeb3Client):
    """
    Interact with a smart contract of the LoveMonsters collection
    https://snowtrace.io/token/0x07e741cf962ef140cba9b15b7e6af7f31f3ed04d
    """

    contract_address = T.cast(
        Address, "0x07E741cf962Ef140cbA9B15B7E6AF7F31F3eD04D"
    )
    this_dir = os.path.dirname(os.path.realpath(__file__))
    module_dir = os.path.dirname(this_dir)
    abi_dir = os.path.join(
        os.path.dirname(module_dir),
        "web3_utils",
        "abi",
        "abi-love-monsters.json",
    )
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def get_base_uri(self) -> str:
        try:
            return self.contract.functions.tokenURIPrefix().call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""


class LoveMonstersMint(NftCollectionAnalyzerBase):
    ATTRIBUTES: T.Dict[str, T.Dict[T.Any, T.Any]] = {
        "SOURCE": {},
        "BACKGROUND": {},
        "BACK": {},
        "HEAD": {},
        "BODY": {},
        "SPOTS": {},
        "SPIKES": {},
        "EYES": {},
        "PUPILS": {},
        "ACCESSORIES": {},
        "BACK GEAR": {},
        "HEAD SPIKES": {},
        "RARITY": {},
    }
    CUSTOM_INFO: T.Dict[str, int] = {
        "emission_multiple": -1,
        "token_id": -1,
    }
    TOKEN_ID_KEY = "edition"
    MAX_TOTAL_SUPPLY = 3333
    MAX_PER_BATCH = 33
    DISCORD_WEBHOOK = "LOVE_MONSTER"
    CONTRACT_ADDRESS: Address = "0x07E741cf962Ef140cbA9B15B7E6AF7F31F3eD04D"

    def __init__(self, force: bool = False):
        super().__init__("love_monsters", force, try_all_mints=True)
        self.w3: LoveMonstersWeb3Client = T.cast(
            LoveMonstersWeb3Client,
            (
                LoveMonstersWeb3Client()
                .set_credentials(ADMIN_ADDRESS, "")
                .set_node_uri(AvalancheCWeb3Client.NODE_URL)
                .set_contract()
            ),
        )

        self.collection_uri = (
            IPFS_BASE_URL + self.w3.get_base_uri().split(":")[1]
        )

    def get_token_uri(self, token_id: int) -> str:
        """
        Should be overridden by derived class to query the contract for the ipfs-like base URI
        """
        return f"{self.collection_uri}{token_id}.json"

    def custom_nft_info(self, token_id: int) -> T.Dict[str, T.Any]:
        return {}
