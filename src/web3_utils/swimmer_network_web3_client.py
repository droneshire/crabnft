from __future__ import annotations


from eth_typing import Address
from web3.middleware import geth_poa_middleware
from web3_utils.web3_client import Web3Client


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
