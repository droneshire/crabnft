from __future__ import annotations

import os
import typing as T
from eth_typing import Address
from eth_typing.encoding import HexStr
from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3.types import TxParams, Wei

from utils.price import Cra
from utils.price import cra_to_wei, wei_to_cra
from web3_utils.swimmer_network_web3_client import SwimmerNetworkClient
from web3_utils.web3_client import Web3Client


class CraSwimmerWeb3Client(SwimmerNetworkClient):
    """
    Interact with the CRA token on Swimmer Network
    """

    contract_address = T.cast(Address, "0xC1a1F40D558a3E82C3981189f61EF21e17d6EB48")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(this_dir, "abi", "abi-erc20.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def get_balance(self) -> Cra:
        try:
            balance = self.contract.functions.balanceOf(address).call()
        except KeyboardInterrupt:
            raise
        except:
            return 0
        return wei_to_cra(balance)

    def transfer_tus(self, to_address: Address, cra: Cra) -> HexStr:
        tx: TxParams = self.build_contract_transaction(
            self.contract.functions.transfer(Web3.toChecksumAddress(to_address), cra_to_wei(cra))
        )
        return self.sign_and_send_transaction(tx)
