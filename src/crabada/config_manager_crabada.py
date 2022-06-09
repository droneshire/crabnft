import copy
import typing as T

from crabada.config_manager import ConfigManager
from crabada.crabada_web2_client import CrabadaWeb2Client
from crabada.types import CrabadaClass
from utils import logger
from utils.config_types import UserConfig
from utils.email import Email
from crabada.game_stats import NULL_GAME_STATS

class CrabadaConfigManager(ConfigManager):

    def __init__(self,
        user: str,
        config: UserConfig,
        send_email_accounts: T.List[Email],
        encrypt_password: str,
        dry_run: bool = False,
        verbose: bool = False
    ):
        super().__init__(user, config, send_email_accounts, encrypt_password, dry_run)
        self.crabada_w2 = CrabadaWeb2Client()
        self.team_composition_and_mp = self.crabada_w2.get_team_compositions_and_mp(
            self.config["address"]
        )
        self.crab_classes = self.crabada_w2.get_crab_classes(self.config["address"])

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
