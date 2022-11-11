import asyncio
import discord
import os

from config_admin import DISCORD_RED_CHIP_STUDIO_BOT_TOKEN
from utils import logger
from discord_bots.sales_bots.joepegs_sales_bot import JoePegsSalesBot

intents: discord.Intents = discord.Intents.default()
intents.typing = False
intents.presences = False
client = discord.Client(intents=intents)

TIME_BETWEEN_CHECKS = 60.0 * 1.0
TIME_BETWEEN_POSTS = 5.0

BOT_NAME = "Red Chip Studio Sales Bot"
ACTIVITY_STATUS = "RCS Sales"
COLLECTIONS = [
    "0x39d9fa049c641c905cc4e1f16c7061aab14ba25e",  # BEEG MACS
    "0x7ba0bc939a74402f479a3d53408dd4b3ccf48563",  # WARRIORS OF FREYA
    "0xba7e1d73e2ea297c473f3d16f428da7a9a7dc516",  # BIFROST - WARRIORS OF FREYA
    "0x6aa86a31629a5499404fdb68b96d59ed41951502",
    "0x20625bb21cbb7f3adb66aa7b1f887c0653bde2a5",
    "0xfad87339fe82fa14cb66d639f2e294c147dc187c",
    "0x6176ba2cdf66e5fdd3551da793d2803131a51cb8",
]
SALES_CHANNEL_ID = 1039107410620600380  # Sales bot channel

discord_bot_dir = logger.get_logging_dir("discord_bots")
log_dir = os.path.join(discord_bot_dir, "red_chip_studio")

sales_bot = JoePegsSalesBot(BOT_NAME, discord.Color.red(), COLLECTIONS, log_dir)


async def sales_loop():
    sales_channel = client.get_channel(SALES_CHANNEL_ID)
    while True:
        logger.print_normal(f"Checking for new sales...")
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


client.run(DISCORD_RED_CHIP_STUDIO_BOT_TOKEN)
