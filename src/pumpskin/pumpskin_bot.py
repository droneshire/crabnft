import getpass
import time
import typing as T
from discord import Color
from discord_webhook import DiscordEmbed, DiscordWebhook

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
    MAX_NUM_NFTS = 1000
    MIN_POTN_TO_CLAIM = 0.0
    MIN_PPIE_TO_CLAIM = 0.0

    def __init__(
        self,
        user: str,
        config: UserConfig,
        email_accounts: T.List[Email],
        encrypt_password: str,
        log_dir: str,
        dry_run: bool,
    ):
        self.config = config
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
            self.config["private_key"], self.address
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
        return 25 if level <= 1 else 25 + 50 * level + 25 * level**2

    @staticmethod
    def _calc_cooldown_from_level(level: int) -> int:
        return level + 1

    @staticmethod
    def _calc_ppie_per_day_from_level(level: int) -> int:
        return level + 3

    def _get_claimable_tokens(
        self, token: str, get_claim_func: T.Callable[int, [int]], token_id: int
    ) -> float:
        claimable = wei_to_token_raw(get_claim_func(token_id))
        logger.print_normal(f"Pumpskin {token_id} has {claimable} ${token} to claim")
        return claimable

    def _claim_potn(self, token_ids: T.List[int]) -> str:
        return self.game_w3.claim_potn()

    def _claim_ppie(self, token_ids: T.List[int]) -> str:
        self.collection_w3.claim_pies(token_ids)

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
            description=f"Finished leveling pumpskin for {self.config['discord_handle'].upper()}\n",
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
        for address, commission_percent in self.config["commission_percent_per_mine"].items():
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

        # Try to claim any POTN and PPEI that we can...
        CLAIMABLES = {
            "POTN": {
                "total": 0.0,
                "ids": [],
                "get": self.game_w3.get_claimable_potn,
                "claim": self._claim_potn,
                "min": self.MIN_POTN_TO_CLAIM,
            },
            "PPIE": {
                "total": 0.0,
                "ids": [],
                "func": self.game_w3.get_claimable_ppie,
                "claim": self._claim_ppie,
                "min": self.MIN_PPIE_TO_CLAIM,
            },
        }

        # See how much we can claim
        for token_id in pumpskin_ids:
            for token, info in CLAIMABLES.items():
                claimable_tokens = self._get_claimable_tokens(token, info["get"], token_id)
                CLAIMABLES[token]["total"] += claimable_tokens
                if claimable_tokens > 0.0:
                    CLAIMABLES[token]["ids"].append(token_id)

        # Claim it if we are above threshold
        for token, info in CLAIMABLES.items():
            if info["total"] >= info["min"]:
                logger.print_normal(
                    f"Attempting to claim {claimable_potn} ${token} for {self.user}..."
                )

                tx_hash = info["claim"](info["ids"])
                tx_receipt = self.game_w3.get_transaction_receipt(tx_hash)
                gas = wei_to_token_raw(self.game_w3.get_gas_cost_of_transaction_wei(tx_receipt))
                logger.print_bold(f"Paid {gas} AVAX in gas")

                self.stats_logger.lifetime_stats["avax_gas"] += gas

                if tx_receipt.get("status", 0) != 1:
                    logger.print_fail(f"Failed to claim ${token}!")
                else:
                    logger.print_ok(f"Successfully claimed ${token}")
                    logger.print_normal(f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n")
            else:
                logger.print_warn(f"Not enough ${token} to claim ({info['total']})")

        for token_id in pumpskin_ids:
            pumpskin: StakedPumpskin = self.collection_w3.get_staked_pumpskin_info(token_id)

            # check to see if we're past the cooldown period
            now = time.time()
            cooldown_time = pumpskin["cooldown_ts"] - now
            if cooldown_time >= 0:
                time_left_pretty = get_pretty_seconds(delta)
                logger.print_warn(
                    f"Pumpskin {token_id} not ready for levelling yet...{time_left_pretty}"
                )
                continue

            potn_balance = self.potn_w3.get_balance()

            # check to see how much POTN needed to level up
            level = pumpskin["kg"] / 100
            logger.print_normal(f"Pumpskin {token_id}, Level {level}")
            level_potn = self._calc_potn_from_level(level + 1)
            potn_to_level = level_potn - pumpskin["eaten_amount"]

            # Drink POTN needed if we have enough
            if potn_balance < potn_to_level:
                logger.print_warn(f"Not enough $POTN to level up {token_id}. Skipping...")
                continue

            num_potn_wei = token_to_wei(potn_to_level)
            logger.print_normal(
                f"Attempting to have pumpskin {token_id} drink {potn_to_level} potion"
            )
            tx_hash = self.game_w3.drink_potion(token_id, num_potn_wei)
            tx_receipt = self.game_w3.get_transaction_receipt(tx_hash)
            gas = wei_to_token_raw(self.game_w3.get_gas_cost_of_transaction_wei(tx_receipt))
            logger.print_bold(f"Paid {gas} AVAX in gas")

            self.stats_logger.lifetime_stats["avax_gas"] += gas

            if tx_receipt.get("status", 0) != 1:
                logger.print_fail(f"Failed to drink potion for ${token}!")
            else:
                logger.print_ok(f"Successfully drank potion for ${token}")
                logger.print_normal(f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n")

            # Level Pumpskin who can be leveled up
            tx_hash = self.collection_w3.level_up_pumpkin(token_id)
            tx_receipt = self.game_w3.get_transaction_receipt(tx_hash)
            gas = wei_to_token_raw(self.game_w3.get_gas_cost_of_transaction_wei(tx_receipt))
            logger.print_bold(f"Paid {gas} AVAX in gas")

            self.stats_logger.lifetime_stats["avax_gas"] += gas

            if tx_receipt.get("status", 0) != 1:
                logger.print_fail(f"Failed to level up ${token}!")
            else:
                logger.print_ok(f"Successfully leveled up ${token}")
                logger.print_normal(f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n")
                self._send_leveling_discord_activity_update(token_id, level + 1)

        ppie_balance = self.ppie_w3.get_balance()

        if ppie_balance < self.MIN_PPIE_TO_STAKE:
            logger.print_warn(
                f"Not going to stake $PPIE since it is below our threshold ({ppie_balance} < {self.MIN_PPIE_TO_STAKE})"
            )
            return

        # Try to stake PPIE
        logger.print_bold(f"Attempting to stake {ppie_balance} $PPIE...")
        tx_hash = self.game_w3.staking_ppie(token_to_wei(ppie_balance))
        tx_receipt = self.game_w3.get_transaction_receipt(tx_hash)
        gas = wei_to_token_raw(self.game_w3.get_gas_cost_of_transaction_wei(tx_receipt))
        logger.print_bold(f"Paid {gas} AVAX in gas")

        self.stats_logger.lifetime_stats["avax_gas"] += gas

        if tx_receipt.get("status", 0) != 1:
            logger.print_fail(f"Failed to stake ${ppie_balance} $PPIE!")
        else:
            logger.print_ok(f"Successfully staked ${ppie_balance} $PPIE")
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
