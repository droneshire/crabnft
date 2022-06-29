import typing as T

from eth_typing import Address


class Faction:
    VICIMA = "Vicima"
    PERLIA = "Perlia"
    YSIA = "Ysia"


#####
# Individual nft information
WyndNft = T.TypedDict(
    "WyndNft",
    {
        "token_id": str,
        "product_id": str,
        "faction": Faction,
        "class": str,
        "element": str,
        "rarity": int,
        "group": T.Literal["rider", "wynd"],
        "owner": Address,
        "image": str,
        "operator_holding_type": str,
        "operator_holding_name": str,
        "isSubmitted": bool,
    },
)

#####
# For nft status
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
    "CountNftStatus",
    {
        "all": int,
        "unassigned": int,
        "marketplace": int,
        "staking": int,
        "assigned": int,
        "game": Game,
    },
)


class AccountOverview(T.TypedDict):
    owner_address: Address
    datetime: str
    count_nfts: CountNftStatus


#####
# For activity choice
class ActivitySelection(T.TypedDict):
    product_ids: T.List[str]
    faction: str
    stage: int
    variation: str
    element_requirement: str
    class_requirement: str


#####
# For activity options
class Variation(T.TypedDict):
    name: str
    class_requirement: str
    element_requirement: str
    success_rate: str


class Action(T.TypedDict):
    level: int
    name: str
    action_text: str
    variations: T.Dict[str, Variation]
    base_success_rate: str


class SelectionDetail(T.TypedDict):
    Ysia: T.List[Action]
    Perlia: T.List[Action]
    Vicima: T.List[Action]


class DailyActivitySelection(T.TypedDict):
    product_ids: T.List[str]
    to_select: str
    stage_level: int
    selection_detail: SelectionDetail


#####
# Activity result
class ElementalStones(T.TypedDict):
    Fire: float
    Wind: float
    Earth: float
    Light: float
    Darkness: float
    Water: float
    elemental_stones_qty: float


class Rewards(T.TypedDict):
    chro: int
    wams: int
    elemental_stones: ElementalStones


class Stage(T.TypedDict):
    level: int
    variation: T.Dict[str, str]
    success: bool
    rewards: Rewards


class ActivityResult(T.TypedDict):
    index: int
    round_index: int
    faction: str
    activity_datetime: str
    stage: Stage
    product_id: str


#####
## Wynd status
ProductMetadata = T.TypedDict(
    "ProductMetadata",
    {
        "class": str,
        "element": str,
        "faction": str,
        "image_url": str,
        "rarity": int,
    },
)


class Stage(T.TypedDict):
    level: int
    rewards: Rewards
    success: bool
    variation: T.Dict[str, str]


class Activity(T.TypedDict):
    activity_datetime: str
    faction: str
    index: int
    product_id: str
    round_index: int
    stage: Stage


class DayLog(T.TypedDict):
    activities: T.List[Activity]
    product_id: str


WyndStatus = T.TypedDict(
    "WyndStatus",
    {
        "product_id": str,
        "type": str,
        "days": T.List[DayLog],
        "product_id": str,
        "product_metadata": ProductMetadata,
    },
)
