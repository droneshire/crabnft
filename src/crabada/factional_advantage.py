import math
import typing as T

from crabada.types import Faction, IdleGame, Team

FACTIONAL_ADVANTAGE_MULT = 0.93
NEUTRAL_ADVANTAGE_MULT = 0.97

FACTIONAL_ADVANTAGE = {
    Faction.ABYSS : [Faction.TRENCH, Faction.MACHINE],
    Faction.FAERIES : [Faction.ABYSS, Faction.ORE],
    Faction.LUX : [Faction.ORE, Faction.FAERIES],
    Faction.MACHINE : [Faction.FAERIES, Faction.LUX],
    Faction.ORE : [Faction.ABYSS, Faction.TRENCH],
    Faction.TRENCH : [Faction.LUX, Faction.MACHINE],
}


def get_faction_adjusted_battle_point(team: Team, game: IdleGame) -> int:
    team_defense_point = team["battle_point"]
    defense_point = game["defense_point"]
    reinforce_point = defense_point - team_defense_point

    attack_faction = T.cast(Faction, game["attack_team_faction"])
    defense_faction = T.cast(Faction, game["defense_team_faction"])

    if defense_faction in FACTIONAL_ADVANTAGE[attack_faction]:
        print("factional advantage found")
        return int(math.ceil(team_defense_point * FACTIONAL_ADVANTAGE_MULT)) + reinforce_point

    if defense_faction == Faction.NO_FACTION:
        print("neutral advantage found")
        return int(math.ceil(team_defense_point * NEUTRAL_ADVANTAGE_MULT)) + reinforce_point

    return defense_point
