import copy
import getpass
import time
import typing as T
from discord import Color
from discord_webhook import DiscordEmbed, DiscordWebhook
from eth_typing import Address

from utils import discord
from utils import logger
from utils.config_types import UserConfig
from utils.email import Email
from utils.general import get_pretty_seconds
from utils.price import token_to_wei, wei_to_token_raw
from utils.user import get_alias_from_user
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.potn_web3_client import PotnWeb3Client
from web3_utils.ppie_web3_client import PpieWeb3Client
from pumpskin.config_manager_pumpskin import PumpskinConfigManager
from pumpskin.game_stats import NULL_GAME_STATS, PumpskinLifetimeGameStatsLogger
from pumpskin.types import StakedPumpskin
from pumpskin.pumpskin_web2_client import PumpskinWeb2Client
from pumpskin.pumpskin_web3_client import (
    PumpskinCollectionWeb3Client,
    PumpskinContractWeb3Client,
    PumpskinNftWeb3Client,
)


class PumpskinBot:
    def __init__(
        self,
        user: str,
        config: UserConfig,
        email_accounts: T.List[Email],
        encrypt_password: str,
        log_dir: str,
        dry_run: bool,
    ):
        self.user: str = user
        self.emails: T.List[Email] = email_accounts
        self.log_dir: str = log_dir
        self.dry_run: bool = dry_run
        self.address: Address = config["address"]

        self.current_stats = copy.deepcopy(NULL_GAME_STATS)

        self.config_mgr = PumpskinConfigManager(
            user,
            config,
            email_accounts,
            encrypt_password,
            log_dir,
            dry_run=dry_run,
            verbose=True,
        )

        self.pumpskin_w2: PumpskinWeb2Client = PumpskinWeb2Client(
            self.config_mgr.config["private_key"], self.address
        )

        self.collection_w3: PumpskinCollectionWeb3Client = (
            PumpskinCollectionWeb3Client()
            .set_credentials(config["address"], config["private_key"])
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_dry_run(dry_run)
        )

        self.game_w3: PumpskinContractWeb3Client = (
            PumpskinContractWeb3Client()
            .set_credentials(config["address"], config["private_key"])
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_dry_run(dry_run)
        )

        self.nft_w3: PumpskinNftWeb3Client = (
            PumpskinNftWeb3Client()
            .set_credentials(config["address"], config["private_key"])
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_dry_run(dry_run)
        )

        self.potn_w3: PotnWeb3Client = T.cast(
            PotnWeb3Client,
            (
                PotnWeb3Client()
                .set_credentials(config["address"], config["private_key"])
                .set_node_uri(AvalancheCWeb3Client.NODE_URL)
                .set_dry_run(dry_run)
            ),
        )

        self.ppie_w3: PpieWeb3Client = T.cast(
            PpieWeb3Client,
            (
                PpieWeb3Client()
                .set_credentials(config["address"], config["private_key"])
                .set_node_uri(AvalancheCWeb3Client.NODE_URL)
                .set_dry_run(dry_run)
            ),
        )

        self.stats_logger = PumpskinLifetimeGameStatsLogger(
            get_alias_from_user(self.user),
            self.log_dir,
            self.config_mgr.get_lifetime_stats(),
            self.dry_run,
            verbose=False,
        )

    @staticmethod
    def _calc_potn_from_level(level: int) -> int:
        return 25 if level <= 1 else int(25 + 50 * level + 25 * level**2)

    @staticmethod
    def _calc_cooldown_from_level(level: int) -> int:
        return level + 1

    @staticmethod
    def _calc_ppie_per_day_from_level(level: int) -> int:
        return level + 3

    def _get_pumpskin_ids(self) -> T.List[int]:
        pumpskin_ids: T.List[int] = self.collection_w3.get_staked_pumpskins(self.address)

        logger.print_ok_blue(f"Found {len(pumpskin_ids)} Pumpskins for user {self.user}!")

        return pumpskin_ids

    def _send_leveling_discord_activity_update(self, token_id: int, level: int) -> None:
        webhook = DiscordWebhook(
            url=discord.DISCORD_WEBHOOK_URL["PUMPSKIN_ACTIVITY"], rate_limit_retry=True
        )
        embed = DiscordEmbed(
            title=f"PUMPSKIN LEVELING",
            description=f"Finished leveling pumpskin for {self.config_mgr.config['discord_handle'].upper()}\n",
            color=Color.orange().value,
        )

        embed.add_embed_field(name=f"Pumpskin", value=f"{token_id}", inline=False)
        embed.add_embed_field(name=f"Level", value=f"{level}", inline=True)

        pumpskin_image_uri = self.pumpskin_w2.get_pumpskin_image(token_id)

        embed.set_thumbnail(url=pumpskin_image_uri, height=100, width=100)
        webhook.add_embed(embed)
        webhook.execute()

    def _update_stats(self) -> None:
        for k, v in self.current_stats.items():
            if type(v) != type(self.stats_logger.lifetime_stats.get(k)):
                logger.print_warn(
                    f"Mismatched stats:\n{self.current_stats}\n{self.stats_logger.lifetime_stats}"
                )
                continue

            if k in ["commission_ppie"]:
                continue

            if isinstance(v, list):
                self.stats_logger.lifetime_stats[k].extend(v)
            elif isinstance(v, dict):
                for i, j in self.stats_logger.lifetime_stats[k].items():
                    self.stats_logger.lifetime_stats[k][i] += self.current_stats[k][i]
            else:
                self.stats_logger.lifetime_stats[k] += v

        self.stats_logger.lifetime_stats["commission_ppie"] = self.stats_logger.lifetime_stats.get(
            "commission_ppie", {COMMISSION_WALLET_ADDRESS: 0.0}
        )

        ppie_rewards = self.current_stats["ppie"]
        for address, commission_percent in self.config_mgr.config[
            "commission_percent_per_mine"
        ].items():
            commission_ppie = ppie_rewards * (commission_percent / 100.0)

            self.stats_logger.lifetime_stats["commission_ppie"][address] = (
                self.stats_logger.lifetime_stats["commission_ppie"].get(address, 0.0)
                + commission_ppie
            )

            logger.print_ok(
                f"Added {commission_ppie} $PPIE for {address} in commission ({commission_percent}%)!"
            )

        self.current_stats = copy.deepcopy(NULL_GAME_STATS)

        logger.print_ok_blue(
            f"Lifetime Stats for {self.user.upper()}\n{json.dumps(self.stats_logger.lifetime_stats, indent=4)}"
        )

    def _run_game_loop(self) -> None:
        # get all pumpskin id's that correspond to the user
        pumpskin_ids: T.List[int] = self._get_pumpskin_ids()

        potn_balance = self.potn_w3.get_balance()
        ppie_balance = self.ppie_w3.get_balance()

        logger.print_bold(f"{self.user} Balances:")
        logger.print_ok_arrow(f"PPIE: {ppie_balance:.2f}")
        logger.print_ok_arrow(f"POTN: {potn_balance:.2f}")
        logger.print_ok_arrow(f"\U0001F383: {len(pumpskin_ids)}")

        # Claim POTN
        logger.print_ok_blue(f"Checking $POTN for claims...")
        total_claimable_potn = wei_to_token_raw(self.game_w3.get_claimable_potn(self.address))

        if (
            total_claimable_potn
            >= self.config_mgr.config["game_specific_configs"]["min_potn_claim"]
        ):
            logger.print_normal(
                f"Attempting to claim {total_claimable_potn:.2f} $POTN for {self.user}..."
            )

            tx_hash = self.game_w3.claim_potn()
            tx_receipt = self.game_w3.get_transaction_receipt(tx_hash)
            gas = wei_to_token_raw(self.game_w3.get_gas_cost_of_transaction_wei(tx_receipt))
            logger.print_bold(f"Paid {gas} AVAX in gas")

            self.stats_logger.lifetime_stats["avax_gas"] += gas

            if tx_receipt.get("status", 0) != 1:
                logger.print_fail(f"Failed to claim $POTN!")
            else:
                logger.print_ok(f"Successfully claimed $POTN")
                logger.print_normal(f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n")
        else:
            logger.print_warn(f"Not enough $POTN to claim ({total_claimable_potn:.2f})")

        # Claim PPIE
        logger.print_ok_blue(f"Checking $PPIE for claims...")
        total_claimable_ppie = 0.0

        ppie_tokens = []
        for token_id in pumpskin_ids:
            claimable_tokens = wei_to_token_raw(self.collection_w3.get_claimable_ppie(token_id))
            logger.print_normal(f"Pumpskin {token_id} has {claimable_tokens:.2f} $PPIE to claim")
            total_claimable_ppie += claimable_tokens

            if claimable_tokens > 0.0:
                ppie_tokens.append(token_id)

        if (
            total_claimable_ppie
            >= self.config_mgr.config["game_specific_configs"]["min_ppie_claim"]
        ):
            logger.print_normal(
                f"Attempting to claim {total_claimable_ppie:.2f} $PPIE for {self.user}..."
            )

            tx_hash = self.collection_w3.claim_pies(ppie_tokens)
            tx_receipt = self.game_w3.get_transaction_receipt(tx_hash)
            gas = wei_to_token_raw(self.game_w3.get_gas_cost_of_transaction_wei(tx_receipt))
            logger.print_bold(f"Paid {gas} AVAX in gas")

            self.stats_logger.lifetime_stats["avax_gas"] += gas

            if tx_receipt.get("status", 0) != 1:
                logger.print_fail(f"Failed to claim $PPIE!")
            else:
                logger.print_ok(f"Successfully claimed $PPIE")
                logger.print_normal(f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n")
        else:
            logger.print_warn(f"Not enough $PPIE to claim ({total_claimable_ppie:.2f})")

        # Now try to level pumpskins...
        for token_id in pumpskin_ids:
            pumpskin: StakedPumpskin = self.collection_w3.get_staked_pumpskin_info(token_id)

            # check to see if we're past the cooldown period
            now = time.time()
            cooldown_time = pumpskin["cooldown_ts"] - now
            if cooldown_time >= 0:
                time_left_pretty = get_pretty_seconds(cooldown_time)
                logger.print_warn(
                    f"Pumpskin {token_id} not ready for leveling yet. Remaining time: {time_left_pretty}"
                )
                continue

            potn_balance = self.potn_w3.get_balance()

            # check to see how much POTN needed to level up
            level = pumpskin["kg"] / 100
            level_potn = self._calc_potn_from_level(level + 1)
            logger.print_ok_blue(f"Pumpskin {token_id}, Level {level} POTN needed: {level_potn}")
            potn_to_level = level_potn - pumpskin["eaten_amount"]

            # Drink POTN needed if we have enough
            if potn_balance < potn_to_level:
                logger.print_warn(
                    f"Not enough $POTN to level up {token_id}. Have: {potn_balance:.2f} Need: {potn_to_level:.2f}. Skipping..."
                )
                continue

            num_potn_wei = token_to_wei(potn_to_level)
            logger.print_normal(
                f"Attempting to have pumpskin {token_id} drink {potn_to_level} $POTN"
            )
            tx_hash = self.game_w3.drink_potion(token_id, num_potn_wei)
            tx_receipt = self.game_w3.get_transaction_receipt(tx_hash)
            gas = wei_to_token_raw(self.game_w3.get_gas_cost_of_transaction_wei(tx_receipt))
            logger.print_bold(f"Paid {gas} AVAX in gas")

            self.stats_logger.lifetime_stats["avax_gas"] += gas

            if tx_receipt.get("status", 0) != 1:
                logger.print_fail(f"Failed to drink potion for {token_id}!")
            else:
                logger.print_ok(f"Successfully drank potion for {token_id}")
                logger.print_normal(f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n")

            # Level Pumpskin who can be leveled up
            logger.print_normal(f"Attempting to Level up pumpskin {token_id} to {level + 1}...")
            tx_hash = self.collection_w3.level_up_pumpkin(token_id)
            tx_receipt = self.game_w3.get_transaction_receipt(tx_hash)
            gas = wei_to_token_raw(self.game_w3.get_gas_cost_of_transaction_wei(tx_receipt))
            logger.print_bold(f"Paid {gas} AVAX in gas")

            self.stats_logger.lifetime_stats["avax_gas"] += gas

            if tx_receipt.get("status", 0) != 1:
                logger.print_fail(f"Failed to level up pumpskin {token_id}!")
            else:
                logger.print_ok(f"Successfully leveled up pumpskin {token_id} to {level + 1}")
                logger.print_normal(f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n")
                self._send_leveling_discord_activity_update(token_id, level + 1)

        ppie_balance = self.ppie_w3.get_balance()

        min_ppie_to_stake = self.config_mgr.config["game_specific_configs"]["min_ppie_stake"]
        if ppie_balance <= min_ppie_to_stake:
            logger.print_warn(
                f"Not going to stake $PPIE since it is below our threshold ({ppie_balance:.2f} < {min_ppie_to_stake:.2f})"
            )
            return

        # Try to stake PPIE
        logger.print_bold(f"Attempting to stake {ppie_balance:.2f} $PPIE...")
        tx_hash = self.game_w3.staking_ppie(token_to_wei(ppie_balance))
        tx_receipt = self.game_w3.get_transaction_receipt(tx_hash)
        gas = wei_to_token_raw(self.game_w3.get_gas_cost_of_transaction_wei(tx_receipt))
        logger.print_bold(f"Paid {gas} AVAX in gas")

        self.stats_logger.lifetime_stats["avax_gas"] += gas

        if tx_receipt.get("status", 0) != 1:
            logger.print_fail(f"Failed to stake ${ppie_balance:.2f} $PPIE!")
        else:
            logger.print_ok(f"Successfully staked ${ppie_balance:.2f} $PPIE")
            logger.print_normal(f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n")

    def init(self) -> None:
        self.config_mgr.init()

    def run(self) -> None:
        logger.print_bold(f"\n\nAttempting leveling activities for {self.user}")

        self._run_game_loop()
        self.stats_logger.write()

    def end(self) -> None:
        self.config_mgr.close()
        self.stats_logger.write()
        logger.print_normal(f"Shutting down {self.user} bot...")
