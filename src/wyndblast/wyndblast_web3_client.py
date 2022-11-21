import os
import json
import typing as T

from eth_typing import Address
from eth_typing.encoding import HexStr
from web3.types import TxParams, Wei

from utils import logger
from web3_utils.web3_client import Web3Client
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client


class WyndblastGameWeb3Client(AvalancheCWeb3Client):
    """
    Interact with a smart contract of the Wyndblast game
    https://snowtrace.io/address/0x7bc18da262327117ef4b4359dda3ef2e9ed3ec54
    """

    contract_address = T.cast(Address, "0x7bc18da262327117ef4b4359dda3ef2e9ed3ec54")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(
        os.path.dirname(this_dir), "web3_utils", "abi", "abi-wyndblast-game.json"
    )
    abi = Web3Client._get_contract_abi_from_file(abi_dir)
    holder_place = 0x01

    def claim_rewards(self) -> HexStr:
        """
        Claim daily activity rewards
        """
        try:
            self.contract.functions.claimReward().call()
            tx: TxParams = self.build_contract_transaction(self.contract.functions.claimReward())
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def move_into_inventory(self, token_ids: T.List[int]) -> HexStr:
        """
        Move nft out daily activities into inventory
        """
        try:
            self.contract.functions.batchDispatch(self.holder_place, token_ids).call()
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.batchDispatch(self.holder_place, token_ids)
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def move_out_of_inventory(self, token_ids: T.List[int]) -> HexStr:
        """
        Move nft out of inventory into daily activities
        """
        try:
            self.contract.functions.batchSubmit(self.holder_place, token_ids).call()
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.batchSubmit(self.holder_place, token_ids)
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

class WyndblastNftGameWeb3Client(AvalancheCWeb3Client):
    """
    Interact with a smart contract of the Wyndblast nfts
    https://snowtrace.io/address/0x4b3903952a25961b9e66216186efd9b21903aed3
    """

    contract_address = T.cast(Address, "0x4b3903952a25961b9e66216186efd9b21903aed3")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(
        os.path.dirname(this_dir), "web3_utils", "abi", "abi-wyndblast-nft.json"
    )
    abi = Web3Client._get_contract_abi_from_file(abi_dir)
