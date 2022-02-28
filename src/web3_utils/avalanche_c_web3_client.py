from __future__ import annotations

from web3.middleware import geth_poa_middleware

from web3_utils.web3_client import Web3Client


class AvalancheCWeb3Client(Web3Client):
    """
    Client to interact with the Avalanche blockchain and
    its smart contracts.
    """

    chain_id: int = 43114
    gas_limit: int = 450000  # sensible value for Avalanche
    max_priority_fee_per_gas_in_gwei: int = 2

    def set_node_uri(self, node_uri: str = None) -> AvalancheCWeb3Client:
        """
        Inject the POA middleware
        """
        super().set_node_uri(node_uri)
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        return self
