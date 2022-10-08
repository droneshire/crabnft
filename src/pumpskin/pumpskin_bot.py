import getpass
import time
import typing as T


from utils import logger
from utils.config_types import UserConfig
from utils.email import Email
from utils.price import wei_to_token_raw
from utils.user import get_alias_from_user
from utils.security import decrypt_secret
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from pumpskin.config_manager_pumpskin import PumpskinConfigManager
from pumpskin.pumpskin_leveling import PumpskinLeveling
from pumpskin.game_stats import NULL_GAME_STATS, PumpskinLifetimeGameStatsLogger
from pumpskin.types import WyndNft
from pumpskin.pumpskin_web2_client import PumpskinWeb2Client
from pumpskin.pumpskin_web3_client import PumpskinGameWeb3Client


class PumpskinBot:
    TIME_BETWEEN_AUTH = 60.0 * 60.0 * 6.0

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

        self.pumpskin_w3: PumpskinGameWeb3Client = (
            PumpskinGameWeb3Client()
            .set_credentials(config["address"], config["private_key"])
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_dry_run(dry_run)
        )

        self.stats_logger = PumpskinLifetimeGameStatsLogger(
            get_alias_from_user(self.user),
            self.log_dir,
            self.config_mgr.get_lifetime_stats(),
            self.dry_run,
            verbose=False,
        )

        self.leveling: PumpskinLeveling = PumpskinLeveling(
            user, config, email_accounts, self.pumpskin_w2, self.pumpskin_w3, self.stats_logger
        )

    def init(self) -> None:
        self.config_mgr.init()
        self.last_auth_time = 0

    def run(self) -> None:
        logger.print_bold(f"\n\nAttempting levelling activities for {self.user}")
        now = time.time()

        if now - self.last_auth_time > self.TIME_BETWEEN_AUTH:
            self.pumpskin_w2.authorize_user()
            self.last_auth_time = now

        self.pumpskin_w2.update_account()
        self.leveling.run_activity()
        self.leveling.check_and_claim_if_needed()
        self.stats_logger.write()

    def end(self) -> None:
        self.config_mgr.close()
        self.stats_logger.write()
        logger.print_normal(f"Shutting down {self.user} bot...")
