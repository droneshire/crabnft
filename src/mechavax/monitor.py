import asyncio
import json
import requests
import web3
import typing as T

from eth_typing import Address
from web3 import Web3
from config_admin import ADMIN_ADDRESS
from mechavax.mechavax_web3client import MechContractWeb3Client, MechArmContractWeb3Client
from utils import discord, logger
from utils.price import wei_to_token, TokenWei
from utils.web2_client import Web2Client
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client


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


class MechMonitor:
    MONITOR_INTERVAL = 5.0

    def __init__(
        self,
        address: Address,
        address_mapping: T.Dict[Address, str],
        discord_channel: str,
        interval: float,
    ) -> None:
        self.interval = interval
        self.webhook = discord.get_discord_hook(discord_channel)
        self.address = address
        self.address_mapping = address_mapping

        self.snowtrace_api = SnowtraceApi()

        self.w3_mech: MechContractWeb3Client = (
            MechContractWeb3Client()
            .set_credentials(ADMIN_ADDRESS, "")
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(False)
        )
        self.w3_arm: MechArmContractWeb3Client = (
            MechArmContractWeb3Client()
            .set_credentials(ADMIN_ADDRESS, "")
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(False)
        )

        self.event_filters: T.Dict[web3._utils.filters.LogFilter, T.Callable[[T.Any], None]] = {
            self.w3_mech.contract.events.LegendaryMechMinted.createFilter(
                fromBlock="latest"
            ): self.legendary_minted_handler,
            self.w3_mech.contract.events.ShirakBalanceUpdated.createFilter(
                fromBlock="latest"
            ): self.shirak_mint_handler,
            self.w3_mech.contract.events.ArmsBonded.createFilter(
                fromBlock="latest"
            ): self.arms_bonded_handler,
        }

    def arms_bonded_handler(self, event: web3.datastructures.AttributeDict) -> None:
        event_data = json.loads(Web3.toJSON(event))
        try:
            user = event_data["args"]["user"]
            token_id = event_data["args"]["mechId"]
            nft = event_data["args"]["nft"]
            arm_id = event_data["args"]["id"]
        except:
            logger.print_warn(f"Failed to process legendary minted event")
            return

        logger.print_ok_blue(
            f"\U0001F916 Arms bonded event: `{user}`, ID: `{token_id}`\nNFT: `{nft}` ID: `{arm_id}`"
        )
        self.webhook.send(
            f"\U0001F916 Arms bonded event: `{user}`, ID: `{token_id}`\nNFT: `{nft}` ID: `{arm_id}`"
        )

    def legendary_minted_handler(self, event: web3.datastructures.AttributeDict) -> None:
        event_data = json.loads(Web3.toJSON(event))
        try:
            user = event_data["args"]["user"]
            token_id = event_data["args"]["mechId"]
            burned_mechs = event_data["args"]["burnedMechIds"]
        except:
            logger.print_warn(f"Failed to process legendary minted event")
            return

        logger.print_ok_blue(f"New ascended minted: {user}, {token_id}, {burned_mechs}")
        self.webhook.send(
            f"\U0001F916 New ascended minted: `{user}`, ID: `{token_id}`\nBurned mechs: {burned_mechs}"
        )

    def shirak_mint_handler(self, event: web3.datastructures.AttributeDict) -> None:
        event_data = json.loads(Web3.toJSON(event))
        try:
            tx_hash = event_data["transactionHash"]
            tx_receipt = self.w3_mech.get_transaction_receipt(tx_hash)
            transaction = tx_receipt["logs"][1]
            price_wei = int(transaction["data"], 16)
            price = wei_to_token(price_wei)
            mint_item = "MARM" if transaction["address"] == self.w3_arm.contract_address else "MECH"
        except:
            logger.print_warn(f"Failed to process shirak mint event\n{event_data}")
            return

        explorer_link = f"Explorer: https://snowtrace.io/tx/{tx_hash}"
        logger.print_ok_blue(
            f"Shirak {mint_item} mint event!\nPrice paid: {price:.2f} $SHK\\{explorer_link}"
        )
        self.webhook.send(
            f"\U0001F916 New {mint_item} Mint Alert!\n\tMinted Price: `{price:.2f} $SHK`\n{explorer_link}"
        )

    async def event_monitors(self, interval: float) -> None:
        while True:
            logger.print_normal("Checking for events...")
            for event_filter, handler in self.event_filters.items():
                for event in event_filter.get_new_entries():
                    handler(event)
            await asyncio.sleep(interval)

    async def stats_monitor(self, interval: float) -> None:
        while True:
            num_minted_mechs_from_shk = self.w3_mech.get_minted_shk_mechs()
            our_mechs = self.w3_mech.get_num_mechs(self.address)
            multiplier = self.w3_mech.get_emmissions_multiplier(self.address)
            shk_balance = self.w3_mech.get_deposited_shk(self.address)
            min_mint_shk = self.w3_mech.get_min_mint_bid()

            message = "\U0001F47E\U0001F47E**Cashflow Cartel Data**\U0001F47E\U0001F47E\n\n"
            message += f"**Mechs**: `{our_mechs}`\n"
            message += f"**SHK Deposited**: `{shk_balance:.2f}`\n"
            message += f"**Multiplier**: `{multiplier:.2f}`\n"
            message += f"**Current Mint Price**: `{min_mint_shk:.2f} $SHK`\n"
            message += f"**SHK Minted Mechs**: `{num_minted_mechs_from_shk:.2f}`\n\n"
            message += f"**Guild Distribution**\n"
            holders = await self.snowtrace_api.get_erc721_token_transfers(self.address)
            for address, data in holders.items():
                address = Web3.toChecksumAddress(address)
                owner = self.address_mapping.get(address, address)
                text = f"\t**{owner}:**"
                for nft_type, tokens in data.items():
                    text += f" {nft_type}s: {len(tokens)}"
                message += text + "\n"
            logger.print_ok_blue(message)
            self.webhook.send(message)
            await asyncio.sleep(interval)

    def run(self) -> None:
        loop = asyncio.get_event_loop()

        logger.print_bold("Starting monitor...")

        try:
            loop.run_until_complete(
                asyncio.gather(
                    self.event_monitors(self.MONITOR_INTERVAL),
                    self.stats_monitor(self.interval),
                )
            )
        finally:
            loop.close()
