import os
import json
import typing as T

from eth_typing import Address
from eth_typing.encoding import HexStr
from web3 import Web3
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
        os.path.dirname(this_dir),
        "web3_utils",
        "abi",
        "abi-wyndblast-game.json",
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
        Move nft out of inventory into game
        """
        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.batchSubmit(self.holder_place, token_ids)
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def move_into_inventory(self, token_ids: T.List[int]) -> HexStr:
        """
        Move nft in inventory from game
        """
        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.batchDispatch(self.holder_place, token_ids)
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""


class WyndblastNftGameWeb3Client(AvalancheCWeb3Client):
    """
    Interact with a smart contract of the Wyndblast nfts
    https://snowtrace.io/address/0x4B3903952A25961B9E66216186Efd9B21903AEd3
    """

    contract_address = T.cast(Address, "0x4B3903952A25961B9E66216186Efd9B21903AEd3")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(os.path.dirname(this_dir), "web3_utils", "abi", "abi-wyndblast-nft.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def set_approval_for_all(self, approval_address: Address, approval: bool) -> HexStr:
        address = Web3.toChecksumAddress(approval_address)
        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.setApprovalForAll(address, approval)
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def is_approved_for_all(self, approval_address: Address) -> HexStr:
        address = Web3.toChecksumAddress(approval_address)
        try:
            return self.contract.functions.isApprovedForAll(self.user_address, address).call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return False
