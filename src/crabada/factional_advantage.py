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
    Faction.NO_FACTION: [],
}


def get_attack_faction(game: IdleGame) -> Faction:
    return T.cast(Faction, game.get("attack_team_faction", ""))


def get_defense_faction(game: IdleGame) -> Faction:
    return T.cast(Faction, game.get("defense_team_faction", ""))


def get_faction_adjusted_battle_point(team: Team, game: IdleGame, verbose: bool = False) -> int:
    team_points = team["battle_point"]

    if game["attack_team_id"] == team["team_id"]:
        # we're looting, so get attack_point
        if verbose:
            logger.print_normal("Getting attack point")
        total_points = game["attack_point"]
        their_faction = get_defense_faction(game)
        our_faction = get_attack_faction(game)
    else:
        # we're mining, get defense_point
        if verbose:
            logger.print_normal("Getting defense point")
        total_points = game["defense_point"]
        their_faction = get_attack_faction(game)
        our_faction = get_defense_faction(game)

    reinforce_points = total_points - team_points

    if verbose:
        logger.print_normal(f"Game[{game['game_id']}]: Theirs: {their_faction} Ours: {our_faction}")

    if our_faction in FACTIONAL_ADVANTAGE.get(their_faction, []):
        if verbose:
            logger.print_ok_blue_arrow(
                f"Game[{game['game_id']}]: Battle point decrease of {(1 - FACTIONAL_ADVANTAGE_MULT) * 100.0:.2f}%"
            )
        return int(math.floor(team_points * FACTIONAL_ADVANTAGE_MULT)) + reinforce_points

    if our_faction == Faction.NO_FACTION:
        if verbose:
            logger.print_ok_blue_arrow(
                f"Game[{game['game_id']}]: Battle point decrease of {(1 - NEUTRAL_ADVANTAGE_MULT)* 100.0:.2f}%"
            )
        return int(math.floor(team_points * NEUTRAL_ADVANTAGE_MULT)) + reinforce_points

    return total_points
