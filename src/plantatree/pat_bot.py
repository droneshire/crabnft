import math
import typing as T
from eth_typing import Address
from web3 import Web3

from config_admin import COINMARKETCAP_API_TOKEN
from plantatree.config_manager_pat import PatConfigManager
from plantatree.game_stats import PatLifetimeGameStatsLogger
from plantatree.pat_web3_client import PlantATreeWeb3Client
from utils import logger
from utils.config_types import UserConfig
from utils.email import Email
from utils.math import Average
from utils.price import get_avax_price_usd
from utils.user import get_alias_from_user
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client


class PatBot:
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
        self.dry_run = dry_run

        self.avg_gas_gwei: Average = Average()
        self.last_replant: float = None
        self.referral_address: Address = Web3.toChecksumAddress(referral_address)

        self.config_mgr = PatConfigManager(
            user,
            config,
            email_accounts,
            encrypt_password,
            log_dir,
            dry_run=dry_run,
            verbose=True,
        )

        self.stats_logger = PatLifetimeGameStatsLogger(
            self.alias,
            self.log_dir,
            self.config_mgr.get_lifetime_stats(),
            self.dry_run,
            verbose=False,
        )

    def run(self) -> None:
        # always assume we're replanting daily, so no tax
        current_day_tax = self.pat_w3.get_current_day_tax(extra_48_tax=False)
        if not math.isclose(0.0, current_day_tax):
            logger.print_ok_blue(f"Today's tax: {current_day_tax:.2f}%")
            return

        gas_price_gwei = self.pat_w3.get_gas_price()
        if gas_price_gwei is None:
            gas_price_gwei = -1.0
        self.avg_gas_gwei.update(gas_price_gwei)

        avax_usd = get_avax_price_usd(COINMARKETCAP_API_TOKEN, self.dry_run)
        logger.print_ok(f"AVAX: ${avax_usd:.3f}, Gas: {gas_price_gwei:.2f}")

    def end(self) -> None:
        logger.print_normal(f"Shutting down bot for {self.user}...")
