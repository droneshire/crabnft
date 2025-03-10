import typing as T
from enum import Enum
from eth_typing import Address
from web3.types import Wei

from utils.price import Tus

"""
Possible states for a team
"""
TeamStatus = T.Literal["MINING", "LOOTING", "AVAILABLE"]
LendingCategories = T.Literal["mine_point", "battle_point", "price"]


class CrabadaGameConfig(T.TypedDict):
    mining_teams: T.Dict[int, int]
    looting_teams: T.Dict[int, int]
    max_reinforcement_price_tus: Tus
    reinforcing_crabs: T.Dict[int, int]
    mining_strategy: str
    looting_strategy: str
    should_reinforce: bool


class MiningTeam(T.TypedDict):
    team_id: int


class MineOption:
    MINE = "MINE"
    LOOT = "LOOT"


class Faction:
    ABYSS = "ABYSS"
    FAERIE = "FAERIE"
    LUX = "LUX"
    MACHINE = "MACHINE"
    ORE = "ORE"
    TRENCH = "TRENCH"
    NO_FACTION = "NO_FACTION"


class CrabadaClass:
    SURGE = 1
    SUNKEN = 2
    PRIME = 3
    BULK = 4
    CRABOID = 5
    RUINED = 6
    GEM = 7
    ORGANIC = 8


CRABADA_ID_TO_CLASS = {
    CrabadaClass.SURGE: "SURGE",
    CrabadaClass.SUNKEN: "SUNKEN",
    CrabadaClass.PRIME: "PRIME",
    CrabadaClass.BULK: "BULK",
    CrabadaClass.CRABOID: "CRABOID",
    CrabadaClass.RUINED: "RUINED",
    CrabadaClass.GEM: "GEM",
    CrabadaClass.ORGANIC: "ORGANIC",
}


class GameProcess(T.TypedDict):
    action: T.Literal[
        "create-game",
        "attack",
        "reinforce-defence",
        "reinforce-attack",
        "settle",
    ]
    transaction_time: int


class LootAttackInfo(T.TypedDict):
    expire_time: int
    game_id: int
    signature: str
    team_id: int


class TeamMember(T.TypedDict):
    """
    Synthetic info about a team member as returned by mine endpoints
    """

    crabada_id: int
    crabada_class: CrabadaClass
    photo: str
    hp: int
    speed: int
    armor: int
    damage: int
    critical: int
    is_origin: int
    is_genesis: int
    legend_number: int


class IdleGame(T.TypedDict):
    game_id: int
    winner_team_id: int
    status: T.Literal["open", "close"]
    # Defense
    team_id: int
    owner: Address
    defense_crabada_number: T.Literal[3, 4, 5]
    defense_point: int
    defense_mine_point: int
    defense_team_members: T.List[TeamMember]
    defense_team_info: T.List[TeamMember]
    defense_team_faction: Faction
    # Attack
    attack_team_id: int
    attack_team_owner: Address
    attack_crabada_number: T.Literal[3, 4, 5]
    attack_point: int
    attack_mine_point: int
    attack_team_info: T.List[TeamMember]
    attack_team_members: T.List[TeamMember]
    attack_team_faction: Faction
    # Rewards
    tus_reward: Wei
    cra_reward: Wei
    miner_tus_reward: Wei
    looter_tus_reward: Wei
    miner_cra_reward: Wei
    looter_cra_reward: Wei
    estimate_looter_lose_cra: Wei
    estimate_looter_lose_tus: Wei
    estimate_looter_win_cra: Wei
    estimate_looter_win_tus: Wei
    estimate_miner_lose_cra: Wei
    estimate_miner_lose_tus: Wei
    estimate_miner_win_cra: Wei
    estimate_miner_win_tus: Wei
    # Time
    start_time: int
    end_time: int
    round: T.Literal[0, 1, 2, 3, 4]
    process: T.List[GameProcess]


class Team(T.TypedDict):
    team_id: int
    battle_point: int
    crabada_1_armor: int
    crabada_1_class: int
    crabada_1_critical: int
    crabada_1_damage: int
    crabada_1_hp: int
    crabada_1_is_genesis: T.Literal[0, 1]
    crabada_1_is_origin: T.Literal[0, 1]
    crabada_1_legend_number: int
    crabada_1_photo: str
    crabada_1_speed: int
    crabada_1_type: int
    crabada_2_armor: int
    crabada_2_class: int
    crabada_2_critical: int
    crabada_2_damage: int
    crabada_2_hp: int
    crabada_2_is_genesis: T.Literal[0, 1]
    crabada_2_is_origin: T.Literal[0, 1]
    crabada_2_legend_number: int
    crabada_2_photo: str
    crabada_2_speed: int
    crabada_2_type: int
    crabada_3_armor: int
    crabada_3_class: int
    crabada_3_critical: int
    crabada_3_damage: int
    crabada_3_hp: int
    crabada_3_is_genesis: T.Literal[0, 1]
    crabada_3_is_origin: T.Literal[0, 1]
    crabada_3_legend_number: int
    crabada_3_photo: str
    crabada_3_speed: int
    crabada_3_type: int
    crabada_id_1: int
    crabada_id_2: int
    crabada_id_3: int
    game_end_time: int
    game_id: int
    game_round: T.Literal[0, 1, 2, 3, 4]
    game_start_time: int
    game_type: T.Literal["mining"]
    looting_point: int
    mine_end_time: int
    mine_point: int
    mine_start_time: int
    owner: Address
    process_status: T.Literal[
        "create-game",
        "attack",
        "reinforce-defence",
        "reinforce-attack",
        "settle",
    ]
    status: TeamStatus
    time_point: int
    faction: Faction


class CrabForLending(T.TypedDict):
    crabada_id: int
    id: int  # it seems to be the same as crabada_id...
    # IMPORTANT: this is expressed as the TUS price multiplied by 10^18
    # (like Wei), which means that a value of 100000000000000000 is 1 TUS
    price: Wei
    crabada_name: str
    lender: Address
    is_being_borrowed: T.Literal[0, 1]
    borrower: Address
    game_id: int
    crabada_type: int
    crabada_class: CrabadaClass
    class_id: int
    class_name: str
    is_origin: T.Literal[0, 1]
    is_genesis: T.Literal[0, 1]
    legend_number: int
    pure_number: int
    photo: str
    hp: int
    speed: int
    damage: int
    critical: int
    armor: int
    battle_point: int
    time_point: int
    mine_point: int


class Crab(T.TypedDict):
    crabada_id: int
    id: int
    crabada_name: str
    team_id: int
    game_id: int
    crabada_status: T.Literal["GAME", "AVAILABLE", "LENDING"]
    owner: Address
    crabada_type: int
    crabada_class: CrabadaClass
    class_id: int
    class_name: str
    is_origin: int
    is_genesis: int
    legend_number: int
    pure_number: int
    photo: str
    hp: int
    damage: int
    armor: int
    speed: int
    critical: int
    battle_point: int
    time_point: int
    mine_point: int
