import os
import json
import typing as T

from eth_typing import Address
from eth_typing.encoding import HexStr
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
    abi_dir = os.path.join(
        os.path.dirname(this_dir), "web3_utils", "abi", "abi-pumpskin-collection.json"
    )
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def level_up_pumpkin(self, token_id: int) -> HexStr:
        """
        Level up a pumpskin
        """
        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.levelUpPumpkin(token_id)
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def claim_pies(self, token_ids: T.List[int]) -> HexStr:
        """
        Claim pies earned from staking pumpskin
        """
        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.claimPies(token_ids)
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def stake(self, token_ids: T.List[int]) -> HexStr:
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
            return ""

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
            return self.contract.functions.getStakedTokens(user_address).call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return []


class PumpskinContractWeb3Client(AvalancheCWeb3Client):
    """
    Interact with a smart contract of the Pumpskin contract
    https://snowtrace.io/address/0x03173999643d809301f7fa44631bc6aac775c7cf
    """

    contract_address = T.cast(Address, "0x03173999643d809301f7fa44631bc6aac775c7cf")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(
        os.path.dirname(this_dir), "web3_utils", "abi", "abi-pumpskin-contract.json"
    )
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def drink_potion(self, token_id: int, num_potn_wei: Wei) -> HexStr:
        """
        Drink potion for a pumpskin
        """
        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.potionPumpkin(token_id, num_potn_wei)
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def staking_ppie(self, amount_ppie_wei: Wei) -> HexStr:
        """
        Stake PPIE
        """
        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.staking(amount_ppie_wei)
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def claim_potn(self) -> HexStr:
        """
        Claim POTN
        """
        try:
            tx: TxParams = self.build_contract_transaction(self.contract.functions.claimpotion())
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def get_claimable_potn(self, user_address: Address) -> Token:
        """
        Get claimable POTN per token
        """
        try:
            ppie_wei: Token = self.contract.functions.claimableView(user_address).call()
            return ppie_wei
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0

    def get_ppie_staked(self, user_address: Address) -> Token:
        """
        Get staked PPIE
        """
        try:
            results: T.List[T.Any] = self.contract.functions.pieStakeHolders(user_address).call()
            return results[2]
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0


class PumpskinNftWeb3Client(AvalancheCWeb3Client):
    """
    Interact with a smart contract of the Pumpskin NFTs
    https://snowtrace.io/address/0x0a27e02fdaf3456bd8843848b728ecbd882510d1
    """

    contract_address = T.cast(Address, "0x0a27e02fdaf3456bd8843848b728ecbd882510d1")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(os.path.dirname(this_dir), "web3_utils", "abi", "abi-pumpskin-nft.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def get_token_of_owner_by_index(self, user_address: Address, slot_index: int) -> int:
        """
        Get the token ID at given index for the user.
        """
        try:
            return self.contract.functions.tokenOfOwnerByIndex(user_address, slot_index).call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return -1

    def get_total_pumpskins_minted(self) -> int:
        """
        Get the total NFTs minted
        """
        try:
            return self.contract.functions.totalSupply().call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return -1

    def get_max_total_pumpskins_to_mint(self) -> int:
        """
        Get the total NFTs minted
        """
        try:
            return self.contract.functions.maxTotalSupply().call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return -1
