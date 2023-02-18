import asyncio
import contextvars
import discord
import functools
import getpass
import json
import math
import os
import table2ascii
import time
import typing as T

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from discord.ext import commands
from rich.progress import track
from web3 import Web3
from config_admin import (
    ADMIN_ADDRESS,
    DISCORD_MECHAVAX_SALES_BOT_TOKEN,
    GUILD_MANAGEMENT_FEE,
    GUILD_MULTIPLIERS,
    GUILD_WALLET_ADDRESS,
    GUILD_WALLET_MAPPING,
    GUILD_WALLET_PRIVATE_KEY,
    MECH_STATS_CACHE_FILE,
    MECH_STATS_HISTORY_FILE,
    MECH_STATS_PLOT,
)
from joepegs.joepegs_api import JOEPEGS_ITEM_URL, JoePegsClient
from mechavax.mechavax_web3client import (
    MechArmContractWeb3Client,
    MechContractWeb3Client,
    ShirakContractWeb3Client,
)
from utils import general, logger
from utils.async_utils import async_func_wrapper
from utils.price import wei_to_token, TokenWei
from utils.security import decrypt_secret
from web3_utils import multicall
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.helpers import process_w3_results, shortened_address_str, resolve_address_to_avvy
from web3_utils.snowtrace import SnowtraceApi

bot = commands.Bot(command_prefix="/", intents=discord.Intents.all())

TOP_N = 5
ALLOWLIST_MINTERS = [
    935440767646851093,  # nftcashflow
]
ALLOWLIST_GUILD = 986151371923410975
ALLOWLIST_CHANNELS = [
    1032890276420800582,  # test channel in p2e auto
    1067902019379142671,  # p2e mechavax channel
]
MINT_ADDRESS = "0x0000000000000000000000000000000000000000"
IGNORE_ADDRESSES = [MINT_ADDRESS, "0xB6C5a50c28805ABB41f79F7945Bf3F9DfeF4C8B0"]


def get_credentials() -> T.Tuple[str, str]:
    encrypt_password = os.getenv("NFT_PWD")
    if not encrypt_password:
        encrypt_password = getpass.getpass(prompt="Enter decryption password: ")

    private_key = decrypt_secret(encrypt_password, GUILD_WALLET_PRIVATE_KEY)
    return GUILD_WALLET_ADDRESS, private_key


ADDRESS, PRIVATE_KEY = get_credentials()


def do_multicall(inputs: T.List[T.Any], fn: T.Callable) -> T.List[T.Tuple]:
    input_chunks = np.array_split(inputs, len(inputs) / 50)

    results = []
    for chunk in input_chunks:
        multicall_result = multicall.aggregate([fn(item) for item in chunk])
        for idx in range(len(chunk)):
            item = chunk[idx]
            result = multicall_result.results[idx].results[0]
            results.append((item, result))
    return results


@bot.event
async def on_ready() -> None:
    for guild in bot.guilds:
        logger.print_ok(f"{bot.user} is connected to guild:\n" f"{guild.name}(id: {guild.id})")

    logger.print_bold(f"Starting bot...")

    try:
        synced = await bot.tree.sync(guild=discord.Object(id=ALLOWLIST_GUILD))
        logger.print_normal(f"{len(synced)} command(s)")
    except Exception as e:
        logger.print_fail(f"{e}")


@bot.tree.command(
    name="getemission",
    description="Get emissions for a given mech id",
    guild=discord.Object(id=ALLOWLIST_GUILD),
)
async def mint_mech_command(interaction: discord.Interaction, mech_id: int) -> None:
    if not any([c for c in ALLOWLIST_CHANNELS if interaction.channel.id == c]):
        await interaction.response.send_message("Invalid channel")
        return

    logger.print_bold(f"Received mint emissions command")
    await interaction.response.defer()

    w3_mech: MechContractWeb3Client = (
        MechContractWeb3Client()
        .set_credentials(ADMIN_ADDRESS, "")
        .set_node_uri(AvalancheCWeb3Client.NODE_URL)
        .set_contract()
        .set_dry_run(False)
    )

    jp_api = JoePegsClient()
    item = jp_api.get_item(w3_mech.contract_address, mech_id)
    name = item.get("metadata", {}).get("name", "UNKNONWN")
    emission_multiplier = w3_mech.get_mech_multiplier(mech_id)
    url = JOEPEGS_ITEM_URL.format(w3_mech.contract_address, mech_id)
    message = (
        f"[**MECH {mech_id}**]({url}) [{name.upper()}] emissions: `{emission_multiplier / 10.0}`"
    )

    await interaction.followup.send(message)


