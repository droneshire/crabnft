import discord
import os

from config_admin import DISCORD_BOT_SERVER, DISCORD_BOT_TOKEN
from utils import logger
from discord_bots import behavior, pumpskin

intents: discord.Intents = discord.Intents.default()
intents.typing = False
intents.presences = False
client = discord.Client(intents=intents)

BOT_RESPONSES: behavior.OnMessage = [
    pumpskin.GetPumpkinLevel,
]


@client.event
async def on_ready() -> None:
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


client.run(DISCORD_BOT_TOKEN)
