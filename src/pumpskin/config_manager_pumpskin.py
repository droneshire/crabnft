import copy
import typing as T

from utils import logger
from utils.config_manager import ConfigManager
from utils.config_types import UserConfig
from utils.email import Email
from pumpskin.game_stats import NULL_GAME_STATS


class PumpskinConfigManager(ConfigManager):
    def __init__(
        self,
        user: str,
        config: UserConfig,
        send_email_accounts: T.List[Email],
        encrypt_password: str,
        log_dir: str,
        dry_run: bool = False,
        verbose: bool = False,
        update_from_src: bool = False,
    ):
        super().__init__(user, config, send_email_accounts, encrypt_password, log_dir, dry_run)
        self.update_from_src = update_from_src

    def init(self):
        if not self.update_from_src:
            self.config = self._load_config()
        self._send_email_config_if_needed()
        self._print_out_config()
        self._save_config()

        copy_config = {}
        for k, v in self.config["game_specific_configs"]["special_pumps"].items():
            copy_config[int(k)] = v
        self.config["game_specific_configs"]["special_pumps"] = copy.deepcopy(copy_config)

    def get_lifetime_stats(self) -> T.Dict[T.Any, T.Any]:
        return copy.deepcopy(NULL_GAME_STATS)