@bot.tree.command(
    name="shkholders",
    description=f"Get top {TOP_N} SHK holders",
    guild=discord.Object(id=ALLOWLIST_GUILD),
)
async def shk_holders_command(interaction: discord.Interaction) -> None:
    if not any([c for c in ALLOWLIST_CHANNELS if interaction.channel.id == c]):
        await interaction.response.send_message("Invalid channel")
        return

    logger.print_bold(f"Received shk holders command")

    if not os.path.isfile(MECH_STATS_CACHE_FILE):
        await interaction.response.send_message("Missing data")
        return

    with open(MECH_STATS_CACHE_FILE, "r") as infile:
        shk_balances = json.load(infile)

    total_shk = 0.0
    for address, totals in shk_balances.items():
        total_shk += totals["shk"]

    sorted_balances = sorted(shk_balances.items(), key=lambda x: -x[1]["shk"])

    body = []
    leader_shk = None
    for address, totals in sorted_balances[:TOP_N]:
        shk = totals["shk"]
        row = [address, f"{shk:,.2f}", f"{shk/total_shk * 100.0:.2f}%"]
        if leader_shk is None:
            leader_shk = shk
            row.append("n/a")
        else:
            row.append(f"{shk/leader_shk * 100.0:.1f}%")
        body.append(row)

    table_text = table2ascii.table2ascii(
        header=["Owner", "$SHK", "% Supply", "% Leader"],
        body=body,
        footer=[],
        alignments=[
            table2ascii.Alignment.LEFT,
            table2ascii.Alignment.CENTER,
            table2ascii.Alignment.CENTER,
            table2ascii.Alignment.CENTER,
        ],
    )

    message = f"```\n{table_text}\n```"
    await interaction.response.send_message(message)


@bot.tree.command(
    name="shktotal",
    description="Total SHK held",
    guild=discord.Object(id=ALLOWLIST_GUILD),
)
async def shk_total_command(interaction: discord.Interaction) -> None:
    if not any([c for c in ALLOWLIST_CHANNELS if interaction.channel.id == c]):
        await interaction.response.send_message("Invalid channel")
        return

    logger.print_bold(f"Received shk total command")

    if not os.path.isfile(MECH_STATS_CACHE_FILE):
        await interaction.response.send_message("Missing data")
        return

    with open(MECH_STATS_CACHE_FILE, "r") as infile:
        shk_balances = json.load(infile)

    total_shk = 0.0
    for address, totals in shk_balances.items():
        total_shk += totals["shk"]

    message = f"**SHK Held:** `{total_shk:,.2f} $SHK`"
    await interaction.response.send_message(message)


@bot.tree.command(
    name="holdercount",
    description="Total wallets with mech(s)",
    guild=discord.Object(id=ALLOWLIST_GUILD),
)
async def holders_total_command(interaction: discord.Interaction) -> None:
    if not any([c for c in ALLOWLIST_CHANNELS if interaction.channel.id == c]):
        await interaction.response.send_message("Invalid channel")
        return

    logger.print_bold(f"Received holder total command")

    if not os.path.isfile(MECH_STATS_CACHE_FILE):
        await interaction.response.send_message("Missing data")
        return

    with open(MECH_STATS_CACHE_FILE, "r") as infile:
        shk_balances = json.load(infile)

    total = len(shk_balances.keys())

    message = f"**Unique holders:** `{total}`"
    await interaction.response.send_message(message)


