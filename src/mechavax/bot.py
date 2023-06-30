import asyncio
import json
import os
import web3
import threading
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
    MechHangerContractWeb3Client,
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
    MINT_BOT_INTERVAL = 1.0
    MAX_SUPPLY = 2250
    MINTING_INFO = {
        "MECH": {
            "cooldown": 60.0 * 60.0 * 5.0,
            "max": 1,
            "period": 60.0 * 60.0 * 24.0 * 7.0,
            "multiplier": 10,
            "enable": True,
            "percent_shk": 1.0,
        },
        "MARM": {
            "cooldown": 60.0 * 1.0,
            "max": 1,
            "period": 2 * 60.0 * 60.0,
            "multiplier": 200,
            "enable": True,
            "percent_shk": 1.0,
        },
    }
    AUTO_DEPOSIT = True

    def __init__(
        self,
        address: Address,
        private_key: str,
        address_mapping: T.Dict[Address, str],
        discord_channel: str,
        mint_discord_channel: str,
        verbose: bool = False,
    ) -> None:
        self.webhook = discord.get_discord_hook(discord_channel)
        self.mint_webhook = discord.get_discord_hook(mint_discord_channel)
        self.address = Web3.toChecksumAddress(address)
        self.address_mapping = address_mapping

        self.mint_cost: T.List[float] = []

        self.w3_mech: MechContractWeb3Client = (
            MechContractWeb3Client()
            .set_credentials(address, private_key)
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(False)
        )
        self.w3_hanger: MechHangerContractWeb3Client = (
            MechHangerContractWeb3Client()
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

        self.verbose = verbose

        self.event_filters: T.Dict[
            web3._utils.filters.LogFilter, T.Callable[[T.Any], None]
        ] = {
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

        self.resolved_address = resolve_address_to_avvy(
            self.w3_mech.w3, address
        )
        logger.print_bold(f"We are {self.resolved_address}")

    def get_events(
        self,
        event_function: T.Any,
        cadence: int = 1,
        latest_only: bool = True,
        age: T.Optional[int] = None,
    ) -> T.List[T.Any]:
        NUM_CHUNKS = int(500 / cadence)
        BLOCK_STEP = 2047
        latest_block = self.w3_mech.w3.eth.block_number
        now = time.time()

        txns = {}
        should_break = False
        for _ in track(range(NUM_CHUNKS), description=f"{event_function}"):
            if should_break:
                break
            try:
                new_events = event_function.getLogs(
                    fromBlock=latest_block - BLOCK_STEP, toBlock=latest_block
                )
            except ValueError:
                logger.print_fail(
                    f"Failed to get events for {event_function} at block {latest_block}"
                )
                break

            for event in new_events:
                tx_hash = event.get("transactionHash", "")
                if age:
                    block_number = event.get("blockNumber", 0)

                    if block_number == 0:
                        continue
                    timestamp = self.w3_mech.w3.eth.get_block(
                        block_number
                    ).timestamp
                    if now - timestamp < age:
                        if tx_hash:
                            txns[tx_hash] = event
                    else:
                        should_break = True
                elif tx_hash:
                    txns[tx_hash] = event

            if len(txns) > 0 and latest_only:
                break

            latest_block -= BLOCK_STEP * cadence
            if latest_block < 0:
                break

        events = txns.values()
        logger.print_ok_blue(f"Found {len(events)} events")
        return events

    def get_events_within(
        self, event_function: T.Any, time_window: float
    ) -> T.List[T.Any]:
        return self.get_events(
            event_function, cadence=1, latest_only=False, age=time_window
        )

    def get_last_mech_mint(self) -> float:
        events = self.get_events(
            self.w3_mech.contract.events.MechPurchased,
            cadence=1,
            latest_only=True,
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
        logger.print_normal(
            f"Last MECH mint happened {get_pretty_seconds(time_since)} ago"
        )
        return latest_event

    def get_last_marm_mint(self) -> float:
        events = self.get_events(
            self.w3_mech.contract.events.ShirakBalanceUpdated,
            cadence=1,
            latest_only=True,
        )

        latest_event = 0
        for event in track(events, description="Marm Purchase Time"):
            block_number = event.get("blockNumber", 0)
            if block_number == 0:
                continue
            timestamp = self.w3_arm.w3.eth.get_block(block_number).timestamp
            latest_event = max(latest_event, timestamp)

        if latest_event == 0:
            logger.print_warn(
                f"Failed to find block timestamp, defaulting to now"
            )
            latest_event = time.time()

        time_since = int(time.time() - latest_event)
        logger.print_normal(
            f"Last MARM mint happened {get_pretty_seconds(time_since)} ago"
        )
        return latest_event

    def mech_minted_handler(
        self, event: web3.datastructures.AttributeDict
    ) -> None:
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

    def marm_minted_handler(
        self, event: web3.datastructures.AttributeDict
    ) -> None:
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

    def arms_bonded_handler(
        self, event: web3.datastructures.AttributeDict
    ) -> None:
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

    def legendary_minted_handler(
        self, event: web3.datastructures.AttributeDict
    ) -> None:
        event_data = json.loads(Web3.toJSON(event))
        try:
            user = event_data["args"]["user"]
            token_id = event_data["args"]["mechId"]
            burned_mechs = event_data["args"]["burnedMechIds"]
        except:
            logger.print_warn(f"Failed to process legendary minted event")
            return

        logger.print_ok_blue(
            f"New ascended minted: {user}, {token_id}, {burned_mechs}"
        )
        self.webhook.send(
            f"\U0001F916 New ascended minted: `{user}`, ID: `{token_id}`\nBurned mechs: {burned_mechs}"
        )

    def shirak_mint_handler(
        self, event: web3.datastructures.AttributeDict
    ) -> None:
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
            logger.print_warn(
                f"Failed to process shirak transfer event\n{event_data}"
            )
            return

        explorer_link = f"Explorer: https://snowtrace.io/tx/{tx_hash}"
        logger.print_ok_blue(
            f"SHK event!\nAmount moved: {price:.2f} $SHK\n{explorer_link}"
        )
        self.webhook.send(
            f"\U0001F916 SHK event!\nAmount: {price:.2f} $SHK\n{explorer_link}"
        )

    async def event_monitors(self) -> None:
        for event_filter, handler in self.event_filters.items():
            try:
                for event in event_filter.get_new_entries():
                    handler(event)
            except:
                logger.print_fail(
                    f"Failed to get entries for event_filter {event_filter}"
                )

    async def stats_monitor(self) -> None:
        num_minted_mechs_from_shk = await async_func_wrapper(
            self.w3_mech.get_minted_shk_mechs
        )
        our_mechs = await async_func_wrapper(
            self.w3_mech.get_num_mechs, self.address
        )
        multiplier = await async_func_wrapper(
            self.w3_mech.get_emmissions_multiplier, self.address
        )
        shk_balance = await async_func_wrapper(
            self.w3_mech.get_deposited_shk, self.address
        )
        min_mint_shk = await async_func_wrapper(self.w3_mech.get_min_mint_bid)

        message = "\U0001F47E\U0001F47E**Cashflow Cartel Data**\U0001F47E\U0001F47E\n\n"
        message += f"**Mechs**: `{our_mechs}`\n"
        message += f"**SHK Deposited**: `{shk_balance:.2f}`\n"
        message += f"**Multiplier**: `{multiplier:.2f}`\n\n"
        message += f"**Current Mint Price**: `{min_mint_shk:.2f} $SHK`\n"
        message += (
            f"**SHK Minted Mechs**: `{num_minted_mechs_from_shk:.2f}`\n\n"
        )

        logger.print_ok_blue(message)

    async def mint_bot(self) -> None:
        mints_within_past_period = await self.get_minting_info()

        if self.MINTING_INFO["MECH"]["enable"]:
            await self.try_to_mint(
                "MECH",
                self.w3_mech,
                mints_within_past_period["MECH"]["total"],
                mints_within_past_period["MECH"]["ours"],
                self.last_time_mech_minted,
            )
        if self.MINTING_INFO["MARM"]["enable"]:
            await self.try_to_mint(
                "MARM",
                self.w3_arm,
                mints_within_past_period["MARM"]["total"],
                mints_within_past_period["MARM"]["ours"],
                self.last_time_marm_minted,
            )

    async def try_to_deposit_shk(self) -> None:
        total_shk = self.w3_shk.get_balance()

        if total_shk > 5.0:
            logger.print_ok_arrow(f"Found {total_shk:.2f} SHK in wallet")

        if not self.AUTO_DEPOSIT:
            return

        if total_shk <= 5.0:
            return

        total_shk_wei = token_to_wei(total_shk)
        logger.print_bold(f"Depositing {total_shk:.2f} SHK in account...")
        tx_hash = await async_func_wrapper(
            self.w3_mech.add_shirak, total_shk_wei
        )

        action_str = f"Deposit {total_shk:.2f} SHK to account"
        _, txn_url = process_w3_results(self.w3_mech, action_str, tx_hash)
        if txn_url:
            message = (
                f"\U0001F389 Successfully deposited {total_shk:.2f}!\n{txn_url}"
            )
            logger.print_ok_arrow(message)
        else:
            message = f"\U00002620 Failed to deposit {total_shk:.2f}!"
            logger.print_fail_arrow(message)

    async def get_minting_info(self) -> T.Dict[str, T.Any]:
        now = time.time()

        mints_within_past_period = {
            "MECH": {
                "total": 0,
                "ours": 0,
                "event": self.w3_mech.contract.events.MechPurchased,
            },
            "MARM": {
                "total": 0,
                "ours": 0,
                "event": self.w3_arm.contract.events.PagePurchased,
            },
        }

        for nft_type in ["MECH", "MARM"]:
            event_function = mints_within_past_period[nft_type]["event"]
            events_within_past_period = self.get_events_within(
                event_function,
                self.MINTING_INFO[nft_type]["period"],
            )
            for mint in events_within_past_period:
                event_data = json.loads(Web3.toJSON(mint))
                minter = mint["args"]["user"]
                time_block = self.w3_mech.w3.eth.get_block(
                    mint["blockNumber"]
                ).timestamp
                try:
                    if now - time_block > self.MINTING_INFO[nft_type]["period"]:
                        continue
                    mints_within_past_period[nft_type]["total"] += 1
                    if minter == self.address:
                        mints_within_past_period[nft_type]["ours"] += 1
                except:
                    logger.print_warn(
                        f"Failed to process {nft_type} mint event\n{event_data}"
                    )
                    continue

        for nft_type in mints_within_past_period.keys():
            ours = mints_within_past_period[nft_type]["ours"]
            total = mints_within_past_period[nft_type]["total"]
            mint_time_window = self.MINTING_INFO[nft_type]["period"]
            logger.print_bold(
                f"We've minted {ours} {nft_type}s in past {get_pretty_seconds(mint_time_window)} out of {total} mints"
            )

        return mints_within_past_period

    async def try_to_mint(
        self,
        nft_type: T.Literal["MECH", "MARM"],
        w3: AvalancheCWeb3Client,
        mints_within_past_period: int,
        num_our_mints: int,
        last_time_minted: float,
    ) -> None:
        now = time.time()
        time_since_last_mint = now - last_time_minted

        if time_since_last_mint < self.MINTING_INFO[nft_type]["cooldown"]:
            logger.print_warn(
                f"Skipping minting {nft_type} since still within window."
            )
            logger.print_normal(
                f"Last mint: {get_pretty_seconds(int(time_since_last_mint))}"
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

        our_shk = current_balances.get(self.address, {}).get("shk", 0.0)

        logger.print_normal(
            f"Total supply SHK: {total_shk:.2f}, ours: {our_shk:.2f}"
        )

        if total_shk <= 0.0:
            return

        shk_ownership_percent = our_shk / total_shk * 100.0
        desired_shk_ownership_percent = self.MINTING_INFO[nft_type][
            "percent_shk"
        ]

        if shk_ownership_percent < desired_shk_ownership_percent:
            logger.print_warn(
                f"Don't own large enough pool of SHK: have {shk_ownership_percent:.2f}% need {desired_shk_ownership_percent:.2f}%"
            )
            return

        shk_balance = await async_func_wrapper(
            self.w3_mech.get_deposited_shk, self.address
        )
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

        logger.print_bold(f"Minted {num_our_mints} {nft_type}s in time window")

        if num_our_mints >= self.MINTING_INFO[nft_type]["max"]:
            logger.print_warn(
                f"Skipping mint of {nft_type} since we've max minted in the time window!"
            )
            return

        logger.print_normal(f"Margin = {savings_margin}")
        tx_hash = await async_func_wrapper(w3.mint_from_shk)
        action_str = f"Mint {nft_type} for {min_mint_shk:.2f} using $SHK balance of {shk_balance:.2f}"
        _, txn_url = process_w3_results(w3, action_str, tx_hash)
        if txn_url:
            message = f"\U0001F389 \U0001F389 \U0001F389 \U0001F389 \U0001F389 \U0001F389 Successfully minted {nft_type}!\n{txn_url}"
            logger.print_ok_arrow(message)
        else:
            message = f"\U00002620 Failed to mint new {nft_type}!"
            logger.print_fail_arrow(message)

        self.mint_webhook.send(message)

    def parse_stats_iteration(self) -> None:
        current_balances = {}
        for nft_id in range(1, self.MAX_SUPPLY + 1):
            address = self.w3_mech.get_owner_of(nft_id)
            if not address:
                continue

            if address in current_balances:
                continue

            current_balances[address] = {}
            current_balances[address]["shk"] = self.w3_mech.get_deposited_shk(
                address
            )
            current_balances[address]["mechs"] = self.w3_mech.get_num_mechs(
                address
            )
            if self.verbose:
                logger.print_normal(
                    f"[{nft_id}/{self.MAX_SUPPLY}] Found {address} with {current_balances[address]['shk']}, {current_balances[address]['mechs']} mechs"
                )

        sorted_stats = {
            k: v
            for k, v in sorted(
                current_balances.items(), key=lambda x: -x[1]["shk"]
            )
        }

        total_shk = 0.0
        for address, totals in sorted_stats.items():
            total_shk += totals["shk"]

        with open(MECH_STATS_CACHE_FILE, "w") as outfile:
            json.dump(sorted_stats, outfile, indent=4)

        if os.path.isfile(MECH_STATS_HISTORY_FILE):
            with open(MECH_STATS_HISTORY_FILE, "r") as infile:
                data_str = infile.read()
                if data_str:
                    data = json.loads(data_str)
                else:
                    data = {}
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

                resolved_address = resolve_address_to_avvy(
                    self.w3_mech.w3, address
                )
                if resolved_address in data and resolved_address != address:
                    data[address] = data[resolved_address]
                    del data[resolved_address]
                    logger.print_normal(
                        f"Converting {resolved_address} -> {address}"
                    )
            json.dump(data, outfile, indent=4)

        logger.print_bold("Updated cache file!")
        time.sleep(1.0)

    async def update_guild_stats(self) -> None:
        if os.path.isfile(MECH_GUILD_STATS_FILE):
            with open(MECH_GUILD_STATS_FILE, "r") as infile:
                data_str = infile.read()
                if data_str:
                    guild_stats = json.loads(data_str)
                else:
                    guild_stats = {}
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

            shortened_address = await async_func_wrapper(
                shortened_address_str, address
            )
            guild_stats[address]["owner"] = GUILD_WALLET_MAPPING.get(
                address, ""
            ).split("#")[0]

            if "MARM" not in guild_stats[address]:
                guild_stats[address]["MARM"] = []

            marms = nft_data.get("MARM", [])
            guild_stats[address]["MARM"] = marms

            if "MECH" not in guild_stats[address]:
                guild_stats[address]["MECH"] = {}

            mechs = nft_data.get("MECH", [])
            multiplier = 0.0
            for mech in track(
                mechs, description=f"Getting Mech Data {shortened_address}"
            ):
                if mech in guild_stats[address]["MECH"]:
                    multiplier += guild_stats[address]["MECH"][mech]
                    continue
                mech_emission = await async_func_wrapper(
                    self.w3_mech.get_mech_multiplier, int(mech)
                )
                guild_stats[address]["MECH"][mech] = mech_emission
                multiplier += mech_emission

            guild_stats[address]["SHK"] = shk_holders.get(address, {}).get(
                "SHK", 0
            )
            multiplier /= 10.0

        logger.print_bold(f"Updated {MECH_GUILD_STATS_FILE}")
        with open(MECH_GUILD_STATS_FILE, "w") as outfile:
            json.dump(guild_stats, outfile, indent=4)

    async def check_and_stake_mechs_in_hangar(self) -> None:
        if self.w3_hanger.is_tour_active():
            logger.print_normal("Tour still going, skipping staking...")
            return

        logger.print_normal("Checking for mechs to stake...")

        if os.path.isfile(MECH_GUILD_STATS_FILE):
            with open(MECH_GUILD_STATS_FILE, "r") as infile:
                data_str = infile.read()
                if data_str:
                    guild_stats = json.loads(data_str)
                else:
                    guild_stats = {}
        else:
            guild_stats = {}

        mechs_list = []
        for address, stats in guild_stats.items():
            if "MECH" not in stats:
                continue
            mechs_list.extend([int(m) for m in stats["MECH"].keys()])

        mechs_list = list(set(mechs_list))

        mechs_off_duty_list = []
        for mech in track(mechs_list, description="Mech Stake Check"):
            is_staked = await async_func_wrapper(
                self.w3_hanger.is_mech_in_hangar, self.address, mech
            )
            if not is_staked:
                logger.print_normal(f"Found off duty mech {mech}...")
                mechs_off_duty_list.append(mech)

        if len(mechs_off_duty_list) == 0:
            logger.print_normal("No mechs to stake...")
            return

        logger.print_bold(f"Staking {len(mechs_off_duty_list)} mechs...")

        await async_func_wrapper(
            self.w3_hanger.stake_mechs_on_tour, token_ids=mechs_off_duty_list
        )

        logger.print_bold("Removing rewards...")

        await async_func_wrapper(self.w3_hanger.withdraw_rewards, self.address)

        logger.print_ok_arrow(
            "Done staking mechs and claiming rewards during off duty!"
        )

    def parse_stats(self) -> None:
        while True:
            try:
                self.parse_stats_iteration()
            except:
                logger.print_fail(f"Failed to parse stats...")

    def run(self) -> None:
        loop = asyncio.get_event_loop()
        logger.print_bold("Starting monitor...")

        thread = threading.Thread(
            target=self.parse_stats, name="inventory", daemon=True
        )
        thread.start()

        try:
            while True:
                loop.run_until_complete(
                    asyncio.gather(
                        self.check_and_stake_mechs_in_hangar(),
                        self.update_guild_stats(),
                        self.try_to_deposit_shk(),
                        self.event_monitors(),
                        self.stats_monitor(),
                        self.mint_bot(),
                    )
                )
        finally:
            loop.close()
