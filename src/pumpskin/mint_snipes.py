import discord
import json
import logging
import os
import typing as T

from config_admin import ADMIN_ADDRESS
from utils import logger
from pumpskin.pumpskin_bot import PumpskinBot, ATTRIBUTES_FILE
from pumpskin.pumpskin_web2_client import PumpskinWeb2Client
from pumpskin.pumpskin_web3_client import PumpskinNftWeb3Client
from pumpskin.types import ATTRIBUTE_TO_EMOJI, Pumpskin
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client


class PumpskinMintSniper:
    def __init__(self, log_dir: str):
        self.w3: PumpskinNftWeb3Client = (
            PumpskinNftWeb3Client()
            .set_credentials(ADMIN_ADDRESS, "")
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(False)
        )
        self.log_dir = log_dir

        self.w2: PumpskinWeb2Client = PumpskinWeb2Client()

        attributes_file = PumpskinBot.get_json_path(ATTRIBUTES_FILE)
        with open(attributes_file, "r") as infile:
            self.pumpskin_stats = json.load(infile)

        self.database_file = os.path.join(self.log_dir, "mint_sniper.json")
        self.posted_items = {}

        if not os.path.isfile(self.database_file):
            self.posted_items["database"] = []
        else:
            with open(self.database_file) as infile:
                self.posted_items = json.load(infile)

    def _get_next_mints(self, num_mints: int) -> T.List[Pumpskin]:
        next_mint = self.w3.get_total_pumpskins_minted()
        logger.print_bold(f"Obtaining mints {next_mint}-{next_mint + num_mints}...")
        next_mints = []
        for token_id in range(next_mint, next_mint + num_mints):
            next_mints.append(self.w2.get_pumpskin_info(token_id))
        return next_mints

    def _get_mint_embed(self, pumpskin_info: Pumpskin) -> discord.Embed:
        token_id = int(
            pumpskin_info.get("edition", pumpskin_info.get["name", [-1, -1]].split("#")[1].strip())
        )
        pumpskin_image_uri = self.w2.get_pumpskin_image(token_id)

        embed = discord.Embed(
            title=f"PUMPʂKIN {token_id}",
            description=f"Unminted Phase 6",
            color=discord.Color.orange().value,
        )
        logger.print_ok(f"Found pump mint #{token_id}")
        pumpskin_rarity = PumpskinBot.calculate_rarity(token_id, pumpskin_info, self.pumpskin_stats)

        embed.set_image(url=pumpskin_image_uri)
        url = "https://pumpskin.xyz/mint"
        icon_url = "https://pumpskin.xyz/_next/image?url=%2Fimages%2Fpt-token.png&w=1920&q=75"
        embed.set_author(name="Mint Link", url=url, icon_url=icon_url)

        if not pumpskin_rarity:
            embed.add_field(name=f"\U0000200b", value=f"UNKNOWN ATTRIBUTES", inline=False)
            return embed

        embed.add_field(name=f"\U0000200b", value=f"**Attribute Rarity**", inline=False)

        trait_count = 0
        overall_rarity = 0.0
        logger.print_normal(f"{json.dumps(pumpskin_rarity, indent=4)}")
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
        return embed

    def get_next_mints_embeds(self, num_mints: int) -> T.List[discord.Embed]:
        embeds = []
        for pumpskin_info in self._get_next_mints(num_mints):
            token_id = pumpskin_info.get(
                "edition", pumpskin_info.get["name", [-1, -1]].split("#")[1].strip()
            )
            if token_id in self.posted_items["database"]:
                continue
            embeds.append(self._get_mint_embed(pumpskin_info))
            self.posted_items["database"].append(token_id)

        with open(self.database_file, "w") as outfile:
            json.dump(self.posted_items, outfile, indent=4)

        return embeds
