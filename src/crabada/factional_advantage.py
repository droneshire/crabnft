import math
import typing as T

from crabada.types import Faction, IdleGame, Team
from utils import logger

FACTIONAL_ADVANTAGE_MULT = 0.93
NEUTRAL_ADVANTAGE_MULT = 0.97

FACTIONAL_ADVANTAGE = {
    Faction.ABYSS: [Faction.TRENCH, Faction.MACHINE],
    Faction.FAERIE: [Faction.ABYSS, Faction.ORE],
    Faction.LUX: [Faction.ORE, Faction.FAERIE],
    Faction.MACHINE: [Faction.FAERIE, Faction.LUX],
    Faction.ORE: [Faction.ABYSS, Faction.TRENCH],
    Faction.TRENCH: [Faction.LUX, Faction.MACHINE],
}


def get_faction_adjusted_battle_point(team: Team, game: IdleGame) -> int:
    team_defense_point = team["battle_point"]
    defense_point = game["defense_point"]
    reinforce_point = defense_point - team_defense_point

    attack_faction = T.cast(Faction, game["attack_team_faction"])
    defense_faction = T.cast(Faction, game["defense_team_faction"])

    logger.print_normal(
        f"Mine[{game['game_id']}]: Attack from {attack_faction} -> {defense_faction}"
    )
    if defense_faction in FACTIONAL_ADVANTAGE[attack_faction]:
        logger.print_normal(
            f"Mine[{game['game_id']}]: Battle point decrease of {(1 - FACTIONAL_ADVANTAGE_MULT) * 100.0}"
        )
        return int(math.ceil(team_defense_point * FACTIONAL_ADVANTAGE_MULT)) + reinforce_point

    if defense_faction == Faction.NO_FACTION:
        logger.print_ok_arrow(
            f"Mine[{game['game_id']}]: Battle point decrease of {(1 - NEUTRAL_ADVANTAGE_MULT)* 100.0}"
        )
        return int(math.ceil(team_defense_point * NEUTRAL_ADVANTAGE_MULT)) + reinforce_point

    return defense_point
