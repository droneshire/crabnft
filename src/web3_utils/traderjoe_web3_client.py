import os
import typing as T

from eth_typing import Address
from eth_typing.encoding import HexStr
from web3 import Web3
from web3.types import TxParams

from utils import logger
from utils.price import TokenWei
from web3_utils.web3_client import Web3Client
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client


class TraderJoeWeb3Client(AvalancheCWeb3Client):
    """
    Interact with a traderjoe router
    https://snowtrace.io/address/0x60aE616a2155Ee3d9A68541Ba4544862310933d4
    """

    contract_address = T.cast(Address, "0x60aE616a2155Ee3d9A68541Ba4544862310933d4")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(os.path.dirname(this_dir), "web3_utils", "abi", "abi-trader-joe.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def get_amounts_out(self, amount_in: TokenWei, path: T.List[str]) -> T.List[TokenWei]:
        try:
            checksum_paths = []
            for p in path:
                address = Web3.toChecksumAddress(p)
                checksum_paths.append(address)
            return self.contract.functions.getAmountsOut(amount_in, checksum_paths).call()
        except Exception as e:
            logger.print_fail(f"{e}")
            return []

    def swap_exact_tokens_for_avax(
        self, amount_in: TokenWei, amount_out_min: TokenWei, path: T.List[str]
    ) -> HexStr:
        # ensure outgoing address matches current private key
        address = Web3.toChecksumAddress(self.user_address)
        if address != Account.from_key(self.private_key).address:
            return ""
        if len(path) < 2:
            return ""

        # deadline is 2 min
        deadline = int(time.time() + (2 * 60))
        try:
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.swapExactTokensForAVAX(
                    amount_in, amount_out_min, path, self.user_address, deadline
                )
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""

    def buy_lp_token(
        self,
        non_avax_token_address: Address,
        amount_token: TokenWei,
        amount_token_min: TokenWei,
        amount_avax_min: TokenWei,
    ) -> HexStr:
        # deadline is 2 min
        deadline = int(time.time() + (2 * 60))
        func = self.contract.functions.addLiquidityAVAX(
            Web3.toChecksumAddress(non_avax_token_address),
            amount_token,
            amount_token_min,
            amount_avax_min,
            self.user_address,
            deadline,
        )
        func.call()
        try:
            tx: TxParams = self.build_contract_transaction(func)
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""
