from __future__ import annotations

from eth_typing import Address
from eth_typing.encoding import HexStr
from web3.middleware import geth_poa_middleware
from web3.types import TxParams
from web3_utils.web3_client import Web3Client

from utils.price import token_to_wei, wei_to_token, TokenWei


class SwimmerNetworkClient(Web3Client):
    """
    Client to interact with the Avalanche blockchain and
    its smart contracts.
    """

    chain_id: int = 73772
    tx_type: int = 0x01
    max_priority_fee_per_gas_in_gwei: int = 1
    NODE_URL = "https://subnets.avax.network/swimmer/mainnet/rpc"

    def set_node_uri(self, node_uri: str = None) -> SwimmerNetworkClient:
        """
        Inject the POA middleware
        """
        super().set_node_uri(node_uri)
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        return self

    def get_balance(self) -> TokenWei:
        try:
            balance = self.contract.functions.balanceOf(
                self.user_address
            ).call()
        except KeyboardInterrupt:
            raise
        except:
            return 0
        return wei_to_token(balance)

    def transfer_token(self, to_address: Address, token: TokenWei) -> HexStr:
        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.transfer(
                    to_address, token_to_wei(token)
                )
            )
            return self.sign_and_send_transaction(tx)
        except KeyboardInterrupt:
            raise
        except:
            return ""
