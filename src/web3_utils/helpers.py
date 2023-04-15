import typing as T
from contextlib import contextmanager

from avvy import AvvyClient
from utils import logger
from utils.price import wei_to_token
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.web3_client import Web3Client


def get_events(
    w3: AvalancheCWeb3Client, event_function: T.Any, max_blocks: int = 20000
) -> T.List[T.Any]:
    BLOCK_CHUNKS = 2048
    latest_block = w3.w3.eth.block_number
    num_blocks = int((latest_block + BLOCK_CHUNKS - 1) / BLOCK_CHUNKS)
    logger.print_normal(f"Searching through {num_blocks} blocks...")
    events = []
    for block in range(num_blocks - max_blocks, num_blocks):
        events.extend(
            event_function.getLogs(
                fromBlock=block, toBlock=block + BLOCK_CHUNKS
            )
        )
    return events


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


def shortened_address_str(address: str) -> str:
    return f"{address[:5]}...{address[-4:]}"


def resolve_address_to_avvy(w3: AvalancheCWeb3Client, address: str) -> str:
    avvy = AvvyClient(w3)
    resolved_address = address
    try:
        hash_name = avvy.reverse(avvy.RECORDS.EVM, address)
        if hash_name:
            name = hash_name.lookup()
            if name:
                resolved_address = name.name
    except:
        logger.print_fail(f"Failed to resolve avvy name for {address}")
    return resolved_address
