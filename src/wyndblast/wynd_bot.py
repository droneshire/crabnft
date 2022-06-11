import getpass
import typing as T


from utils import logger
from utils.config_types import UserConfig
from utils.email import Email
from utils.security import decrypt_secret
from wyndblast.config_manager_wyndblast import WyndblastConfigManager
from wyndblast.daily_activities import DailyActivitiesGame
from wyndblast.wyndblast_web2_client import WyndblastWeb2Client


class WyndBot:
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
        self.daily_activities: DailyActivitiesGame = DailyActivitiesGame(self.user, self.wynd_w2)

    def init(self) -> None:
        self.config_mgr.init()
        self.wynd_w2.authorize_user()
        self.wynd_w2.update_account()

    def run(self) -> None:
        logger.print_bold(f"Attempting daily activities for {self.user}")
        self.daily_activities.run_activity()

    def end(self) -> None:
        self.config_mgr.close()
        logger.print_normal(f"Shutting down {self.user} bot...")
