import asyncio as aio
import copy
import datetime as dt
import os
import tomllib
from loguru import logger
from typing import Any

from monitor import (
    Bot,
    PositionMonitor,
    MarketMonitor,
    OrderMonitor,
    ExchangeMonitor,
    MonitorGroup,
)


async def launch(
    config: dict[str, Any],
) -> None:
    aio.get_event_loop().slow_callback_duration = config["asyncio"][
        "slow_callback_duration"
    ]

    if config["loguru"]["logger"]["remove"]:
        logger.remove()
    for kwargs in config["loguru"]["logger"]["add"]:
        dir_name = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        kwargs["sink"] = os.path.join(f"./logs/{dir_name}/", kwargs["sink"])
        logger.add(**kwargs)

    position_bot = Bot(config["feishu_bot"]["webhook_position"])
    market_bot = Bot(config["feishu_bot"]["webhook_market"])
    order_bot = Bot(config["feishu_bot"]["webhook_order"])
    exchange_bot = Bot(config["feishu_bot"]["webhook_exchange"])

    monitors = []
    for kwargs in config["monitors"]:
        kwargs = copy.deepcopy(kwargs)
        kwargs["key"] = config["binance_account"]["key"]
        kwargs["secret"] = config["binance_account"]["secret"]
        cls = kwargs.pop("cls")
        if "PositionMonitor" == cls:
            monitor = PositionMonitor(position_bot, **kwargs)
        elif "MarketMonitor" == cls:
            monitor = MarketMonitor(market_bot, **kwargs)
        elif "OrderMonitor" == cls:
            monitor = OrderMonitor(order_bot, **kwargs)
        elif "ExchangeMonitor" == cls:
            monitor = ExchangeMonitor(exchange_bot, **kwargs)
        monitors.append(monitor)
    monitor_group = MonitorGroup(monitors)

    logger.critical(">>> ENTER >>>")
    async with position_bot, market_bot, order_bot, exchange_bot, monitor_group:
        try:
            await aio.Future()
        except aio.CancelledError as e:
            print(repr(e))
    logger.critical("<<< EXIT <<<")


def main() -> None:
    config = {}
    with (
        open(r"./config.toml", mode="rb") as f0,
        open(r"./config-private.toml", mode="rb") as f1,
    ):
        config.update(tomllib.load(f0))
        config.update(tomllib.load(f1))

    aio.run(launch(config), debug=config["asyncio"]["debug"])


if __name__ == "__main__":
    main()
