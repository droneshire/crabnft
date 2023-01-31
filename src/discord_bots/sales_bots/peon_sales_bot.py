import discord
import typing as T

from web3.types import Address

from discord_bots.sales_bots.joepegs_sales_bot import JoePegsSalesBot
from utils import logger


class PeonSalesBot(JoePegsSalesBot):
    def __init__(
        self,
        bot_name: str,
        collection_color: discord.Color,
        collections: T.List[Address],
        log_dir: str,
    ):
        super().__init__(bot_name, collection_color, collections, log_dir)

    def custom_filter_for_item(self, price: float, item: T.Dict[T.Any, T.Any]) -> bool:
        pass

    def add_custom_embed_fields(
        self, embed: discord.Embed, embed_type: int, item: T.Dict[T.Any, T.Any]
    ) -> discord.Embed:
        pass
