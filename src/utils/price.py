import re
import requests
import typing as T

from coinmarketcapapi import CoinMarketCapAPI, CoinMarketCapAPIError

from web3 import Web3
from web3.types import Wei

Tus = T.NewType("Tus", int)
Cra = T.NewType("Cra", int)


class Prices:
    def __init__(self, avax_usd, tus_usd, cra_usd):
        self.avax_usd = avax_usd
        self.tus_usd = tus_usd
        self.cra_usd = cra_usd

    def update(self, avax_usd, tus_usd, cra_usd):
        if avax_usd is not None:
            self.avax_usd = avax_usd
        if tus_usd is not None:
            self.tus_usd = tus_usd
        if cra_usd is not None:
            self.cra_usd = cra_usd

    def cra_to_tus(self, cra: Cra) -> float:
        try:
            tus_per_cra = self.cra_usd / self.tus_usd
            return tus_per_cra * cra
        except:
            return 0.0


def get_avax_price_usd(api_token: str) -> T.Optional[float]:
    price = 1.0
    for symbol in ["btcusd", "avaxbtc"]:
        api_url = f"https://cloud.iexapis.com/stable/crypto/{symbol}/price?token={api_token}"
        try:
            raw = requests.get(api_url, timeout=5.0).json()
            price = price * float(raw["price"])
        except KeyboardInterrupt:
            raise
        except:
            return None

    return price


def get_token_price_usd(api_token: str, symbol: str) -> T.Optional[float]:
    try:
        data = CoinMarketCapAPI(api_key=api_token).cryptocurrency_info(symbol=symbol).data
        description = data[symbol]["description"]
        match = re.search(r"\d+\.\d+\s+USD", description)
        if match:
            return float(match.group().split()[0])
    except:
        pass
    return None


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


def cra_to_wei(cra: int) -> Wei:
    """
    Convert CRA to Wei; this is required before making comparisons
    because the Crabada APIs (both Web2 and Web3) always return Wei.

    The conversion is 1 CRA = 10^18 Wei.
    """
    return Web3.toWei(cra, "ether")


def wei_to_cra(wei: Wei) -> Tus:
    """
    Convert Wei to CRA
    """
    return T.cast(Cra, Web3.fromWei(wei, "ether"))


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
