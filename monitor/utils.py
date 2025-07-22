import aiofiles
import asyncio
import datetime
import json
import math
import pathlib
import requests
import time
from typing import Any, Callable
from binance.error import ClientError, ServerError

__all__ = [
    "format_symbol",
    "time_ms",
    "parse_interval",
    "format_milliseconds",
    "until_next",
    "until_next_day",
    "until_next_hour",
    "until_next_minute",
    "until_next_second",
    "restapi_wrapper",
    "json_load",
    "json_dump",
    "csv_append",
    "csv_appendrows",
]


def format_symbol(
    symbol: str,
) -> str:
    for suffix in "USDT", "USDC", "BTC", "ETH", "BNB":
        if symbol.endswith(suffix):
            symbol = symbol[: -len(suffix)] + "/" + suffix
            break
    return symbol


def time_ms() -> int:
    return int(1000 * time.time())


def parse_interval(
    s: str,
) -> int:
    milliseconds = 0
    unit_map = {
        "d": 1000 * 60 * 60 * 24,
        "h": 1000 * 60 * 60,
        "m": 1000 * 60,
        "s": 1000,
        "ms": 1,
    }
    for part in s.split():
        leng = 2 if part.endswith("ms") else 1
        milliseconds += int(part[:-leng]) * unit_map[part[-leng:]]
    return milliseconds


def format_milliseconds(
    milliseconds: int,
) -> str:
    if milliseconds < 0:
        raise ValueError("milliseconds cannot be negative")
    if 0 == milliseconds:
        return "0ms"
    s = ""
    seconds, milliseconds = divmod(milliseconds, 1000)
    if 0 < milliseconds:
        s = f"{milliseconds}ms {s}"
    minutes, seconds = divmod(seconds, 60)
    if 0 < seconds:
        s = f"{seconds}s {s}"
    hours, minutes = divmod(minutes, 60)
    if 0 < minutes:
        s = f"{minutes}m {s}"
    days, hours = divmod(hours, 24)
    if 0 < hours:
        s = f"{hours}h {s}"
    if 0 < days:
        s = f"{days}d {s}"
    return s[:-1]


def until_next(
    td: datetime.timedelta,
    **kwargs,
) -> datetime.timedelta:
    td = abs(td)
    now = datetime.datetime.now()
    nxt = now.replace(**kwargs)
    if nxt < now:
        nxt += math.ceil((now - nxt) / td) * td
    return nxt - now


def until_next_day(
    *,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    microsecond: int = 0,
) -> float:
    return until_next(
        datetime.timedelta(days=1),
        hour=hour,
        minute=minute,
        second=second,
        microsecond=microsecond,
    ).total_seconds()


def until_next_hour(
    *,
    minute: int = 0,
    second: int = 0,
    microsecond: int = 0,
) -> float:
    return until_next(
        datetime.timedelta(hours=1),
        minute=minute,
        second=second,
        microsecond=microsecond,
    ).total_seconds()


def until_next_minute(
    *,
    second: int = 0,
    microsecond: int = 0,
) -> float:
    return until_next(
        datetime.timedelta(minutes=1),
        second=second,
        microsecond=microsecond,
    ).total_seconds()


def until_next_second(
    *,
    microsecond: int = 0,
) -> float:
    return until_next(
        datetime.timedelta(seconds=1),
        microsecond=microsecond,
    ).total_seconds()


async def restapi_wrapper[ReturnType](
    func: Callable[..., ReturnType],
    /,
    *args,
    **kwargs,
) -> ReturnType:
    excs = []
    delay = 1.0
    max_tries = 3
    for _ in range(max_tries):
        try:
            res = await asyncio.to_thread(func, *args, **kwargs)
            break
        except ClientError as e:
            excs.append(e)
        except ServerError as e:
            excs.append(e)
        except requests.ConnectionError as e:
            excs.append(e)
        except Exception as e:
            excs.append(e)
        await asyncio.sleep(delay)
    else:
        raise ExceptionGroup(f"{max_tries=}", excs)
    return res


file_locks: dict[pathlib.Path, asyncio.Lock] = {}


async def json_load(
    path: pathlib.Path,
) -> Any:
    if not path.is_file():
        return {}
    if path not in file_locks:
        file_locks[path] = asyncio.Lock()
    async with file_locks[path]:
        async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
            s = await f.read()
    var = json.loads(s)
    return var


async def json_dump(
    path: pathlib.Path,
    obj: Any,
) -> None:
    if path not in file_locks:
        file_locks[path] = asyncio.Lock()
    async with file_locks[path]:
        if not path.is_file():
            await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        s = json.dumps(obj)
        async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
            await f.write(s)
            await f.flush()


async def csv_append(
    path: pathlib.Path,
    row: dict[str, Any],
):
    if path not in file_locks:
        file_locks[path] = asyncio.Lock()
    async with file_locks[path]:
        keys = list(row.keys())
        if not path.is_file():
            await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
            async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
                await f.write(",".join(keys) + "\n")
                await f.flush()
        async with aiofiles.open(path, mode="a", encoding="utf-8") as f:
            await f.write(",".join(str(row[key]) for key in keys) + "\n")
            await f.flush()


async def csv_appendrows(
    path: pathlib.Path,
    rows: list[dict[str, Any]],
) -> None:
    if 0 == len(rows):
        return
    if path not in file_locks:
        file_locks[path] = asyncio.Lock()
    async with file_locks[path]:
        keys = list(rows[0].keys())
        if not path.is_file():
            await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
            async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
                await f.write(",".join(keys) + "\n")
                await f.flush()
        async with aiofiles.open(path, mode="a", encoding="utf-8") as f:
            await f.writelines(",".join(str(row[key]) for key in keys) + "\n" for row in rows)
            await f.flush()
