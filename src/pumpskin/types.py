import typing as T

from eth_typing import Address


class StakedPumpskin(T.TypedDict):
    kg: int
    since_ts: int
    last_skipped_ts: int
    eaten_amount: int
    cooldown_ts: int


class Pumpskin(T.TypedDict):
    name: str
    description: str
    image: str
    attributes: T.List[T.Dict[str, str]]
    dna: str
    edition: int


class Rarity(T.TypedDict):
    Background: float
    Frame: float
    Body: float
    Neck: float
    Eyes: float
    Head: float
    Facial: float
    Item: float
