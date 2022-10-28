from __future__ import annotations

from eth_typing import Address
from utils.price import Avax
from web3.middleware import geth_poa_middleware
from web3_utils.web3_client import Web3Client


class AvalancheCWeb3Client(Web3Client):
    """
    Client to interact with the Avalanche blockchain and
    its smart contracts.
    """

    TUS_CONTRACT_ADDRESS = Address("0xf693248F96Fe03422FEa95aC0aFbBBc4a8FdD172")
    CRA_CONTRACT_ADDRESS = Address("0xA32608e873F9DdEF944B24798db69d80Bbb4d1ed")

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
