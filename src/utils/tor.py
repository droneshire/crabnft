import requests

from stem import Signal
from stem.control import Controller


def renew_connection(password: str):
    # signal TOR for a new connection
    with Controller.from_port(port=9051) as controller:
        controller.authenticate(password=password)
        controller.signal(Signal.NEWNYM)


def get_tor_session() -> requests.Session:
    session = requests.Session()
    session.proxies = {
        "http": "socks5://127.0.0.1:9050",
        "https": "socks5://127.0.0.1:9050",
    }
    return session
