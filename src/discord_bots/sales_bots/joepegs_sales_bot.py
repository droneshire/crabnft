import discord
import datetime
import json
import math
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
            self.posted_items = {"sold": [], "listed": []}
        else:
            with open(self.database_file) as infile:
                self.posted_items = json.load(infile)

        self._migrate_db()

    def _migrate_db(self) -> None:
        if "database" in self.posted_items:
            sold_items = self.posted_items["database"]
            del self.posted_items["database"]
            self.posted_items["listed"] = []
            self.posted_items["sold"] = sold_items

    def custom_filter_for_item(self) -> bool:
        # Override this in any derived class to provide a custom filter for
        # a collection and associated floor
        pass

    def add_custom_embed_fields(self, embed: discord.Embed) -> discord.Embed:
        # Override this in any derived class to add more custom info to the default embed
        pass

    def _get_recent_sales(self) -> T.List[Activity]:
        all_sales = []
        for collection in self.collections:
            for page in range(1, 5):
                all_sales.extend(self.client.get_sales(collection, params={"pageNum": page}))

        now = time.time()
        recent_sales = []
        for sale in all_sales:
            if sale["tokenId"] in self.posted_items["sold"]:
                logger.print_normal(
                    f"Skipping {sale['tokenId']} collection {sale['collectionName']} since already posted..."
                )
                continue
            if now - sale["timestamp"] > self.MAX_TIME_SINCE_SALE:
                logger.print_normal(f"Skipping {sale['tokenId']} since too old...")
                continue
            logger.print_normal(f"Found new sale of {sale['tokenId']}")
            recent_sales.append(sale)
        return recent_sales

    def _get_recent_discount_listings(self) -> T.List[T.Dict[T.Any, T.Any]]:
        new_listings = {}
        floors = {}
        for collection in self.collections:
            new_listings[collection] = self.client.get_listings(
                collection, params={"orderBy": "recent_listing"}
            )
            floors[collection] = self.client.get_floor_avax(collection)

        snipe_listings = []
        for collection, listings in new_listings.items():
            for listing in listings:
                if listing["tokenId"] in self.posted_items["listed"]:
                    logger.print_normal(f"Skipping {listing['tokenId']} since already posted...")
                    continue
                list_price_wei = int(listing["currentAsk"]["price"])
                price = wei_to_token_raw(list_price_wei)
                # TODO: filter based on previous floors
                if price > floors[collection]:
                    continue
                logger.print_normal(f"Found new listing of {listing['tokenId']}")
                snipe_listings.append(listing)
        return snipe_listings

    def _get_listing_embed(self, listing: T.Dict[T.Any, T.Any]) -> discord.Embed:
        collection_name = listing["collectionName"]
        token_id = listing["tokenId"]
        name = listing["metadata"]["name"] if listing["metadata"]["name"] else token_id
        sale_name_url = f"[{name}]({JOEPEGS_URL.format(listing['collection']) + token_id})"
        embed = discord.Embed(
            title=f"{collection_name} Listing",
            description=f"New listing on JOEPEGS - {sale_name_url} below floor\n",
            color=self.collection_color.value,
        )
        price_wei = int(listing["currentAsk"]["price"])
        price_avax = wei_to_token_raw(price_wei)

        embed.add_field(name=f"\U0001F4B0 Price", value=f"{price_avax:.2f} AVAX", inline=True)
        embed.set_image(url=listing["metadata"]["image"])

        return embed

    def _get_sales_embed(self, sale: Activity) -> discord.Embed:
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

        if math.isclose(collection_floor_avax, 0.0):
            embed.add_field(
                name=f"Price Floor",
                value=f"N/A",
                inline=False,
            )
        else:
            percent_of_floor = price_avax / collection_floor_avax
            above_below_str = "above" if percent_of_floor > 1.0 else "below"
            percent_str = (
                percent_of_floor - 1.0 if percent_of_floor > 1.0 else 1.0 - percent_of_floor
            )
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
            self.posted_items["sold"].append(sale["tokenId"])
            embeds.append(self._get_sales_embed(sale))

        with open(self.database_file, "w") as outfile:
            json.dump(self.posted_items, outfile, indent=4)

        return embeds

    def get_listing_embeds(self) -> T.List[discord.Embed]:
        embeds = []
        for listing in self._get_recent_discount_listings():
            self.posted_items["listed"].append(listing["tokenId"])
            embeds.append(self._get_listing_embed(listing))

        with open(self.database_file, "w") as outfile:
            json.dump(self.posted_items, outfile, indent=4)

        return embeds
