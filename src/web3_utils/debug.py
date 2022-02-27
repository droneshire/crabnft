from typing import Any
from eth_typing.encoding import HexStr
from src.libs.Web3Client.Web3Client import Web3Client
from web3 import Web3
from web3.datastructures import AttributeDict
import pprint

def printTxInfo(client: Web3Client, txHash: HexStr) -> None:
    """
    Get a transaction receipt and print it, together with
    the tx cost
    """
    logger.print_normal(">>> TX SENT!")
    logger.print_normal("Hash = " + txHash)
    logger.print_normal("Waiting for transaction to finalize...")
    tx_receipt = client.getTransactionReceipt(txHash)
    logger.print_normal(">>> TX IS ON THE BLOCKCHAIN :-)")
    pprint.pprint(tx_receipt)
    logger.print_normal(">>> ETH SPENT")
    logger.print_normal(Web3.fromWei(tx_receipt['effectiveGasPrice']*tx_receipt['gasUsed'], 'ether'))

def pprintAttributeDict(attributeDict: AttributeDict[str, Any]) -> None:
    """
    Web3 often returns AttributeDict instead of simple Dictionaries;
    this function pretty prints an AttributeDict
    """
    logger.print_normal('{')
    for key, value in attributeDict.items():
        logger.print_normal(f"  {key} -> {pprint.pformat(value, indent=4)}")
    logger.print_normal('}')
