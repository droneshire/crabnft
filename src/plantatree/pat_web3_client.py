import os
import json
import typing as T

from eth_typing import Address
from eth_typing.encoding import HexStr
from web3 import Web3
from web3.types import TxParams, Wei

from utils import logger
from utils.price import Token, token_to_wei, wei_to_token_raw
from web3_utils.web3_client import Web3Client
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.avax_web3_client import AvaxCWeb3Client


class PlantATreeWeb3Client(AvalancheCWeb3Client):
    """
    Interact with a smart contract of the Plant a Tree collection
    https://snowtrace.io/address/0xFd97C61962FF2aE3D08491Db4805E7E46F38C502
    """

    contract_address = T.cast(Address, "0xFd97C61962FF2aE3D08491Db4805E7E46F38C502")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(os.path.dirname(this_dir), "web3_utils", "abi", "abi-plant-a-tree.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def re_plant(self, referral_address: Address) -> HexStr:
        """
        Re-plant trees
        """
        try:
            address = Web3.toChecksumAddress(referral_address)
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.RePlantATree(address)
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def plant_tree(self, avax: float, referral_address: Address) -> HexStr:
        """
        Plant new trees
        """
        try:
            address = Web3.toChecksumAddress(referral_address)
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.PlantATree(address), token_to_wei(avax)
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def harvest(self) -> HexStr:
        """
        Harvest rewards
        """
        try:
            tx: TxParams = self.build_contract_transaction(self.contract.functions.HarvestTrees())
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def get_current_day_tax(self, extra_48_tax: bool) -> float:
        """
        Get today's tax
        """
        try:
            return float(
                self.contract.functions.getCurrentDayExtraTax(extra_48_tax).call(
                    {"from": self.user_address}
                )
            )
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0.0

    def is_harvest_day(self) -> bool:
        """
        Is harvest day, yo? i.e. tax is 0%
        """
        try:
            return self.contract.functions.isHarvestDay().call({"from": self.user_address})
        except Exception as e:
            logger.print_fail(f"{e}")
            return False

    def get_my_referral_rewards(self) -> int:
        """
        Referral awards
        """
        try:
            return self.contract.functions.getMyReferralsRewardsTotal().call(
                {"from": self.user_address}
            )
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0

    def get_seconds_since_last_replant(self) -> float:
        """
        Get time in seconds since last replant
        """
        try:
            seconds = self.contract.functions.diffTimeSinceLastRePlantTree().call(
                {"from": self.user_address}
            )
            return float(seconds)
        except Exception as e:
            logger.print_fail(f"{e}")
            return -1.0

    def get_contract_balance(self) -> float:
        avax_w3: AvaxCWeb3Client = T.cast(
            AvaxCWeb3Client,
            (
                AvaxCWeb3Client()
                .set_credentials(self.contract_address, "")
                .set_node_uri(AvalancheCWeb3Client.NODE_URL)
                .set_dry_run(self.dry_run)
            ),
        )
        try:
            avax_balance = avax_w3.get_balance()
            return avax_balance
        except Exception as e:
            logger.print_fail(f"{e}")
            return False

    def did_48_hour_replant(self) -> bool:
        try:
            return self.contract.functions.hasNoCompoundLast48Hours().call(
                {"from": self.user_address}
            )
        except Exception as e:
            logger.print_fail(f"{e}")
            return False

    def get_total_contract_trees(self) -> int:
        try:
            return self.contract.functions.totalPlantedBalance().call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0

    def get_my_total_trees(self) -> int:
        try:
            return self.contract.functions.getMyTrees().call({"from": self.user_address})
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0

    def calculate_harvest_reward(self) -> float:
        my_trees = self.get_my_total_trees()
        try:
            return wei_to_token_raw(
                self.contract.functions.calculateTreeSell(my_trees).call(
                    {"from": self.user_address}
                )
            )
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0.0
