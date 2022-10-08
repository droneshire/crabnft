import typing as T


def calc_potn_from_level(level: int) -> int:
    return 25 if level <= 1 else 25 + 50 * level + 25 * level**2


def calc_cooldown_from_level(level: int) -> int:
    return level + 1


def calc_ppie_per_day_from_level(level: int) -> int:
    return level + 3
