import asyncio
import os
import json
import typing as T

from eth_typing import Address
from eth_typing.encoding import HexStr
from web3 import Web3
from web3.types import TxParams, Wei

from utils import logger
from utils.price import token_to_wei, wei_to_token, TokenWei
from web3_utils.web3_client import Web3Client
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from pumpskin.types import StakedPumpskin


class ShirakContractWeb3Client(AvalancheCWeb3Client):
    """
    https://snowtrace.io/address/0x7D57f563db93F257BD556D86e6FEe7079c80226e
    """

    contract_address = T.cast(
        Address, "0x7D57f563db93F257BD556D86e6FEe7079c80226e"
    )
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(
        os.path.dirname(this_dir), "web3_utils", "abi", "abi-erc20.json"
    )
    abi = Web3Client._get_contract_abi_from_file(abi_dir)


class MechArmContractWeb3Client(AvalancheCWeb3Client):
    """
    https://snowtrace.io/address/0x311E1a6c9190fA6847dC6B4617AE36c1277Fb24b
    """

    contract_address = T.cast(
        Address, "0x311E1a6c9190fA6847dC6B4617AE36c1277Fb24b"
    )
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(
        os.path.dirname(this_dir),
        "web3_utils",
        "abi",
        "abi-mech-blank-armament.json",
    )
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def get_min_mint_bid(self) -> float:
        try:
            price: TokenWei = self.contract.functions.armPrice().call()
            return wei_to_token(price)
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0.0

    def get_min_mint_bid_wei(self) -> TokenWei:
        try:
            price: TokenWei = self.contract.functions.armPrice().call()
            return price
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0

    def mint_from_shk(
        self, max_price_shk: T.Optional[float] = None, use_deposit: bool = True
    ) -> HexStr:
        if max_price_shk is None:
            price_shk_wei: TokenWei = self.get_min_mint_bid_wei()
        else:
            price_shk_wei: TokenWei = token_to_wei(max_price_shk)

        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.mintFromShirak(
                    price_shk_wei, use_deposit
                )
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""


class MechContractWeb3Client(AvalancheCWeb3Client):
    """
    https://snowtrace.io/address/0xB68f42c2c805b81DaD78d2f07244917431c7F322
    """

    contract_address = T.cast(
        Address, "0xB68f42c2c805b81DaD78d2f07244917431c7F322"
    )
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(
        os.path.dirname(this_dir), "web3_utils", "abi", "abi-mechavax.json"
    )
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def get_base_uri(self) -> HexStr:
        try:
            return self.contract.functions.BASE_URI().call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def get_mech_multiplier(self, token_id: int) -> int:
        if token_id < 0:
            return -1

        try:
            return self.contract.functions.getMechEmissionMultiple(
                token_id
            ).call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return -1

    def get_minted_shk_mechs(self) -> int:
        try:
            return self.contract.functions.numMintedFromShirak().call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0

    def get_num_mechs(self, address: Address) -> int:
        address = Web3.toChecksumAddress(address)
        try:
            data: T.List[T.Any] = self.contract.functions.getUserData(
                address
            ).call()
            return data[0]
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0

    def get_emmissions_multiplier(self, address: Address) -> float:
        address = Web3.toChecksumAddress(address)
        try:
            data: T.List[T.Any] = self.contract.functions.getUserData(
                address
            ).call()
            return data[1] / 10.0
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0.0

    def get_user_emmissions_multiplier(self, address: Address) -> float:
        address = Web3.toChecksumAddress(address)
        try:
            return self.contract.functions.getUserEmissionMultiple(
                address
            ).call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0.0

    def get_deposited_shk(self, address: Address) -> float:
        address = Web3.toChecksumAddress(address)
        try:
            shirak: TokenWei = self.contract.functions.shirakBalance(
                address
            ).call()
            return wei_to_token(shirak)
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0

    def get_min_mint_bid(self) -> float:
        try:
            price: TokenWei = self.contract.functions.mechPrice().call()
            return wei_to_token(price)
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0.0

    def get_min_mint_bid_wei(self) -> TokenWei:
        try:
            price: TokenWei = self.contract.functions.mechPrice().call()
            return price
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0

    def get_owner_of(self, token_id: int) -> Address:
        try:
            address = self.contract.functions.ownerOf(token_id).call()
            return Web3.toChecksumAddress(address)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def mint_from_shk(
        self, max_price_shk: T.Optional[float] = None, use_deposit: bool = True
    ) -> HexStr:
        if max_price_shk is None:
            price_shk_wei: TokenWei = self.get_min_mint_bid_wei()
        else:
            price_shk_wei: TokenWei = token_to_wei(max_price_shk)

        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.mintFromShirak(
                    price_shk_wei, use_deposit
                )
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def mint_legendary(self, list_of_mechs: T.List[int]) -> HexStr:
        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.mintLegendaryMech(list_of_mechs)
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def add_shirak(self, shk_amount_wei: int) -> HexStr:
        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.addShirak(shk_amount_wei)
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""


class MechHangerContractWeb3Client(AvalancheCWeb3Client):
    """
    https://snowtrace.io/address/0xAb13B3a9923CC6549944f5fb5035B473e14FEB99
    """

    contract_address = T.cast(
        Address, "0xAb13B3a9923CC6549944f5fb5035B473e14FEB99"
    )
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(
        os.path.dirname(this_dir), "web3_utils", "abi", "abi-mech-hanger.json"
    )
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def time_till_next_tour(self) -> int:
        try:
            return int(
                time.time() - self.contract.functions.nextStageStart().call()
            )
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0

    def is_tour_active(self) -> bool:
        try:
            return self.contract.functions.tourActive().call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return False

    def get_pending_shk(self, address: Address) -> TokenWei:
        address = Web3.toChecksumAddress(address)
        try:
            return self.contract.functions.pendingReward(address).call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return 0

    def is_mech_in_hangar(self, address: Address, token_id: int) -> bool:
        address = Web3.toChecksumAddress(address)
        try:
            return self.contract.functions.userMechStaked(
                address, token_id
            ).call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return False

    def stake_mechs_on_tour(self, token_ids: T.List[int]) -> HexStr:
        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.stake(token_ids)
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def withdraw_rewards(
        self, address: Address, amount: float = None
    ) -> HexStr:
        address = Web3.toChecksumAddress(address)
        if amount is None:
            amount = self.get_pending_shk(address)
        else:
            amount = token_to_wei(amount)

        if amount == 0:
            return

        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.withdrawRewards(amount)
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""
