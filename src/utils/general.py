from typing import Any, Dict, List

def getPrettySeconds(s: int) -> str:
    """Given an amount of seconds, return a formatted string with
    hours, minutes and seconds; taken from
    https://stackoverflow.com/a/775075/2972183"""
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f'{h:d}h:{m:02d}m:{s:02d}s'

def firstOrNone(l: List[Any]) -> Any:
    """Return the first element of a list or None
    if 1) it is not set or 2) it is falsey"""
    try:
        return l[0]
    except:
        return None

def secondOrNone(l: List[Any]) -> Any:
    """Return the second element of a list or None
    if 1) it is not set or 2) it is falsey"""
    try:
        return l[1]
    except:
        return None

def thirdOrNone(l: List[Any]) -> Any:
    """Return the third element of a list or None
    if 1) it is not set or 2) it is falsey"""
    try:
        return l[2]
    except:
        return None

def fourthOrNone(l: List[Any]) -> Any:
    """Return the fourth element of a list or None
    if 1) it is not set or 2) it is falsey"""
    try:
        return l[3]
    except:
        return None

def findInList(l: List[Dict[str, Any]], k: str, v: Any) -> Any:
    """
    Search a list of dictionaries for a specific one
    """
    return firstOrNone([i for i in l if i[k] == v])
