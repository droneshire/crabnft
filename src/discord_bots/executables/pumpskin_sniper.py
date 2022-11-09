import asyncio
import discord
import os

from config_admin import DISCORD_PUMPSKIN_SALES_BOT_TOKEN
from utils import logger
from discord_bots.sales_bots.joepegs_sales_bot import JoePegsSalesBot
from pumpskin.pumpskin_web3_client import PumpskinNftWeb3Client

intents: discord.Intents = discord.Intents.default()
intents.typing = False
intents.presences = False
client = discord.Client(intents=intents)

TIME_BETWEEN_CHECKS = 1.0
BOT_NAME = "Pumpskin Sniper"
ACTIVITY_STATUS = "Pumpskin Market"
COLLECTIONS = [
    PumpskinNftWeb3Client.contract_address,
    "0xCF735808a42c06EA06533CE2bC4a4A3a78565326",
    "0xDBcd3d15F4dC4e59DA79008f5997f262C06f1F3A",
]
SALES_CHANNEL_ID = 1032881170838462474  # Deals channel P2E


async def sales_loop():
    sales_channel = client.get_channel(SALES_CHANNEL_ID)
    while True:
        embeds = sales_bot.get_sales_embeds()
        for embed in embeds:
            await sales_channel.send(embed=embed)
        await asyncio.sleep(TIME_BETWEEN_CHECKS)


@client.event
async def on_ready() -> None:
    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(type=discord.ActivityType.watching, name=ACTIVITY_STATUS),
    )
    await client.user.edit(username=BOT_NAME)

    for guild in client.guilds:
        logger.print_ok(f"{client.user} is connected to guild:\n" f"{guild.name}(id: {guild.id})")

    client.loop.create_task(sales_loop())


client.run(DISCORD_PUMPSKIN_SALES_BOT_TOKEN)
