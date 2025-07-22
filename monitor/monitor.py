import aiofiles
import asyncio
import bisect
import collections
import inspect
import json
import math
import pathlib
from types import TracebackType
from typing import Any, Iterable, Self, Type
from binance.um_futures import UMFutures
from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient
from binance.websocket.binance_socket_manager import BinanceSocketManager
from loguru import logger

from .cards import *
from .utils import *
from .feishu import *
from .timewindow import *

__all__ = [
    "BaseMonitor",
    "PositionMonitor",
    "MarketMonitor",
    "OrderMonitor",
    "ExchangeMonitor",
    "MonitorGroup",
]


class BaseMonitor:

    def __init__(
        self,
    ) -> None:
        self._tasks: list[asyncio.Task[None]] = []

    async def __aenter__(
        self,
    ) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        await self.stop()

    async def start(
        self,
    ) -> None:
        logger.info(f"{self} starting")
        if self.running:
            logger.warning(f"{self} have started")
            return
        coroutines = []
        for name in dir(self):
            if not name.startswith("monitor"):
                continue
            attr = getattr(self, name)
            if not inspect.iscoroutinefunction(attr):
                continue
            coroutines.append(attr())
        self._tasks.extend(map(asyncio.create_task, coroutines))
        logger.info(f"{self} started")

    async def stop(
        self,
    ) -> None:
        logger.info(f"{self} stopping")
        if not self.running:
            logger.warning(f"{self} have stopped")
            return
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info(f"{self} stopped")

    @property
    def running(
        self,
    ) -> bool:
        return not all(task.cancelled() or task.done() for task in self._tasks)


