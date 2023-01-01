import requests
import time
import typing as T

from yaspin import yaspin

from utils import logger, proxy


@yaspin(text="Waiting...")
def wait(wait_time) -> None:
    time.sleep(wait_time)


class Web2Client:
    def __init__(
        self,
        base_url: str,
        rate_limit_delay: float = 5.0,
        use_proxy: bool = True,
        dry_run: bool = False,
    ) -> None:
        self.dry_run = dry_run
        self.base_url = base_url
        self.rate_limit_delay = rate_limit_delay

        if dry_run:
            logger.print_warn("Web2 Client in dry run mode...")

        if use_proxy:
            self.proxies = proxy.Proxies()
            self.proxies.init()
        else:
            self.proxies = None

    def _get_request(
        self,
        url: str,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
        timeout: float = 5.0,
    ) -> T.Any:
        if self.rate_limit_delay > 0.0:
            wait(self.rate_limit_delay)

        if self.proxies is not None:
            proxy = {"https": self.proxies.get_proxy()}
        else:
            proxy = None

        try:
            return requests.request(
                "GET", url, params=params, headers=headers, timeout=timeout, proxies=proxy
            ).json()
        except KeyboardInterrupt:
            raise
        except:
            return {}

    def _post_request(
        self,
        url: str,
        json_data: T.Dict[str, T.Any] = {},
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
        timeout: float = 5.0,
        delay: float = 5.0,
    ) -> T.Any:
        if self.dry_run:
            return {}

        if delay > 0.0:
            wait(delay)

        try:
            return requests.request(
                "POST", url, json=json_data, params=params, headers=headers, timeout=timeout
            ).json()
        except KeyboardInterrupt:
            raise
        except:
            return {}
