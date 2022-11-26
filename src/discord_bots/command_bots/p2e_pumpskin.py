import discord
import json
import typing as T

from config_pumpskin import USERS
from discord_bots.command_bots.default import OnMessage
from pumpskin.utils import calc_ppie_earned_per_day
from pumpskin.pumpskin_web3_client import PumpskinCollectionWeb3Client, PumpskinContractWeb3Client
from utils import logger
from utils.config_types import UserConfig
from utils.price import wei_to_token
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client


class ManageAccounts(OnMessage):
    HOTKEY = f"?config"
    ALLOWLIST_GUILDS = [986151371923410975]
    ALLOWLIST_CHANNELS = [
        1032890276420800582,  # test channel in p2e auto
        1035266046480896141,  # p2e pumpskin bot channel
    ]

    @staticmethod
    def _get_config_stats(
        username: str,
        pfp: str,
        potn_per_day: float,
        ppie_per_day: float,
        config: T.Dict[str, T.Any],
    ) -> None:
        embed = discord.Embed(
            title=f"{username}",
            description=f"User configuration for Pumpskin",
            color=discord.Color.orange().value,
        )

        embed.add_field(name="POTN/Day", value=f"{potn_per_day:.2f}", inline=True)
        embed.add_field(name="PPIE/Day", value=f"{ppie_per_day:.2f}", inline=True)
        embed.add_field(name=f"\U0000200b", value=f"**Current Config**", inline=False)

        for config, setting in config.items():
            text = " ".join([c[0].upper() + c[1:] for c in config.split("_")])
            if isinstance(setting, float):
                value = f"{setting:.2f}"
            elif isinstance(setting, dict):
                value = f"{json.dumps(setting, indent=4)}"
            else:
                value = f"{setting}"

            if "multiplier" in text.lower() and "ppie" in text.lower():
                value += f" -> {ppie_per_day * setting:.2f} $PPIE"
            elif "multiplier" in text.lower() and "potn" in text.lower():
                value += f" -> {potn_per_day * setting:.2f} $POTN"

            if "percent" in text.lower() and "lp" not in text.lower():
                embed.add_field(name=text, value=value, inline=True)
            else:
                embed.add_field(name=text, value=value, inline=False)

        embed.set_thumbnail(url=pfp)
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

        discord_user = ""
        user_name = ""
        user_config = {}
        for user, config in USERS.items():
            if str(message.author) == config["discord_handle"]:
                discord_user = config["discord_handle"].split("#")[0].upper()
                user_config = config
                user_name = user
                break

        if not discord_user:
            logger.print_normal(f"Unauthorized access")
            return f"Unathorized access"

        # if "pumpskin botter" not in [y.name.lower() for y in message.author.roles]:
        #     message.author.add_roles("Pumpskin Botter")

        pfp = message.author.avatar_url

        collection_w3: PumpskinCollectionWeb3Client = (
            PumpskinCollectionWeb3Client()
            .set_credentials(config["address"], "")
            .set_node_uri(PumpskinCollectionWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(False)
        )
        contract_w3: PumpskinContractWeb3Client = (
            PumpskinContractWeb3Client()
            .set_credentials(config["address"], "")
            .set_node_uri(PumpskinContractWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(False)
        )

        pumpskin_ids = {k: "" for k in collection_w3.get_staked_pumpskins(user_config["address"])}

        pumpskins = {}
        for token_id in pumpskin_ids:
            pumpskin: StakedPumpskin = collection_w3.get_staked_pumpskin_info(token_id)
            pumpskins[token_id] = pumpskin

        ppie_staked = wei_to_token(contract_w3.get_ppie_staked(user_config["address"]))
        potn_per_day = ppie_staked * 3.0
        ppie_per_day = calc_ppie_earned_per_day(pumpskins)
        logger.print_normal(f"{user} -> PPIE/Day: {ppie_per_day} POTN/Day: {potn_per_day}")

        try:
            return cls._get_config_stats(
                discord_user, pfp, potn_per_day, ppie_per_day, user_config["game_specific_configs"]
            )
        except:
            logger.print_normal(f"Failed to get config")
            return f"Failed to get config"
