import asyncio
import typing as T


async def async_func_wrapper(function: T.Callable[[T.Any], T.Any], *args, **kwargs) -> T.Any:
    return function(*args, **kwargs)