@bot.tree.command(
    name="plots",
    description=f"Plot of SHK held for top {TOP_N} holders",
    guild=discord.Object(id=ALLOWLIST_GUILD),
)
async def shk_plots_command(
    interaction: discord.Interaction,
    nft_type: T.Literal["MECHS", "SHK"],
    address: str = "",
    top_n_holders: int = TOP_N,
    delta: bool = False,
) -> None:
    if not any([c for c in ALLOWLIST_CHANNELS if interaction.channel.id == c]):
        await interaction.response.send_message("Invalid channel")
        return

    logger.print_bold(f"Received plots command")

    if not os.path.isfile(MECH_STATS_HISTORY_FILE):
        await interaction.response.send_message("Missing data")
        return

    if not os.path.isfile(MECH_STATS_CACHE_FILE):
        await interaction.response.send_message("Missing data")
        return

    with open(MECH_STATS_CACHE_FILE, "r") as infile:
        shk_balances = json.load(infile)

    sorted_balances = sorted(shk_balances.items(), key=lambda x: -x[1][nft_type.lower()])

    top_holders = []

    if address and top_n_holders:
        top_n_holders = 1

    if address:
        w3: MechContractWeb3Client = (
            MechContractWeb3Client()
            .set_credentials(ADMIN_ADDRESS, "")
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(False)
        )
        resolved_address = await async_func_wrapper(resolve_address_to_avvy, w3.w3, address)
        if Web3.isChecksumAddress(resolved_address):
            resolved_address = await async_func_wrapper(shortened_address_str, resolved_address)
        top_holders.append(resolved_address)
    else:
        for stats in sorted_balances[:top_n_holders]:
            address = stats[0]
            if Web3.isChecksumAddress(address):
                address = await async_func_wrapper(shortened_address_str, stats[0])
            top_holders.append(address)

    with open(MECH_STATS_HISTORY_FILE, "r") as infile:
        data = json.load(infile)

    plot = []
    row_label = []
    row_length = 0
    for address, stats in data.items():
        if Web3.isChecksumAddress(address):
            address = await async_func_wrapper(shortened_address_str, address)

        if address not in top_holders:
            continue

        row_label.append(address)
        if delta:
            MAX_DELTA = 100
            row = [min(v, MAX_DELTA) for v in np.diff(stats[nft_type.lower()])]
        else:
            row = stats[nft_type.lower()]
        plot.append(row)
        row_length = max(row_length, len(row))

    row_label.append("sample")
    plot.append(list(range(row_length)))

    dataframe = pd.DataFrame(plot, index=row_label).T
    logger.print_normal(f"{dataframe}")

    if delta:
        title = f"{nft_type.upper()} Rate Change"
    else:
        title = f"{nft_type.upper()} Over Time"
    dataframe.plot(x="sample", y=top_holders, kind="line", title=title)
    plt.legend(bbox_to_anchor=(1.05, 0.5), loc="center left", borderaxespad=0)
    await async_func_wrapper(plt.savefig, MECH_STATS_PLOT, bbox_inches="tight", dpi=100)

    embed = discord.Embed()
    attachment = discord.File(MECH_STATS_PLOT)
    embed.set_image(url=f"attachment://{os.path.basename(MECH_STATS_PLOT)}")
    await interaction.response.send_message(embed=embed, file=attachment)


@bot.tree.command(
    name="mechholders",
    description=f"Get top {TOP_N} MECH holders",
    guild=discord.Object(id=ALLOWLIST_GUILD),
)
async def mech_holders_command(interaction: discord.Interaction) -> None:
    if not any([c for c in ALLOWLIST_CHANNELS if interaction.channel.id == c]):
        await interaction.response.send_message("Invalid channel")
        return

    logger.print_bold(f"Received mech holders command")

    if not os.path.isfile(MECH_STATS_CACHE_FILE):
        await interaction.response.send_message("Missing data")
        return

    with open(MECH_STATS_CACHE_FILE, "r") as infile:
        shk_balances = json.load(infile)

    sorted_balances = sorted(shk_balances.items(), key=lambda x: -x[1]["mechs"])

    total_mechs = 0
    for _, totals in sorted_balances:
        total_mechs += totals.get("mechs", 0)

    body = []
    for address, totals in sorted_balances[:TOP_N]:
        row = [address, totals["mechs"], f"{float(totals['mechs']) / total_mechs * 100.0:.2f}%"]
        body.append(row)

    table_text = table2ascii.table2ascii(
        header=["Owner", "MECHS", "% Total Supply"],
        body=body,
        footer=[],
        alignments=[
            table2ascii.Alignment.LEFT,
            table2ascii.Alignment.CENTER,
            table2ascii.Alignment.CENTER,
        ],
    )
    message = f"```\n{table_text}\n```"
    await interaction.response.send_message(message)


