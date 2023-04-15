import discord
import typing as T

# Base class for parsing and responding to messages
class OnMessage:
    HOTKEY = ""
    ALLOWLIST_CHANNELS = []
    ALLOWLIST_GUILDS = []

    def response(
        cls, message: discord.message.Message
    ) -> T.Union[str, discord.Embed]:
        raise NotImplementedError()
