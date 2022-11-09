import asyncio
import discord
import os

from config_admin import DISCORD_BOT_SERVER, DISCORD_P2E_BOT_TOKEN
from utils import logger
from discord_bots.command_bots import default, p2e_pumpskin


intents: discord.Intents = discord.Intents.default()
intents.typing = False
intents.presences = False
client = discord.Client(intents=intents)

BOT_RESPONSES: default.OnMessage = [
    p2e_pumpskin.ManageAccounts,
]


@client.event
async def on_ready() -> None:
    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(type=discord.ActivityType.watching, name="Your mom"),
    )

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


client.run(DISCORD_P2E_BOT_TOKEN)
