import logging
import os
import typing as T

from crabada.game_stats import CrabadaLifetimeGameStatsLogger
from utils.game_stats import LifetimeGameStatsLogger
from utils import logger
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.chro_web3_client import ChroWeb3Client
from web3_utils.swimmer_network_web3_client import SwimmerNetworkClient
from web3_utils.tus_swimmer_web3_client import TusSwimmerWeb3Client
from web3_utils.web3_client import Web3Client
from wyndblast.game_stats import WyndblastLifetimeGameStatsLogger


class GameCollection:
    TOKEN: T.Optional[str] = None
    GAME: T.Optional[str] = None
    DISCORD: T.Optional[str] = None

    def __init__(
        self,
        user: str,
        config: T.Dict[str, T.Any],
        min_amount_to_transfer: int,
    ) -> None:
        self.stats_logger: LifetimeGameStatsLogger = None
        self.client: Web3Client = None
        self.min_amount_to_transfer: int = min_amount_to_transfer
        self.commission: float = None
        self.explorer_url: str = ""
        self.lifetime_stats_file: str = os.path.join(
            logger.get_logging_dir(self.GAME.lower()), "stats", "commission_lifetime_bot_stats.json"
        )
        logger.print_ok_arrow(f"Using {self} token for collections")

    def __repr__(self) -> str:
        return self.TOKEN

    def __str__(self) -> str:
        return self.TOKEN


class Crabada(GameCollection):
    TOKEN = "TUS"
    GAME = "Crabada"
    DISCORD = "CRABADA_UPDATES"

    def __init__(
        self, user: str, config: T.Dict[str, T.Any], log_dir: str, dry_run: bool = False
    ) -> None:
        super().__init__(user, config, 15)

        self.stats_logger = CrabadaLifetimeGameStatsLogger(user, log_dir, {})
        print(log_dir, self.stats_logger.get_game_stats())
        self.commission = self.stats_logger.get_game_stats()["commission_tus"]
        self.client = token_client = T.cast(
            TusSwimmerWeb3Client,
            (
                TusSwimmerWeb3Client()
                .set_credentials(config["address"], config["private_key"])
                .set_node_uri(SwimmerNetworkClient.NODE_URL)
                .set_dry_run(dry_run)
            ),
        )
        self.explorer_url = "https://explorer.swimmer.network/tx"


class Wyndblast(GameCollection):
    TOKEN = "CHRO"
    GAME = "Wyndblast"
    DISCORD = "WYNDBLAST_UPDATES"

    def __init__(
        self, user: str, config: T.Dict[str, T.Any], log_dir: str, dry_run: bool = False
    ) -> None:
        super().__init__(user, config, 50)

        self.stats_logger = WyndblastLifetimeGameStatsLogger(user, log_dir, {})
        self.commission = self.stats_logger.get_game_stats()["commission_chro"]
        self.client = T.cast(
            ChroWeb3Client,
            (
                ChroWeb3Client()
                .set_credentials(config["address"], config["private_key"])
                .set_node_uri(AvalancheCWeb3Client.NODE_URL)
                .set_dry_run(dry_run)
            ),
        )
        self.explorer_url = "https://snowtrace.io/tx"


COMMISSION_GAMES: T.Dict[str, GameCollection] = {
    "CRABADA": Crabada,
    "WYNDBLAST": Wyndblast,
}
