import typing as T

from eth_typing import Address

class DailyActivity(T.TypedDict):
    idle: int
    active: int
    completed_stage_1: int
    completed_stage_2: int
    completed_stage_3: int
    needs_to_buy_ticket: int

class Game(T.TypedDict):
    daily_activity: DailyActivity
    breeding: int
    training: int
    forging: int
    pvp: int
    pve: int

CountNftStatus = T.TypedDict(
    {
        "all": int,
        "unassigned": int,
        "marketplace": int,
        "staking": int,
        "assigned": int,
        "game": Game,
    }
)

class WyndNftStatus(T.TypedDict):
    owner_address: Address
    datetime: str
    count_nfts: CountNftStatus
