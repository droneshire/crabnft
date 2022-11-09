import json

from config_admin import ADMIN_ADDRESS
from joepegs.joepegs_api import JoePegsClient, JOEPEGS_URL
from pumpskin.pumpskin_bot import PumpskinBot, RARITY_FILE
from pumpskin.pumpskin_web3_client import PumpskinCollectionWeb3Client, PumpskinNftWeb3Client
from pumpskin.types import StakedPumpskin
from utils import discord, logger
from utils.price import wei_to_token
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client


def post_rarist_listings(max_rarity: float, max_price: float, quiet: bool = True) -> None:
    joepegs = JoePegsClient()
    listings = joepegs.get_listings(
        PumpskinNftWeb3Client.contract_address, params={"orderBy": "rarity_desc"}
    )

    rarity_file = PumpskinBot.get_json_path(RARITY_FILE)
    with open(rarity_file, "r") as infile:
        collection_rarity = json.load(infile)

    w3: PumpskinCollectionWeb3Client = (
        PumpskinCollectionWeb3Client()
        .set_credentials(ADMIN_ADDRESS, "")
        .set_node_uri(AvalancheCWeb3Client.NODE_URL)
        .set_contract()
        .set_dry_run(False)
    )

    list_pricing = []
    for pump in listings:
        token_id = int(pump["tokenId"])
        list_price_wei = int(pump["currentAsk"]["price"])
        price = float(wei_to_token(list_price_wei))
        rarity = collection_rarity[str(token_id)]["Overall"]["rarity"] * 100.0
        pumpskin: StakedPumpskin = w3.get_staked_pumpskin_info(token_id)
        level = pumpskin.get("kg", 10000) / 100
        list_pricing.append((price, rarity, token_id, level))

    sorted_listings = sorted(list_pricing, key=lambda p: (-p[3], p[1], p[0]))

    discord.get_discord_hook("PUMPSKIN_MARKET").send("**LISTINGS:**")

    text = ""
    for listing in sorted_listings:
        if listing[0] > max_price:
            continue
        url = JOEPEGS_URL.format(PumpskinNftWeb3Client.contract_address) + listing[2]
        text += f"**{listing[2]}** [ML {listing[3]}]: {listing[1]:.2f}% - {listing[0]:.2f} $AVAX | {url}\n"
        if len(text) > 1500:
            logger.print_bold(text)
            discord.get_discord_hook("PUMPSKIN_MARKET").send(text)
            text = ""

    if text:
        logger.print_bold(text)
        discord.get_discord_hook("PUMPSKIN_MARKET").send(text)
