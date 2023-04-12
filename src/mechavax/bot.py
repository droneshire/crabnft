import asyncio
import json
import os
import web3
import time
import typing as T

from eth_typing import Address
from rich.progress import track
from web3 import Web3

from config_mechavax import (
    GUILD_WALLET_ADDRESS,
    GUILD_WALLET_MAPPING,
    MECH_STATS_HISTORY_FILE,
    MECH_STATS_CACHE_FILE,
    MECH_GUILD_STATS_FILE,
)
from mechavax.mechavax_web3client import (
    MechContractWeb3Client,
    MechArmContractWeb3Client,
    ShirakContractWeb3Client,
)
from utils import discord, logger
from utils.general import get_pretty_seconds
from utils.async_utils import async_func_wrapper
from utils.price import wei_to_token, token_to_wei, TokenWei
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.helpers import (
    process_w3_results,
    resolve_address_to_avvy,
    shortened_address_str,
)
from web3_utils.snowtrace import SnowtraceApi


class MechBot:
    MONITOR_INTERVAL = 5.0
    MINT_BOT_INTERVAL = 1.0
    MAX_SUPPLY = 2250
    MINTING_INFO = {
        "MECH": {
            "cooldown": 60.0 * 60.0 * 5.0,
            "max": 1,
            "period": 60.0 * 60.0 * 48.0,
            "multiplier": 5,
            "enable": True,
            "percent_shk": 0.0,
        },
        "MARM": {
            "cooldown": 60.0 * 1.0,
            "max": 2,
            "period": 60.0 * 60.0,
            "multiplier": 100,
            "enable": True,
            "percent_shk": 0.0,
        },
    }
    AUTO_DEPOSIT = True

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
        self.w3_shk: ShirakContractWeb3Client = (
            ShirakContractWeb3Client()
            .set_credentials(address, private_key)
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(False)
        )

        self.last_time_mech_minted = self.get_last_mech_mint()
        self.last_time_marm_minted = self.get_last_marm_mint()

        self.lock = asyncio.Lock()

        self.event_filters: T.Dict[web3._utils.filters.LogFilter, T.Callable[[T.Any], None]] = {
            self.w3_mech.contract.events.LegendaryMechMinted.createFilter(
                fromBlock="latest"
            ): self.legendary_minted_handler,
            # self.w3_mech.contract.events.ShirakBalanceUpdated.createFilter(
            #     fromBlock="latest"
            # ): self.shirak_mint_handler,
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

        self.resolved_address = resolve_address_to_avvy(self.w3_mech.w3, address)
        logger.print_bold(f"We are {self.resolved_address}")

    def get_events(
        self, event_function: T.Any, cadence: int = 1, latest_only: bool = True
    ) -> T.List[T.Any]:
        NUM_CHUNKS = int(100 / cadence)
        latest_block = self.w3_mech.w3.eth.block_number

        events = []
        for i in track(range(NUM_CHUNKS), description=f"{event_function}"):
            events.extend(
                event_function.getLogs(fromBlock=latest_block - 2048, toBlock=latest_block)
            )
            if len(events) > 0 and latest_only:
                break

            latest_block -= 2048 * cadence
            if latest_block < 0:
                break

        return events

    def get_events_within(self, event_function: T.Any, time_window: float) -> T.List[T.Any]:
        events = self.get_events(event_function, cadence=1, latest_only=False)

        now = time.time()
        inx_min = 0
        inx_max = len(events) - 1
        inx = 0

        while (inx_max - inx_min) > 1:
            block_number = events[inx].get("blockNumber", 0)

            if block_number == 0:
                return []

            timestamp = self.w3_mech.w3.eth.get_block(block_number).timestamp

            if now - timestamp > time_window:
                inx_max = inx
            else:
                inx_min = inx

            avg = inx_max + inx_min
            avg /= 2
            inx = int(avg)

        return events[:inx]

    def get_last_mech_mint(self) -> float:
        events = self.get_events(
            self.w3_mech.contract.events.MechPurchased, cadence=1, latest_only=True
        )

        latest_event = 0
        for event in track(events, description="Mech Purchase Time"):
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
        events = self.get_events(
            self.w3_arm.contract.events.PagePurchased, cadence=1, latest_only=True
        )

        latest_event = 0
        for event in track(events, description="Marm Purchase Time"):
            block_number = event.get("blockNumber", 0)
            if block_number == 0:
                continue
            timestamp = self.w3_arm.w3.eth.get_block(block_number).timestamp
            latest_event = max(latest_event, timestamp)

        if latest_event == 0:
            logger.print_warn(f"Failed to find block timestamp, defaulting to now")
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
        for event_filter, handler in self.event_filters.items():
            try:
                for event in event_filter.get_new_entries():
                    handler(event)
            except:
                logger.print_fail(f"Failed to get entries for event_filter {event_filter}")
        await asyncio.sleep(interval)

    async def stats_monitor(self, interval: float) -> None:
        num_minted_mechs_from_shk = await async_func_wrapper(self.w3_mech.get_minted_shk_mechs)
        our_mechs = await async_func_wrapper(self.w3_mech.get_num_mechs, self.address)
        multiplier = await async_func_wrapper(self.w3_mech.get_emmissions_multiplier, self.address)
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
        if self.MINTING_INFO["MECH"]["enable"]:
            await self.try_to_mint(
                self.w3_mech,
                self.w3_mech.contract.events.MechPurchased,
                "MECH",
                self.last_time_mech_minted,
            )
        if self.MINTING_INFO["MARM"]["enable"]:
            await self.try_to_mint(
                self.w3_arm,
                self.w3_arm.contract.events.PagePurchased,
                "MARM",
                self.last_time_marm_minted,
            )
        await asyncio.sleep(self.MINT_BOT_INTERVAL)

    async def try_to_deposit_shk(self) -> None:
        total_shk = self.w3_shk.get_balance()

        if total_shk > 5.0:
            logger.print_ok_arrow(f"Found {total_shk:.2f} SHK in wallet")

        if not self.AUTO_DEPOSIT:
            await asyncio.sleep(60.0 * 60.0)
            return

        if total_shk <= 5.0:
            await asyncio.sleep(60.0 * 60.0)
            return

        total_shk_wei = token_to_wei(total_shk)
        logger.print_bold(f"Depositing {total_shk:.2f} SHK in account...")
        tx_hash = await async_func_wrapper(self.w3_mech.add_shirak, total_shk_wei)

        action_str = f"Deposit {total_shk:.2f} SHK to account"
        _, txn_url = process_w3_results(self.w3_mech, action_str, tx_hash)
        if txn_url:
            message = f"\U0001F389 Successfully deposited {total_shk:.2f}!\n{txn_url}"
            logger.print_ok_arrow(message)
        else:
            message = f"\U00002620 Failed to deposit {total_shk:.2f}!"
            logger.print_fail_arrow(message)
            await asyncio.sleep(60.0 * 60.0)

    async def try_to_mint(
        self,
        w3: AvalancheCWeb3Client,
        event_function: T.Any,
        nft_type: T.Literal["MECH", "MARM"],
        last_time_minted: float,
    ) -> None:
        now = time.time()
        time_since_last_mint = now - last_time_minted
        time_window = self.MINTING_INFO[nft_type]["period"]

        mints_within_past_period = self.get_events_within(event_function, time_window)

        num_mints = 0
        for mint in mints_within_past_period:
            minter = mint["args"]["user"]
            if minter == self.address:
                num_mints += 1

        if time_window > 60.0 * 60.0:
            time_unit_str = "hours"
            time_window /= 60.0 * 60.0
        else:
            time_unit_str = "minutes"
            time_window /= 60.0

        logger.print_bold(
            f"We've minted {num_mints} {nft_type}s in past {time_window} {time_unit_str} out of {len(mints_within_past_period)} mints"
        )

        if time_since_last_mint < self.MINTING_INFO[nft_type]["cooldown"]:
            logger.print_normal(
                f"Skipping minting {nft_type} since still within window: {get_pretty_seconds(int(time_since_last_mint))}"
            )
            return

        if not os.path.isfile(MECH_STATS_CACHE_FILE):
            logger.print_warn(f"Missing {MECH_STATS_CACHE_FILE}")
            return

        with open(MECH_STATS_CACHE_FILE, "r") as infile:
            current_balances = json.load(infile)

        total_shk = 0.0
        for _, totals in current_balances.items():
            total_shk += totals["shk"]

        our_shk = current_balances.get(self.resolved_address, {}).get("shk", 0.0)

        logger.print_normal(f"Total supply SHK: {total_shk:.2f}, ours: {our_shk:.2f}")

        if total_shk <= 0.0:
            return

        shk_ownership_percent = our_shk / total_shk * 100.0
        desired_shk_ownership_percent = self.MINTING_INFO[nft_type]["percent_shk"]

        if shk_ownership_percent < desired_shk_ownership_percent:
            logger.print_warn(
                f"Don't own large enough pool of SHK: have {shk_ownership_percent:.2f}% need {desired_shk_ownership_percent:.2f}%"
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
            message = f"\U0001F389 Successfully minted {nft_type}!\n{txn_url}"
            logger.print_ok_arrow(message)
        else:
            message = f"\U00002620 Failed to mint new {nft_type}!"
            logger.print_fail_arrow(message)

        self.webhook.send(message)
        await asyncio.sleep(self.MINT_BOT_INTERVAL)

    async def parse_stats_iteration(self) -> None:
        current_balances = {}
        for nft_id in range(1, self.MAX_SUPPLY + 1):
            address = await async_func_wrapper(self.w3_mech.get_owner_of, nft_id)
            if not address:
                continue

            await asyncio.sleep(0.05)

            if address in current_balances:
                continue

            current_balances[address] = {}
            current_balances[address]["shk"] = await async_func_wrapper(
                self.w3_mech.get_deposited_shk, address
            )
            current_balances[address]["mechs"] = await async_func_wrapper(
                self.w3_mech.get_num_mechs, address
            )
            logger.print_normal(
                f"Found {address} with {current_balances[address]['shk']}, {current_balances[address]['mechs']} mechs"
            )

        sorted_stats = {
            k: v for k, v in sorted(current_balances.items(), key=lambda x: -x[1]["shk"])
        }

        total_shk = 0.0
        for address, totals in sorted_stats.items():
            total_shk += totals["shk"]

        with open(MECH_STATS_CACHE_FILE, "w") as outfile:
            json.dump(sorted_stats, outfile, indent=4)

        if os.path.isfile(MECH_STATS_HISTORY_FILE):
            with open(MECH_STATS_HISTORY_FILE, "r") as infile:
                data = json.load(infile)
        else:
            data = {}

        with open(MECH_STATS_HISTORY_FILE, "w") as outfile:
            for address, stats in current_balances.items():
                if address not in data:
                    data[address] = {}

                for k, v in stats.items():
                    if k not in data[address]:
                        data[address][k] = []
                    data[address][k].append(v)

                resolved_address = await async_func_wrapper(
                    resolve_address_to_avvy, self.w3_mech.w3, address
                )
                if resolved_address in data and resolved_address != address:
                    data[address] = data[resolved_address]
                    del data[resolved_address]
                    logger.print_normal(f"Converting {resolved_address} -> {address}")
            json.dump(data, outfile, indent=4)

        logger.print_bold("Updated cache file!")
        await asyncio.sleep(10.0)

    async def update_guild_stats(self) -> None:
        if os.path.isfile(MECH_GUILD_STATS_FILE):
            with open(MECH_GUILD_STATS_FILE, "r") as infile:
                guild_stats = json.load(infile)
        else:
            guild_stats = {}

        holders = await async_func_wrapper(
            SnowtraceApi().get_erc721_token_transfers, GUILD_WALLET_ADDRESS
        )
        shk_holders = await async_func_wrapper(
            SnowtraceApi().get_erc20_token_transfers, GUILD_WALLET_ADDRESS
        )

        for address, nft_data in holders.items():
            address = Web3.toChecksumAddress(address)
            if address not in guild_stats:
                guild_stats[address] = {}

            shortened_address = await async_func_wrapper(shortened_address_str, address)
            guild_stats[address]["owner"] = GUILD_WALLET_MAPPING.get(address, "").split("#")[0]

            if "MARM" not in guild_stats[address]:
                guild_stats[address]["MARM"] = []

            marms = nft_data.get("MARM", [])
            guild_stats[address]["MARM"] = marms

            if "MECH" not in guild_stats[address]:
                guild_stats[address]["MECH"] = {}

            mechs = nft_data.get("MECH", [])
            multiplier = 0.0
            for mech in track(mechs, description=f"Getting Mech Data {shortened_address}"):
                if mech in guild_stats[address]["MECH"]:
                    multiplier += guild_stats[address]["MECH"][mech]
                    continue
                mech_emission = await async_func_wrapper(
                    self.w3_mech.get_mech_multiplier, int(mech)
                )
                guild_stats[address]["MECH"][mech] = mech_emission
                multiplier += mech_emission

            guild_stats[address]["SHK"] = shk_holders.get(address, {}).get("SHK", 0)
            multiplier /= 10.0

        logger.print_bold(f"Updated {MECH_GUILD_STATS_FILE}")
        with open(MECH_GUILD_STATS_FILE, "w") as outfile:
            json.dump(guild_stats, outfile, indent=4)

        await asyncio.sleep(60.0 * 60.0 * 10.0)

    async def parse_stats(self) -> None:
        await self.parse_stats_iteration()
        try:
            pass
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except:
            logger.print_fail(f"Failed to parse stats...")

    def run(self) -> None:
        loop = asyncio.get_event_loop()
        logger.print_bold("Starting monitor...")

        try:
            while True:
                loop.run_until_complete(
                    asyncio.gather(
                        self.update_guild_stats(),
                        self.try_to_deposit_shk(),
                        self.event_monitors(self.MONITOR_INTERVAL),
                        self.stats_monitor(self.interval),
                        self.mint_bot(),
                        self.parse_stats(),
                    )
                )
        finally:
            loop.close()
