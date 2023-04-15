import copy
import json
import typing as T

from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.types import CrabadaClass
from utils import logger
from utils.config_manager import ConfigManager
from utils.config_types import UserConfig
from utils.email import Email
from utils.security import decrypt
from crabada.game_stats import NULL_GAME_STATS


class CrabadaConfigManager(ConfigManager):
    def __init__(
        self,
        user: str,
        config: UserConfig,
        send_email_accounts: T.List[Email],
        encrypt_password: str,
        log_dir: str,
        crabada_w2: CrabadaWeb2Client,
        dry_run: bool = False,
        verbose: bool = False,
    ):
        super().__init__(
            user,
            config,
            send_email_accounts,
            encrypt_password,
            log_dir,
            dry_run,
        )
        self.crabada_w2 = crabada_w2
        self.team_composition_and_mp = self.crabada_w2.get_team_compositions_and_mp(
            self.config["address"]
        )
        self.crab_classes = self.crabada_w2.get_crab_classes(self.config["address"])

    def _load_config(self) -> UserConfig:
        config_file = self._get_config_file()
        try:
            with open(config_file, "r") as infile:
                byte_key = str.encode(self.encrypt_password)
                load_config: UserConfig = json.load(infile)
                copy_config = copy.deepcopy(load_config)
                for old_game_key in [
                    "mining_teams",
                    "looting_teams",
                    "max_reinforcement_price_tus",
                    "reinforcing_crabs",
                    "mining_strategy",
                    "looting_strategy",
                    "should_reinforce",
                ]:
                    if "game_specific_configs" not in load_config.keys():
                        load_config["game_specific_configs"] = {}

                    if old_game_key in load_config:
                        load_config["game_specific_configs"][old_game_key] = copy_config[
                            old_game_key
                        ]
                        if old_game_key in [
                            "max_reinforcement_price_tus",
                            "should_reinforce",
                        ]:
                            del load_config[old_game_key]

                if load_config["sms_number"] == "+1":
                    load_config["sms_number"] = ""
                load_config["private_key"] = decrypt(
                    byte_key, load_config["private_key"], decode=True
                ).decode()
                for config_key in [
                    "mining_teams",
                    "looting_teams",
                    "reinforcing_crabs",
                ]:
                    for k, v in copy_config["game_specific_configs"].get(config_key, {}).items():
                        del load_config["game_specific_configs"][config_key][k]
                        load_config["game_specific_configs"][config_key][int(k)] = v
                return load_config
        except:
            return copy.deepcopy(self.config)

    def _get_empty_new_config(self) -> UserConfig:
        new_config = copy.deepcopy(self.config)

        assert self.config is not None, "Empty config"

        if "game_specific_configs" not in new_config:
            new_config["game_specific_configs"] = {}

        delete_keys = [
            "mining_teams",
            "looting_teams",
            "reinforcing_crabs",
            "max_reinforcement_price_tus",
            "should_reinforce",
        ]

        for del_key in delete_keys:
            if del_key in new_config:
                new_config["game_specific_configs"][del_key] = new_config[del_key]
                del new_config[del_key]

            if isinstance(new_config["game_specific_configs"][del_key], dict):
                new_config["game_specific_configs"][del_key] = {}
            if isinstance(new_config["game_specific_configs"][del_key], bool):
                new_config["game_specific_configs"][del_key] = False
            if isinstance(new_config["game_specific_configs"][del_key], int):
                new_config["game_specific_configs"][del_key] = 0
            if isinstance(new_config["game_specific_configs"][del_key], float):
                new_config["game_specific_configs"][del_key] = 0.0

        del new_config["max_gas_price_gwei"]
        new_config["max_gas_price_gwei"] = 0.0
        return new_config

    def _get_team_composition_and_mp(
        self, team: int, config: UserConfig
    ) -> T.Tuple[CrabadaClass, int]:
        self.team_composition_and_mp = {}
        self.team_composition_and_mp = self.crabada_w2.get_team_compositions_and_mp(
            config["address"]
        )
        return self.team_composition_and_mp.get(team, (["UNKNOWN"] * 3, 0))

    def _get_crab_class(self, crab: int, config: UserConfig) -> str:
        self.crab_classes = {}
        self.crab_classes = self.crabada_w2.get_crab_classes(config["address"])
        return self.crab_classes.get(crab, "UNKNOWN")

    def get_lifetime_stats(self) -> T.Dict[T.Any, T.Any]:
        return copy.deepcopy(NULL_GAME_STATS)
