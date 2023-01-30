import os
import json
import typing as T

from eth_typing import Address
from eth_typing.encoding import HexStr
from web3 import Web3
from web3.types import TxParams, Wei

from utils import logger
from utils.price import wei_to_token, TokenWei
from web3_utils.web3_client import Web3Client
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from pumpskin.types import StakedPumpskin


class MechArmContractWeb3Client(AvalancheCWeb3Client):
    """
    https://snowtrace.io/address/0x311E1a6c9190fA6847dC6B4617AE36c1277Fb24b
    """

    contract_address = T.cast(Address, "0x311E1a6c9190fA6847dC6B4617AE36c1277Fb24b")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(
        os.path.dirname(this_dir), "web3_utils", "abi", "abi-mech-blank-armament.json"
    )
    abi = Web3Client._get_contract_abi_from_file(abi_dir)


class MechContractWeb3Client(AvalancheCWeb3Client):
    """
    https://snowtrace.io/address/0xB68f42c2c805b81DaD78d2f07244917431c7F322
    """

    contract_address = T.cast(Address, "0xB68f42c2c805b81DaD78d2f07244917431c7F322")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(os.path.dirname(this_dir), "web3_utils", "abi", "abi-mechavax.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def get_minted_shk_mechs(self) -> int:
        try:
            return self.contract.functions.numMintedFromShirak().call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0

    def get_num_mechs(self, address: Address) -> int:
        address = Web3.toChecksumAddress(address)
        try:
            data: T.List[T.Any] = self.contract.functions.getUserData(address).call()
            return data[0]
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0

    def get_emmissions_multiplier(self, address: Address) -> float:
        address = Web3.toChecksumAddress(address)
        try:
            data: T.List[T.Any] = self.contract.functions.getUserData(address).call()
            return data[1] / 10.0
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0.0

    def get_deposited_shk(self, address: Address) -> float:
        address = Web3.toChecksumAddress(address)
        try:
            shirak: TokenWei = self.contract.functions.shirakBalance(address).call()
            return wei_to_token(shirak)
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0

    def get_min_mint_bid(self) -> float:
        try:
            price: TokenWei = self.contract.functions.mechPrice().call()
            return wei_to_token(price)
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0.0
