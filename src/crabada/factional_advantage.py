import math
import typing as T
from discord import Color

from crabada.types import Faction, IdleGame, Team, TeamMember
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

FACTION_ICON_URLS = {
    Faction.ABYSS: "https://drive.google.com/uc?export=view&id=1TaRYPXPjSbJvY83Z__05U8sb9nY6y76O",
    Faction.FAERIE: "https://drive.google.com/uc?export=view&id=1g-dKGur0Dt6XvVNKLneTSL9hTI7iCL6e",
    Faction.LUX: "https://drive.google.com/uc?export=view&id=1L192vnT4hbwlgFxr0HIF9D22RuBNimpz",
    Faction.MACHINE: "https://drive.google.com/uc?export=view&id=1YhA-O86EkI1U0xACx33nk2N4qBxL44hs",
    Faction.ORE: "https://drive.google.com/uc?export=view&id=1SLraoFKLPT8s1vJhcDo5wm2_3umhwfdi",
    Faction.TRENCH: "https://drive.google.com/uc?export=view&id=1cr23fk1onoHw4o63fziB2Djucijfdo7E",
    Faction.NO_FACTION: "https://drive.google.com/uc?export=view&id=17kJOWyAWyK0FVEfVaR8PN-FyS-qgAGkf",
}


FACTION_COLORS = {
    Faction.ABYSS: Color.purple(),
    Faction.FAERIE: Color.green(),
    Faction.LUX: Color.gold(),
    Faction.MACHINE: Color.blue(),
    Faction.ORE: Color.red(),
    Faction.TRENCH: Color.teal(),
    Faction.NO_FACTION: Color.light_grey(),
}


def get_bp_mp_from_mine(
    mine: IdleGame, is_looting: bool = False, verbose: bool = False
) -> T.Tuple[int, int]:
    if is_looting:
        battle_point = get_faction_adjusted_battle_point(mine, is_looting=True)
    else:
        battle_point = get_faction_adjusted_battle_point(mine, is_looting=False)

    mine_point = 0

    if is_looting:
        key = "attack_team_info" if "attack_team_info" in mine else "attack_team_members"
    else:
        key = "defense_team_info" if "defense_team_info" in mine else "defense_team_members"

    for crab in mine[key]:
        _, mp = get_bp_mp_from_crab(crab)
        mine_point += mp

    if verbose:
        logger.print_normal(
            f"{'Loot' if is_looting else 'Mine'} BP: {battle_point} MP: {mine_point} "
        )

    return battle_point, mine_point


def get_bp_mp_from_crab(crab: TeamMember) -> T.Tuple[int, int]:
    battle_point = crab["hp"] + crab["damage"] + crab["armor"]
    mine_point = crab["speed"] + crab["critical"]
    return battle_point, mine_point


def get_bp_mp_from_team(team: Team) -> T.Tuple[int, int]:
    battle_point = 0
    mine_point = 0
    for i in range(1, 4):
        battle_point += (
            team[f"crabada_{i}_hp"] + team[f"crabada_{i}_damage"] + team[f"crabada_{i}_armor"]
        )
        mine_point += team[f"crabada_{i}_speed"] + team[f"crabada_{i}_critical"]
    return battle_point, mine_point


def get_attack_faction(game: IdleGame) -> Faction:
    return T.cast(Faction, game.get("attack_team_faction", ""))


def get_defense_faction(game: IdleGame) -> Faction:
    return T.cast(Faction, game.get("defense_team_faction", ""))


def get_faction_adjusted_battle_points_from_teams(
    loot_team: Team, mine_team: Team, verbose: bool = False
) -> (int, int):
    mine_faction = mine_team["faction"]
    loot_faction = loot_team["faction"]

    mine_point = mine_team["battle_point"]
    if mine_faction == Faction.NO_FACTION:
        mine_point = int(math.floor(mine_point * NEUTRAL_ADVANTAGE_MULT))
    elif mine_faction in FACTIONAL_ADVANTAGE.get(loot_faction, []):
        mine_points = int(math.floor(mine_point * FACTIONAL_ADVANTAGE_MULT))

    loot_point = loot_team["battle_point"]
    if loot_faction == Faction.NO_FACTION:
        loot_point = int(math.floor(loot_point * NEUTRAL_ADVANTAGE_MULT))
    elif loot_faction in FACTIONAL_ADVANTAGE.get(mine_faction, []):
        loot_point = int(math.floor(loot_point * FACTIONAL_ADVANTAGE_MULT))

    return loot_point, mine_point


def get_faction_adjusted_battle_point(
    game: IdleGame, is_looting: bool = False, verbose: bool = False
) -> int:
    team_points = 0

    if is_looting:
        # we're looting, so get attack_point
        if verbose:
            logger.print_normal("Getting attack point")
        for crab in game["attack_team_members"]:
            bp, _ = get_bp_mp_from_crab(crab)
            team_points += bp
        total_points = game["attack_point"]
        their_faction = get_defense_faction(game)
        our_faction = get_attack_faction(game)
    else:
        # we're mining, get defense_point
        if verbose:
            logger.print_normal("Getting defense point")
        for crab in game["defense_team_members"]:
            bp, _ = get_bp_mp_from_crab(crab)
            team_points += bp
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
