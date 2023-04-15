import os
import typing as T

from eth_typing import Address
from eth_typing.encoding import HexStr
from web3 import Web3

from config_admin import ADMIN_ADDRESS
from mint_sniper.rarity import NftCollectionAnalyzerBase
from utils import logger
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.web3_client import Web3Client


class AhmcWeb3Client(AvalancheCWeb3Client):
    """
    Interact with a smart contract of the AHMC collection
    https://snowtrace.io/address/0x66F703e48F68C03FFFEE0eAee7BE2fE411cB3713
    """

    contract_address = T.cast(
        Address, "0x66F703e48F68C03FFFEE0eAee7BE2fE411cB3713"
    )
    this_dir = os.path.dirname(os.path.realpath(__file__))
    module_dir = os.path.dirname(this_dir)
    abi_dir = os.path.join(
        os.path.dirname(module_dir), "web3_utils", "abi", "abi-ahcp-nft.json"
    )
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def get_token_uri(self, token_id: int) -> HexStr:
        try:
            return self.contract.functions.tokenURI(token_id).call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""


class AhmcMint(NftCollectionAnalyzerBase):
    ATTRIBUTES: T.Dict[str, T.Dict[T.Any, T.Any]] = {
        "Background": {},
        "Body Style": {},
        "Brake Calipers": {},
        "Charm": {},
        "Decal": {},
        "Exhaust": {},
        "Headlights": {},
        "Hood": {},
        "Neon Effects": {},
        "Spoiler": {},
        "Wheels": {},
    }
    MAX_TOTAL_SUPPLY = 10000
    DISCORD_WEBHOOK = "DEEP_ALPHA_MINT_MINER"
    CONTRACT_ADDRESS: Address = "0x66F703e48F68C03FFFEE0eAee7BE2fE411cB3713"

    def __init__(self, force: bool = False):
        super().__init__(
            "avalanche_hills_muscle_cars", force, try_all_mints=False
        )
        self.w3: AhmcWeb3Client = T.cast(
            AhmcWeb3Client,
            (
                AhmcWeb3Client()
                .set_credentials(ADMIN_ADDRESS, "")
                .set_node_uri(AvalancheCWeb3Client.NODE_URL)
                .set_contract()
            ),
        )

        self.collection_uri = self.w3.get_token_uri(0).split("?")[0]

    def get_token_uri(self, token_id: int) -> str:
        """
        Should be overridden by derived class to query the contract for the ipfs-like base URI
        """
        return f"{self.collection_uri}?id={token_id}"
