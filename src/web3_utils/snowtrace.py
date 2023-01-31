import typing as T

from eth_typing import Address

from utils import logger
from utils.web2_client import Web2Client


class SnowtraceApi(Web2Client):
    SNOWTRACE_API_URL = "https://api.snowtrace.io/api"

    def __init__(self) -> None:
        super().__init__(self.SNOWTRACE_API_URL)

    async def get_erc721_token_transfers(
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
                token_id = token["tokenID"]
                nft_type = token["tokenSymbol"]
                if address not in tokens:
                    tokens[address] = {}
                tokens[address][nft_type] = tokens[address].get(nft_type, []) + [token_id]
                logger.print_normal(f"Found {nft_type} {token_id} from {address}")
        except:
            logger.print_fail(f"Failed to get token transfers")

        return tokens
