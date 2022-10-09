from __future__ import annotations

import os
import typing as T
from eth_typing import Address
from eth_typing.encoding import HexStr
from web3.middleware import geth_poa_middleware
from web3.types import TxParams, Wei

from utils.price import Tus
from utils.price import token_to_wei, wei_to_token
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.web3_client import Web3Client


class PpieWeb3Client(AvalancheCWeb3Client):
    """
    Interact with the PPIE token
    """

    contract_address = T.cast(Address, "0x325A9463E93aB79bf0302353c99EF70f43f33637")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    # standard erc20 token abi so reusing tus
    abi_dir = os.path.join(this_dir, "abi", "abi-tus.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def get_balance(self) -> Tus:
        try:
            balance = self.contract.functions.balanceOf(self.user_address).call()
        except KeyboardInterrupt:
            raise
        except:
            return 0
        return wei_to_token(balance)

    def transfer_token(self, to_address: Address, tus: Tus) -> HexStr:
        tx: TxParams = self.build_contract_transaction(
            self.contract.functions.transfer(to_address, token_to_wei(tus))
        )
        return self.sign_and_send_transaction(tx)
