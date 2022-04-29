import copy
import deepdiff
import gspread
import os
import typing as T

from utils import logger
from utils.config_types import UserConfig
from utils.email import Email, send_email
from utils.google_sheets import GoogleSheets
from utils.user import get_alias_from_user


class ConfigManager:
    def __init__(
        self, user: str, config: UserConfig, email_accounts: T.List[Email], dry_run: bool = False
    ):
        self.config = config
        self.user = user
        self.alias = get_alias_from_user(user)

        self.emails = email_accounts

        self.dry_run = dry_run

        self.config_gsheet_title = f"{self.alias.upper()} Crabada Bot Configuration"
        this_dir = os.path.dirname(os.path.realpath(__file__))
        creds_dir = os.path.dirname(this_dir)
        credentials = os.path.join(creds_dir, "credentials.json")
        self.gsheet = GoogleSheets(self.config_gsheet_title, credentials)

    def init(self) -> None:
        self._print_out_config()
        self._send_email_config_if_needed()
        self._save_config()

    def check_for_updated_config(self) -> UserConfig:
        # TODO: implement reading from config file
        pass

    def _get_save_config(self) -> T.Dict[T.Any, T.Any]:
        save_config = copy.deepcopy(self.config)
        for dont_save_key in [
            "crabada_key",
            "address",
            "commission_percent_per_mine",
            "discord_handle",
        ]:
            del save_config[dont_save_key]
        return json.loads(json.dumps(save_config))

    def _save_config(self) -> None:
        if self.dry_run:
            return

        config = self._get_save_config()
        log_dir = logger.get_logging_dir()
        config_file = os.path.join(logger.get_logging_dir(), f"{self.user.lower()}_config.json")
        with open(config_file, "w") as outfile:
            json.dump(config, outfile, indent=4)

    def _load_config(self) -> T.Dict[T.Any, T.Any]:
        log_dir = logger.get_logging_dir()
        config_file = os.path.join(logger.get_logging_dir(), f"{self.user.lower()}_config.json")
        try:
            with open(config_file, "r") as infile:
                return json.load(infile)
        except:
            return {}

    def _get_email_config(self) -> str:
        content = ""
        for config_key, value in self._get_save_config().items():
            new_value = value

            if isinstance(value, T.List):
                new_value = "\n\t".join([str(v) for v in value])

            if isinstance(value, T.Dict):
                new_value = ""
                for k, v in value.items():
                    new_value += f"{k}: {str(v)}\n"

            if isinstance(value, bool):
                new_value = str(value)

            content += f"{config_key.upper()}:\n{new_value}\n\n"
        return content

    def _did_config_change(self) -> bool:
        current = self._get_save_config()
        old = self._load_config()

        diff = deepdiff.DeepDiff(old, current)
        if diff:
            logger.print_normal(f"{diff}")
            return True
        return False

    def _print_out_config(self) -> None:
        logger.print_bold(f"{self.user} Configuration\n")
        for config_item, value in self.config.items():
            if config_item == "crabada_key":
                continue
            logger.print_normal(f"\t{config_item}: {value}")
        logger.print_normal("")

    def _send_email_config_if_needed(self) -> None:
        content = self._get_email_config()

        if self.dry_run or not self._did_config_change():
            return

        logger.print_warn(f"Config changed for {self.alias}, sending config email...")

        email_message = f"Hello {self.alias}!\n\n"
        email_message += "Here is your updated bot configuration:\n\n"
        email_message += content

        send_email(
            self.emails,
            self.config["email"],
            f"\U0001F980 Crabada Bot Config Change Notification",
            email_message,
        )