class PositionMonitor(BaseMonitor):

    def __init__(
        self,
        bot: Bot,
        *,
        key: str | None = None,
        secret: str | None = None,
        minute: int = 0,
        drawdown_percent_threshold: float = 5.0,
        **kwargs,
    ) -> None:
        super().__init__()
        self.bot = bot
        self.client = UMFutures(
            key=key,
            secret=secret,
            **kwargs,
        )
        self.minute = minute
        self.drawdown_percent_threshold = drawdown_percent_threshold

    async def monitor_position(
        self,
    ) -> None:
        at_all_element = at_all_element_factory()
        error_card = error_card_factory()
        position_card = position_card_factory()

        position1_csv = pathlib.Path(r"./position1.csv")
        position2_csv = pathlib.Path(r"./position2.csv")
        var_json = pathlib.Path(r"./var.json")
        var = await json_load(var_json)
        totl_max = float(var.setdefault("totl_max", "0.0"))
        account_dq = collections.deque(maxlen=1)
        position_dq = collections.deque(maxlen=12)
        delay = until_next_hour(minute=self.minute)
        sleep_task = asyncio.create_task(asyncio.sleep(delay))
        while True:
            await sleep_task
            delay = until_next_hour(minute=self.minute)
            sleep_task = asyncio.create_task(asyncio.sleep(delay))
            position_card["body"]["elements"][1]["rows"] = rows1 = []
            position_card["body"]["elements"][2]["rows"] = rows2 = []
            while 3 < len(position_card["body"]["elements"]):
                del position_card["body"]["elements"][-1]
            try:
                data = await restapi_wrapper(self.client.account)
            except Exception as e:
                logger.error(repr(e))
                error_card["body"]["elements"][1]["text"]["content"] = repr(e)
                await self.bot.send_interactive(error_card)
                continue
            account = data
            try:
                data = await restapi_wrapper(self.client.get_position_risk)
            except Exception as e:
                logger.error(repr(e))
                error_card["body"]["elements"][1]["text"]["content"] = repr(e)
                await self.bot.send_interactive(error_card)
                continue
            position = {x["symbol"]: x for x in data}
            rows1.append({"indicator": "多仓"})
            rows1.append({"indicator": "空仓"})
            rows1.append({"indicator": "总仓"})
            rows1.append({"indicator": "总资产"})
            long = shrt = 0.0
            long_up, shrt_up = 0.0, 0.0
            for position in position.values():
                if "-" == position["notional"][0]:
                    shrt += -float(position["notional"])
                    shrt_up += float(position["unRealizedProfit"])
                else:
                    long += float(position["notional"])
                    long_up += float(position["unRealizedProfit"])
            lort = long + shrt
            lort_up = long_up + shrt_up
            totl = float(account["totalMarginBalance"])
            rows1[0]["notional"] = long
            rows1[1]["notional"] = shrt
            rows1[2]["notional"] = lort
            rows1[3]["notional"] = totl
            rows1[0]["unrealized_profit"] = long_up
            rows1[1]["unrealized_profit"] = shrt_up
            rows1[2]["unrealized_profit"] = lort_up
            if 1 <= len(position_dq):
                oth_positions = position_dq[-1]
                oth_long = oth_shrt = 0.0
                for position in oth_positions.values():
                    if "-" == position["notional"][0]:
                        oth_shrt += -float(position["notional"])
                    else:
                        oth_long += float(position["notional"])
                long_pnl1h = long - oth_long
                shrt_pnl1h = oth_shrt - shrt
                lort_pnl1h = long_pnl1h + shrt_pnl1h
                rows1[0]["pnl1h"] = long_pnl1h
                rows1[1]["pnl1h"] = shrt_pnl1h
                rows1[2]["pnl1h"] = lort_pnl1h
            if 1 <= len(account_dq):
                oth_account = account_dq[-1]
                oth_totl = float(oth_account["totalMarginBalance"])
                totl_pnl1h = totl - oth_totl
                rows1[3]["pnl1h"] = totl_pnl1h
            var = await json_load(var_json)
            totl_max = max(totl_max, float(var.setdefault("totl_max", "0.0")))
            totl_max = max(totl_max, totl)
            if 0 < totl_max:
                totl_drawdown_percent = 100 * (totl_max - totl) / totl_max
                rows1[3]["drawdown_percent"] = totl_drawdown_percent
            for position in sorted(
                position.values(),
                key=lambda x: ("-" == x["notional"][0], -float(x["unRealizedProfit"])),
            ):
                ps = "-" == position["notional"][0]
                ps_str = "<font color='red'>空</font>" if ps else "<font color='green'>多</font>"
                symbol = position["symbol"]
                fsymbol = format_symbol(symbol)
                notional = abs(float(position["notional"]))
                notional_percent = 100 * notional / lort if 0 < lort else 0.0
                unrealized_profit = float(position["unRealizedProfit"])
                position_amt = abs(float(position["positionAmt"]))
                entry_price = float(position["entryPrice"])
                mark_price = float(position["markPrice"])
                entry_notional = entry_price * position_amt
                unrealized_profit_percent = 100 * unrealized_profit / entry_notional if 0 < entry_notional else 0.0
                row = {"position": f"{ps_str} {fsymbol}"}
                row["notional"] = notional
                row["notional_percent"] = notional_percent
                row["unrealized_profit"] = unrealized_profit
                row["unrealized_profit_percent"] = unrealized_profit_percent
                row["position_amt"] = position_amt
                row["entry_price"] = entry_price
                row["mark_price"] = mark_price
                if 1 <= len(position_dq) and symbol in position_dq[-1]:
                    oth_positions = position_dq[-1]
                    oth_mark_price = float(oth_positions[symbol]["markPrice"])
                    if 0 < oth_mark_price:
                        change1h_percent = 100 * (mark_price - oth_mark_price) / oth_mark_price
                        row["change1h_percent"] = change1h_percent
                if 12 <= len(position_dq) and symbol in position_dq[-12]:
                    oth_positions = position_dq[-12]
                    oth_mark_price = float(oth_positions[symbol]["markPrice"])
                    if 0 < oth_mark_price:
                        change12h_percent = 100 * (mark_price - oth_mark_price) / oth_mark_price
                        row["change12h_percent"] = change12h_percent
                rows2.append(row)
            account_dq.append(account)
            position_dq.append(position)
            if self.drawdown_percent_threshold <= rows1[3]["drawdown_percent"]:
                position_card["body"]["elements"].append(at_all_element)
            await self.bot.send_interactive(position_card)
            var["totl_max"] = str(totl_max)
            await json_dump(var_json, var)
            timestamp = time_ms()
            await csv_append(position1_csv, {"timestamp": timestamp, "table": rows1})
            await csv_append(position2_csv, {"timestamp": timestamp, "table": rows2})


