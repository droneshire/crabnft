import asyncio
import discord
import os
import table2ascii
import typing as T

from discord import app_commands
from discord.ext import commands
from web3 import Web3

from config_admin import (
    DISCORD_MECHAVAX_SALES_BOT_TOKEN,
    GUILD_WALLET_ADDRESS,
    GUILD_WALLET_MAPPING,
)
from mechavax.mechavax_web3client import MechContractWeb3Client
from utils import logger
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
    marms = len(holders[MINT_ADDRESS].get("MARM", []))
    mechs = len(holders[MINT_ADDRESS].get("MECH", []))
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
