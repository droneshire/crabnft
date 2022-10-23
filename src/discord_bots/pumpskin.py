import discord
import time
import typing as T

from discord import Color
from discord_webhook import DiscordEmbed, DiscordWebhook

from config_admin import ADMIN_ADDRESS
from discord_bots.behavior import OnMessage
from utils import logger
from utils.general import get_pretty_seconds
from pumpskin.pumpskin_bot import PumpskinBot
from pumpskin.pumpskin_web3_client import PumpskinCollectionWeb3Client
from pumpskin.pumpskin_web2_client import PumpskinWeb2Client
from pumpskin.types import StakedPumpskin
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client


class GetPumpkinLevel(OnMessage):
    HOTKEY = f"?plvl"
    ALLOWLIST_GUILDS = [986151371923410975, 1020800321569697792]
    ALLOWLIST_CHANNELS = [1027614935523532900, 1032890276420800582, 1032276350045798441]

    @staticmethod
    def _get_pumpskin_info_embed(
        token_id: int, level: int, image_uri: str, cooldown_time: str
    ) -> None:
        embed = discord.Embed(
            title=f"PUMP$KIN INFO",
            description=f"Cooldown time: {cooldown_time}\n",
            color=Color.orange().value,
        )

        embed.add_field(name=f"Pumpskin", value=f"{token_id}", inline=False)
        embed.add_field(name=f"Level", value=f"{level}", inline=True)
        ppie_per_day = PumpskinBot._calc_ppie_per_day_from_level(level)
        embed.add_field(name=f"$PPIE/Day", value=f"{ppie_per_day}", inline=True)
        potn_to_level = PumpskinBot._calc_potn_from_level(level)
        embed.add_field(name=f"Cost For Next Level:", value=f"{potn_to_level} $POTN", inline=False)

        embed.set_thumbnail(url=image_uri)
        return embed

    @classmethod
    def response(cls, message: discord.message.Message) -> T.Union[str, discord.Embed]:
        text = message.content.lower().strip()
        if not text.startswith(cls.HOTKEY):
            return ""

        if not any([g for g in cls.ALLOWLIST_GUILDS if message.guild.id == g]):
            return ""

        logger.print_normal(message.channel.name, message.channel.id)
        if not any([c for c in cls.ALLOWLIST_CHANNELS if message.channel.id == c]):
            return ""

        try:
            token_id = int(text.strip().split(cls.HOTKEY)[1])
        except ValueError:
            return ""

        # try:
        w3: PumpskinCollectionWeb3Client = (
            PumpskinCollectionWeb3Client()
            .set_credentials(ADMIN_ADDRESS, "")
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_dry_run(False)
        )

        w2: PumpskinWeb2Client = PumpskinWeb2Client()

        pumpskin_info: StakedPumpskin = w3.get_staked_pumpskin_info(token_id)
        pumpskin_image_uri = w2.get_pumpskin_image(token_id)

        now = time.time()
        cooldown_time = pumpskin_info["cooldown_ts"] - now
        if cooldown_time < 0:
            cooldown_time = 0
        cooldown_time_pretty = get_pretty_seconds(cooldown_time)

        ml = int(pumpskin_info["kg"] / 100)

        embed = cls._get_pumpskin_info_embed(token_id, ml, pumpskin_image_uri, cooldown_time_pretty)

        logger.print_normal(f"\U0001F383 **Pumpskin {token_id}**: ` ML {ml} `-> {message.channel}")
        return embed
        # except:
        #     logger.print_normal(f"Unknown level for Pumpskin \U0001F937")
        #     return f"Unknown level for Pumpskin \U0001F937"