@bot.tree.command(
    name="mintmech",
    description="Mint a mech from the guild wallet. Authorized users only",
    guild=discord.Object(id=ALLOWLIST_GUILD),
)
async def mint_mech_command(interaction: discord.Interaction) -> None:
    if not any([c for c in ALLOWLIST_CHANNELS if interaction.channel.id == c]):
        await interaction.response.send_message("Invalid channel")
        return

    if not any([u for u in ALLOWLIST_MINTERS if interaction.user.id == u]):
        await interaction.response.send_message("Insufficient permissions")
        return

    logger.print_bold(f"Received mintmech command")
    await interaction.response.defer()

    w3_mech: MechContractWeb3Client = (
        MechContractWeb3Client()
        .set_credentials(ADDRESS, PRIVATE_KEY)
        .set_node_uri(AvalancheCWeb3Client.NODE_URL)
        .set_contract()
        .set_dry_run(False)
    )

    shk_balance = await async_func_wrapper(w3_mech.get_deposited_shk, GUILD_WALLET_ADDRESS)
    min_mint_shk = await async_func_wrapper(w3_mech.get_min_mint_bid)

    tx_hash = await async_func_wrapper(w3_mech.mint_from_shk)
    action_str = f"Mint MECH for {min_mint_shk:.2f} using $SHK balance of {shk_balance:.2f}"
    _, txn_url = process_w3_results(w3_mech, action_str, tx_hash)
    if txn_url:
        message = (
            f"\U0001F389\U0001F389 Successfully minted a new MECH!\U0001F389\U0001F389\n{txn_url}"
        )
        logger.print_ok_arrow(message)
    else:
        message = f"\U00002620\U00002620 Failed to mint new MECH!\U00002620\U00002620"
        logger.print_fail_arrow(message)

    await interaction.followup.send(message)


@bot.tree.command(
    name="lastmint",
    description="Get last mint",
    guild=discord.Object(id=ALLOWLIST_GUILD),
)
async def get_last_mint_command(
    interaction: discord.Interaction, nft_type: T.Literal["MECH", "MARM"]
) -> None:
    if not any([c for c in ALLOWLIST_CHANNELS if interaction.channel.id == c]):
        await interaction.response.send_message("Invalid channel")
        return

    logger.print_bold(f"Received lastmint command")

    w3_mech: MechContractWeb3Client = (
        MechContractWeb3Client()
        .set_credentials(ADMIN_ADDRESS, "")
        .set_node_uri(AvalancheCWeb3Client.NODE_URL)
        .set_contract()
        .set_dry_run(False)
    )

    w3_arm: MechArmContractWeb3Client = (
        MechArmContractWeb3Client()
        .set_credentials(ADMIN_ADDRESS, "")
        .set_node_uri(AvalancheCWeb3Client.NODE_URL)
        .set_contract()
        .set_dry_run(False)
    )

    latest_block = w3_mech.w3.eth.block_number
    if nft_type == "MECH":
        event_function = w3_mech.contract.events.MechPurchased
    elif nft_type == "MARM":
        event_function = w3_mech.contract.events.ShirakBalanceUpdated
    else:
        logger.print_fail(f"Invalid parameters {nft_type}")
        await interaction.response.send_message("Invalid parameters")
        return

    events = []
    for i in range(500):
        events.extend(event_function.getLogs(fromBlock=latest_block - 2048, toBlock=latest_block))
        if len(events) > 0:
            break

        latest_block -= 2048
        if latest_block < 0:
            break

    data = json.dumps(Web3.toJSON(events))

    price = 0.0
    latest_event = 0
    for event in events:
        block_number = event.get("blockNumber", 0)
        if block_number == 0:
            continue

        if nft_type == "MECH":
            price_wei = event.get("args", {}).get("price", 0.0)
            price = wei_to_token(price_wei)
            timestamp = w3_mech.w3.eth.get_block(block_number).timestamp
        elif nft_type == "MARM":
            tx_hash = event["transactionHash"]
            tx_receipt = w3_arm.get_transaction_receipt(tx_hash)
            transaction = tx_receipt["logs"][1]
            if transaction["address"] != w3_arm.contract_address:
                continue

            price_wei = int(transaction["data"], 16)
            price = wei_to_token(price_wei)
            timestamp = w3_arm.w3.eth.get_block(block_number).timestamp

        latest_event = max(latest_event, timestamp)

    time_since = int(time.time() - latest_event)

    message = (
        f"Last mint happened `{general.get_pretty_seconds(time_since)}` ago for `{price:.2f} $SHK`"
    )
    logger.print_normal(message)
    await interaction.response.send_message(message)


