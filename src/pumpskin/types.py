import typing as T

from eth_typing import Address


class StakedPumpskin(T.TypedDict):
    kg: int
    since_ts: int
    last_skipped_ts: int
    eaten_amount: int
    cooldown_ts: int
