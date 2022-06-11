import copy
import typing as T

from utils import logger
from utils.config_manager import ConfigManager
from utils.config_types import UserConfig
from utils.email import Email
from wyndblast.game_stats import NULL_GAME_STATS


class WyndblastConfigManager(ConfigManager):
    def __init__(
        self,
        user: str,
        config: UserConfig,
        send_email_accounts: T.List[Email],
        encrypt_password: str,
        log_dir: str,
        dry_run: bool = False,
        verbose: bool = False,
    ):
        super().__init__(user, config, send_email_accounts, encrypt_password, log_dir, dry_run)

    def init(self):
        self._print_out_config()
        self.config = self._load_config()
        self._send_email_config_if_needed()
        self._save_config()

    def _load_config(self) -> UserConfig:
        config_file = self._get_config_file()
        try:
            with open(config_file, "r") as infile:
                byte_key = str.encode(self.encrypt_password)
                load_config: UserConfig = json.load(infile)
                copy_config = copy.deepcopy(load_config)

                if load_config["sms_number"] == "+1":
                    load_config["sms_number"] = ""
                load_config["private_key"] = decrypt(
                    byte_key, load_config["private_key"], decode=True
                ).decode()
                return load_config
        except:
            return copy.deepcopy(self.config)

    def _get_empty_new_config(self) -> UserConfig:
        new_config = copy.deepcopy(self.config)

        assert self.config is not None, "Empty config"

        if "game_specific_configs" not in new_config:
            new_config["game_specific_configs"] = {}

        delete_keys = []

        for del_key in delete_keys:
            if del_key in new_config["game_specific_configs"]:
                del new_config["game_specific_configs"][del_key]
            if isinstance(self.config["game_specific_configs"][del_key], dict):
                new_config["game_specific_configs"][del_key] = {}
            if isinstance(self.config["game_specific_configs"][del_key], bool):
                new_config["game_specific_configs"][del_key] = False
            if isinstance(self.config["game_specific_configs"][del_key], int):
                new_config["game_specific_configs"][del_key] = 0
            if isinstance(self.config["game_specific_configs"][del_key], float):
                new_config["game_specific_configs"][del_key] = 0.0

        del new_config["max_gas_price_gwei"]
        new_config["max_gas_price_gwei"] = 0.0
        return new_config

    def get_lifetime_stats(self) -> T.Dict[T.Any, T.Any]:
        return copy.deepcopy(NULL_GAME_STATS)
