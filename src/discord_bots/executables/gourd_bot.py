import asyncio
import discord
import os

from config_admin import DISCORD_BOT_SERVER, DISCORD_BOT_TOKEN
from utils import logger
from discord_bots import behavior, pumpskin
from pumpskin.pumpskin_bot import PumpskinBot

intents: discord.Intents = discord.Intents.default()
intents.typing = False
intents.presences = False
client = discord.Client(intents=intents)

BOT_RESPONSES: behavior.OnMessage = [
    pumpskin.GetPumpkinLevel,
    pumpskin.GetPumpkinRoi,
    pumpskin.SnoopChannel,
]

STATUS_UPDATE_TIME = 60 * 2


async def status_task():
    last_status = ""
    while True:
        minted, supply = PumpskinBot.get_mint_stats()
        mint_status = f"Mint {minted}/{supply}"
        logger.print_normal(f"Updating: {mint_status}")
        if last_status != mint_status:
            await client.user.edit(username=mint_status)
        last_status = mint_status
        await asyncio.sleep(STATUS_UPDATE_TIME)


@client.event
async def on_ready() -> None:
    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(type=discord.ActivityType.watching, name="Pump$kin Contract"),
    )
    for guild in client.guilds:
        logger.print_ok(f"{client.user} is connected to guild:\n" f"{guild.name}(id: {guild.id})")

    client.loop.create_task(status_task())


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


client.run(DISCORD_BOT_TOKEN)