@bot.tree.command(
    name="mintcost",
    description="Get current cost in $SHK to mint MECH",
    guild=discord.Object(id=ALLOWLIST_GUILD),
)
async def guild_stats_command(interaction: discord.Interaction) -> None:
    if not any([c for c in ALLOWLIST_CHANNELS if interaction.channel.id == c]):
        await interaction.response.send_message("Invalid channel", ephemeral=True)
        return

    logger.print_bold(f"Received mintcost command")

    w3_mech: MechContractWeb3Client = (
        MechContractWeb3Client()
        .set_credentials(ADMIN_ADDRESS, "")
        .set_node_uri(AvalancheCWeb3Client.NODE_URL)
        .set_contract()
        .set_dry_run(False)
    )

    mint_cost_shk = await async_func_wrapper(w3_mech.get_min_mint_bid)
    await interaction.response.send_message(f"Next mint cost: `{mint_cost_shk:.2f} $SHK`")


async def get_guild_table_row(
    totals: T.Dict[str, int],
    address: str,
    nft_data: T.Dict[str, T.Dict[str, T.Any]],
    token_data: T.Dict[str, T.Dict[str, T.Any]],
    emissions: bool,
) -> T.Tuple[T.List[T.Any], float]:
    row = []

    w3_mech: MechContractWeb3Client = (
        MechContractWeb3Client()
        .set_credentials(ADMIN_ADDRESS, "")
        .set_node_uri(AvalancheCWeb3Client.NODE_URL)
        .set_contract()
        .set_dry_run(False)
    )

    address = Web3.toChecksumAddress(address)
    shortened_address = await async_func_wrapper(shortened_address_str, address)
    row.append(shortened_address)
    owner = GUILD_WALLET_MAPPING.get(address, "").split("#")[0]
    row.append(owner)
    marms = nft_data.get("MARM", [])
    mechs = nft_data.get("MECH", [])
    multiplier = 0
    if emissions:
        for mech in mechs:
            multiplier += await async_func_wrapper(w3_mech.get_mech_multiplier, int(mech))
    shk = token_data.get("SHK", 0)
    row.append(len(mechs))
    row.append(len(marms))
    row.append(int(shk))
    totals["MECH"] += len(mechs)
    totals["MARM"] += len(marms)
    totals["SHK"] += shk

    if emissions:
        multiplier /= 10.0
        row.append(f"{multiplier:.1f}")
        totals["Emissions"] += multiplier

    ownership_points = 0
    ownership_points += len(mechs) * GUILD_MULTIPLIERS["MECH"]
    ownership_points += len(marms) * GUILD_MULTIPLIERS["MARM"]
    ownership_points += shk * GUILD_MULTIPLIERS["SHK"]
    if emissions:
        ownership_points += multiplier * GUILD_MULTIPLIERS["Emissions"]

    return row, ownership_points


