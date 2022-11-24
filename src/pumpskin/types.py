import typing as T

from eth_typing import Address

ATTRIBUTE_TO_EMOJI = {
    "Facial": "\U0001F604",
    "Background": "\U0001F5BC",
    "Body": "\U0001F9CD",
    "Eyes": "\U0001F440",
    "Frame": "\U0001FA9F",
    "Head": "\U0001F383",
    "Item": "\U0001F45C",
    "Neck": "\U0001F454",
    "Overall": "\U0001F4C8",
}


class Category:
    PROFIT = "PROFIT"
    HOLD = "HOLD"
    LEVELLING = "LEVELLING"
    LP = "LP"


ALL_CATEGORIES = [Category.PROFIT, Category.HOLD, Category.LEVELLING, Category.LP]


class Tokens:
    PPIE = "PPIE"
    POTN = "POTN"


class StakedPumpskin(T.TypedDict):
    kg: int
    since_ts: int
    last_skipped_ts: int
    eaten_amount: int
    cooldown_ts: intmax


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
