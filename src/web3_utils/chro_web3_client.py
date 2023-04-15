from __future__ import annotations

import os
import typing as T
from eth_typing import Address

from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.web3_client import Web3Client


class ChroWeb3Client(AvalancheCWeb3Client):
    """
    Interact with the Chro token
    """

    contract_address = T.cast(
        Address, "0xbf1230bb63bfD7F5D628AB7B543Bcefa8a24B81B"
    )
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(this_dir, "abi", "abi-chro.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)