class MarketMonitor(BaseMonitor):

    def __init__(
        self,
        bot: Bot,
        *,
        key: str | None = None,
        secret: str | None = None,
        params: dict[str, float] = {},
        speed: int = 1,
        maxm: int = 256,
        **kwargs,
    ) -> None:
        super().__init__()
        self.bot = bot
        self.client = UMFutures(
            key=key,
            secret=secret,
            **kwargs,
        )
        self.wsclient = UMFuturesWebsocketClient(
            on_message=self.on_message,
            on_open=self.on_open,
            on_close=self.on_close,
            on_error=self.on_error,
            on_ping=self.on_ping,
            on_pong=self.on_pong,
        )
        self.positions = {}
        self.speed = speed
        self.tws = tws = []
        for interval, change_percent in sorted(
            (parse_interval(interval), change_percent) for interval, change_percent in params.items()
        ):
            unit = interval // maxm
            tw = SparseTimewindow(interval, unit=unit)
            tw.change_percent = change_percent
            tws.append(tw)

    async def start(
        self,
    ) -> None:
        if self.running:
            return
        self.wsclient.mark_price_all_market(speed=self.speed)
        stream = f"!markPrice@arr@{self.speed}s" if 1 == self.speed else "!markPrice@arr"
        logger.info(f"SUBSCRIBE: {stream}")
        await super().start()

    async def stop(
        self,
    ) -> None:
        if not self.running:
            return
        await super().stop()
        self.wsclient.stop()

    def on_message(
        self,
        socket_manager: BinanceSocketManager,
        data: bytes | str,
    ) -> None:
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            logger.warning(f"{repr(e)}\n{data}")
            return
        if isinstance(data, list):
            logger.debug(f"on_message\n{data}")
            mps = {x["s"]: x for x in data}
            for tw in self.tws:
                tw.push(mps, time_ms())

    def on_open(
        self,
        socket_manager: BinanceSocketManager,
    ) -> None:
        logger.info(f"on_open")

    def on_close(
        self,
        socket_manager: BinanceSocketManager,
    ) -> None:
        logger.info(f"on_close")

    def on_error(
        self,
        socket_manager: BinanceSocketManager,
        e: Exception,
    ) -> None:
        logger.warning(f"on_error\n{repr(e)}")
        socket_manager.create_ws_connection()
        self.wsclient.mark_price_all_market(speed=self.speed)
        stream = f"!markPrice@arr@{self.speed}s" if 1 == self.speed else "!markPrice@arr"
        logger.info(f"SUBSCRIBE: {stream}")

    def on_ping(
        self,
        socket_manager: BinanceSocketManager,
        data: bytes | str,
    ) -> None:
        logger.debug(f"on_ping\n{data}")

    def on_pong(
        self,
        socket_manager: BinanceSocketManager,
    ) -> None:
        logger.debug(f"on_pong")

    async def monitor_positions(
        self,
    ) -> None:
        error_card = error_card_factory()

        delay = 10 * 60 * 1.0
        sleep_task = asyncio.create_task(asyncio.sleep(0.0))
        while True:
            await sleep_task
            sleep_task = asyncio.create_task(asyncio.sleep(delay))
            try:
                data = await restapi_wrapper(self.client.get_position_risk)
            except Exception as e:
                logger.error(repr(e))
                error_card["body"]["elements"][1]["text"]["content"] = repr(e)
                await self.bot.send_interactive(error_card)
                continue
            self.positions.clear()
            self.positions.update((x["symbol"], x) for x in data)

    async def monitor_market(
        self,
    ) -> None:
        market_card = market_card_factory()

        memories = {}
        delay = 10 * 1.0
        sleep_task = asyncio.create_task(asyncio.sleep(delay))
        while True:
            await sleep_task
            sleep_task = asyncio.create_task(asyncio.sleep(delay))
            market_card["body"]["elements"][1]["rows"] = rows = []
            sorting_map = {}
            for tw in self.tws:
                if tw.empty():
                    break
                mps0, t0 = tw.head()
                mps1, t1 = tw.tail()
                if t1 - t0 + 2 * tw.unit + 8_000 < tw.interval:
                    break
                for symbol in mps0.keys() & mps1.keys():
                    mp0 = float(mps0[symbol]["p"])
                    mp1 = float(mps1[symbol]["p"])
                    if not 0 < mp0:
                        continue
                    change_percent = 100 * (mp1 - mp0) / mp0
                    if abs(change_percent) < tw.change_percent:
                        continue
                    t = time_ms()
                    if t - memories.get((symbol, tw.interval), -math.inf) < tw.interval:
                        continue
                    memories[symbol, tw.interval] = t
                    row = {}
                    fsymbol = format_symbol(symbol)
                    if symbol in self.positions:
                        ps = "-" == self.positions[symbol]["notional"][0]
                        ps_str = "<font color='red'>空</font>" if ps else "<font color='green'>多</font>"
                        row["symbol"] = f"{ps_str} {fsymbol}"
                    else:
                        row["symbol"] = fsymbol
                    row["timedelta"] = format_milliseconds(tw.interval)
                    row["change_percent"] = change_percent
                    rows.append(row)
                    sorting_map[row["symbol"]] = (
                        0 if symbol in self.positions else 1,
                        tw.interval,
                        -abs(change_percent),
                    )
            if 0 < len(rows):
                rows.sort(key=lambda x: sorting_map[x["symbol"]])
                await self.bot.send_interactive(market_card)


