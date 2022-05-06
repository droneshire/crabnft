import re
import requests
import typing as T

from coinmarketcapapi import CoinMarketCapAPI, CoinMarketCapAPIError

from web3 import Web3
from web3.types import Wei

from utils import logger

Tus = T.NewType("Tus", int)
Cra = T.NewType("Cra", int)
Avax = T.NewType("Avax", int)

DEFAULT_GAS_USED = 0.2

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

    def cra_to_tus(self, cra: float) -> float:
        try:
            tus_per_cra = self.cra_usd / self.tus_usd
            return tus_per_cra * cra
        except:
            return 0.0

    def avax_to_tus(self, avax: float) -> float:
        try:
            tus_per_avax = self.avax_usd / self.tus_usd
            return tus_per_avax * avax
        except:
            return 0.0


def get_avax_price_usd(api_token: str, dry_run: bool = False) -> T.Optional[float]:
    if dry_run:
        return 1.0

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


def get_token_price_usd(api_token: str, symbol: str, dry_run: bool = False) -> T.Optional[float]:
    if dry_run:
        return 1.0
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


def is_gas_too_high(gas_price_gwei: float, max_price_gwei: float, margin: int = 0) -> bool:
    gas_price_limit = max_price_gwei + margin
    if gas_price_gwei is not None and (int(gas_price_gwei) > int(gas_price_limit)):
        logger.print_warn(f"Warning: High Gas ({gas_price_gwei}) > {gas_price_limit}!")
        return True
    return False
