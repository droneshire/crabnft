import discord
import time
import typing as T

from discord import Color
from discord_webhook import DiscordEmbed, DiscordWebhook

from config_admin import ADMIN_ADDRESS
from crabada.crabada_web2_client import CrabadaWeb2Client
from discord_bots.behavior import OnMessage
from pumpskin.pumpskin_bot import PumpskinBot
from pumpskin.pumpskin_web3_client import PumpskinCollectionWeb3Client, PumpskinNftWeb3Client
from pumpskin.pumpskin_web2_client import PumpskinWeb2Client
from pumpskin.types import StakedPumpskin
from utils import logger
from utils.general import get_pretty_seconds
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client


AUTHOR_ICON_URL = "https://dwrcsi0lsmew9.cloudfront.net/AIWU_0x0c7cb7d9bbc1c2c9adc5406e9633d5e1fef2e883_56__width_750.jpg"
AUTHOR_TWITTER_URL = "https://twitter.com/Nftcashflow1"


class GetPumpkinLevel(OnMessage):
    HOTKEY = f"?plvll"
    ALLOWLIST_GUILDS = [986151371923410975, 1020800321569697792]
    ALLOWLIST_CHANNELS = [
        1027614935523532900,  # pumpskin main channel p2e auto
        1032890276420800582,  # test channel in p2e auto
        # 1032276350045798441, # farmers market in pumpskin
        1033839826182619228,  # pumpskin bot channel
    ]

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
        ppie_per_day = PumpskinBot.calc_ppie_per_day_from_level(level)
        embed.add_field(name=f"$PPIE/Day", value=f"{ppie_per_day}", inline=True)
        potn_to_level = PumpskinBot.calc_potn_from_level(level)
        embed.add_field(name=f"Level Up:", value=f"{potn_to_level} $POTN", inline=True)
        embed.add_field(
            name=f"\U0000200b", value=f"------------Attribute Rarity------------", inline=False
        )

        trait_count = 0
        for trait, rarity in PumpskinBot.calculate_rarity(
            token_id, PumpskinBot.get_attributes_file()
        ).items():
            if trait == "Overall":
                continue
            rarity_percent = rarity * 100.0
            trait_count += 1
            inline = trait_count % 9 != 0
            embed.add_field(name=f"{trait[:9]}", value=f"{rarity_percent:.2f}%", inline=inline)

        embed.add_field(name=f"\U0000200b", value=f"\U0000200b", inline=True)
        embed.set_thumbnail(url=image_uri)
        embed.set_author(name="NftCashFlow", url=AUTHOR_TWITTER_URL, icon_url=AUTHOR_ICON_URL)
        embed.set_footer(text=f"Tips appreciated {ADMIN_ADDRESS} \U0001F64F")
        return embed

    @classmethod
    def response(cls, message: discord.message.Message) -> T.Union[str, discord.Embed]:
        if not any([g for g in cls.ALLOWLIST_GUILDS if message.guild.id == g]):
            return ""

        logger.print_normal(f"{message.channel.name} id: {message.channel.id}")
        if not any([c for c in cls.ALLOWLIST_CHANNELS if message.channel.id == c]):
            return ""

        text = message.content.lower().strip()
        if not text.startswith(cls.HOTKEY):
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


class GetPumpkinRoi(OnMessage):
    HOTKEY = f"?proi"
    ALLOWLIST_GUILDS = [986151371923410975, 1020800321569697792]
    ALLOWLIST_CHANNELS = [
        1027614935523532900,  # pumpskin main channel p2e auto
        1032890276420800582,  # test channel in p2e auto
        # 1032276350045798441, # farmers market in pumpskin
        # 1033839826182619228,  # pumpskin bot channel
    ]

    @staticmethod
    def _get_pumpskin_roi_embed(
        pumpskin_price_avax: float, ppie_price_usd: float, roi_days: float
    ) -> None:
        embed = discord.Embed(
            title=f"PUMP$KIN ROI",
            description=f"Return on investment for a new mint\n",
            color=Color.red().value,
        )
        embed.add_field(name=f"ROI", value=f"{roi_days:.2f} days", inline=False)
        embed.add_field(
            name=f"\U0001F383 Price", value=f"{pumpskin_price_avax:.2f} $AVAX", inline=True
        )
        embed.add_field(name=f"$PPIE Price", value=f"{ppie_price_usd:.5f} $USD", inline=True)
        return embed

    @classmethod
    def response(cls, message: discord.message.Message) -> T.Union[str, discord.Embed]:
        if not any([g for g in cls.ALLOWLIST_GUILDS if message.guild.id == g]):
            return ""

        logger.print_normal(f"{message.channel.name} id: {message.channel.id}")
        if not any([c for c in cls.ALLOWLIST_CHANNELS if message.channel.id == c]):
            return ""

        text = message.content.lower().strip()
        if not text.startswith(cls.HOTKEY):
            return ""

        logger.print_normal(f"{message.channel.id}")
        try:
            pumpskin_price_avax = float(text.strip().split(cls.HOTKEY)[1].strip())
        except ValueError:
            return ""

        crabada_web2 = CrabadaWeb2Client()
        prices = crabada_web2.get_pricing_data()

        # TODO: get price from LP
        ppie_price_usd = 0.3

        roi_days = PumpskinBot.calc_roi_from_mint(
            ppie_price_usd, prices.avax_usd, pumpskin_price_avax
        )
        return cls._get_pumpskin_roi_embed(pumpskin_price_avax, ppie_price_usd, roi_days)


class SnoopChannel(OnMessage):
    ALLOWLIST_GUILDS = [986151371923410975, 1020800321569697792]
    ALLOWLIST_CHANNELS = [
        1032890276420800582,  # test channel in p2e auto
        1021670710344687666,  # early founders channel for pumpskin
    ]

    @classmethod
    def response(cls, message: discord.message.Message) -> T.Union[str, discord.Embed]:
        if not any([g for g in cls.ALLOWLIST_GUILDS if message.guild.id == g]):
            return ""

        logger.print_normal(f"{message.channel.name} id: {message.channel.id}")
        if not any([c for c in cls.ALLOWLIST_CHANNELS if message.channel.id == c]):
            return ""

        logger.print_normal(f"From: {message.author}\n\n{message.content}\n")
        return ""
