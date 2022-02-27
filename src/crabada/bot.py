import time
import typing

from crabada.types import CrabForLending, Team
from crabada.web2_api import Web2WebClient
from crabada.web3_api import Web3WebClient

from crabada.types import IdleGame

from utils.config_types import UserConfig
from crabada.crabada_web3_client import CrabadaWeb3Client

class CrabadaBot:
    AVAX_NODE_URL = "https://api.avax.network/ext/bc/C/rpc"

    def __init__(self, user : str, config : UserConfig, dry_run : bool) -> None:
        self.user = user
        self.config = config
        self.crabada_w3 = cast(CrabadaWeb3Client, (CrabadaWeb3Client()
                        .setNodeUri(self.AVAX_NODE_URL)
                        .setCredentials(config.address, config.private_key)))

    def get_user() -> str:
        return self.user

    def run(self) -> None:
        try:
            while True:
                time.sleep(5.0)
        finally:
            print(f"Exiting bot for {self.user}...")
