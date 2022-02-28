import typing as T
from eth_typing import Address

from utils.price import Tus


class MiningTeam(T.TypedDict):
    team_id: int


class UserConfig(T.TypedDict):
    private_key: str
    address: Address
    mining_teams: T.List[MiningTeam]
    max_gas_price: float
    max_reinforcement_price_tus: Tus
    max_reinforce_bp_delta: int
