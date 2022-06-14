from __future__ import annotations

import os
import typing as T
from eth_typing import Address
from eth_typing.encoding import HexStr
from web3.middleware import geth_poa_middleware
from web3.types import TxParams, Wei

from utils.price import Chro
from utils.price import chro_to_wei, wei_to_chro
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.web3_client import Web3Client


class ChroWeb3Client(AvalancheCWeb3Client):
    """
    Interact with the Chro token
    """

    contract_address = T.cast(Address, "0xbf1230bb63bfD7F5D628AB7B543Bcefa8a24B81B")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(this_dir, "abi", "abi-chro.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def get_balance(self) -> chro:
        try:
            balance = self.contract.functions.balanceOf(self.user_address).call()
        except KeyboardInterrupt:
            raise
        except:
            return 0
        return wei_to_chro(balance)

    def transfer_chro(self, to_address: Address, chro: Chro) -> HexStr:
        tx: TxParams = self.build_contract_transaction(
            self.contract.functions.transfer(to_address, chro_to_wei(chro))
        )
        return self.sign_and_send_transaction(tx)
