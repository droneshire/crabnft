import requests
import typing as T

from web3 import Web3
from web3.types import Wei

Tus = T.NewType("Tus", int)


def get_avax_price_usd(api_token: str) -> T.Optional[float]:
    price = 1.0
    for symbol in ["btcusd", "avaxbtc"]:
        api_url = f"https://cloud.iexapis.com/stable/crypto/{symbol}/price?token={api_token}"
        try:
            raw = requests.get(api_url, timeout=5.0).json()
            price = price * float(raw["price"])
        except:
            return None

    return price


def tus_to_wei(tus: int) -> Wei:
    """
    Convert TUS to Wei; this is required before making comparisons
    because the Crabada APIs (both Web2 and Web3) always return Wei.

    The conversion is 1 TUS = 10^18 Wei.
    """
    return Web3.toWei(tus, "ether")


def wei_to_tus(wei: Wei) -> Tus:
    """
    Convert Wei to TUS
    """
    return T.cast(Tus, Web3.fromWei(wei, "ether"))


def wei_to_tus_raw(wei: Wei) -> float:
    """
    Convert Wei to TUS in float
    """
    return T.cast(float, float(Web3.fromWei(wei, "ether")))


def wei_to_cra_raw(wei: Wei) -> float:
    """
    Convert Wei to CRA in float
    """
    return T.cast(float, float(Web3.fromWei(wei, "ether")))
