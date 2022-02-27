from __future__ import annotations

from web3.middleware import geth_poa_middleware

from web3_utils.web3_client import Web3Client


class AvalancheCWeb3Client(Web3Client):
    """
    Client to interact with the Avalanche blockchain and
    its smart contracts.
    """

    chainId: int = 43114
    gasLimit: int = 450000  # sensible value for Avalanche
    maxPriorityFeePerGasInGwei: int = 2

    def setNodeUri(self, nodeUri: str = None) -> AvalancheCWeb3Client:
        """
        Inject the POA middleware
        """
        super().setNodeUri(nodeUri)
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        return self
