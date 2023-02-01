import asyncio
import discord
import os

from config_admin import DISCORD_PUMPSKIN_BOT_TOKEN
from utils import logger
from discord_bots.command_bots import default, pumpskin
from pumpskin.bot import PumpskinBot
from pumpskin.utils import get_mint_stats

intents: discord.Intents = discord.Intents.default()
intents.typing = False
intents.presences = False
client = discord.Client(intents=intents)

BOT_RESPONSES: default.OnMessage = [
    pumpskin.GetPumpkinLevel,
    pumpskin.GetPumpkinRoi,
    pumpskin.SnoopChannel,
    pumpskin.MintNumber,
]


DEFAULT_WAIT_TIME = 400


async def status_task():
    last_status = ""
    wait_time = DEFAULT_WAIT_TIME
    while True:
        await asyncio.sleep(wait_time)
        minted, supply = get_mint_stats()
        mint_status = f"Mint {minted}/{supply}"
        logger.print_normal(f"Updating: {mint_status}")
        if last_status != mint_status:
            try:
                await client.user.edit(username=mint_status)
                wait_time = DEFAULT_WAIT_TIME
                last_status = mint_status
            except:
                wait_time = wait_time * 2
                logger.print_fail(f"Failed to update username status")


@client.event
async def on_ready() -> None:
    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(type=discord.ActivityType.watching, name="Pump$kin Contract"),
    )
    await client.user.edit(username="Pumpskin Bot")

    for guild in client.guilds:
        logger.print_ok(f"{client.user} is connected to guild:\n" f"{guild.name}(id: {guild.id})")


@client.event
async def on_message(message: discord.message.Message) -> None:

    if message.author == client.user:
        return

    for bot in BOT_RESPONSES:
        response = bot.response(message)
        if response:
            if type(response) == discord.Embed:
                await message.channel.send(embed=response)
            else:
                await message.channel.send(response)


client.run(DISCORD_PUMPSKIN_BOT_TOKEN)
