import json
import typing as T

from eth_typing import Address
from web3 import Web3

from config_admin import SNOWTRACE_API_KEY
from utils import logger, price
from utils.web2_client import Web2Client


class SnowtraceApi(Web2Client):
    SNOWTRACE_API_URL = "https://api.snowtrace.io/api"

    def __init__(self) -> None:
        super().__init__(self.SNOWTRACE_API_URL, rate_limit_delay=0.0)

    def get_erc721_token_transfers(
        self, target_address: Address
    ) -> T.Dict[Address, T.Dict[str, T.List[int]]]:
        url = self.SNOWTRACE_API_URL
        params = {
            "module": "account",
            "action": "tokennfttx",
            "address": target_address,
            "startblock": 0,
            "endblock": 999999999,
            "sort": "asc",
        }
        tokens = {}
        try:
            response = self._get_request(url, params=params)
            for token in response["result"]:
                address = token["from"]
                checksum_address = Web3.toChecksumAddress(address)
                token_id = token["tokenID"]
                nft_type = token["tokenSymbol"]
                if checksum_address not in tokens:
                    tokens[checksum_address] = {}
                tokens[checksum_address][nft_type] = tokens[checksum_address].get(nft_type, []) + [
                    token_id
                ]
                logger.print_normal(f"Found {nft_type} {token_id} from {checksum_address}")
        except:
            logger.print_fail(f"Failed to get ERC721 token transfers")

        return tokens

    def get_erc20_token_transfers(
        self, target_address: Address
    ) -> T.Dict[Address, T.Dict[str, float]]:
        url = self.SNOWTRACE_API_URL
        params = {
            "module": "account",
            "action": "tokentx",
            "address": target_address,
            "startblock": 0,
            "endblock": 999999999,
            "sort": "asc",
            "apikey": SNOWTRACE_API_KEY,
        }

        tokens = {}
        try:
            response = self._get_request(url, params=params)
            for transfer in response["result"]:
                address = transfer["from"]
                to_address = transfer["to"]
                checksum_address = Web3.toChecksumAddress(address)
                if Web3.toChecksumAddress(to_address) != Web3.toChecksumAddress(target_address):
                    continue
                symbol = transfer["tokenSymbol"]
                amount_wei = int(transfer["value"])
                amount = price.wei_to_token(amount_wei)
                if checksum_address not in tokens:
                    tokens[checksum_address] = {}
                tokens[checksum_address][symbol] = tokens[checksum_address].get(symbol, 0) + amount
                logger.print_normal(f"Found {amount:.2f} {symbol} from {checksum_address}")
        except:
            logger.print_fail(f"Failed to get ERC20 token transfers")
        return tokens
