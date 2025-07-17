import asyncio
import tomllib
from loguru import logger

from monitor import *


async def main() -> None:
    with open(r"./config.toml", mode="rb") as f:
        config = tomllib.load(f)
    with open(r"./config-private.toml", mode="rb") as f:
        config_private = tomllib.load(f)

    if config["loguru"]["logger"]["remove"]:
        logger.remove()
    for kwargs in config["loguru"]["logger"]["add"]:
        logger.add(**kwargs)

    SLOW_CALLBACK_DURATION = float(config["asyncio"]["slow_callback_duration"])
    asyncio.get_event_loop().slow_callback_duration = SLOW_CALLBACK_DURATION

    MARKET_PARAMS = {key: float(val) for key, val in config["market_monitor"]["params"].items()}
    MARKET_SPEED = int(config["market_monitor"]["speed"])
    MARKET_MAXM = int(config["market_monitor"]["maxm"])

    BN_KEY = config_private["binance_account"]["key"]
    BN_SECRET = config_private["binance_account"]["secret"]
    FS_WEBHOOK_POSITION = config_private["feishu_bot"]["webhook_position"]
    FS_WEBHOOK_MARKET = config_private["feishu_bot"]["webhook_market"]
    FS_WEBHOOK_ORDER = config_private["feishu_bot"]["webhook_order"]
    FS_WEBHOOK_EXCHANGE = config_private["feishu_bot"]["webhook_exchange"]

    logger.critical(">>> ENTER >>>")
    async with (
        Bot(FS_WEBHOOK_POSITION) as position_bot,
        Bot(FS_WEBHOOK_MARKET) as market_bot,
        Bot(FS_WEBHOOK_ORDER) as order_bot,
        Bot(FS_WEBHOOK_EXCHANGE) as exchange_bot,
        PositionMonitor(
            position_bot,
            key=BN_KEY,
            secret=BN_SECRET,
        ),
        MarketMonitor(
            market_bot,
            key=BN_KEY,
            secret=BN_SECRET,
            params=MARKET_PARAMS,
            speed=MARKET_SPEED,
            maxm=MARKET_MAXM,
        ),
        OrderMonitor(
            order_bot,
            key=BN_KEY,
            secret=BN_SECRET,
        ),
        ExchangeMonitor(
            exchange_bot,
            key=BN_KEY,
            secret=BN_SECRET,
        ),
    ):
        try:
            await asyncio.Future()
        except asyncio.CancelledError as e:
            pass
    logger.critical("<<< EXIT <<<")


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
