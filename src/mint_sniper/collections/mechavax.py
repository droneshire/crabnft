import os
import time
import typing as T

from eth_typing import Address
from eth_typing.encoding import HexStr
from web3 import Web3

from config_admin import ADMIN_ADDRESS
from joepegs.joepegs_api import JoePegsClient
from mint_sniper.rarity import NftCollectionAnalyzerBase
from utils import logger
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.web3_client import Web3Client


class MechavaxWeb3Client(AvalancheCWeb3Client):
    """
    Interact with a smart contract of the Mechavax collection
    https://snowtrace.io/address/0xB68f42c2c805b81DaD78d2f07244917431c7F322
    """

    contract_address = T.cast(Address, "0xB68f42c2c805b81DaD78d2f07244917431c7F322")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    module_dir = os.path.dirname(this_dir)
    abi_dir = os.path.join(os.path.dirname(module_dir), "web3_utils", "abi", "abi-mechavax.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def get_base_uri(self) -> HexStr:
        try:
            return self.contract.functions.BASE_URI().call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def get_mech_multiplier(self, token_id: int) -> int:
        try:
            return self.contract.functions.getMechEmissionMultiple(token_id).call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return -1


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
        self.w3: MechavaxWeb3Client = T.cast(
            MechavaxWeb3Client,
            (
                MechavaxWeb3Client()
                .set_credentials(ADMIN_ADDRESS, "")
                .set_node_uri(AvalancheCWeb3Client.NODE_URL)
                .set_contract()
            ),
        )

        self.collection_uri = self.w3.get_base_uri()
        self.jp_api = JoePegsClient()

    def get_token_uri(self, token_id: int) -> str:
        """
        Should be overridden by derived class to query the contract for the ipfs-like base URI
        """
        return f"{self.collection_uri}{token_id}.json"

    def custom_nft_info(self, token_id: int) -> T.Dict[str, T.Any]:
        self.CUSTOM_INFO["emission_multiple"] = self.w3.get_mech_multiplier(token_id)
        self.CUSTOM_INFO["token_id"] = -1

        item = self.jp_api.get_item(self.CONTRACT_ADDRESS, token_id)
        if item and "tokenId" in item:
            self.CUSTOM_INFO["token_id"] = int(item.get("tokenId", -1))
        else:
            logger.print_warn(f"No data for {token_id}:\n{item}")
        time.sleep(0.25)

        return self.CUSTOM_INFO
