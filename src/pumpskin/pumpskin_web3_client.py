import os
import json
import typing as T

from eth_typing import Address
from eth_typing.encoding import HexStr
from web3 import Web3
from web3.types import TxParams, Wei

from utils import logger
from utils.price import wei_to_token, TokenWei
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
    NODE_URL = "https://rpc.ankr.com/avalanche"

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

    def get_claimable_ppie(self, token_id: int) -> TokenWei:
        """
        Get claimable PPIE per token
        """
        try:
            ppie_wei: TokenWei = self.contract.functions.claimableView(token_id).call()
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
    NODE_URL = "https://nd-649-527-621.p2pify.com/310e4898cbdec5754dfb9abfc8fbd9f4/ext/bc/C/rpc"

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
            return self.sign_and_send_transaction(
                self.build_contract_transaction(self.contract.functions.staking(amount_ppie_wei))
            )
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

    def get_claimable_potn(self, user_address: Address) -> TokenWei:
        """
        Get claimable POTN per token
        """
        try:
            address = Web3.toChecksumAddress(user_address)
            ppie_wei: TokenWei = self.contract.functions.claimableView(address).call()
            return ppie_wei
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0

    def get_ppie_staked(self, user_address: Address) -> TokenWei:
        """
        Get staked PPIE
        """
        try:
            address = Web3.toChecksumAddress(user_address)
            results: T.List[T.Any] = self.contract.functions.pieStakeHolders(address).call()
            return results[2]
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0


class PumpskinNftWeb3Client(AvalancheCWeb3Client):
    """
    Interact with a smart contract of the Pumpskin NFTs
    https://snowtrace.io/address/0x0a27e02fdaf3456bd8843848b728ecbd882510d1
    """

    PT_TOKEN_ADDRESS = T.cast(Address, "0xd38188B000b42E463C305b5004BC9ff80D638dE2")
    contract_address = T.cast(Address, "0x0a27e02fdaf3456bd8843848b728ecbd882510d1")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(os.path.dirname(this_dir), "web3_utils", "abi", "abi-pumpskin-nft.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)
    NODE_URL = "https://nd-649-527-621.p2pify.com/310e4898cbdec5754dfb9abfc8fbd9f4/ext/bc/C/rpc"

    def get_token_of_owner_by_index(self, user_address: Address, slot_index: int) -> int:
        """
        Get the token ID at given index for the user.
        """
        try:
            address = Web3.toChecksumAddress(user_address)
            return self.contract.functions.tokenOfOwnerByIndex(address, slot_index).call()
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

    def mint(self, user_address: Address, quantity: int) -> HexStr:
        """
        Mint pumpskin[s]
        """
        try:
            address = Web3.toChecksumAddress(user_address)
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.claim(address, quantity, self.PT_TOKEN_ADDRESS, 1, [], 0)
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""


class LpStakingContractWeb3Client(AvalancheCWeb3Client):
    def stake(self, amount: TokenWei) -> HexStr:
        """
        Stake LP tokens
        """
        try:
            tx: TxParams = self.build_contract_transaction(self.contract.functions.stake(amount))
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def withdraw(self, amount: TokenWei) -> HexStr:
        """
        Unstake LP tokens
        """
        try:
            tx: TxParams = self.build_contract_transaction(self.contract.functions.withdraw(amount))
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def claim_rewards(self) -> HexStr:
        """
        Claim staking POTN rewards (gets POTN)
        """
        try:
            tx: TxParams = self.build_contract_transaction(self.contract.functions.getReward())
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def get_rewards(self) -> float:
        try:
            value = self.contract.functions.earned(self.user_address).call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0.0
        return wei_to_token(value)

    def get_total_claimed_rewards(self) -> float:
        try:
            value = self.contract.functions.rewards(self.user_address).call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0.0
        return wei_to_token(value)

    def get_my_percent_of_lp(self) -> float:
        try:
            total = float(self.contract.functions.totalSupply().call())
            mine = float(self.contract.functions.balanceOf(self.user_address).call())
            return mine / float(total) * 100.0
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0.0

    def get_rewards_rate_per_day(self) -> float:
        raise NotImplementedError


class PpieLpStakingContractWeb3Client(LpStakingContractWeb3Client):
    """
    Interact with a smart contract of pumpskin PPIE/AVAX LP interaction
    https://snowtrace.io/address/0xbbBc80230E50E26cD448f38D8f2aEC977AD8Fa78
    """

    contract_address = T.cast(Address, "0xbbBc80230E50E26cD448f38D8f2aEC977AD8Fa78")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(
        os.path.dirname(this_dir), "web3_utils", "abi", "abi-pumpskin-staking.json"
    )
    abi = Web3Client._get_contract_abi_from_file(abi_dir)
    NODE_URL = "https://nd-649-527-621.p2pify.com/310e4898cbdec5754dfb9abfc8fbd9f4/ext/bc/C/rpc"


class PotnLpStakingContractWeb3Client(LpStakingContractWeb3Client):
    """
    Interact with a smart contract of pumpskin POTN/AVAX LP interaction
    https://snowtrace.io/address/0x231add43e238b037E488a35014D2646D056df971
    """

    contract_address = T.cast(Address, "0x231add43e238b037e488a35014d2646d056df971")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(
        os.path.dirname(this_dir), "web3_utils", "abi", "abi-pumpskin-staking.json"
    )
    abi = Web3Client._get_contract_abi_from_file(abi_dir)
    NODE_URL = "https://nd-649-527-621.p2pify.com/310e4898cbdec5754dfb9abfc8fbd9f4/ext/bc/C/rpc"
