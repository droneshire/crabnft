import asyncio
import discord
import os

from config_admin import DISCORD_PUMPSKIN_MINT_BOT_TOKEN
from utils import logger
from pumpskin.mint_snipes import PumpskinMintSniper

intents: discord.Intents = discord.Intents.default()
intents.typing = False
intents.presences = False
client = discord.Client(intents=intents)

TIME_BETWEEN_CHECKS = 5.0
BOT_NAME = "Pumpskin Sniper"
ACTIVITY_STATUS = "Mint"
CHANNEL_ID = 1039611842525405204  # test channel
NEXT_MINTS = 15


async def sales_loop() -> None:
    channel = client.get_channel(CHANNEL_ID)
    discord_bot_dir = logger.get_logging_dir("discord_bots")
    log_dir = os.path.join(discord_bot_dir, "pumpskin_mint")
    sniper = PumpskinMintSniper(log_dir)
    while True:
        embeds = sniper.get_next_mints_embeds(NEXT_MINTS)
        for embed in embeds:
            await channel.send(embed=embed)
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


client.run(DISCORD_PUMPSKIN_MINT_BOT_TOKEN)
