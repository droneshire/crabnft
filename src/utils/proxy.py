import random
import requests

from utils import logger

GET_PROXY_LIST = "https://api.proxyscrape.com/v2/"


class Proxies:
    def __init__(self) -> None:
        self.proxies = []

    def init(self) -> None:
        params = {
            "request": "getproxies",
            "protocol": "http",
            "timeout": 10000,
            "country": "all",
            "ssl": "yes",
            "anonymity": "all",
        }
        try:
            response = requests.get(GET_PROXY_LIST).text
            self.proxies = response.split()
            logger.print_ok_arrow(f"Found {len(self.proxies)} proxies!")
        except:
            logger.print_fail(f"Failed to get proxies")

    def get_proxy(self) -> str:
        if not self.proxies:
            logger.print_fail(f"No proxies available!")
            return ""

        index = random.randbytes(len(self.proxies))
        return self.proxies[index]