class OrderMonitor(BaseMonitor):

    def __init__(
        self,
        bot: Bot,
        *,
        key: str | None = None,
        secret: str | None = None,
        bookticker_dqs_maxlen: int = 100,
        **kwargs,
    ) -> None:
        super().__init__()
        self.bot = bot
        self.client = UMFutures(
            key=key,
            secret=secret,
            **kwargs,
        )
        self.wsclient = UMFuturesWebsocketClient(
            on_message=self.on_message,
            on_open=self.on_open,
            on_close=self.on_close,
            on_error=self.on_error,
            on_ping=self.on_ping,
            on_pong=self.on_pong,
        )
        self.bookticker_dqs_maxlen = bookticker_dqs_maxlen
        self.listenkey = "xxx"
        self.bookticker_dqs = {}
        self.order_tickers = {}
        self.orders = collections.deque()

    async def start(
        self,
    ) -> None:
        if self.running:
            return
        try:
            data = await restapi_wrapper(self.client.new_listen_key)
        except Exception as e:
            logger.error(repr(e))
            error_card = error_card_factory()
            error_card["body"]["elements"][1]["text"]["content"] = repr(e)
            await self.bot.send_interactive(error_card)
        self.listenkey = data["listenKey"]
        self.wsclient.user_data(self.listenkey)
        logger.info(f"SUBSCRIBE: {self.listenkey}")
        await super().start()

    async def stop(
        self,
    ) -> None:
        if not self.running:
            return
        await super().stop()
        self.wsclient.stop()
        try:
            data = await restapi_wrapper(self.client.close_listen_key, self.listenkey)
        except Exception as e:
            logger.error(repr(e))
            error_card = error_card_factory()
            error_card["body"]["elements"][1]["text"]["content"] = repr(e)
            await self.bot.send_interactive(error_card)

    def on_message(
        self,
        socket_manager: BinanceSocketManager,
        data: bytes | str,
    ) -> None:
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            logger.warning(f"{repr(e)}\n{data}")
            return
        if isinstance(data, dict) and "ORDER_TRADE_UPDATE" == data.get("e"):
            logger.info(f"on_message\n{data}")
            if "NEW" == data["o"]["x"]:
                symbol = data["o"]["s"]
                timestamp = data["o"]["T"]
                self.order_tickers[data["o"]["i"]] = {}
                self.order_tickers[data["o"]["i"]]["timestamp"] = timestamp
                if symbol not in self.bookticker_dqs:
                    return
                bookticker_dq = self.bookticker_dqs[symbol]
                idx = bisect.bisect_right(bookticker_dq, timestamp, key=lambda x: x["T"]) - 1
                logger.debug(f"idx: {idx}")
                if idx < 0:
                    logger.warning(f"No bookTicker for {symbol} at {timestamp}")
                    return
                bookticker = bookticker_dq[idx]
                self.order_tickers[data["o"]["i"]]["bookticker"] = bookticker
            else:
                self.orders.append(data)
        if isinstance(data, dict) and "bookTicker" == data.get("e"):
            symbol = data["s"]
            if symbol not in self.bookticker_dqs:
                self.bookticker_dqs[symbol] = collections.deque(maxlen=self.bookticker_dqs_maxlen)
            self.bookticker_dqs[symbol].append(data)

    def on_open(
        self,
        socket_manager: BinanceSocketManager,
    ) -> None:
        logger.info(f"on_open")

    def on_close(
        self,
        socket_manager: BinanceSocketManager,
    ) -> None:
        logger.info(f"on_close")

    def on_error(
        self,
        socket_manager: BinanceSocketManager,
        e: Exception,
    ) -> None:
        logger.warning(f"on_error\n{repr(e)}")
        socket_manager.create_ws_connection()
        self.wsclient.user_data(self.listenkey)
        logger.info(f"SUBSCRIBE: {self.listenkey}")
        for symbol in self.bookticker_dqs:
            self.wsclient.book_ticker(symbol)
            logger.info(f"SUBSCRIBE: {symbol.lower()}@bookTicker")

    def on_ping(
        self,
        socket_manager: BinanceSocketManager,
        data: bytes | str,
    ) -> None:
        logger.debug(f"on_ping\n{data}")

    def on_pong(
        self,
        socket_manager: BinanceSocketManager,
    ) -> None:
        logger.debug(f"on_pong")

    async def monitor_listenkey(
        self,
    ) -> None:
        error_card = error_card_factory()

        delay = 10 * 60 * 1.0
        sleep_task = asyncio.create_task(asyncio.sleep(delay))
        while True:
            await sleep_task
            sleep_task = asyncio.create_task(asyncio.sleep(delay))
            try:
                data = await restapi_wrapper(self.client.new_listen_key)
            except Exception as e:
                logger.error(repr(e))
                error_card["body"]["elements"][1]["text"]["content"] = repr(e)
                await self.bot.send_interactive(error_card)
                continue
            new_listenkey = data["listenKey"]
            if self.listenkey == new_listenkey:
                continue
            self.wsclient.user_data(self.listenkey, action="UNSUBSCRIBE")
            logger.info(f"UNSUBSCRIBE: {self.listenkey}")
            self.listenkey = new_listenkey
            self.wsclient.user_data(self.listenkey)
            logger.info(f"SUBSCRIBE: {self.listenkey}")

    async def monitor_booktickers(
        self,
    ) -> None:
        error_card = error_card_factory()

        delay = 60 * 60 * 1.0
        sleep_task = asyncio.create_task(asyncio.sleep(0.0))
        while True:
            await sleep_task
            sleep_task = asyncio.create_task(asyncio.sleep(delay))
            try:
                data = await restapi_wrapper(self.client.book_ticker)
            except Exception as e:
                logger.error(repr(e))
                error_card["body"]["elements"][1]["text"]["content"] = repr(e)
                await self.bot.send_interactive(error_card)
                continue
            symbols = {x["symbol"] for x in data}
            for symbol in self.bookticker_dqs.keys() - symbols:
                self.wsclient.book_ticker(symbol, action="UNSUBSCRIBE")
                del self.bookticker_dqs[symbol]
                logger.info(f"UNSUBSCRIBE: {symbol.lower()}@bookTicker")
            for symbol in symbols - self.bookticker_dqs.keys():
                self.wsclient.book_ticker(symbol)
                logger.info(f"SUBSCRIBE: {symbol.lower()}@bookTicker")

    async def monitor_order(
        self,
    ) -> None:
        order_card = order_card_factory()

        orders_csv = pathlib.Path(r"./orders.csv")
        delay = until_next_minute()
        sleep_task = asyncio.create_task(asyncio.sleep(delay))
        while True:
            await sleep_task
            delay = until_next_minute()
            sleep_task = asyncio.create_task(asyncio.sleep(delay))
            order_card["body"]["elements"][1]["rows"] = rows = []
            orders = sorted(self.orders, key=lambda x: x["o"]["T"])
            self.orders.clear()
            for order in orders:
                timestamp = order["o"]["T"]
                order_id = order["o"]["i"]
                side = order["o"]["S"]
                fside = "<font color='green'>买</font>" if "BUY" == side else "<font color='red'>卖</font>"
                symbol = order["o"]["s"]
                fsymbol = format_symbol(symbol)
                last_price = float(order["o"]["L"])
                last_quantity = float(order["o"]["l"])
                last_notional = last_quantity * last_price
                realized_profit = float(order["o"]["rp"])
                price = float(order["o"]["p"])
                quantity = float(order["o"]["q"])
                cum_quantity = float(order["o"]["z"])
                filled_percent = 100 * cum_quantity / quantity if 0 < quantity else 0.0
                slippage = last_price - price
                slippage_percent = 100 * slippage / price if 0 < price else 0.0
                commission = float(order["o"]["n"])
                commission_percent = 100 * commission / last_notional if 0 < last_notional else 0.0
                if order_id in self.order_tickers:
                    order_ticker = self.order_tickers.pop(order_id)
                    delay = timestamp - order_ticker["timestamp"]
                    fdelay = format_milliseconds(delay)
                else:
                    delay = None
                    fdelay = "--"
                is_maker = order["o"]["m"]
                role = "MAKER" if is_maker else "TAKER"
                task = order["o"]["x"]
                status = order["o"]["X"]
                order_type = order["o"]["o"]
                valid_type = order["o"]["f"]
                row = {}
                row["timestamp"] = timestamp
                row["order_id"] = order_id
                row["side"] = fside
                row["symbol"] = fsymbol
                row["last_quantity"] = last_quantity
                row["last_price"] = last_price
                row["last_notional"] = last_notional
                row["slippage"] = slippage
                row["slippage_percent"] = slippage_percent
                row["commission"] = commission
                row["commission_percent"] = commission_percent
                row["realized_profit"] = realized_profit
                row["filled_percent"] = filled_percent
                row["delay"] = fdelay
                row["role"] = role
                row["task"] = task
                row["status"] = status
                row["order_type"] = order_type
                row["valid_type"] = valid_type
                rows.append(row)
            if 0 < len(rows):
                await self.bot.send_interactive(order_card)
                await csv_appendrows(orders_csv, rows)