@bot.tree.command(
    name="guildstats",
    description="Get Cashflow Cartel Guild Stats",
    guild=discord.Object(id=ALLOWLIST_GUILD),
)
async def guild_stats_command(interaction: discord.Interaction, with_emissions: bool) -> None:
    if not any([c for c in ALLOWLIST_CHANNELS if interaction.channel.id == c]):
        await interaction.response.send_message("Invalid channel", ephemeral=True)
        return

    logger.print_bold(f"Received guildstats command")
    await interaction.response.defer()

    holders = await async_func_wrapper(
        SnowtraceApi().get_erc721_token_transfers, GUILD_WALLET_ADDRESS
    )
    shk_holders = await async_func_wrapper(
        SnowtraceApi().get_erc20_token_transfers, GUILD_WALLET_ADDRESS
    )

    if not holders:
        await interaction.followup.send("Could not obtain data. Try again later...")
        return

    totals = {"MECH": 0, "MARM": 0, "SHK": 0}
    if with_emissions:
        totals["Emissions"] = 0

    info = {}
    for address, data in holders.items():
        address = Web3.toChecksumAddress(address)
        row, points = await get_guild_table_row(
            totals, address, data, shk_holders.get(address, {}), with_emissions
        )
        if address in IGNORE_ADDRESSES:
            points = 0

        info[address] = (row, points)

    total_guild_management_percents = sum([f for f in GUILD_MANAGEMENT_FEE.values()])
    total_ownership_points = sum([points for _, points in info.values()])
    total_ownership_points_after_fees = total_ownership_points / (
        1 - total_guild_management_percents
    )

    rows = []
    total_ownership_percent = 0.0
    for address, data in info.items():
        row, points = data
        fee_percent = GUILD_MANAGEMENT_FEE.get(address, 0.0) / total_guild_management_percents
        fee_points = fee_percent * (total_ownership_points_after_fees - total_ownership_points)
        ownership_percent = points + fee_points
        ownership_percent /= total_ownership_points_after_fees
        ownership_percent *= 100.0
        total_ownership_percent += ownership_percent
        row.append(ownership_percent)
        rows.append(row)

    body = []
    rows.sort(key=lambda x: x[-1])
    rows.reverse()

    for row in rows:
        row[-1] = f"{row[-1]:.1f}%"
        body.append(row)

    assert math.isclose(
        total_ownership_percent, 100.0, abs_tol=0.0001
    ), f"ownership doesn't equal 100%! {total_ownership_percent}"

    message = "**Guild Distribution**\n"
    header = ["Address", "Owner", "MECH", "MARM", "SHK"]
    footer = [
        "Totals",
        "",
        totals["MECH"],
        totals["MARM"],
        f"{int(totals['SHK'])}",
    ]

    if with_emissions:
        header.append("Emissions")
        footer.append(f"{totals['Emissions']:.1f}")

    header.append("Ownership")
    footer.append("100%")

    table_text = table2ascii.table2ascii(
        header=header,
        body=body,
        footer=footer,
    )
    message += f"```\n{table_text}\n```"

    w3_mech: MechContractWeb3Client = (
        MechContractWeb3Client()
        .set_credentials(ADMIN_ADDRESS, "")
        .set_node_uri(AvalancheCWeb3Client.NODE_URL)
        .set_contract()
        .set_dry_run(False)
    )

    multiplier = await async_func_wrapper(w3_mech.get_emmissions_multiplier, GUILD_WALLET_ADDRESS)
    shk_balance = await async_func_wrapper(w3_mech.get_deposited_shk, GUILD_WALLET_ADDRESS)

    message += f"**SHK Deposited**: `{shk_balance:.2f}` | "
    message += f"**Multiplier**: `{multiplier:.2f}`\n"
    weights = " ".join([f"**{k}:** `{v}x`, " for k, v in GUILD_MULTIPLIERS.items()])
    message += f"**Ownership Weights:**\n{weights}\n\n"
    message += f"**Ownership % includes management fee\n"

    logger.print_ok_blue(message)

    await interaction.followup.send(message)


bot.run(DISCORD_MECHAVAX_SALES_BOT_TOKEN)
