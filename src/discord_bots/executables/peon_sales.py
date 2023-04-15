import asyncio
import discord
import os

from config_admin import DISCORD_PEON_SALES_BOT_TOKEN
from utils import file_util, logger
from discord_bots.sales_bots.peon_sales_bot import PeonSalesBot

intents: discord.Intents = discord.Intents.default()
intents.typing = False
intents.presences = False
client = discord.Client(intents=intents)

TIME_BETWEEN_CHECKS = 60.0 * 1.0
TIME_BETWEEN_POSTS = 5.0

BOT_NAME = "Peon Sales Bot"
ACTIVITY_STATUS = "Peon Sales"
COLLECTIONS = [
    "0x4c5a8b71330d751bf995472f3ab8ceb06a98dd47",
    "0x9a27660a1b610d3e617ca9fc58a648360e58bb9d",
    "0xcff1013584060cf075adf27dba1d2b5ad99d134c",
    "0x8fc82cbdd4babfa5b7d63044f1c253696451faef",
]
SALES_CHANNEL_ID = 1061841037422759936  # Sales bot channel P2E

discord_bot_dir = logger.get_logging_dir("discord_bots")
log_dir = os.path.join(discord_bot_dir, "peon_sales")
file_util.make_sure_path_exists(log_dir)
sales_bot = PeonSalesBot(
    BOT_NAME, discord.Color.dark_grey(), COLLECTIONS, log_dir
)


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
        activity=discord.Activity(
            type=discord.ActivityType.watching, name=ACTIVITY_STATUS
        ),
    )
    await client.user.edit(username=BOT_NAME)

    for guild in client.guilds:
        logger.print_ok(
            f"{client.user} is connected to guild:\n"
            f"{guild.name}(id: {guild.id})"
        )

    client.loop.create_task(sales_loop())


client.run(DISCORD_PEON_SALES_BOT_TOKEN)
