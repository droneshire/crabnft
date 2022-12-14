import os
import json
import typing as T

from eth_typing import Address
from eth_typing.encoding import HexStr
from web3 import Web3
from web3.types import TxParams, Wei

from mint_sniper.rarity import NftCollectionAnalyzerBase


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
    DISCORD_WEBHOOK = "DEEP_ALPHA_AHMC"
    CONTRACT_ADDRESS: Address = "0x66F703e48F68C03FFFEE0eAee7BE2fE411cB3713"

    def __init__(
        self,
    ):
        super().__init__("avalanche_hills_muscle_cars")

    def get_collection_uri(self) -> str:
        """
        Should be overridden by derived class to query the contract for the ipfs-like base URI
        """
        raise NotImplementedError
