from __future__ import annotations

import os
import typing as T
from eth_typing import Address

from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.web3_client import Web3Client


class PotnLpWeb3Client(AvalancheCWeb3Client):
    """
    Interact with the POTN/LP token
    """

    contract_address = T.cast(Address, "0xf45719FA196B37027d31A5509F84F7BD7096ea72")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    src_dir = os.path.dirname(this_dir)
    web3_utils_dir = os.path.join(src_dir, "web3_utils")
    # standard erc20 token abi so reusing tus
    abi_dir = os.path.join(web3_utils_dir, "abi", "abi-tus.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)


class PpieLpWeb3Client(AvalancheCWeb3Client):
    """
    Interact with the PPIE/LP token
    """

    contract_address = T.cast(Address, "0x06Ca569b7C3053Fa885B37006bFA0eE24a38aECA")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    src_dir = os.path.dirname(this_dir)
    web3_utils_dir = os.path.join(src_dir, "web3_utils")
    # standard erc20 token abi so reusing tus
    abi_dir = os.path.join(web3_utils_dir, "abi", "abi-tus.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)
