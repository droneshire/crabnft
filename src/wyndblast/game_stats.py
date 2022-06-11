import typing as T

from wyndblast import types


class DailyActivityLifetimeStats(T.TypedDict):
    chro: float
    wams: float
    elemental_stones: T.List[str]
    wins: int
    losses: int
    win_percentage: float


NULL_GAME_STATS = {
    "chro": 0.0,
    "wams": 0.0,
    "elemental_stones": [],
    "wins": 0,
    "losses": 0,
    "win_percentage": 0.0,
}
