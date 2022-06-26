import getpass
import time
import typing as T


from utils import logger
from utils.config_types import UserConfig
from utils.email import Email
from utils.security import decrypt_secret
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from wyndblast.config_manager_wyndblast import WyndblastConfigManager
from wyndblast.daily_activities import DailyActivitiesGame
from wyndblast.wyndblast_web2_client import WyndblastWeb2Client
from wyndblast.wyndblast_web3_client import WyndblastGameWeb3Client
from wyndblast.types import WyndNft


class WyndBot:
    TIME_BETWEEN_AUTH = 60.0 * 60.0 * 4.0

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

        self.last_auth_time = 0

        self.config_mgr = WyndblastConfigManager(
            user,
            config,
            email_accounts,
            encrypt_password,
            log_dir,
            dry_run=dry_run,
            verbose=True,
        )

        self.wynd_w2: WyndblastWeb2Client = WyndblastWeb2Client(
            self.config["private_key"], self.address
        )

        self.wynd_w3: WyndblastGameWeb3Client = (
            WyndblastGameWeb3Client()
            .set_credentials(config["address"], config["private_key"])
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_dry_run(dry_run)
        )

        self.daily_activities: DailyActivitiesGame = DailyActivitiesGame(
            user,
            config,
            email_accounts,
            self.wynd_w2,
            self.wynd_w3,
        )

    def _check_and_submit_available_inventory(self) -> None:
        wynd_infos: T.List[WyndNft] = self.wynd_w2.get_wynd_status()
        logger.print_ok_blue(f"Searching for NFTs in inventory...")
        wynds_to_move_to_game = []
        for wynd in wynd_infos:
            if not wynd["isSubmitted"]:
                logger.print_ok_blue_arrow(f"Found {wynd['token_id']} in inventory...")
                wynds_to_move_to_game.append(int(wynd["token_id"]))

        if not wynds_to_move_to_game:
            logger.print_normal(f"No NFTs found in inventory")
            return

        logger.print_bold(f"Attempting to move wynds from inventory to game...")
        tx_hash = self.wynd_w3.move_out_of_inventory(token_ids=wynds_to_move_to_game)
        tx_receipt = self.wynd_w3.get_transaction_receipt(tx_hash)
        if tx_receipt["status"] != 1:
            logger.print_fail(f"Failed to move wynds to game!")
        else:
            logger.print_ok(f"Successfully moved to game")

    def init(self) -> None:
        self.config_mgr.init()
        self.wynd_w2.authorize_user()
        self.wynd_w2.update_account()
        self.last_auth_time = time.now()

    def run(self) -> None:
        logger.print_bold(f"\n\nAttempting daily activities for {self.user}")
        now = time.now()

        if now - self.last_auth_time > self.TIME_BETWEEN_AUTH:
            self.wynd_w2.authorize_user()
            self.wynd_w2.update_account()
            self.last_auth_time = now

        self._check_and_submit_available_inventory()
        self.daily_activities.run_activity()
        self.daily_activities.check_and_claim_if_needed()

    def end(self) -> None:
        self.config_mgr.close()
        logger.print_normal(f"Shutting down {self.user} bot...")
