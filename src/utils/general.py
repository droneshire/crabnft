import typing as T


def get_pretty_seconds(s: int) -> str:
    """Given an amount of seconds, return a formatted string with
    hours, minutes and seconds; taken from
    https://stackoverflow.com/a/775075/2972183"""
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:d}h:{m:02d}m:{s:02d}s"


def first_or_none(l: T.List[T.Any]) -> T.Any:
    """Return the first element of a list or None
    if 1) it is not set or 2) it is falsey"""
    try:
        return l[0]
    except:
        return None


def second_or_none(l: T.List[T.Any]) -> T.Any:
    """Return the second element of a list or None
    if 1) it is not set or 2) it is falsey"""
    try:
        return l[1]
    except:
        return None


def third_or_none(l: T.List[T.Any]) -> T.Any:
    """Return the third element of a list or None
    if 1) it is not set or 2) it is falsey"""
    try:
        return l[2]
    except:
        return None


def n_or_better_or_none(n: int, l: T.List[T.Any]) -> T.Any:
    """Return the nth element of a list or lower otherwise None"""
    for i in range(n, 0, -1):
        if len(l) >= i:
            return l[i - 1]
    return None


def fourth_or_none(l: T.List[T.Any]) -> T.Any:
    """Return the fourth element of a list or None
    if 1) it is not set or 2) it is falsey"""
    try:
        return l[3]
    except:
        return None


def find_in_list(l: T.List[T.Dict[str, T.Any]], k: str, v: T.Any) -> T.Any:
    """
    Search a list of dictionaries for a specific one
    """
    return first_or_none([i for i in l if i[k] == v])
