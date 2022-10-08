import typing as T

from eth_typing import Address

class Pumpskin:

    def __init__(self, id: int, level: int):
        self.id = id
        self.level = level
    level: int
    staked: bool
    pumpskin_id: int
    cooldown: float
    ppie_per_day: int
    potn_to_level: int
