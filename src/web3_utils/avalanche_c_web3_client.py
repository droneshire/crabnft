from __future__ import annotations

from eth_typing import Address
from utils.price import Avax
from eth_typing.encoding import HexStr
from web3.middleware import geth_poa_middleware
from web3.types import TxParams, Wei
from web3_utils.web3_client import Web3Client

from utils.price import token_to_wei, wei_to_token, TokenWei

MAX_UINT256 = 2**256 - 1


class AvalancheCWeb3Client(Web3Client):
    """
    Client to interact with the Avalanche blockchain and
    its smart contracts.
    """

    chain_id: int = hex(43114)
    gas_limit: int = 400000  # sensible value for Avalanche
    tx_type: int = 0x02
    max_priority_fee_per_gas_in_gwei: int = 2
    NODE_URL = "https://api.avax.network/ext/bc/C/rpc"

    def set_node_uri(self, node_uri: str = None) -> AvalancheCWeb3Client:
        """
        Inject the POA middleware
        """
        super().set_node_uri(node_uri)
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        return self

    def approve(self, max_amount: int = MAX_UINT256) -> HexStr:
        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.approve(self.contract_checksum_address, max_amount)
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

    def get_balance(self) -> float:
        try:
            balance = self.contract.functions.balanceOf(self.user_address).call()
        except KeyboardInterrupt:
            raise
        except:
            return 0.0
        return wei_to_token(balance)

    def transfer_token(self, to_address: Address, token: TokenWei) -> HexStr:
        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.transfer(to_address, token_to_wei(token))
            )
            return self.sign_and_send_transaction(tx)
        except KeyboardInterrupt:
            raise
        except:
            return ""
