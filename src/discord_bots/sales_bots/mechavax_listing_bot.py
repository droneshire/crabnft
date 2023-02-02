import discord
import json
import typing as T

from web3.types import Address

from config_admin import ADMIN_ADDRESS
from discord_bots.sales_bots.joepegs_sales_bot import JoePegsSalesBot
from mechavax.mechavax_web3client import MechContractWeb3Client
from mint_sniper.collections.mechavax import MechavaxMint
from utils import logger
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client


class MechavaxListingBot(JoePegsSalesBot):
    MIN_MULTIPLIER = 6
    MIN_PRICE_AVAX = 1.98

    def __init__(
        self,
        bot_name: str,
        collection_color: discord.Color,
        collections: T.List[Address],
        log_dir: str,
    ):
        super().__init__(bot_name, collection_color, collections, log_dir)
        self.w3: MechContractWeb3Client = T.cast(
            MechContractWeb3Client,
            (
                MechContractWeb3Client()
                .set_credentials(ADMIN_ADDRESS, "")
                .set_node_uri(AvalancheCWeb3Client.NODE_URL)
                .set_contract()
            ),
        )
        self.rarity = MechavaxMint()

    def custom_filter_for_item(self, price: float, item: T.Dict[T.Any, T.Any]) -> bool:
        token_id = int(item["tokenId"])
        multiplier = self.w3.get_mech_multiplier(token_id)
        if multiplier < self.MIN_MULTIPLIER:
            return False
        if price > self.MIN_PRICE_AVAX:
            return False

        return True

    def add_custom_embed_fields(
        self, embed: discord.Embed, embed_type: int, item: T.Dict[T.Any, T.Any]
    ) -> discord.Embed:
        token_id = int(item["tokenId"])
        multiplier = self.w3.get_mech_multiplier(token_id)
        with open(self.rarity.files["rarity"]) as infile:
            data = json.load(infile)
            rarity = data.get(str(token_id), {}).get("Overall", {}).get("rarity", -0.01) * 100.0
        embed.add_field(
            name=f"\U0001F522 Emissions Multiplier", value=f"{multiplier}", inline=False
        )
        embed.add_field(name=f"Rarity", value=f"{rarity:.2f}%", inline=False)
        return embed
