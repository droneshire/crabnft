import asyncio
import json
import web3
import time
import typing as T

from eth_typing import Address
from web3 import Web3

from mechavax.mechavax_web3client import MechContractWeb3Client, MechArmContractWeb3Client
from utils import discord, logger
from utils.general import get_pretty_seconds
from utils.async_utils import async_func_wrapper
from utils.price import wei_to_token, TokenWei
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.helpers import process_w3_results


class MechBot:
    MONITOR_INTERVAL = 5.0
    MINT_BOT_INTERVAL = 60.0 * 5.0
    MINTING_INFO = {
        "MECH": {
            "cooldown": 60.0 * 60.0 * 5.0,
            "max": 3,
            "multiplier": 2,
        },
        "MARM": {
            "cooldown": 60.0 * 30.0,
            "max": 3,
            "multiplier": 100,
        },
    }
    SHK_SAVINGS_MULT = 3
    ENABLE_AUTO_MINT = False

    def __init__(
        self,
        address: Address,
        private_key: str,
        address_mapping: T.Dict[Address, str],
        discord_channel: str,
        interval: float,
    ) -> None:
        self.interval = interval
        self.webhook = discord.get_discord_hook(discord_channel)
        self.address = address
        self.address_mapping = address_mapping

        self.mint_cost: T.List[float] = []

        self.w3_mech: MechContractWeb3Client = (
            MechContractWeb3Client()
            .set_credentials(address, private_key)
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(False)
        )
        self.w3_arm: MechArmContractWeb3Client = (
            MechArmContractWeb3Client()
            .set_credentials(address, private_key)
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(False)
        )

        self.last_time_mech_minted = self.get_last_mech_mint()
        self.last_time_marm_minted = self.get_last_marm_mint()

        self.event_filters: T.Dict[web3._utils.filters.LogFilter, T.Callable[[T.Any], None]] = {
            self.w3_mech.contract.events.LegendaryMechMinted.createFilter(
                fromBlock="latest"
            ): self.legendary_minted_handler,
            self.w3_mech.contract.events.ShirakBalanceUpdated.createFilter(
                fromBlock="latest"
            ): self.shirak_mint_handler,
            self.w3_arm.contract.events.PagePurchased.createFilter(
                fromBlock="latest"
            ): self.marm_minted_handler,
            self.w3_mech.contract.events.ArmsBonded.createFilter(
                fromBlock="latest"
            ): self.arms_bonded_handler,
            self.w3_mech.contract.events.MechPurchased.createFilter(
                fromBlock="latest",
            ): self.mech_minted_handler,
        }

    def get_events(self, event_function: T.Any) -> T.List[T.Any]:
        latest_block = self.w3_mech.w3.eth.block_number

        events = []
        for i in range(500):
            events.extend(
                event_function.getLogs(fromBlock=latest_block - 2048, toBlock=latest_block)
            )
            if len(events) > 0:
                break

            latest_block -= 2048
            if latest_block < 0:
                break

        return events

    def get_events_within(self, event_function: T.Any, time_window: float) -> T.List[T.Any]:
        events = self.get_events(event_function)

        now = time.time()
        events_within_time = []

        for event in events:
            block_number = event.get("blockNumber", 0)
            if block_number == 0:
                continue
            timestamp = self.w3_mech.w3.eth.get_block(block_number).timestamp

            if now - timestamp > time_window:
                continue

            events_within_time.append(event)

        return events_within_time

    def get_last_mech_mint(self) -> float:
        events = self.get_events(self.w3_mech.contract.events.MechPurchased)

        latest_event = 0
        for event in events:
            block_number = event.get("blockNumber", 0)
            if block_number == 0:
                continue
            timestamp = self.w3_mech.w3.eth.get_block(block_number).timestamp
            latest_event = max(latest_event, timestamp)

        if latest_event == 0:
            latest_event = time.time()

        time_since = int(time.time() - latest_event)
        logger.print_normal(f"Last MECH mint happened {get_pretty_seconds(time_since)} ago")
        return latest_event

    def get_last_marm_mint(self) -> float:
        events = self.get_events(self.w3_mech.contract.events.ShirakBalanceUpdated)

        latest_event = 0
        for event in events:
            block_number = event.get("blockNumber", 0)
            if block_number == 0:
                continue
            tx_hash = event["transactionHash"]
            tx_receipt = self.w3_arm.get_transaction_receipt(tx_hash)
            transaction = tx_receipt["logs"][1]
            if transaction["address"] != self.w3_arm.contract_address:
                continue

            timestamp = self.w3_arm.w3.eth.get_block(block_number).timestamp
            latest_event = max(latest_event, timestamp)

        if latest_event == 0:
            latest_event = time.time()

        time_since = int(time.time() - latest_event)
        logger.print_normal(f"Last MARM mint happened {get_pretty_seconds(time_since)} ago")
        return latest_event

    def mech_minted_handler(self, event: web3.datastructures.AttributeDict) -> None:
        event_data = json.loads(Web3.toJSON(event))
        self.last_time_mech_minted = time.time()
        try:
            tx_hash = event_data["transactionHash"]
            user = event_data["args"]["user"]
            token_id = event_data["args"]["mechId"]
            price_wei = event_data["args"]["price"]
            price = wei_to_token(price_wei)
        except:
            logger.print_warn(f"Failed to process MECH minted event")
            return

        self.mint_cost.append(price)
        explorer_link = f"Explorer: https://snowtrace.io/tx/{tx_hash}"
        message = f"\U0001F916 New MECH Mint Alert!\n\tMech ID: {token_id}\n\rMinted Price: `{price:.2f} $SHK`\n\t{explorer_link}"
        logger.print_ok_blue(message)
        self.webhook.send(message)

    def marm_minted_handler(self, event: web3.datastructures.AttributeDict) -> None:
        event_data = json.loads(Web3.toJSON(event))
        self.last_time_marm_minted = time.time()
        try:
            tx_hash = event_data["transactionHash"]
            user = event_data["args"]["user"]
            token_id = event_data["args"]["armId"]
            price_wei = event_data["args"]["price"]
            price = wei_to_token(price_wei)
        except:
            logger.print_warn(f"Failed to process MARM minted event")
            return

        self.mint_cost.append(price)
        explorer_link = f"Explorer: https://snowtrace.io/tx/{tx_hash}"
        message = f"\U0001F916 New MARM Mint Alert!\n\tArm ID: {token_id}\n\rMinted Price: `{price:.2f} $SHK`\n\t{explorer_link}"
        logger.print_ok_blue(message)
        self.webhook.send(message)

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
            if (
                transaction["address"] == self.w3_arm.contract_address
                or transaction["address"] == self.w3_mech.contract_address
            ):
                return
            logger.print_warn(f"Non-mint shirak event...")
        except:
            logger.print_warn(f"Failed to process shirak transfer event\n{event_data}")
            return

        explorer_link = f"Explorer: https://snowtrace.io/tx/{tx_hash}"
        logger.print_ok_blue(f"SHK event!\nAmount moved: {price:.2f} $SHK\n{explorer_link}")
        self.webhook.send(f"\U0001F916 SHK event!\nAmount: {price:.2f} $SHK\n{explorer_link}")

    async def event_monitors(self, interval: float) -> None:
        while True:
            for event_filter, handler in self.event_filters.items():
                try:
                    for event in event_filter.get_new_entries():
                        handler(event)
                except:
                    logger.print_fail(f"Failed to get entries for event_filter {event_filter}")
            await asyncio.sleep(interval)

    async def stats_monitor(self, interval: float) -> None:
        while True:
            num_minted_mechs_from_shk = await async_func_wrapper(self.w3_mech.get_minted_shk_mechs)
            our_mechs = await async_func_wrapper(self.w3_mech.get_num_mechs, self.address)
            multiplier = await async_func_wrapper(
                self.w3_mech.get_emmissions_multiplier, self.address
            )
            shk_balance = await async_func_wrapper(self.w3_mech.get_deposited_shk, self.address)
            min_mint_shk = await async_func_wrapper(self.w3_mech.get_min_mint_bid)

            message = "\U0001F47E\U0001F47E**Cashflow Cartel Data**\U0001F47E\U0001F47E\n\n"
            message += f"**Mechs**: `{our_mechs}`\n"
            message += f"**SHK Deposited**: `{shk_balance:.2f}`\n"
            message += f"**Multiplier**: `{multiplier:.2f}`\n\n"
            message += f"**Current Mint Price**: `{min_mint_shk:.2f} $SHK`\n"
            message += f"**SHK Minted Mechs**: `{num_minted_mechs_from_shk:.2f}`\n\n"

            logger.print_ok_blue(message)
            await asyncio.sleep(interval)

    async def mint_bot(self) -> None:
        if not self.ENABLE_AUTO_MINT:
            return

        while True:
            await self.try_to_mint(
                self.w3_mech,
                self.w3_mech.contract.events.MechPurchased,
                "MECH",
                self.last_time_mech_minted,
            )
            await self.try_to_mint(
                self.w3_arm,
                self.w3_arm.contract.events.PagePurchased,
                "MARM",
                self.last_time_marm_minted,
            )
            await asyncio.sleep(self.MINT_BOT_INTERVAL)

    async def try_to_mint(
        self,
        w3: AvalancheCWeb3Client,
        event_function: T.Any,
        nft_type: T.Literal["MECH", "MARM"],
        last_time_minted: float,
    ) -> None:
        now = time.time()
        time_since_last_mint = now - last_time_minted

        if time_since_last_mint < self.MINTING_INFO[nft_type]["cooldown"]:
            logger.print_normal(
                f"Skipping minting {nft_type} since still within window: {get_pretty_seconds(int(time_since_last_mint))}"
            )
            return

        shk_balance = await async_func_wrapper(self.w3_mech.get_deposited_shk, self.address)
        min_mint_shk = await async_func_wrapper(w3.get_min_mint_bid)

        savings_margin = shk_balance / min_mint_shk
        savings_mult = self.MINTING_INFO[nft_type]["multiplier"]

        logger.print_normal(
            f"{nft_type}: Ask {min_mint_shk:.2f}, Have {shk_balance:.2f}, Need {min_mint_shk * savings_mult:.2f}"
        )

        if savings_margin < savings_mult:
            logger.print_normal(
                f"Skipping minting {nft_type} since we don't have enough SHK ({savings_mult}): {savings_margin:.2f}"
            )
            return

        mints_within_past_day = self.get_events_within(event_function, 60.0 * 60.0 * 24.0)

        num_mints = 0
        for mint in mints_within_past_day:
            minter = mint["args"]["user"]
            if minter == self.address:
                num_mints += 1

        logger.print_bold(
            f"We've minted {nft_type}s {num_mints} in past 24 hours out of {len(mints_within_past_day)} mints"
        )

        if num_mints >= self.MINTING_INFO[nft_type]["max"]:
            logger.print_warn(f"Skipping mint of {nft_type} since we've max minted today!")
            return

        logger.print_normal(f"Margin = {savings_margin}")
        tx_hash = await async_func_wrapper(w3.mint_from_shk)
        action_str = (
            f"Mint {nft_type} for {min_mint_shk:.2f} using $SHK balance of {shk_balance:.2f}"
        )
        _, txn_url = process_w3_results(w3, action_str, tx_hash)
        if txn_url:
            message = f"\U0001F389 Successfully minted a new {nft_type}!\n{txn_url}"
            logger.print_ok_arrow(message)
        else:
            message = f"\U00002620 Failed to mint new {nft_type}!"
            logger.print_fail_arrow(message)

        self.webhook.send(message)
        await asyncio.sleep(self.MINT_BOT_INTERVAL)

    def run(self) -> None:
        loop = asyncio.get_event_loop()

        logger.print_bold("Starting monitor...")

        try:
            loop.run_until_complete(
                asyncio.gather(
                    self.event_monitors(self.MONITOR_INTERVAL),
                    self.stats_monitor(self.interval),
                    self.mint_bot(),
                )
            )
        finally:
            loop.close()
