import asyncio
import discord
import os

from config_admin import DISCORD_MECHAVAX_SALES_BOT_TOKEN
from utils import file_util, logger
from discord_bots.sales_bots.mechavax_listing_bot import MechavaxListingBot

intents: discord.Intents = discord.Intents.default()
intents.typing = False
intents.presences = False
client = discord.Client(intents=intents)

TIME_BETWEEN_CHECKS = 30.0
TIME_BETWEEN_POSTS = 3.0

BOT_NAME = "Mechavax Listing Bot"
ACTIVITY_STATUS = "Mechavax Listings"
COLLECTIONS = [
    "0xb68f42c2c805b81dad78d2f07244917431c7f322",
]
SALES_CHANNEL_ID = 1069755720469319810  # Sales bot channel P2E

discord_bot_dir = logger.get_logging_dir("discord_bots")
log_dir = os.path.join(discord_bot_dir, "mechavax_listings")
file_util.make_sure_path_exists(log_dir)
sales_bot = MechavaxListingBot(BOT_NAME, discord.Color.dark_blue(), COLLECTIONS, log_dir)


async def listings_loop():
    sales_channel = client.get_channel(SALES_CHANNEL_ID)
    while True:
        logger.print_ok_blue(f"Checking for new listings...")
        embeds = sales_bot.get_listing_embeds()
        logger.print_bold(f"Found {len(embeds)} listings")
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

    client.loop.create_task(listings_loop())


client.run(DISCORD_MECHAVAX_SALES_BOT_TOKEN)
