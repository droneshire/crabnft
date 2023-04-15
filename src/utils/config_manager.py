import copy
import deepdiff
import json
import os
import time
import typing as T

from utils import logger
from utils.config_types import UserConfig
from utils.security import decrypt, encrypt
from utils.email import Email, send_email
from utils.user import get_alias_from_user


def get_config_file(log_dir: str, user: str) -> str:
    return os.path.join(log_dir, "stats", f"{user.lower()}_config.json")


class ConfigManager:
    CONFIG_UPDATE_TIME = 60.0 * 30.0

    def __init__(
        self,
        user: str,
        config: UserConfig,
        send_email_accounts: T.List[Email],
        encrypt_password: str,
        log_dir: str,
        dry_run: bool = False,
    ):
        self.config = config
        self.user = user
        self.alias = get_alias_from_user(user)
        self.log_dir = log_dir
        self.encrypt_password = encrypt_password

        self.send_email_accounts = send_email_accounts

        self.dry_run = dry_run
        self.last_config_update_time = 0.0

        self.game_string = config["game"].upper()

    def init(self) -> None:
        raise NotImplementedError

    def check_for_config_updates(self) -> bool:
        raise NotImplementedError

    def close(self) -> None:
        self._save_config()

    def get_lifetime_stats(self) -> T.Dict[T.Any, T.Any]:
        raise NotImplementedError

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

    def _get_save_config(self) -> T.Dict[T.Any, T.Any]:
        save_config = copy.deepcopy(self.config)
        byte_key = str.encode(self.encrypt_password)
        save_config["private_key"] = encrypt(
            byte_key, str.encode(self.config["private_key"]), encode=True
        )
        return save_config

    def _get_config_file(self) -> str:
        return get_config_file(self.log_dir, self.user.lower())

    def _save_config(self) -> None:
        if self.dry_run:
            return

        config = self._get_save_config()
        config_file = self._get_config_file()
        with open(config_file, "w") as outfile:
            json.dump(config, outfile, indent=4)

    def _should_ignore_config_key(self, item_key: str) -> bool:
        return item_key in self._get_ignore_config_keys()

    def _get_ignore_config_keys(self) -> T.List[str]:
        return [
            "private_key",
            "address",
            "commission_percent_per_mine",
            "discord_handle",
            "get_sms_updates",
            "get_sms_updates_loots",
            "get_sms_updates_alerts",
            "group",
        ]

    def _get_email_config(self, config) -> str:
        content = ""
        for config_key, value in config.items():
            new_value = value

            if self._should_ignore_config_key(config_key):
                continue

            if isinstance(value, T.List):
                new_value = "\n\t".join([str(v) for v in value])

            if isinstance(value, T.Dict):
                new_value = ""
                for k, v in value.items():
                    if "authorization" in k:
                        continue
                    if isinstance(v, T.List):
                        v = "\n\t".join([str(l) for l in v])
                    new_value += f"{' '.join(k.split('_'))} = {v}\n"

            if isinstance(value, bool):
                new_value = str(value)

            content += f"{config_key.upper()}:\n{new_value}\n\n"
        return content

    def _did_config_change(self) -> bool:
        current = self._get_save_config()
        old = self._load_config()

        for config in [current, old]:
            for del_key in self._get_ignore_config_keys():
                del config[del_key]
                if isinstance(config.get(del_key), dict):
                    config[del_key] = {}
                if isinstance(config.get(del_key), bool):
                    config[del_key] = False
                if isinstance(config.get(del_key), int):
                    config[del_key] = 0
                if isinstance(config.get(del_key), float):
                    config[del_key] = 0.0

        diff = deepdiff.DeepDiff(old, current)
        if diff:
            logger.print_normal(f"{diff}")
            return True
        return False

    def _print_out_config(self) -> None:
        logger.print_bold(f"{self.user} Configuration\n")
        for config_item, value in self.config.items():
            if config_item == "private_key":
                continue

            logger.print_normal(f"\t{config_item}: {value}")
        logger.print_normal("")

    def _send_email_config_if_needed(self) -> None:
        if self.dry_run or not self._did_config_change():
            return

        logger.print_warn(
            f"Config changed for {self.alias}, sending config email..."
        )
        self._send_email_config()

    def _send_email_config(self) -> None:
        if not self.config["get_email_updates"]:
            return

        if self.dry_run:
            return

        content = self._get_email_config(self.config)

        email_message = f"Hello {self.alias}!\n\n"
        email_message += "Here is your updated bot configuration:\n\n"
        email_message += content

        send_email(
            self.send_email_accounts,
            self.config["email"],
            f"{self.game_string} Config Change Notification",
            email_message,
        )
