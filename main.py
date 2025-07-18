import asyncio
import copy
import tomllib
from loguru import logger

from monitor import *


async def main() -> None:
    config = {}
    with (
        open(r"./config.toml", mode="rb") as f0,
        open(r"./config-private.toml", mode="rb") as f1,
    ):
        config.update(tomllib.load(f0))
        config.update(tomllib.load(f1))

    asyncio.get_event_loop().slow_callback_duration = config["asyncio"]["slow_callback_duration"]

    if config["loguru"]["logger"]["remove"]:
        logger.remove()
    for kwargs in config["loguru"]["logger"]["add"]:
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
            await asyncio.Future()
        except asyncio.CancelledError as e:
            pass
    logger.critical("<<< EXIT <<<")


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
