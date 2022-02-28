import typing as T
from eth_typing import Address

from utils.price import Tus


class MiningTeam(T.TypedDict):
    team_id: int


class SmsConfig(T.TypedDict):
    account_sid: str
    account_auth_token: str
    from_sms_number: str
    admin_sms_number: str


class UserConfig(T.TypedDict):
    private_key: str
    address: Address
    mining_teams: T.List[MiningTeam]
    max_gas_price: float
    max_reinforcement_price_tus: Tus
    max_reinforce_bp_delta: int
    commission_percent_per_mine: float
    sms_number: str
    get_sms_updates: bool
