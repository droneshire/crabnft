import typing as T

class MiningTeam(T.TypedDict):
    team_id : int


class UserConfig(T.TypedDict):
    private_key : str
    address : str
    mining_teams : T.List[MiningTeam]
    max_gas_price : float
    max_reinforcement_price_tus : float
    
