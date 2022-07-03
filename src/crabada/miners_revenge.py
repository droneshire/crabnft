import json
import math
import typing as T

from crabada.types import CrabForLending, IdleGame
from crabada.factional_advantage import get_bp_mp_from_crab
from crabada.factional_advantage import get_faction_adjusted_battle_point
from utils import logger

BASE_CHANCE = 7.0
MP_MODIFIER = 1.25
CN_MODIFIER = 20.0
HIGH_BP_CRAB_BATTLE_POINT = 237
HIGH_BP_CRAB_MINE_POINT = 67
HIGH_MP_CRAB_BATTLE_POINT = 220
HIGH_MP_CRAB_MINE_POINT = 82


def miners_revenge(
    defense_point: int,
    attack_point: int,
    defense_mine_point: int,
    additional_crabs: T.List[CrabForLending],
    num_defense_crabs: int,
    is_looting: bool,
    verbose: bool = False,
) -> float:
    num_additional_crabs = 0

    for crab in additional_crabs:
        bp, mp = get_bp_mp_from_crab(crab)
        if is_looting:
            # looting is always after defense, so we already know their equivalent defense_point
            attack_point += bp
        else:
            defense_point += bp
            attack_point += HIGH_BP_CRAB_BATTLE_POINT
            defense_mine_point += mp
            num_additional_crabs += 1

    if verbose:
        logger.print_normal(f"MR D:{defense_point} A:{attack_point}")

    if verbose:
        logger.print_normal(f"MR defense MP {defense_mine_point}")

    revenge = BASE_CHANCE
    mine_point = defense_mine_point / (num_defense_crabs + num_additional_crabs)

    if mine_point > 56:
        revenge += MP_MODIFIER * (mine_point - 56)
    else:
        revenge += MP_MODIFIER

    if attack_point > defense_point:
        revenge += CN_MODIFIER / math.sqrt(attack_point - defense_point)
    else:
        revenge += CN_MODIFIER

    return revenge


def calc_miners_revenge(
    mine: IdleGame,
    is_looting: bool,
    additional_crabs: T.List[CrabForLending] = [],
    verbose: bool = False,
) -> float:
    defense_point = get_faction_adjusted_battle_point(mine, is_looting=False)
    attack_point = get_faction_adjusted_battle_point(mine, is_looting=True)

    defense_mine_point = 0
    key = "defense_team_info" if "defense_team_info" in mine else "defense_team_members"
    for crab in mine[key]:
        _, defense_mp = get_bp_mp_from_crab(crab)
        defense_mine_point += defense_mp

    return miners_revenge(
        defense_point,
        attack_point,
        defense_mine_point,
        additional_crabs,
        len(mine[key]),
        is_looting,
        verbose,
    )
