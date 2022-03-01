from __future__ import annotations

import json
import typing as T
from contextlib import contextmanager

from eth_account.datastructures import SignedTransaction
from eth_typing import Address, BlockIdentifier, ChecksumAddress
from eth_typing.encoding import HexStr
from web3 import Web3
from web3.contract import Contract, ContractFunction
from web3.types import BlockData, Nonce, TxParams, TxReceipt, TxData


@contextmanager
def web3_transaction(out_of_gas_handler: T.Callable) -> T.Iterator[None]:
    try:
        yield
    except ValueError as exception:
        if exception["message"].startswith("insufficient funds for gas"):
            out_of_gas_handler()
        else:
            raise exception


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
    privateKey: str = None
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
            "type": 0x2,
            "chainId": self.chain_id,
            "gas": self.gas_limit,  # type: ignore
            "maxFeePerGas": Web3.toWei(self.estimate_max_fee_per_gas_in_gwei(), "gwei"),
            "maxPriorityFeePerGas": Web3.toWei(self.max_priority_fee_per_gas_in_gwei, "gwei"),
            "nonce": self.get_nonce(),
        }
        return tx

    def build_transaction_with_value(self, to: Address, value_in_eth: float) -> TxParams:
        """
        Build a transaction involving a transfer of value to an address,
        where the value is expressed in the blockchain token (e.g. ETH or AVAX).
        """
        tx = self.build_base_transaction()
        tx_value: TxParams = {"to": to, "value": self.w3.toWei(value_in_eth, "ether")}
        tx.update(tx_value)
        return tx

    def build_contract_transaction(self, contractFunction: ContractFunction) -> TxParams:
        """
        Build a transaction that involves a contract interation.

        Requires passing the contract function as detailed in the docs:
        https://web3py.readthedocs.io/en/stable/web3.eth.account.html#sign-a-contract-transaction
        """
        baseTx = self.build_base_transaction()
        return contractFunction.buildTransaction(baseTx)

    ####################
    # Sign & send Tx
    ####################

    def sign_transaction(self, tx: TxParams) -> SignedTransaction:
        """
        Sign the give transaction; the private key must have
        been set with setCredential().
        """
        return self.w3.eth.account.sign_transaction(tx, self.privateKey)

    def send_signed_transaction(self, signed_tx: SignedTransaction) -> HexStr:
        """
        Send a signed transaction and return the tx hash
        """
        if self.dry_run:
            return ""

        try:
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            self.nonce = self.get_nonce()
        except ValueError as exception:
            if exception["message"].starts_with("nonce too low:"):
                self.nonce += 1
            else:
                raise exception
        return self.w3.toHex(tx_hash)

    def sign_and_send_transaction(self, tx: TxParams) -> HexStr:
        """
        Sign a transaction and send it
        """
        signed_tx = self.sign_transaction(tx)
        return self.send_signed_transaction(signed_tx)

    def get_transaction_receipt(self, tx_hash: HexStr) -> TxReceipt:
        """
        Given a transaction hash, wait for the blockchain to confirm
        it and return the tx receipt.
        """
        if self.dry_run:
            return {"status": 1}
        return self.w3.eth.wait_for_transaction_receipt(tx_hash)

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
        return self.w3.eth.get_transaction_count(self.user_address)

    def estimate_max_fee_per_gas_in_gwei(self) -> int:
        """
        Gets the base fee from the latest block and returns a maxFeePerGas
        estimate as 2 * baseFee + maxPriorityFeePerGas, as done in the
        web3 gas_price_strategy middleware (and also here >
        https://ethereum.stackexchange.com/a/113373/89782)
        """
        latest_block = self.w3.eth.get_block("latest")
        baseFeeInWei = latest_block["baseFeePerGas"]  # in wei
        baseFeeInGwei = int(Web3.fromWei(baseFeeInWei, "gwei"))
        return 2 * baseFeeInGwei + self.max_priority_fee_per_gas_in_gwei

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

    ####################
    # Setters
    ####################

    def set_contract(
        self, address: Address, abi_file: str = None, abi: T.Dict[str, T.Any] = None
    ) -> Web3Client:
        """
        Load the smart contract, required before running
        build_contract_transaction().

        Run only after setting the node URI (set_node_uri)
        """
        self.contract_address = address
        self.contract_checksum_address = Web3.toChecksumAddress(address)
        if abi_file:  # Read the contract's ABI from a JSON file
            self.abi = self._get_contract_abi_from_file(abi_file)
        elif abi:  # read the contract's ABI from a string
            self.abi = abi
        if not self.abi:
            raise MissingParameter("Missing ABI")
        self.contract = self.w3.eth.contract(address=self.contract_checksum_address, abi=self.abi)
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
        # Set the contract if possible, e.g. if the subclass defines address & ABI.
        try:
            self.set_contract(address=self.contract_address, abi=self.abi)
        except:
            pass
        return self

    def set_credentials(self, user_address: Address, privateKey: str) -> Web3Client:
        """
        Set credentials, must be set before set_node_uri
        """
        self.user_address = user_address
        self.privateKey = privateKey
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
