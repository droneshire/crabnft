import discord
import datetime
import json
import os
import time
import typing as T

from web3.types import Address

from joepegs.joepegs_api import JOEPEGS_URL, JoePegsClient
from joepegs.types import Activity
from utils import logger
from utils.price import wei_to_token_raw


class JoePegsSalesBot:
    MAX_TIME_SINCE_SALE = 60.0 * 60.0 * 24

    def __init__(
        self,
        bot_name: str,
        collection_color: discord.Color,
        collections: T.List[Address],
        log_dir: str,
    ):
        self.collections = collections
        self.bot_name = bot_name
        self.client = JoePegsClient()
        self.collection_color = collection_color

        self.log_dir = log_dir
        self.database_file = os.path.join(self.log_dir, "joepegs_sales.json")
        if not os.path.isfile(self.database_file):
            self.posted_sales = []
        else:
            with open(self.database_file) as infile:
                database = json.load(infile)
            self.posted_sales = database["database"]

    def _get_recent_sales(self) -> T.List[Activity]:
        all_sales = []
        for collection in self.collections:
            all_sales.extend(self.client.get_sales(collection))

        now = time.time()
        recent_sales = []
        for sale in all_sales:
            if sale["tokenId"] in self.posted_sales:
                logger.print_normal(f"Skipping {sale['tokenId']} since already posted...")
                continue
            if now - sale["timestamp"] > self.MAX_TIME_SINCE_SALE:
                logger.print_normal(f"Skipping {sale['tokenId']} since too old...")
                continue
            logger.print_normal(f"Found new sale of {sale['tokenId']}")
            recent_sales.append(sale)
        return recent_sales

    def _get_sales_embed(self, sale: Activity) -> None:
        collection_name = sale["collectionName"]
        token_id = sale["tokenId"]
        name = sale["name"] if sale["name"] else token_id
        sale_name_url = f"[{name}]({JOEPEGS_URL.format(sale['collection']) + token_id})"
        embed = discord.Embed(
            title=f"{collection_name} Sale",
            description=f"New sale on JOEPEGS - {sale_name_url} sold\n",
            color=self.collection_color.value,
        )
        price_wei = int(sale["price"])
        price_avax = wei_to_token_raw(price_wei)

        embed.add_field(name=f"\U0001F4B0 Sold for", value=f"{price_avax:.2f} AVAX", inline=True)
        # TODO(ross): implement last sold
        # embed.add_field(name=f"Last sold for", value=f"{sale['price_avax']:.2f} AVAX", inline=True)

        collection_address = sale["collection"]
        collection_floor_avax = self.client.get_floor_avax(collection_address)
        percent_of_floor = price_avax / collection_floor_avax
        above_below_str = "above" if percent_of_floor > 1.0 else "below"
        percent_str = percent_of_floor - 1.0 if percent_of_floor > 1.0 else 1.0 - percent_of_floor
        percent_str = percent_str * 100.0

        embed.add_field(
            name=f"Price Floor",
            value=f"{collection_floor_avax:.2f} AVAX. Sold {percent_str:.0f}% {above_below_str} floor",
            inline=False,
        )
        embed.set_image(url=sale["image"])
        timestamp = sale["timestamp"]
        purchase_date = datetime.datetime.fromtimestamp(timestamp)
        purchase_date_string = purchase_date.strftime("%d/%b/%Y %H:%M:%S")
        embed.set_footer(text=f"Sold on {purchase_date_string} UTC")
        return embed

    def get_sales_embeds(self) -> T.List[discord.Embed]:
        sales = self._get_recent_sales()
        timestamp_sales = {}
        for sale in sales:
            timestamp_sales[sale["timestamp"]] = sale

        sorted_sales = sorted(timestamp_sales.keys())
        embeds = []
        for timestamp in sorted_sales:
            sale = timestamp_sales[timestamp]
            self.posted_sales.append(sale["tokenId"])
            embeds.append(self._get_sales_embed(sale))

        database = {"database": self.posted_sales}
        with open(self.database_file, "w") as outfile:
            json.dump(database, outfile, indent=4)

        return embeds
