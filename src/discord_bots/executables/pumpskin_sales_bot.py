import asyncio
import discord
import os

from config_admin import DISCORD_PUMPSKIN_SALES_BOT_TOKEN
from utils import logger
from discord_bots.joepegs_sales_bot import JoePegsSalesBot
from pumpskin.pumpskin_web3_client import PumpskinNftWeb3Client

intents: discord.Intents = discord.Intents.default()
intents.typing = False
intents.presences = False
client = discord.Client(intents=intents)

TIME_BETWEEN_CHECKS = 60.0 * 1.0
TIME_BETWEEN_POSTS = 5.0

BOT_NAME = "Pumpskin Sales Bot"
ACTIVITY_STATUS = "Pumpskin Sales"
COLLECTIONS = [
    PumpskinNftWeb3Client.contract_address,
]
SALES_CHANNEL_ID = 1039452204257521684  # Sales bot channel P2E

discord_bot_dir = logger.get_logging_dir("discord_bots")
log_dir = os.path.join(discord_bot_dir, "pumpskin_sales")

sales_bot = JoePegsSalesBot(BOT_NAME, discord.Color.orange(), COLLECTIONS, log_dir)


async def sales_loop():
    sales_channel = client.get_channel(SALES_CHANNEL_ID)
    while True:
        logger.print_ok_blue(f"Checking for new sales...")
        embeds = sales_bot.get_sales_embeds()
        for embed in embeds:
            await sales_channel.send(embed=embed)
            await asyncio.sleep(TIME_BETWEEN_POSTS)
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
