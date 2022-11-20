from __future__ import annotations

import os
import typing as T
from eth_typing import Address

from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.web3_client import Web3Client


class TusWeb3Client(AvalancheCWeb3Client):
    """
    Interact with the TUS token
    """

    contract_address = T.cast(Address, "0xf693248f96fe03422fea95ac0afbbbc4a8fdd172")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(this_dir, "abi", "abi-tus.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)
