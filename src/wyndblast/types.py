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


class Countdown(T.TypedDict):
    daily_countdown_second: int
    weekly_countdown_second: int
    daily_reset_at: str
    weekly_reset_at: str


QuestRewards = T.TypedDict("QuestRewards", {"type": str, "amount": int})


class LevelQuests(T.TypedDict):
    description: str
    rewards: T.List[QuestRewards]
    is_completed: bool
    quest_id: str
    category: str


class PveStages(T.TypedDict):
    unlocked: T.List[str]
    completed: T.List[str]


PveRewardMetadata = T.TypedDict(
    "PveRewardMetadata",
    {
        "type": str,
        "quest_description": str,
        "quest_category": str,
        "quest_id": str,
        "stage_id": str,
    },
)

PveReward = T.TypedDict(
    "PveReward",
    {
        "event": str,
        "obtained_at": int,
        "metadata": PveRewardMetadata,
        "id": str,
        "currency": str,
        "category": str,
        "user_id": str,
        "claimed_at": int,
        "amount": int,
        "is_claimed": bool,
    },
)


class PveRewards(T.TypedDict):
    user_id: str
    total: int
    claimable: int
    claimed: int
    rewards: T.List[PveReward]


class PveUser(T.TypedDict):
    username: str
    wallet_address: str
    user_id: str
    level: int
    exp: int
    level_up_exp: int
    max_stamina: int
    max_unit_cost: int
    max_unit_slot: int
    stamina: int
    opening_scene: bool


PveWyndDna = T.TypedDict(
    "PveWyndDna",
    {
        "head": str,
        "tail": str,
        "hind_legs": str,
        "all": str,
        "crest": str,
        "fore_legs": str,
        "saddle": str,
        "wings": str,
        "body": str,
    },
)


PveRiderDna = T.TypedDict(
    "PveRiderDna",
    {
        "body_armor": str,
        "top": str,
        "upper_arm_armor": str,
        "all": str,
        "lower_arm_armor": str,
        "nose": str,
        "mouth": str,
        "body": str,
        "eyes": str,
    },
)


class PveItemStats(T.TypedDict):
    health: float
    mana: float
    health_regen: float
    mana_regen: float
    armor: float
    magic_resist: float
    attack_damage: float
    magic_damage: float
    move_speed: float
    attack_range: float
    attack_speed: float
    critical_damage: float
    critical_chance: float
    level: float
    exp: float
    level_up_exp: float


PveSkills = T.TypedDict(
    "PveSkills",
    {
        "id": str,
        "name": str,
        "owner": str,
        "class": str,
        "type": str,
        "cost": int,
        "stack_cost": int,
        "description": str,
        "code": str,
        "pseudo_code": str,
        "_category": str,
        "_action": str,
        "_status": str,
        "_condition": str,
        "part": str,
        "availability": str,
    },
)

PveWyndMetadata = T.TypedDict(
    "PveMetadata",
    {
        "class": str,
        "element": str,
        "type": str,
        "part_ids": str,
        "dna": PveWyndDna,
        "generation": int,
        "image_url": str,
        "breed_count": int,
        "extension_code": str,
        "rarity": int,
        "faction": str,
        "cost": int,
        "stats": PveItemStats,
        "skills": T.List[PveSkills],
    },
)

PveRiderMetadata = T.TypedDict(
    "PveRiderMetadata",
    {
        "class": str,
        "element": str,
        "type": str,
        "part_ids": str,
        "dna": PveRiderDna,
        "generation": int,
        "image_url": str,
        "breed_count": int,
        "extension_code": str,
        "rarity": int,
        "faction": str,
        "cost": int,
        "stats": PveItemStats,
        "skills": T.List[PveSkills],
    },
)


class PveWynd(T.TypedDict):
    holder_place_name: str
    owner_address: Address
    wallet_address: Address
    metadata: PveWyndMetadata
    product_id: Address
    holder_place: int
    cooldown_time: int


class PveRider(T.TypedDict):
    holder_place_name: str
    owner_address: Address
    wallet_address: Address
    metadata: PveRiderMetadata
    product_id: Address
    holder_place: int
    cooldown_time: int


class PveNfts(T.TypedDict):
    wynd: T.List[PveWynd]
    rider: T.List[PveRider]
    equipement: T.List[T.Any]


class WyndLevelUpResponse(T.TypedDict):
    is_level_up: bool
    stats: PveItemStats


class BattleUnit(T.TypedDict):
    equipment_dna: str
    rider_dna: str
    wynd_dna: str


class BattleSetup(T.TypedDict):
    enemy: T.List[BattleUnit]
    player: T.List[BattleUnit]


class BattlePayload(T.TypedDict):
    duration: int
    lobby_id: str
    result: str
    setup: BattleSetup
    stage_id: str
    survived: BattleSetup


class ClaimQuests(T.TypedDict):
    user: PveUser
    is_level_up: bool
    exp: int


class Unit(T.TypedDict):
    equipment_product_id: str
    rider_product_id: str
    wynd_product_id: str


class UnitPreset(T.TypedDict):
    unit: Unit
    name: str


class Positions(T.TypedDict):
    x: float
    y: float


class Units(T.TypedDict):
    equipment_product_id: str
    position: Positions
    rider_product_id: str
    wynd_product_id: str


class TeamPreset(T.TypedDict):
    units: Units
    name: str
