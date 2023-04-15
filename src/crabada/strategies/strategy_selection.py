import typing as T

from crabada.strategies.strategy import Strategy
from crabada.strategies import looting, looting_delayed_reinforce
from crabada.strategies import (
    mining,
    mining_delayed_reinforce,
    mining_scattered_reinforce,
)
from crabada.types import MineOption

STRATEGY_SELECTION: T.Dict[str, Strategy] = {
    "PreferOtherBpCrabs": looting.PreferOtherBpCrabs,
    "PreferOwnBpCrabs": looting.PreferOwnBpCrabs,
    "LootingDelayReinforcementStrategy": looting_delayed_reinforce.LootingDelayReinforcementStrategy,
    "PreferOtherBpCrabsAndDelayReinforcement": looting_delayed_reinforce.PreferOtherBpCrabsAndDelayReinforcement,
    "PreferOwnBpCrabsAndDelayReinforcement": looting_delayed_reinforce.PreferOwnBpCrabsAndDelayReinforcement,
    "PreferOtherMpCrabs": mining.PreferOtherMpCrabs,
    "PreferOwnMpCrabs": mining.PreferOwnMpCrabs,
    "MiningDelayReinforcementStrategy": mining_delayed_reinforce.MiningDelayReinforcementStrategy,
    "PreferOtherMpCrabsAndDelayReinforcement": mining_delayed_reinforce.PreferOtherMpCrabsAndDelayReinforcement,
    "PreferOwnMpCrabsAndDelayReinforcement": mining_delayed_reinforce.PreferOwnMpCrabsAndDelayReinforcement,
    "ScatteredReinforcement": mining_scattered_reinforce.ScatteredReinforcement,
    "ScatteredDelayReinforcement": mining_scattered_reinforce.ScatteredDelayReinforcement,
}


def strategy_to_game_type(strategy: Strategy) -> MineOption:
    return (
        MineOption.LOOT
        if isinstance(strategy, looting.LootingStrategy)
        else MineOption.MINE
    )