class ExchangeMonitor(BaseMonitor):

    def __init__(
        self,
        bot: Bot,
        *,
        key: str | None = None,
        secret: str | None = None,
        minute: int = 0,
        **kwargs,
    ) -> None:
        super().__init__()
        self.bot = bot
        self.client = UMFutures(
            key=key,
            secret=secret,
            **kwargs,
        )
        self.positions = {}
        self.minute = minute

    async def monitor_positions(
        self,
    ) -> None:
        error_card = error_card_factory()

        delay = 50 * 60 * 1.0
        sleep_task = asyncio.create_task(asyncio.sleep(0.0))
        while True:
            await sleep_task
            sleep_task = asyncio.create_task(asyncio.sleep(delay))
            try:
                data = await restapi_wrapper(self.client.get_position_risk)
            except Exception as e:
                logger.error(repr(e))
                error_card["body"]["elements"][1]["text"]["content"] = repr(e)
                await self.bot.send_interactive(error_card)
                continue
            self.positions.clear()
            self.positions.update((x["symbol"], x) for x in data)

    async def monitor_exchange(
        self,
    ) -> None:
        error_card = error_card_factory()
        exchange_card = exchange_card_factory()

        memories = {}
        perpetual_time = 4133404800000
        delay = until_next_hour(minute=self.minute)
        sleep_task = asyncio.create_task(asyncio.sleep(delay))
        while True:
            await sleep_task
            delay = until_next_hour(minute=self.minute)
            sleep_task = asyncio.create_task(asyncio.sleep(delay))
            try:
                data = await restapi_wrapper(self.client.exchange_info)
            except Exception as e:
                logger.error(repr(e))
                error_card["body"]["elements"][1]["text"]["content"] = repr(e)
                await self.bot.send_interactive(error_card)
                continue
            exchange_card["body"]["elements"][1]["rows"] = rows = []
            symbols = data["symbols"]
            try:
                data = await restapi_wrapper(self.client.time)
            except Exception as e:
                logger.error(repr(e))
                error_card["body"]["elements"][1]["text"]["content"] = repr(e)
                await self.bot.send_interactive(error_card)
                continue
            server_time = data["serverTime"]
            for data in symbols:
                if "PERPETUAL" != data["contractType"]:
                    continue
                symbol = data["symbol"]
                status = data["status"]
                onboard_date = data["onboardDate"]
                delivery_date = data["deliveryDate"]
                if not (server_time < delivery_date < perpetual_time or server_time < onboard_date < perpetual_time):
                    continue
                t = time_ms()
                if symbol in memories:
                    continue
                memories[symbol] = t
                row = {}
                fsymbol = format_symbol(symbol)
                if symbol in self.positions:
                    ps = "-" == self.positions[symbol]["notional"][0]
                    ps_str = "<font color='red'>空</font>" if ps else "<font color='green'>多</font>"
                    row["symbol"] = f"{ps_str} {fsymbol}"
                else:
                    row["symbol"] = fsymbol
                row["status"] = status
                row["onboard_date"] = onboard_date
                row["delivery_date"] = delivery_date
                rows.append(row)
            if 0 < len(rows):
                await self.bot.send_interactive(exchange_card)


class MonitorGroup[BaseMonitor]:

    def __init__(
        self,
        monitors: Iterable[BaseMonitor],
    ) -> None:
        self.monitors = list(monitors)

    async def __aenter__(
        self,
    ) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        await self.stop()

    async def start(
        self,
    ) -> None:
        logger.info(f"{self} starting")
        if self.running:
            logger.warning(f"{self} have started")
            return
        for monitor in self.monitors:
            await monitor.start()
        logger.info(f"{self} started")

    async def stop(
        self,
    ) -> None:
        logger.info(f"{self} stopping")
        if not self.running:
            logger.warning(f"{self} have stopped")
            return
        for monitor in reversed(self.monitors):
            await monitor.stop()
        logger.info(f"{self} stopped")

    @property
    def running(
        self,
    ) -> bool:
        return any(monitor.running for monitor in self.monitors)
