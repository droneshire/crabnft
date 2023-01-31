import asyncio
import discord
import json
import os
import table2ascii
import time
import typing as T

from discord.ext import commands
from web3 import Web3

from config_admin import (
    ADMIN_ADDRESS,
    DISCORD_MECHAVAX_SALES_BOT_TOKEN,
    GUILD_WALLET_ADDRESS,
    GUILD_WALLET_MAPPING,
)
from mechavax.mechavax_web3client import MechContractWeb3Client
from utils import general, logger
from utils.price import wei_to_token, TokenWei
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.snowtrace import SnowtraceApi

bot = commands.Bot(command_prefix="/", intents=discord.Intents.all())

ALLOWLIST_GUILD = 986151371923410975
ALLOWLIST_CHANNELS = [
    1032890276420800582,  # test channel in p2e auto
    1067902019379142671,  # p2e mechavax channel
]
MINT_ADDRESS = "0x0000000000000000000000000000000000000000"


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
    name="lastmint",
    description="Get last mint",
    guild=discord.Object(id=ALLOWLIST_GUILD),
)
async def get_last_mint_command(interaction: discord.Interaction) -> None:
    logger.print_normal(f"Received lastmint command")
    await interaction.response.defer()

    w3_mech: MechContractWeb3Client = (
        MechContractWeb3Client()
        .set_credentials(ADMIN_ADDRESS, "")
        .set_node_uri(AvalancheCWeb3Client.NODE_URL)
        .set_contract()
        .set_dry_run(False)
    )

    latest_block = w3_mech.w3.eth.block_number
    events = []
    for i in range(500):
        events.extend(
            w3_mech.contract.events.MechPurchased.getLogs(
                fromBlock=latest_block - 2048, toBlock=latest_block
            )
        )
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
        price_wei = event.get("args", {}).get("price", 0.0)
        price = wei_to_token(price_wei)
        timestamp = w3_mech.w3.eth.get_block(block_number).timestamp
        latest_event = max(latest_event, timestamp)

    time_since = int(time.time() - latest_event)

    message = (
        f"Last mint happened `{general.get_pretty_seconds(time_since)}` ago for `{price:.2f} $SHK`"
    )
    logger.print_normal(message)
    await interaction.followup.send(message)


@bot.tree.command(
    name="guildstats",
    description="Get Cashflow Cartel Guild Stats",
    guild=discord.Object(id=ALLOWLIST_GUILD),
)
async def guild_stats_command(interaction: discord.Interaction) -> None:
    if not any([c for c in ALLOWLIST_CHANNELS if interaction.channel.id == c]):
        await interaction.response.send_message("Invalid channel", ephemeral=True)
        return

    logger.print_normal(f"Received guildstats command")
    await interaction.response.defer()

    holders = await SnowtraceApi().get_erc721_token_transfers(GUILD_WALLET_ADDRESS)

    if not holders:
        await interaction.followup.send("Could not obtain data. Try again later...")
        return

    body = []
    totals = {"MECH": 0, "MARM": 0}

    for address, data in holders.items():
        row = []
        address = Web3.toChecksumAddress(address)
        if address == MINT_ADDRESS:
            continue
        row.append(f"{address[:5]}...{address[-4:]}")
        owner = GUILD_WALLET_MAPPING.get(address, "")
        row.append(owner)
        marms = len(data.get("MARM", []))
        mechs = len(data.get("MECH", []))
        row.append(mechs)
        row.append(marms)
        totals["MECH"] += mechs
        totals["MARM"] += marms
        body.append(row)

    row = []
    row.append(f"{MINT_ADDRESS[:5]}...{MINT_ADDRESS[-4:]}")
    owner = GUILD_WALLET_MAPPING.get(MINT_ADDRESS, "")
    row.append(owner)
    marms = len(holders.get(MINT_ADDRESS, {}).get("MARM", []))
    mechs = len(holders.get(MINT_ADDRESS, {}).get("MECH", []))
    row.append(mechs)
    row.append(marms)
    totals["MECH"] += mechs
    totals["MARM"] += marms
    body.append(row)

    message = "**Guild Distribution**\n"
    table_text = table2ascii.table2ascii(
        header=["Address", "Owner", "MECH", "MARM"],
        body=body,
        footer=["Totals", "", totals["MECH"], totals["MARM"]],
    )
    message += f"```\n{table_text}\n```"
    logger.print_ok_blue(message)

    await interaction.followup.send(message)


bot.run(DISCORD_MECHAVAX_SALES_BOT_TOKEN)
