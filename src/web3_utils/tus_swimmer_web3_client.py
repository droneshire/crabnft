from __future__ import annotations

import os
import typing as T
from eth_typing import Address
from eth_typing.encoding import HexStr
from web3.middleware import geth_poa_middleware
from web3.types import TxParams, Wei

from utils.price import Tus
from utils.price import tus_to_wei, wei_to_token
from web3_utils.swimmer_network_web3_client import SwimmerNetworkClient
from web3_utils.web3_client import Web3Client


class TusSwimmerWeb3Client(SwimmerNetworkClient):
    """
    Interact with the native TUS token on Swimmer Network
    """

    def get_balance(self) -> Tus:
        try:
            balance = self.w3.eth.get_balance(self.user_address)
        except KeyboardInterrupt:
            raise
        except:
            return 0
        return wei_to_token(balance)

    def transfer_token(self, to_address: Address, tus: Tus) -> HexStr:
        tx: TxParams = self.build_transaction_with_value_in_wei(to_address, tus_to_wei(tus))
        return self.sign_and_send_transaction(tx)
