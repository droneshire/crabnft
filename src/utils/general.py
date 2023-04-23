import typing as T

TIMESTAMP_FORMAT = "%m/%d/%Y %H:%M:%S"


def dict_sum(d: T.Dict[T.Any, T.Any]) -> float:
    sum = 0.0
    for _, v in d.items():
        if isinstance(v, T.Dict):
            sum += dict_sum(v)
        else:
            sum += v
    return sum


def dict_keys_snake_to_camel(d: T.Dict[T.Any, T.Any]) -> T.Dict[T.Any, T.Any]:
    if not isinstance(d, dict):
        return {}

    new = {}
    for k, v in d.items():
        if isinstance(k, str):
            if len(k) > 1:
                split_k = k.split("_")
                k = split_k[0] + "".join(s.title() for s in split_k[1:])
            else:
                k = k.lower()

        if isinstance(v, T.Dict):
            new[k] = dict_keys_snake_to_camel(v)
        else:
            new[k] = v
    return new


def dict_keys_camel_to_snake(d: T.Dict[T.Any, T.Any]) -> T.Dict[T.Any, T.Any]:
    if not isinstance(d, dict):
        return {}

    new = {}
    for k, v in d.items():
        if isinstance(k, str):
            snake = inflection.underscore(k)
            if snake != k.lower():
                k = snake

        if isinstance(v, T.Dict):
            new[k] = dict_keys_camel_to_snake(v)
        else:
            new[k] = v
    return new


def get_pretty_seconds(s: int, use_days: bool = False) -> str:
    """Given an amount of seconds, return a formatted string with
    hours, minutes and seconds; taken from
    https://stackoverflow.com/a/775075/2972183"""
    s = int(s)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if use_days:
        d, h = divmod(h, 24)
        string = f"{d:d}d:{h:d}h:{m:02d}m:{s:02d}s"
    else:
        string = f"{h:d}h:{m:02d}m:{s:02d}s"
    return string


def first_or_none(l: T.List[T.Any]) -> T.Any:
    """Return the first element of a list or None
    if 1) it is not set or 2) it is falsey"""
    try:
        return l[0]
    except KeyboardInterrupt:
        raise
    except:
        return None


def second_or_none(l: T.List[T.Any]) -> T.Any:
    """Return the second element of a list or None
    if 1) it is not set or 2) it is falsey"""
    try:
        return l[1]
    except KeyboardInterrupt:
        raise
    except:
        return None


def third_or_none(l: T.List[T.Any]) -> T.Any:
    """Return the third element of a list or None
    if 1) it is not set or 2) it is falsey"""
    try:
        return l[2]
    except KeyboardInterrupt:
        raise
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
    except KeyboardInterrupt:
        raise
    except:
        return None


def find_in_list(l: T.List[T.Dict[str, T.Any]], k: str, v: T.Any) -> T.Any:
    """
    Search a list of dictionaries for a specific one
    """
    return first_or_none([i for i in l if i[k] == v])
