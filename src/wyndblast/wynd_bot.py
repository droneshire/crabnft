import getpass
import time
import typing as T
from yaspin import yaspin

from config_wyndblast import BETA_TEST_LIST, DAILY_ENABLED, PVE_ENABLED
from utils import logger
from utils.config_types import UserConfig
from utils.email import Email
from utils.price import wei_to_token
from utils.user import get_alias_from_user
from utils.security import decrypt_secret
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from wyndblast.config_manager_wyndblast import WyndblastConfigManager
from wyndblast.daily_activities import DailyActivitiesGame
from wyndblast.daily_activities_web2_client import DailyActivitiesWyndblastWeb2Client
from wyndblast.game_stats import NULL_GAME_STATS, WyndblastLifetimeGameStatsLogger
from wyndblast.pve import PveGame
from wyndblast.pve_web2_client import PveWyndblastWeb2Client
from wyndblast.types import WyndNft
from wyndblast.wyndblast_web2_client import WyndblastWeb2Client
from wyndblast.wyndblast_web3_client import WyndblastGameWeb3Client, WyndblastNftGameWeb3Client


class WyndBot:
    TIME_BETWEEN_AUTH = 60.0 * 60.0 * 2.0

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
        self.alias = get_alias_from_user(user)
        self.user: str = user
        self.emails: T.List[Email] = email_accounts
        self.log_dir: str = log_dir
        self.dry_run: bool = dry_run
        self.address: Address = config["address"]

        self.last_pve_auth_time = 0

        self.config_mgr = WyndblastConfigManager(
            user,
            config,
            email_accounts,
            encrypt_password,
            log_dir,
            dry_run=dry_run,
            verbose=True,
        )

        self.wynd_w2: DailyActivitiesWyndblastWeb2Client = DailyActivitiesWyndblastWeb2Client(
            self.config["private_key"],
            self.address,
            WyndblastWeb2Client.DAILY_ACTIVITY_BASE_URL,
            dry_run=dry_run,
        )
        self.pve_w2: PveWyndblastWeb2Client = PveWyndblastWeb2Client(
            self.config["private_key"],
            self.address,
            WyndblastWeb2Client.PVE_BASE_URL,
            dry_run=dry_run,
        )

        self.wynd_w3: WyndblastGameWeb3Client = (
            WyndblastGameWeb3Client()
            .set_credentials(config["address"], config["private_key"])
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(dry_run)
        )

        self.nft_w3: WyndblastNftGameWeb3Client = (
            WyndblastNftGameWeb3Client()
            .set_credentials(config["address"], config["private_key"])
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(dry_run)
        )

        self.stats_logger = WyndblastLifetimeGameStatsLogger(
            self.alias,
            self.log_dir,
            self.config_mgr.get_lifetime_stats(),
            self.dry_run,
            verbose=False,
        )

        self.daily_activities: DailyActivitiesGame = DailyActivitiesGame(
            user, config, email_accounts, self.wynd_w2, self.wynd_w3, self.stats_logger
        )

        self.pve: PveGame = PveGame(
            user, config, email_accounts, self.pve_w2, self.wynd_w3, self.stats_logger
        )

    def _check_and_submit_available_inventory(self) -> None:
        wynd_infos: T.List[WyndNft] = self.wynd_w2.get_wynd_status()
        logger.print_ok_blue(f"Searching for NFTs in inventory...")
        wynds_to_move = []
        for wynd in wynd_infos:
            if not wynd["isSubmitted"]:
                logger.print_ok_blue_arrow(f"Found {wynd['token_id']} in inventory...")
                wynds_to_move.append(int(wynd["token_id"]))

        if not wynds_to_move:
            logger.print_normal(f"No NFTs found in inventory")
            return

        logger.print_bold(f"Attempting to move wynds from inventory to game...")
        if not self.nft_w3.is_approved_for_all(self.wynd_w3.contract_checksum_address):
            logger.print_bold(f"Allowing access to wynds...")
            tx_hash = self.nft_w3.set_approval_for_all(self.wynd_w3.contract_checksum_address, True)
            tx_receipt = self.nft_w3.get_transaction_receipt(tx_hash)
            gas = wei_to_token(self.nft_w3.get_gas_cost_of_transaction_wei(tx_receipt))
            logger.print_bold(f"Paid {gas} AVAX in gas")

            self.stats_logger.lifetime_stats["avax_gas"] += gas

            if tx_receipt.get("status", 0) != 1:
                logger.print_warn(f"Failed to allow access!")
            else:
                logger.print_ok(f"Successfully allowed access")
                logger.print_normal(f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n")

        time.sleep(5.0)

        tx_hash = self.wynd_w3.move_out_of_inventory(token_ids=wynds_to_move)
        tx_receipt = self.wynd_w3.get_transaction_receipt(tx_hash)
        gas = wei_to_token(self.wynd_w3.get_gas_cost_of_transaction_wei(tx_receipt))
        logger.print_bold(f"Paid {gas} AVAX in gas")

        self.stats_logger.lifetime_stats["avax_gas"] += gas
        if tx_receipt.get("status", 0) != 1:
            logger.print_fail(f"Failed to move wynds to game!\n{tx_receipt}")
        else:
            logger.print_ok(f"Successfully moved to game")
            logger.print_normal(f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n")

    def _check_and_maybe_secure_account(self) -> None:
        if DAILY_ENABLED or PVE_ENABLED:
            return

        if not self.wynd_w2.update_account():
            self.wynd_w2.authorize_user()
            self.wynd_w2.update_account()

        wynd_infos: T.List[WyndNft] = self.wynd_w2.get_wynd_status()
        logger.print_ok_blue(f"Searching for NFTs in game...")
        wynds_to_move = []
        for wynd in wynd_infos:
            if wynd["isSubmitted"]:
                logger.print_ok_blue_arrow(f"Found {wynd['token_id']} in game...")
                wynds_to_move.append(int(wynd["token_id"]))

        if wynds_to_move:
            logger.format_ok_blue_arrow(f"Moving {len(wynds_to_move)} wynds out of game")
            tx_hash = self.wynd_w3.move_out_of_inventory(wynds_to_move)
            tx_receipt = self.nft_w3.get_transaction_receipt(tx_hash)
            gas = wei_to_token(self.nft_w3.get_gas_cost_of_transaction_wei(tx_receipt))
            logger.print_bold(f"Paid {gas} AVAX in gas")

            self.stats_logger.lifetime_stats["avax_gas"] += gas

            if tx_receipt.get("status", 0) != 1:
                logger.print_warn(f"Failed to move wynds out of game!")
            else:
                logger.print_ok(f"Successfully move wynds out of game")
                logger.print_normal(f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n")

        else:
            logger.print_normal(f"No NFTs found in game")

        if self.nft_w3.is_approved_for_all(self.wynd_w3.contract_checksum_address):
            logger.format_ok_blue_arrow(f"Locking down NFTs since not playing game")
            tx_hash = self.nft_w3.set_approval_for_all(
                self.wynd_w3.contract_checksum_address, False
            )
            tx_receipt = self.nft_w3.get_transaction_receipt(tx_hash)
            gas = wei_to_token(self.nft_w3.get_gas_cost_of_transaction_wei(tx_receipt))
            logger.print_bold(f"Paid {gas} AVAX in gas")

            self.stats_logger.lifetime_stats["avax_gas"] += gas

            if tx_receipt.get("status", 0) != 1:
                logger.print_warn(f"Failed to remove nft access!")
            else:
                logger.print_ok(f"Successfully removed nft access")
                logger.print_normal(f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n")

        if self.wynd_w3.is_allowed():
            logger.format_ok_blue_arrow(f"Locking down game contract since not playing game")
            tx_hash = self.nft_w3.unapprove()
            tx_receipt = self.nft_w3.get_transaction_receipt(tx_hash)
            gas = wei_to_token(self.nft_w3.get_gas_cost_of_transaction_wei(tx_receipt))
            logger.print_bold(f"Paid {gas} AVAX in gas")

            self.stats_logger.lifetime_stats["avax_gas"] += gas

            if tx_receipt.get("status", 0) != 1:
                logger.print_warn(f"Failed to remove contract access!")
            else:
                logger.print_ok(f"Successfully removed contract access")
                logger.print_normal(f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n")

    def init(self) -> None:
        self.config_mgr.init()

    def run(self) -> None:
        logger.print_bold(f"\n\nAttempting daily activities for {self.user}")

        if DAILY_ENABLED:
            if not self.wynd_w2.update_account():
                self.wynd_w2.authorize_user()
                self.wynd_w2.update_account()

            self._check_and_submit_available_inventory()
            self.daily_activities.run_activity()

        if self.alias in BETA_TEST_LIST and PVE_ENABLED:
            logger.print_bold(f"\n\nAttempting PVE game for {self.user}")
            self.pve_w2.logout_user()
            self.pve_w2.authorize_user()

            self.pve.play_game()

        self._check_and_maybe_secure_account()

        self.stats_logger.write()

    def end(self) -> None:
        self.config_mgr.close()
        self.stats_logger.write()
        logger.print_normal(f"Shutting down {self.user} bot...")
