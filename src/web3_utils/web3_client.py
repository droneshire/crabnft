from __future__ import annotations

import json
import requests
import typing as T
from contextlib import contextmanager

from eth_account.datastructures import SignedTransaction
from eth_typing import Address, BlockIdentifier, ChecksumAddress
from eth_typing.encoding import HexStr
from utils import logger
from web3 import eth, exceptions, Web3
from web3.contract import Contract, ContractFunction
from web3.gas_strategies import rpc
from web3.types import BlockData, Nonce, TxParams, TxReceipt, TxData, Wei


@contextmanager
def web3_transaction(
    err_string_compare: str, handler: T.Callable
) -> T.Iterator[None]:
    try:
        yield
    except exceptions.ContractLogicError as e:
        logger.print_fail(f"{e}")
        if err_string_compare in str(e):
            handler()
    except requests.exceptions.HTTPError as e:
        logger.print_fail(f"{e}")
    except ValueError as e:
        logger.print_fail(f"{e}")
        if err_string_compare in e.args[0]["message"]:
            handler()
    except Exception as e:
        logger.print_fail(f"{e}")
        if err_string_compare in e:
            handler()


class MissingParameter(Exception):
    pass


class Web3Client:
    """
    Client to interact with a blockchain, with smart
    contract support.

    Wrapper of the Web3 library intended to make it easier
    to use.

    Attributes
    ----------
    max_priority_fee_per_gas_in_gwei : int
    gas_limit : int
    contract_address : Address
    abi: T.Dict[str, T.Any] = None
    chain_id: int = None
    node_uri: str = None
    user_address: Address = None
    private_key: str = None
    dry_run: bool

    Derived attributes
    ----------
    contract_checksum_address: str = None
    w3: Web3 = None
    nonce: Nonce = None
    contract: Contract = None
    """

    ####################
    # Build Tx
    ####################

    def build_base_transaction(self) -> TxParams:
        """
        Build a basic EIP-1559 transaction with just nonce, chain ID and gas;
        before invoking this method you need to have specified a chain_id and
        called set_node_uri().

        Gas is estimated according to the formula
        maxMaxFeePerGas = 2 * baseFee + maxPriorityFeePerGas.
        """
        tx: TxParams = {
            "type": self.tx_type,
            "chainId": self.chain_id,
            "from": self.user_address,
        }
        gas_fee_gwei: T.Optional[float] = None

        if self.tx_type == 1:
            self.w3.eth.set_gas_price_strategy(rpc.rpc_gas_price_strategy)
            tx["gasPrice"] = self.w3.eth.generate_gas_price()
            gas_fee_gwei = float(Web3.fromWei(tx["gasPrice"], "gwei"))
        elif self.tx_type == 2:
            tx["maxFeePerGas"] = Web3.toWei(
                self.estimate_max_fee_per_gas_in_gwei(), "gwei"
            )
            tx["maxPriorityFeePerGas"] = Web3.toWei(
                self.max_priority_fee_per_gas_in_gwei, "gwei"
            )

        tx["nonce"] = self.get_nonce()

        return tx

    def build_transaction_with_value(
        self, to: Address, value_in_eth: float
    ) -> TxParams:
        """
        Build a transaction involving a transfer of value to an address,
        where the value is expressed in the blockchain token (e.g. ETH or AVAX or TUS).
        """
        tx = self.build_base_transaction()
        tx_value: TxParams = {
            "to": to,
            "value": self.w3.toWei(value_in_eth, "ether"),
        }
        tx.update(tx_value)
        return tx

    def build_transaction_with_value_in_wei(
        self,
        to: Address,
        value_in_wei: Wei,
    ) -> TxParams:
        """
        Build a transaction involving a transfer of value (in Wei) to an address,
        where the value is expressed in the blockchain token (e.g. ETH or AVAX or TUS).
        """
        tx = self.build_base_transaction()
        extra_params: TxParams = {
            "to": to,
            "value": value_in_wei,
            "gas": self.estimate_gas_for_transfer(to, value_in_wei),  # type: ignore
        }
        tx.update(extra_params)
        return tx

    def build_contract_transaction(
        self, contract_function: ContractFunction, value_in_wei: Wei = None
    ) -> TxParams:
        """
        Build a transaction that involves a contract interation.

        Requires passing the contract function as detailed in the docs:
        https://web3py.readthedocs.io/en/stable/web3.eth.account.html#sign-a-contract-transaction
        """
        base_tx = self.build_base_transaction()
        if value_in_wei:
            base_tx["value"] = value_in_wei
        return contract_function.buildTransaction(base_tx)

    ####################
    # Sign & send Tx
    ####################

    def sign_transaction(self, tx: TxParams) -> T.Optional[SignedTransaction]:
        """
        Sign the give transaction; the private key must have
        been set with setCredential().
        """
        if self.dry_run:
            return None

        return self.w3.eth.account.sign_transaction(tx, self.private_key)

    def send_signed_transaction(self, signed_tx: SignedTransaction) -> HexStr:
        """
        Send a signed transaction and return the tx hash
        """
        if self.dry_run:
            return ""

        hex_tx_hash = ""
        try:
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            self.nonce = self.get_nonce()
            hex_tx_hash = self.w3.toHex(tx_hash)
        except ValueError as e:
            if "nonce too low:" in e.args[0]["message"]:
                logger.print_warn(f"Nonce too low! Incrementing nonce")
                self.nonce += 1
            else:
                raise e
        return hex_tx_hash

    def sign_and_send_transaction(self, tx: TxParams) -> HexStr:
        """
        Sign a transaction and send it
        """
        if self.dry_run:
            return ""

        signed_tx = self.sign_transaction(tx)
        return self.send_signed_transaction(signed_tx)

    def get_transaction_receipt(self, tx_hash: HexStr) -> TxReceipt:
        """
        Given a transaction hash, wait for the blockchain to confirm
        it and return the tx receipt.
        """
        if self.dry_run:
            return {"status": 1}
        if not tx_hash:
            return {"status": 0}
        try:
            return self.w3.eth.wait_for_transaction_receipt(tx_hash)
        except KeyboardInterrupt:
            raise
        except:
            return {"status": 10}

    def get_transaction(self, tx_hash: HexStr) -> TxData:
        """
        Given a transaction hash, get the transaction; will raise error
        if the transaction has not been mined yet.
        """
        return self.w3.eth.get_transaction(tx_hash)

    ####################
    # Utils
    ####################

    def get_nonce(self) -> Nonce:
        try:
            return self.w3.eth.get_transaction_count(self.user_address)
        except:
            return 0

    def get_gas_price(self, unit: str = "gwei") -> T.Optional[int]:
        try:
            if unit == "wei":
                return self.w3.eth.gas_price
            else:
                return self.w3.fromWei(self.w3.eth.gas_price, unit)
        except:
            return None

    def estimate_max_fee_per_gas_in_gwei(self) -> int:
        """
        Gets the base fee from the latest block and returns a maxFeePerGas
        estimate as 2 * baseFee + maxPriorityFeePerGas, as done in the
        web3 gas_price_strategy middleware (and also here >
        https://ethereum.stackexchange.com/a/113373/89782)
        """
        latest_block = self.w3.eth.get_block("latest")
        base_fee_wei = latest_block["baseFeePerGas"]  # in wei
        base_fee_gwei = int(Web3.fromWei(base_fee_wei, "gwei"))
        return 2 * base_fee_gwei + self.max_priority_fee_per_gas_in_gwei

    def get_latest_block(self) -> BlockData:
        """
        Return the latest block
        """
        return self.w3.eth.get_block("latest")

    def get_pending_block(self) -> BlockData:
        """
        Return the pending block
        """
        return self.w3.eth.get_block("pending")

    def get_gas_cost_of_transaction_wei(self, tx_receipt: TxReceipt) -> Wei:
        return tx_receipt.get("effectiveGasPrice", 0.0) * tx_receipt.get(
            "gasUsed", 0.0
        )

    def get_gas_cost_of_transaction_wei_from_gas_used(
        self, gas_used_wei: float, gas_price_wei: T.Optional[float] = None
    ) -> Wei:
        return (
            gas_used_wei * gas_price_wei
            if gas_price_wei is not None
            else self.w3.eth.gas_price
        )

    def estimate_gas_for_transfer(self, to: Address, value_in_wei: Wei) -> int:
        """
        Return the gas that would be required to send some ETH
        (expressed in Wei) to an address
        """
        return self.w3.eth.estimate_gas(
            {
                "from": self.user_address,
                "to": to,
                "value": value_in_wei,
            }
        )

    ####################
    # Setters
    ####################

    def set_contract(self) -> Web3Client:
        """
        Load the smart contract, required before running
        build_contract_transaction().

        Run only after setting the node URI (set_node_uri)
        """
        self.contract_checksum_address = Web3.toChecksumAddress(
            self.contract_address
        )
        self.contract = self.w3.eth.contract(
            address=self.contract_checksum_address, abi=self.abi
        )
        return self

    def set_node_uri(self, node_uri: str = None) -> Web3Client:
        """
        Set node URI and initalize provider (HTTPS & WS supported).

        Provide an empty node_uri to use autodetection,
        docs here https://web3py.readthedocs.io/en/stable/providers.html#how-automated-detection-works
        """
        self.node_uri = node_uri
        self.w3 = self._get_provider()
        self.nonce = self.get_nonce()
        return self

    def set_credentials(
        self, user_address: Address, private_key: str
    ) -> Web3Client:
        """
        Set credentials, must be set before set_node_uri
        """
        self.user_address = Web3.toChecksumAddress(user_address)
        self.private_key = private_key
        return self

    def set_chain_id(self, chain_id: int) -> Web3Client:
        self.chain_id = int(chain_id)
        return self

    def set_max_priority_fee_per_gas_in_gwei(
        self, max_priority_fee_per_gas_in_gwei: int
    ) -> Web3Client:
        self.max_priority_fee_per_gas_in_gwei = max_priority_fee_per_gas_in_gwei
        return self

    def set_gas_limit(self, gas_limit: int) -> Web3Client:
        self.gas_limit = gas_limit
        return self

    def set_dry_run(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        return self

    @staticmethod
    def _get_contract_abi_from_file(file_name: str) -> T.Any:
        with open(file_name) as file:
            return json.load(file)

    def _get_provider(self) -> Web3:
        if self.node_uri[0:4] == "http":
            return Web3(Web3.HTTPProvider(self.node_uri))
        elif self.node_uri[0:2] == "ws":
            return Web3(Web3.WebsocketProvider(self.node_uri))
        else:
            return Web3()
