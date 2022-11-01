import os
import json
import typing as T

from eth_typing import Address
from eth_typing.encoding import HexStr
from web3 import Web3
from web3.types import TxParams, Wei

from utils import logger
from utils.price import wei_to_token_raw, Token
from web3_utils.web3_client import Web3Client
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from pumpskin.types import StakedPumpskin


class PumpskinCollectionWeb3Client(AvalancheCWeb3Client):
    """
    Interact with a smart contract of the Pumpskins collection
    https://snowtrace.io/address/0x94fde8DF71106cf2CF0141ce77546c2B3E35B243
    """

    contract_address = T.cast(Address, "0x94fde8DF71106cf2CF0141ce77546c2B3E35B243")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(os.path.dirname(this_dir), "web3_utils", "abi", "abi-plant-a-tree.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def re_plant(self, user_address: Address) -> HexStr:
        """
        Re-plant trees
        """
        try:
            address = Web3.toChecksumAddress(user_address)
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.RePlantATree(address)
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def harvest(self, token_ids: T.List[int]) -> HexStr:
        """
        Harvest rewards
        """
        try:
            tx: TxParams = self.build_contract_transaction(self.contract.functions.HarvestTrees())
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def get_rewards(self, token_ids: T.List[int]) -> HexStr:
        """
        Stake pumpskins
        """
        try:
            tx: TxParams = self.build_contract_transaction(self.contract.functions.stake(token_ids))
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def get_claimable_ppie(self, token_id: int) -> Token:
        """
        Get claimable PPIE per token
        """
        try:
            ppie_wei: Token = self.contract.functions.claimableView(token_id).call()
            return ppie_wei
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0

    def get_staked_pumpskin_info(self, token_id: int) -> StakedPumpskin:
        try:
            pumpskin_info = self.contract.functions.stakedPumpskins(token_id).call()
            pumpskin: StakedPumpskin = StakedPumpskin(
                kg=pumpskin_info[0],
                since_ts=pumpskin_info[1],
                last_skipped_ts=pumpskin_info[2],
                eaten_amount=pumpskin_info[3],
                cooldown_ts=pumpskin_info[4],
            )
            return pumpskin
        except Exception as e:
            logger.print_fail(f"{e}")
            return {}

    def get_staked_pumpskins(self, user_address: Address) -> T.List[int]:
        """
        Get the token ID at given index for the user. We use this as a hack way to get all the
        NFTs owned by a user by iterating through indices until we error out
        """
        try:
            address = Web3.toChecksumAddress(user_address)
            return self.contract.functions.getStakedTokens(address).call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return []
