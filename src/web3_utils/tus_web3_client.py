from __future__ import annotations

import os
import typing as T
from eth_typing import Address
from eth_typing.encoding import HexStr
from web3.middleware import geth_poa_middleware
from web3.types import TxParams, Wei

from utils.price import Tus
from utils.price import tus_to_wei, wei_to_tus
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.web3_client import Web3Client


class TusWeb3Client(AvalancheCWeb3Client):
    """
    Interact with the TUS token
    """

    contract_address = T.cast(Address, "0xf693248f96fe03422fea95ac0afbbbc4a8fdd172")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(this_dir, "abi", "abi-tus.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def get_balance(self) -> Tus:
        try:
            balance = self.contract.functions.balanceOf(self.user_address).call()
        except KeyboardInterrupt:
            raise
        except:
            return 0
        return wei_to_tus(balance)

    def transfer_tus(self, to_address: Address, tus: Tus) -> HexStr:
        tx: TxParams = self.build_contract_transaction(
            self.contract.functions.transfer(to_address, tus_to_wei(tus))
        )
        return self.sign_and_send_transaction(tx)
