import copy
import deepdiff
import json
import math
import typing as T

from discord import Color
from discord_webhook import DiscordEmbed, DiscordWebhook
from eth_typing import Address
from web3 import Web3

from config_pat import COMMISSION_WALLET_ADDRESS
from plantatree.config_manager_pat import PatConfigManager
from plantatree.game_stats import NULL_GAME_STATS, PatLifetimeGameStatsLogger
from plantatree.pat_web3_client import PlantATreeWeb3Client
from utils import discord, logger
from utils.config_types import UserConfig
from utils.email import Email, send_email
from utils.general import get_pretty_seconds
from utils.math import Average
from utils.price import wei_to_token_raw
from utils.user import get_alias_from_user
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client


class Action:
    REPLANT = "replant"
    PLANT = "plant"
    HARVEST = "harvest"


class PatBot:
    REPLANT_TIME_DELTA = 60.0 * 60.0 * 4.0

    def __init__(
        self,
        user: str,
        config: UserConfig,
        email_accounts: T.List[Email],
        encrypt_password: str,
        referral_address: Address,
        log_dir: str,
        dry_run: bool,
    ):
        self.pat_w3: PlantATreeWeb3Client = (
            PlantATreeWeb3Client()
            .set_credentials(config["address"], config["private_key"])
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(dry_run)
        )

        self.user = user
        self.alias = get_alias_from_user(self.user)
        self.log_dir = log_dir
        self.emails = email_accounts
        self.dry_run = dry_run

        self.avg_gas_gwei: Average = Average()
        self.avg_gas_used: Average = Average(0.001570347)

        self.referral_address: Address = Web3.toChecksumAddress(referral_address)
        self.todays_tax = 100.0

        self.txns = []

        self.config_mgr = PatConfigManager(
            user,
            config,
            email_accounts,
            encrypt_password,
            log_dir,
            dry_run=dry_run,
            verbose=True,
        )

        self.current_stats = copy.deepcopy(NULL_GAME_STATS)

        self.stats_logger = PatLifetimeGameStatsLogger(
            self.alias,
            self.log_dir,
            self.config_mgr.get_lifetime_stats(),
            self.dry_run,
            verbose=False,
        )

    def _send_discord_activity_update(
        self, action: Action, gas: float, rewards_avax: float
    ) -> None:
        webhook = DiscordWebhook(
            url=discord.DISCORD_WEBHOOK_URL["PAT_ACTIVITY"], rate_limit_retry=True
        )
        discord_username = self.config_mgr.config["discord_handle"].split("#")[0].upper()
        EMBED_COLOR = {
            Action.HARVEST: Color.gold().value,
            Action.REPLANT: Color.green().value,
            Action.PLANT: Color.blue().value,
        }[action]
        embed = DiscordEmbed(
            title=f"\U0001F332 PAT Activity",
            description=f"Bot action for {discord_username}\n",
            color=EMBED_COLOR,
        )
        embed.add_embed_field(name=f"Action", value=f"{action.upper()}", inline=False)
        embed.add_embed_field(name=f"Gas", value=f"{gas}", inline=False)
        embed.add_embed_field(name=f"Today's Tax", value=f"{self.todays_tax:.1f}%", inline=False)

        contract_balance = self.pat_w3.get_contract_balance()
        embed.add_embed_field(
            name=f"Contract Balance", value=f"{contract_balance:.2f} $AVAX", inline=True
        )
        embed.add_embed_field(
            name=f"Rewards Earned", value=f"{rewards_avax:.2f} $AVAX", inline=True
        )
        IMAGE_URL = {
            Action.HARVEST: "https://plantatree.finance/images/logo/logo_.png",
            Action.REPLANT: "https://plantatree.finance/images/logo/Plant_A_Tree_Logo_1.png",
            Action.PLANT: "https://plantatree.finance/images/logo/Plant_A_Tree_Logo_1.png",
        }[action]

        embed.set_thumbnail(
            url=IMAGE_URL,
            height=100,
            width=100,
        )
        webhook.add_embed(embed)
        webhook.execute()

    def _send_email_update(self) -> None:
        content = f"Plant A Tree Stats for {self.user.upper()}:\n"
        content += f"Replants: {self.current_stats['replants']}\n"
        content += f"Harvests: {self.current_stats['harvests']}\n\n"
        if self.txns:
            content += f"TXs:\n"
            for tx in self.txns:
                content += f"{tx}\n"
            self.txns.clear()

        logger.print_bold("\n" + content + "\n")

        content += f"Lifetime Stats:\n{json.dumps(self.stats_logger.lifetime_stats, indent=4)}\n\n"
        content += f"--------------------\n"

        diff = deepdiff.DeepDiff(self.current_stats, NULL_GAME_STATS)
        if not diff:
            logger.print_normal(f"Didn't update any stats, not sending email...")
            return

        if self.dry_run:
            return

        subject = f"\U0001F332 Plant a Tree Bot Update"

        if self.config_mgr.config["email"]:
            send_email(
                self.emails,
                self.config_mgr.config["email"],
                subject,
                content,
            )

    def _update_stats(self) -> None:
        for k, v in self.current_stats.items():
            if type(v) != type(self.stats_logger.lifetime_stats.get(k)):
                logger.print_warn(
                    f"Mismatched stats:\n{self.current_stats}\n{self.stats_logger.lifetime_stats}"
                )
                continue

            if k in ["commission_avax"]:
                continue

            if isinstance(v, list):
                self.stats_logger.lifetime_stats[k].extend(v)
            elif isinstance(v, dict):
                for i, j in self.stats_logger.lifetime_stats[k].items():
                    self.stats_logger.lifetime_stats[k][i] += self.current_stats[k][i]
            else:
                self.stats_logger.lifetime_stats[k] += v

        self.stats_logger.lifetime_stats["commission_avax"] = self.stats_logger.lifetime_stats.get(
            "commission_avax", {COMMISSION_WALLET_ADDRESS: 0.0}
        )

        avax_rewards = self.current_stats["avax_harvested"]
        for address, commission_percent in self.config_mgr.config[
            "commission_percent_per_mine"
        ].items():
            commission_avax = avax_rewards * (commission_percent / 100.0)

            self.stats_logger.lifetime_stats["commission_avax"][address] = (
                self.stats_logger.lifetime_stats["commission_avax"].get(address, 0.0)
                + commission_avax
            )

            if not math.isclose(0.0, commission_avax):
                logger.print_ok(
                    f"Added {commission_avax} $AVAX for {address} in commission ({commission_percent}%)!"
                )

        self.current_stats = copy.deepcopy(NULL_GAME_STATS)

        logger.print_ok_blue(
            f"Lifetime Stats for {self.user.upper()}\n{json.dumps(self.stats_logger.lifetime_stats, indent=4)}"
        )

    def _harvest(self, rewards_avax: float) -> bool:
        logger.print_bold(f"It's HARVEST DAY! Attempting to reap \U0001F332 \U0001F332...")
        tx_hash = self.pat_w3.harvest()
        tx_receipt = self.pat_w3.get_transaction_receipt(tx_hash)

        gas = wei_to_token_raw(self.pat_w3.get_gas_cost_of_transaction_wei(tx_receipt))
        self.avg_gas_used.update(gas)
        self.stats_logger.lifetime_stats["avax_gas"] += gas
        logger.print_bold(f"Paid {gas} AVAX in gas")

        if tx_receipt.get("status", 0) != 1:
            logger.print_fail(f"Failed to harvest rewards!")
            return False
        else:
            logger.print_ok(f"Successfully completed harvest!\n{tx_receipt}")
            self.txns.append(f"https://snowtrace.io/tx/{tx_hash}")
            logger.print_normal(f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n")
            self.current_stats["harvests"] += 1
            self._send_discord_activity_update(Action.HARVEST, gas, rewards_avax)
        return True

    def _replant(self, rewards_avax: float) -> bool:
        logger.print_bold(f"Attempting to replant \U0001F332 \U0001F332...")
        tx_hash = self.pat_w3.re_plant(self.referral_address)
        tx_receipt = self.pat_w3.get_transaction_receipt(tx_hash)

        gas = wei_to_token_raw(self.pat_w3.get_gas_cost_of_transaction_wei(tx_receipt))
        self.avg_gas_used.update(gas)
        self.stats_logger.lifetime_stats["avax_gas"] += gas
        logger.print_bold(f"Paid {gas} AVAX in gas")

        if tx_receipt.get("status", 0) != 1:
            logger.print_fail(f"Failed to replant!")
            return False
        else:
            logger.print_ok(f"Successfully completed replant!")
            self.txns.append(f"https://snowtrace.io/tx/{tx_hash}")
            logger.print_normal(f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n")
            self.current_stats["replants"] += 1
            self._send_discord_activity_update(Action.REPLANT, gas, rewards_avax)
        return True

    def _should_replant(self) -> bool:
        last_replant = self.pat_w3.get_seconds_since_last_replant()
        logger.print_ok_blue(f"Last replant: {get_pretty_seconds(last_replant)} ago")
        min_time_replant = 60.0 * 60.0 * 1.0

        if last_replant < max(
            min_time_replant,
            self.config_mgr.config["game_specific_configs"]["time_between_plants"],
        ):
            return False

        return True

    def _calc_total_trees(self) -> int:
        TSN = 10000.0
        TSNH = 5000.0
        trees = self.pat_w3.get_my_total_trees()
        rewards = float(self.pat_w3.calculate_harvest_reward(trees))
        contract_balance = float(self.pat_w3.get_contract_balance())
        trees = float(trees)
        trees_total = (
            (TSN * contract_balance - rewards * TSNH) * trees / rewards - TSNH * trees
        ) / TSN
        return int(trees_total)

    def run(self, avax_usd: float) -> None:
        gas_price_gwei = self.pat_w3.get_gas_price()
        if gas_price_gwei is None:
            gas_price_gwei = -1.0
        self.avg_gas_gwei.update(gas_price_gwei)

        self.todays_tax = self.pat_w3.get_current_day_tax(extra_48_tax=False)
        is_harvest_day = math.isclose(0.0, self.todays_tax)

        logger.print_bold(f"{self.user.upper()} \U0001F332 Stats:")
        logger.print_ok_arrow(f"Referral Awards: {self.pat_w3.get_my_referral_rewards()} trees")
        logger.print_ok_blue_arrow(f"Today's tax: {self.todays_tax:.2f}%")
        logger.print_ok_blue_arrow(
            f"Contract balance: {self.pat_w3.get_contract_balance():.2f} $AVAX"
        )
        my_trees = self.pat_w3.get_my_total_trees()
        rewards_avax = self.pat_w3.calculate_harvest_reward(my_trees)
        logger.print_ok(f"Rewards: {rewards_avax}")
        logger.print_ok(f"My Trees: {my_trees}")

        if is_harvest_day and self.pat_w3.is_harvest_day() and self.pat_w3.did_48_hour_replant():
            self._harvest(rewards_avax)

        if self.todays_tax > 30.0 and self._should_replant():
            self._replant(rewards_avax)
        else:
            logger.print_warn(f"Skipping replant b/c we are in the harvest window!")

        self._send_email_update()
        self._update_stats()

    def end(self) -> None:
        logger.print_normal(f"Shutting down bot for {self.user}...")
