import typing as T
from eth_typing import Address


class SmsConfig(T.TypedDict):
    account_sid: str
    account_auth_token: str
    from_sms_number: str
    admin_sms_number: str
    enable_admin_sms: bool


class UserConfig(T.TypedDict):
    group: int
    game: str
    private_key: str
    address: Address
    game_specific_configs: T.Dict[T.Any, T.Any]
    max_gas_price_gwei: int
    commission_percent_per_mine: T.Dict[Address, float]
    sms_number: str
    email: str
    get_sms_updates: bool
    get_sms_updates_loots: bool
    get_sms_updates_alerts: bool
    get_email_updates: bool
