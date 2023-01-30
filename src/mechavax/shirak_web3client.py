from __future__ import annotations

import os
import typing as T
from eth_typing import Address

from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.web3_client import Web3Client


class ShirakWeb3Client(AvalancheCWeb3Client):
    """
    Interact with the Shirak token SHK
    https://snowtrace.io/address/0x7d57f563db93f257bd556d86e6fee7079c80226e
    """

    contract_address = T.cast(Address, "0x7D57f563db93F257BD556D86e6FEe7079c80226e")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    src_dir = os.path.dirname(this_dir)
    web3_utils_dir = os.path.join(src_dir, "web3_utils")
    abi_dir = os.path.join(web3_utils_dir, "abi", "abi-shirak.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)
