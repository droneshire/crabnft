from __future__ import annotations

import os
import typing as T
from eth_typing import Address

from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.web3_client import Web3Client


class PpieWeb3Client(AvalancheCWeb3Client):
    """
    Interact with the PPIE token
    """

    contract_address = T.cast(Address, "0x325A9463E93aB79bf0302353c99EF70f43f33637")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    # standard erc20 token abi so reusing tus
    abi_dir = os.path.join(this_dir, "abi", "abi-tus.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)
