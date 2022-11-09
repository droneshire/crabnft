import discord
import time
import typing as T

from config_admin import ADMIN_ADDRESS
from crabada.crabada_web2_client import CrabadaWeb2Client
from discord_bots.command_bots.default import OnMessage
from joepegs.joepegs_api import JOEPEGS_ICON_URL, JOEPEGS_URL
from pumpskin.listings import post_rarist_listings
from pumpskin.pumpskin_bot import PumpskinBot, ATTRIBUTES_FILE
from pumpskin.pumpskin_web3_client import PumpskinCollectionWeb3Client, PumpskinNftWeb3Client
from pumpskin.pumpskin_web2_client import PumpskinWeb2Client
from pumpskin.types import StakedPumpskin
from utils import logger
from utils.general import get_pretty_seconds
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client


ATTRIBUTE_TO_EMOJI = {
    "Facial": "\U0001F604",
    "Background": "\U0001F5BC",
    "Body": "\U0001F9CD",
    "Eyes": "\U0001F440",
    "Frame": "\U0001FA9F",
    "Head": "\U0001F383",
    "Item": "\U0001F45C",
    "Neck": "\U0001F454",
    "Overall": "\U0001F4C8",
}


class GetPumpkinLevel(OnMessage):
    HOTKEY = f"?plvl"
    ALLOWLIST_GUILDS = [986151371923410975, 1020800321569697792]
    ALLOWLIST_CHANNELS = [
        1027614935523532900,  # pumpskin main channel p2e auto
        1032890276420800582,  # test channel in p2e auto
        # 1032276350045798441, # farmers market in pumpskin
        1033839826182619228,  # pumpskin bot channel
        1035266046480896141,  # p2e auto bot command pumskin channel
    ]

    @staticmethod
    def _get_pumpskin_info_embed(
        token_id: int, level: int, image_uri: str, cooldown_time: str
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"PUMPʂKIN {token_id}",
            description=f"Level {level}",
            color=discord.Color.orange().value,
        )

        embed.add_field(name=f"Pumpskin", value=f"{token_id}", inline=True)
        embed.add_field(name=f"Cooldown", value=f"{cooldown_time}", inline=False)
        ppie_per_day = PumpskinBot.calc_ppie_per_day_from_level(level)
        embed.add_field(name=f"$PPIE/Day", value=f"{ppie_per_day}", inline=True)
        potn_to_level = PumpskinBot.calc_potn_from_level(level)
        embed.add_field(name=f"Level Up:", value=f"{potn_to_level} $POTN", inline=False)
        embed.add_field(name=f"\U0000200b", value=f"**Attribute Rarity**", inline=False)

        pumpskin_rarity = PumpskinBot.calculate_rarity_from_query(
            token_id, PumpskinBot.get_json_path(ATTRIBUTES_FILE)
        )

        if not pumpskin_rarity:
            return ""

        trait_count = 0
        overall_rarity = 0.0
        for trait, info in pumpskin_rarity.items():
            if trait == "Overall":
                overall_rarity = info["rarity"] * 100.0
                continue
            rarity_percent = info["rarity"] * 100.0
            trait_count += 1
            inline = trait_count % 9 != 0
            embed.add_field(
                name=f"{ATTRIBUTE_TO_EMOJI[trait]} {trait}",
                value=f"{info['trait']}: {rarity_percent:.2f}%",
                inline=inline,
            )

        embed.add_field(
            name=f"{ATTRIBUTE_TO_EMOJI[trait]} Overall", value=f"{overall_rarity:.2f}%", inline=True
        )
        embed.set_thumbnail(url=image_uri)
        url = JOEPEGS_URL.format(PumpskinNftWeb3Client.contract_address) + str(token_id)
        embed.set_author(name="JoePeg Link", url=f"{url}", icon_url=f"{JOEPEGS_ICON_URL}")
        return embed

    @classmethod
    def response(cls, message: discord.message.Message) -> T.Union[str, discord.Embed]:
        if not any([g for g in cls.ALLOWLIST_GUILDS if message.guild.id == g]):
            return ""

        if not any([c for c in cls.ALLOWLIST_CHANNELS if message.channel.id == c]):
            return ""

        text = message.content.lower().strip()
        if not text.startswith(cls.HOTKEY):
            return ""

        try:
            token_id = int(text.strip().split(cls.HOTKEY)[1])
        except ValueError:
            return ""

        minted, _ = PumpskinBot.get_mint_stats()

        if token_id > minted:
            return "Not yet minted"

        try:
            w3: PumpskinCollectionWeb3Client = (
                PumpskinCollectionWeb3Client()
                .set_credentials(ADMIN_ADDRESS, "")
                .set_node_uri(AvalancheCWeb3Client.NODE_URL)
                .set_contract()
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

            embed = cls._get_pumpskin_info_embed(
                token_id, ml, pumpskin_image_uri, cooldown_time_pretty
            )

            logger.print_normal(
                f"\U0001F383 **Pumpskin {token_id}**: ` ML {ml} `-> {message.channel}"
            )
            return embed
        except:
            logger.print_normal(f"Unknown level for Pumpskin \U0001F937")
            return f"Unknown level for Pumpskin \U0001F937"


class GetPumpkinRoi(OnMessage):
    HOTKEY = f"?proi"
    ALLOWLIST_GUILDS = [986151371923410975, 1020800321569697792]
    ALLOWLIST_CHANNELS = [
        1027614935523532900,  # pumpskin main channel p2e auto
        1032890276420800582,  # test channel in p2e auto
        # 1032276350045798441, # farmers market in pumpskin
        # 1033839826182619228,  # pumpskin bot channel
        1035266046480896141,  # p2e auto bot command pumskin channel
    ]

    @staticmethod
    def _get_pumpskin_roi_embed(
        pumpskin_price_avax: float, ppie_price_usd: float, roi_days: float
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"PUMPʂKIN ROI",
            description=f"Return on investment for a new mint\n",
            color=discord.Color.red().value,
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
        # 1032890276420800582,  # test channel in p2e auto
        # 1021670710344687666,  # early founders channel for pumpskin
        # 1021704887127511090,  # mod channel pumpskin
        # 1035266046480896141,  # p2e auto bot command pumskin channel
        1021670920772931604,  # ogs cahnnel pumpskin
    ]

    @classmethod
    def response(cls, message: discord.message.Message) -> T.Union[str, discord.Embed]:
        if not any([g for g in cls.ALLOWLIST_GUILDS if message.guild.id == g]):
            return ""

        logger.print_normal(f"{message.channel.name} id: {message.channel.id}")
        if not any([c for c in cls.ALLOWLIST_CHANNELS if message.channel.id == c]):
            return ""

        logger.print_normal(f"{message.channel.name} id: {message.channel.id}")
        logger.print_normal(f"From: {message.author}\n\n{message.content}\n")
        return ""


class MintNumber(OnMessage):
    HOTKEY = f"?mint"
    ALLOWLIST_GUILDS = [986151371923410975, 1020800321569697792]
    ALLOWLIST_CHANNELS = [
        1027614935523532900,  # pumpskin main channel p2e auto
        1032890276420800582,  # test channel in p2e auto
        1032276350045798441,  # farmers market in pumpskin
        1033839826182619228,  # pumpskin bot channel
        1035266046480896141,  # p2e auto bot command pumskin channel
    ]

    @classmethod
    def response(cls, message: discord.message.Message) -> T.Union[str, discord.Embed]:
        if not any([g for g in cls.ALLOWLIST_GUILDS if message.guild.id == g]):
            return ""

        text = message.content.lower().strip()
        if not text.startswith(cls.HOTKEY):
            return ""

        minted, supply = PumpskinBot.get_mint_stats()

        return f"Minted: `{minted}/{supply}`"


class MintNumber(OnMessage):
    HOTKEY = f"?deals"
    ALLOWLIST_GUILDS = [986151371923410975]
    ALLOWLIST_CHANNELS = [
        1032890276420800582,  # test channel in p2e auto
        1032881170838462474,  # p2e pumpskin market deals
        1035266046480896141,  # p2e auto bot command pumskin channel
    ]

    @classmethod
    def response(cls, message: discord.message.Message) -> T.Union[str, discord.Embed]:
        if not any([g for g in cls.ALLOWLIST_GUILDS if message.guild.id == g]):
            return ""

        text = message.content.lower().strip()
        if not text.startswith(cls.HOTKEY):
            return ""

        try:
            max_price_avax = float(text.strip().split(cls.HOTKEY)[1].strip())
        except ValueError:
            return ""

        post_rarist_listings(30.0, max_price_avax, True)

        return ""
