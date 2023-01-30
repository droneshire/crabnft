import asyncio

from eth_typing import Address
from web3 import Web3

from config_admin import ADMIN_ADDRESS
from mechavax.mechavax_web3client import MechContractWeb3Client
from utils import discord, logger
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client


class MechMonitor:
    MONITOR_INTERVAL = 5.0

    def __init__(self, address: Address, discord_channel: str, interval: float) -> None:
        self.interval = interval
        self.webhook = discord.get_discord_hook(discord_channel)
        self.address = address

        self.w3: MechContractWeb3Client = (
            MechContractWeb3Client()
            .set_credentials(ADMIN_ADDRESS, "")
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(False)
        )
        self.event_filters: T.Dict[web3._utils.filters.LogFilter, T.Callable[[T.Any], None]] = {
            self.w3.contract.events.MechPurchased.createFilter(
                fromBlock="latest"
            ): self.mint_handler,
            self.w3.contract.events.ShirakBalanceUpdated.createFilter(
                fromBlock="latest"
            ): self.shirak_updated_handler,
        }

    def mint_handler(self, event) -> None:
        logger.print_ok_blue(f"Mint event!\n{Web3.toJSON(event)}")
        self.webhook.send(f"{Web3.toJSON(event)}")

    def shirak_updated_handler(self, event) -> None:
        logger.print_ok_blue(f"Shirak updated event!\n{Web3.toJSON(event)}")
        self.webhook.send(f"{Web3.toJSON(event)}")

    async def event_monitors(self, interval: float) -> None:
        while True:
            logger.print_normal("Checking for events...")
            for event_filter, handler in self.event_filters.items():
                for event in event_filter.get_new_entries():
                    handler(event)
            await asyncio.sleep(interval)

    async def stats_monitor(self, interval: float) -> None:
        while True:
            num_minted_mechs_from_shk = self.w3.get_minted_shk_mechs()
            our_mechs = self.w3.get_num_mechs(self.address)
            multiplier = self.w3.get_emmissions_multiplier(self.address)
            shk_balance = self.w3.get_deposited_shk(self.address)
            min_mint_shk = self.w3.get_min_mint_bid()

            message = "\U0001F47E\U0001F47E**Cashflow Cartel Data**\U0001F47E\U0001F47E\n\n"
            message += f"**Mechs**: `{our_mechs}`\n"
            message += f"**SHK Deposited**: `{shk_balance:.2f}`\n"
            message += f"**Multiplier**: `{multiplier:.2f}`\n"
            message += f"**Current Mint Price**: `{min_mint_shk:.2f} $SHK`\n"
            message += f"**SHK Minted Mechs**: `{num_minted_mechs_from_shk:.2f}`\n"
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
