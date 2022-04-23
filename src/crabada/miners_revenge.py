import json
import math
import typing as T

from crabada.types import IdleGame
from crabada.factional_advantage import get_bp_mp_from_crab
from crabada.factional_advantage import get_faction_adjusted_battle_point
from utils import logger

BASE_CHANCE = 7.0
MP_MODIFIER = 1.25
CN_MODIFIER = 20.0


def calc_miners_revenge(mine: IdleGame, verbose: bool = False) -> float:
    defense_point = get_faction_adjusted_battle_point(mine, is_looting=False)
    attack_point = get_faction_adjusted_battle_point(mine, is_looting=True)

    if verbose:
        logger.print_normal(f"MR: D:{defense_point} A:{attack_point}")

    defense_mine_point = 0
    attack_mine_point = 0

    key = "defense_team_info" if "defense_team_info" in mine else "defense_team_members"
    for crab in mine[key]:
        _, defense_mp = get_bp_mp_from_crab(crab)
        defense_mine_point += defense_mp

    if verbose:
        logger.print_normal(f"MR: defense MP {defense_mine_point}")

    revenge = BASE_CHANCE
    mine_point = defense_mine_point / len(mine[key])

    if mine_point > 56:
        revenge += MP_MODIFIER * (mine_point - 56)
    else:
        revenge += MP_MODIFIER

    if attack_point > defense_point:
        revenge += CN_MODIFIER / math.sqrt(attack_point - defense_point)
    else:
        revenge += CN_MODIFIER

    return revenge
