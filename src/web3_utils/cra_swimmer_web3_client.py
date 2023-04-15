from __future__ import annotations

import os
import typing as T
from eth_typing import Address

from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.web3_client import Web3Client


class CraSwimmerWeb3Client(SwimmerNetworkClient):
    """
    Interact with the CRA token on Swimmer Network
    """

    contract_address = T.cast(
        Address, "0xC1a1F40D558a3E82C3981189f61EF21e17d6EB48"
    )
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(this_dir, "abi", "abi-erc20.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)
