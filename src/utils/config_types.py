import typing as T
from eth_typing import Address

from utils.price import Tus
from crabada.strategies.strategy import Strategy
from crabada.types import CrabForLending


class MiningTeam(T.TypedDict):
    team_id: int


class SmsConfig(T.TypedDict):
    account_sid: str
    account_auth_token: str
    from_sms_number: str
    admin_sms_number: str
    enable_admin_sms: bool


class UserConfig(T.TypedDict):
    private_key: str
    address: Address
    mining_teams: T.List[MiningTeam]
    looting_teams: T.List[MiningTeam]
    max_gas_price: int
    max_gas_price_gwei: int
    max_reinforcement_price_tus: Tus
    max_reinforce_bp_delta: int
    reinforcing_crabs: T.List[CrabForLending]
    mining_reinforcement_strategy: Strategy
    looting_reinforcement_strategy: Strategy
    commission_percent_per_mine: float
    sms_number: str
    email: str
    get_sms_updates: bool
    get_email_updates: bool
    should_reinforce: bool
