import typing as T
from contextlib import contextmanager

from utils import logger
from utils.price import wei_to_token
from web3_utils.web3_client import Web3Client


def process_w3_results(
    web3_client: Web3Client, action_str: str, tx_hash: str
) -> T.Tuple[float, str]:
    logger.print_bold(f"{action_str}")

    tx_receipt = web3_client.get_transaction_receipt(tx_hash)
    gas = wei_to_token(web3_client.get_gas_cost_of_transaction_wei(tx_receipt))
    logger.print_bold(f"Paid {gas} AVAX in gas")

    if tx_receipt.get("status", 0) != 1:
        logger.print_fail(f"Failed to: {action_str}!")
        return gas, ""
    else:
        logger.print_ok(f"Successfully: {action_str}")
        txn = f"https://snowtrace.io/tx/{tx_hash}"
        logger.print_normal(f"Explorer: {txn}\n\n")
        return gas, txn
