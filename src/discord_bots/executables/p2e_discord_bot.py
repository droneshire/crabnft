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
    guild = discord.utils.get(client.guilds, name=DISCORD_BOT_SERVER)

    logger.print_ok(
        f"{client.user} is connected to the following guild:\n" f"{guild.name}(id: {guild.id})"
    )


@client.event
async def on_message(message: discord.message.Message) -> None:
    print(message.content)

    if message.author == client.user:
        return

    for bot in BOT_RESPONSES:
        response = bot.response(message.content)
        if response:
            await message.channel.send(response)


client.run(DISCORD_BOT_TOKEN)
