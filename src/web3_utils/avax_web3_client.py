from __future__ import annotations

import os
import typing as T
from eth_typing import Address
from eth_typing.encoding import HexStr
from web3.types import TxParams

from utils.price import Avax
from utils.price import token_to_wei, wei_to_token
from web3_utils.web3_client import Web3Client

MAX_UINT256 = 2**256 - 1


class AvaxCWeb3Client(Web3Client):
    """
    Client to interact with the AVAX token
    """

    WAVAX_ADDRESS = "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7"

    def get_balance(self) -> Avax:
        try:
            balance = self.w3.eth.get_balance(self.user_address)
        except KeyboardInterrupt:
            raise
        except:
            return 0
        return wei_to_token(balance)

    def approve(self, max_amount: int = MAX_UINT256) -> HexStr:
        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.approve(
                    self.contract_checksum_address, max_amount
                )
            )
            return self.sign_and_send_transaction(tx)
        except KeyboardInterrupt:
            raise
        except:
            return ""

    def is_allowed(self) -> bool:
        try:
            return (
                self.contract.functions.allowance(
                    self.user_address, self.contract_checksum_address
                ).call()
                > 0
            )
        except KeyboardInterrupt:
            raise
        except:
            return False

    def transfer_token(self, to_address: Address, token: TokenWei) -> HexStr:
        try:
            tx: TxParams = self.build_transaction_with_value_in_wei(
                to_address, token_to_wei(avax)
            )
            return self.sign_and_send_transaction(tx)
        except KeyboardInterrupt:
            raise
        except:
            return ""

    def unwrap(self, amount: float) -> HexStr:
        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.withdraw(amount)
            )
            return self.sign_and_send_transaction(tx)
        except KeyboardInterrupt:
            raise
        except:
            return ""
