import json
import requests
import threading
import time
import typing as T

from utils import logger
from utils.config_types import UserConfig
from utils.user import get_alias_from_user


class HealthMonitor:
    SLEEP_TIME = 60.0 * 2.0

    def __init__(
        self,
        server_url: str,
        bot_name: str,
        users: T.List[UserConfig],
        verbose: bool = False,
    ) -> None:
        self.bot_name = bot_name
        self.users = users
        self.server_url = server_url
        self.verbose = verbose

    def update(self) -> None:
        url = self.server_url + f"/health/{self.bot_name}"

        aliases = {}
        for user in self.users:
            alias = get_alias_from_user(user, False)
            aliases[alias] = aliases.get(alias, 0) + 1

        users = []
        for user, wallets in aliases.items():
            users.append({"username": user, "wallets": wallets})

        data = {
            "name": self.bot_name,
            "num_users": len(self.users),
            "users": users,
        }

        if self.verbose:
            logger.print_normal(f"Ping from {self.bot_name}...")
            logger.print_normal(f"{json.dumps(data,indent=4)}")

        try:
            response = requests.post(
                url,
                json=json.loads(json.dumps(data)),
                headers={"accept": "application/json, text/plain, */*"},
            ).json()
        except:
            logger.print_fail(f"Failed to update {self.server_url} for {self.bot_name}")

    def run(self, daemon: bool = True) -> None:
        def loop() -> None:
            while True:
                self.update()
                time.sleep(self.SLEEP_TIME)

        if daemon:
            thread = threading.Thread(
                name=f"{self.bot_name}_health_monitor", target=loop, daemon=True
            )
            thread.start()
        else:
            loop()
