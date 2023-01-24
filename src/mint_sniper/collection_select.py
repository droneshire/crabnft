import typing as T

from enum import Enum
from mint_sniper.collections.ahmc import AhmcMint
from mint_sniper.collections.mechavax import MechavaxMint


class Collections(Enum):
    AHMCMINT = AhmcMint.__name__
    MECHAVAX = MechavaxMint.__name__
