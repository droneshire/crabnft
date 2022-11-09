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


class TakerBid(T.TypedDict):
    isOrderAsk: bool
    taker: Address
    price: int
    tokenId: int
    minPercentageToAsk: int
    params: bytes


class MakerBid(T.TypedDict):
    isOrderAsk: bool
    signer: Address
    collection: Address
    price: int
    tokenId: int
    amount: int
    strategy: Address
    currency: Address
    nonce: int
    startTime: int
    endTime: int
    minPercentageToAsk: int
    params: bytes
    v: int
    r: bytes
    s: bytes


class JoePegsWeb3Client(AvalancheCWeb3Client):
    """
    Interact with a smart contract of the JoePegs listings
    https://snowtrace.io/address/0xbb01D7ad46A1229F8383F4e863abf4461b427745
    TODO: untested!
    """

    contract_address = T.cast(Address, "0xbb01D7ad46A1229F8383F4e863abf4461b427745")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(os.path.dirname(this_dir), "web3_utils", "abi", "abi-joepegs.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def purchase_using_avax_and_wavax(self, taker: TakerBid, maker: MakerBid) -> HexStr:
        """
        Purchase from JoePegs
        """
        taker_tuple = (
            taker["isOrderAsk"],
            taker["taker"],
            taker["price"],
            taker["tokenId"],
            taker["minPercentageToAsk"],
            taker["params"],
        )
        maker_tuple = (
            maker["isOrderAsk"],
            maker["signer"],
            maker["collection"],
            maker["price"],
            maker["tokenId"],
            maker["amount"],
            maker["strategy"],
            maker["currency"],
            maker["nonce"],
            maker["startTime"],
            maker["endTime"],
            maker["minPercentageToAsk"],
            maker["params"],
            maker["v"],
            maker["r"],
            maker["s"],
        )
        try:
            self.contract.functions.matchAskWithTakerBidUsingAVAXAndWAVAX(
                taker_tuple, maker_tuple
            ).call()
            tx: TxParams = self.build_contract_transaction(
                self.contract.functions.matchAskWithTakerBidUsingAVAXAndWAVAX(
                    taker_tuple, maker_tuple
                )
            )
            return self.sign_and_send_transaction(tx)
        except Exception as e:
            logger.print_fail(f"{e}")
            return ""
