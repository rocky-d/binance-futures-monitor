import asyncio
import collections
import json
import math
import pathlib
from types import TracebackType
from typing import Iterable, Self, Type
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
        coros = []
        for name in dir(self):
            if not name.startswith("monitor"):
                continue
            attr = getattr(self, name)
            if not asyncio.iscoroutinefunction(attr):
                continue
            coros.append(attr())
        self._tasks.extend(map(asyncio.create_task, coros))
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
        proxies: dict[str, str] | None = None,
        minute: int = 0,
        drawdown_percent_threshold: float = 5.0,
        **kwargs,
    ) -> None:
        super().__init__()
        self._bot = bot
        self._client = UMFutures(
            key=key,
            secret=secret,
            proxies=proxies,
            **kwargs,
        )
        self._minute = minute
        self._drawdown_percent_threshold = drawdown_percent_threshold

    async def monitor_position(
        self,
    ) -> None:
        at_all_element = at_all_element_factory()
        error_card = error_card_factory()
        position_card = position_card_factory()

        position_csv = pathlib.Path(r"./data/position.csv")
        var_json = pathlib.Path(r"./data/var.json")
        account_dq = collections.deque(maxlen=1)
        position_dq = collections.deque(maxlen=12)
        delay = until_next_hour(minute=self._minute)
        sleep_task = asyncio.create_task(asyncio.sleep(delay))
        while True:
            await sleep_task
            delay = until_next_hour(minute=self._minute)
            sleep_task = asyncio.create_task(asyncio.sleep(delay))
            position_card["body"]["elements"][1]["rows"] = rows1 = [
                {"indicator": x} for x in ("多仓", "空仓", "总仓", "总资产")
            ]
            position_card["body"]["elements"][2]["rows"] = rows2 = []
            while 3 < len(position_card["body"]["elements"]):
                del position_card["body"]["elements"][-1]
            try:
                task1 = asyncio.create_task(restapi_wrapper(self._client.account))
                task2 = asyncio.create_task(restapi_wrapper(self._client.get_position_risk))
                task3 = asyncio.create_task(restapi_wrapper(self._client.time))
                data1 = await task1
                data2 = await task2
                data3 = await task3
            except Exception as e:
                error_card["body"]["elements"][1]["text"]["content"] = message = repr(e)
                logger.error(message)
                await self._bot.send_interactive(error_card)
                continue
            account = data1
            position = {x["symbol"]: x for x in data2}
            server_time = data3["serverTime"]
            long = shrt = 0.0
            long_up, shrt_up = 0.0, 0.0
            for pos in position.values():
                if "-" == pos["notional"][0]:
                    shrt += -float(pos["notional"])
                    shrt_up += float(pos["unRealizedProfit"])
                else:
                    long += float(pos["notional"])
                    long_up += float(pos["unRealizedProfit"])
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
                oth_position = position_dq[-1]
                oth_long = oth_shrt = 0.0
                for oth_pos in oth_position.values():
                    if "-" == oth_pos["notional"][0]:
                        oth_shrt += -float(oth_pos["notional"])
                    else:
                        oth_long += float(oth_pos["notional"])
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
            totl_max = max(totl, float(var.get("totl_max", "0.0")))
            var["totl_max"] = str(totl_max)
            if 0 < totl_max:
                drawdown_percent = 100 * (totl_max - totl) / totl_max
                rows1[3]["drawdown_percent"] = drawdown_percent
                if self._drawdown_percent_threshold <= drawdown_percent:
                    position_card["body"]["elements"].append(at_all_element)
            for pos in sorted(
                position.values(),
                key=lambda x: ("-" == x["notional"][0], -float(x["unRealizedProfit"])),
            ):
                ps = "-" == pos["notional"][0]
                f_ps = markdown_color("空", "red") if ps else markdown_color("多", "green")
                symbol = pos["symbol"]
                f_symbol = format_symbol(symbol)
                notional = abs(float(pos["notional"]))
                notional_percent = 100 * notional / lort if 0 < lort else 0.0
                unrealized_profit = float(pos["unRealizedProfit"])
                position_amt = abs(float(pos["positionAmt"]))
                entry_price = float(pos["entryPrice"])
                mark_price = float(pos["markPrice"])
                entry_notional = entry_price * position_amt
                unrealized_profit_percent = 100 * unrealized_profit / entry_notional if 0 < entry_notional else 0.0
                row = {"position": f"{f_ps} {f_symbol}"}
                rows2.append(row)
                row["notional"] = notional
                row["notional_percent"] = notional_percent
                row["unrealized_profit"] = unrealized_profit
                row["unrealized_profit_percent"] = unrealized_profit_percent
                row["position_amt"] = position_amt
                row["entry_price"] = entry_price
                row["mark_price"] = mark_price
                if 1 <= len(position_dq) and symbol in position_dq[-1]:
                    oth_position = position_dq[-1]
                    oth_mark_price = float(oth_position[symbol]["markPrice"])
                    if 0 < oth_mark_price:
                        change1h_percent = 100 * (mark_price - oth_mark_price) / oth_mark_price
                        row["change1h_percent"] = change1h_percent
                if 12 <= len(position_dq) and symbol in position_dq[-12]:
                    oth_position = position_dq[-12]
                    oth_mark_price = float(oth_position[symbol]["markPrice"])
                    if 0 < oth_mark_price:
                        change12h_percent = 100 * (mark_price - oth_mark_price) / oth_mark_price
                        row["change12h_percent"] = change12h_percent
            account_dq.append(account)
            position_dq.append(position)
            csv_row = {"timestamp": server_time, "table1": rows1, "table2": rows2}
            task1 = asyncio.create_task(self._bot.send_interactive(position_card))
            task2 = asyncio.create_task(json_dump(var_json, var))
            task3 = asyncio.create_task(csv_append(position_csv, csv_row))
            await task1
            await task2
            await task3


class MarketMonitor(BaseMonitor):

    def __init__(
        self,
        bot: Bot,
        *,
        key: str | None = None,
        secret: str | None = None,
        proxies: dict[str, str] | None = None,
        params: dict[str, float] = {},
        speed: int = 1,
        maxm: int = 256,
        **kwargs,
    ) -> None:
        super().__init__()
        self._bot = bot
        self._client = UMFutures(
            key=key,
            secret=secret,
            proxies=proxies,
            **kwargs,
        )
        self._wsclient = UMFuturesWebsocketClient(
            on_message=self.on_message,
            on_open=self.on_open,
            on_close=self.on_close,
            on_error=self.on_error,
            on_ping=self.on_ping,
            on_pong=self.on_pong,
            is_combined=False,
            proxies=proxies,
        )
        self._positions = {}
        self._speed = speed
        self._tws = tws = []
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
        self._wsclient.mark_price_all_market(speed=self._speed)
        stream = f"!markPrice@arr@{self._speed}s" if 1 == self._speed else "!markPrice@arr"
        logger.info(f"SUBSCRIBE: {stream}")
        await super().start()

    async def stop(
        self,
    ) -> None:
        if not self.running:
            return
        await super().stop()
        self._wsclient.stop()

    def on_message(
        self,
        socket_manager: BinanceSocketManager,
        data: bytes | str,
    ) -> None:
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            logger.warning(f"on_message\n{repr(e)}\n{repr(data)}")
            return
        if isinstance(data, list):
            logger.debug(f"on_message\n{repr(data)}")
            mps = {x["s"]: x for x in data}
            for tw in self._tws:
                tw.push(mps, time_ms())
        else:
            logger.info(f"on_message\n{repr(data)}")

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
        self._wsclient.mark_price_all_market(speed=self._speed)
        stream = f"!markPrice@arr@{self._speed}s" if 1 == self._speed else "!markPrice@arr"
        logger.info(f"SUBSCRIBE: {stream}")

    def on_ping(
        self,
        socket_manager: BinanceSocketManager,
        data: bytes | str,
    ) -> None:
        logger.debug(f"on_ping\n{repr(data)}")

    def on_pong(
        self,
        socket_manager: BinanceSocketManager,
    ) -> None:
        logger.debug(f"on_pong")

    async def monitor_positions(
        self,
    ) -> None:
        error_card = error_card_factory()

        delay = 60 * 1.0
        sleep_task = asyncio.create_task(asyncio.sleep(0.0))
        while True:
            await sleep_task
            sleep_task = asyncio.create_task(asyncio.sleep(delay))
            try:
                data = await restapi_wrapper(self._client.get_position_risk)
            except Exception as e:
                error_card["body"]["elements"][1]["text"]["content"] = message = repr(e)
                logger.error(message)
                await self._bot.send_interactive(error_card)
                continue
            self._positions.clear()
            self._positions.update((x["symbol"], x) for x in data)

    async def monitor_market(
        self,
    ) -> None:
        market_card = market_card_factory()

        memories = {}
        delay = self._speed * 2 * 1.0
        sleep_task = asyncio.create_task(asyncio.sleep(delay))
        while True:
            await sleep_task
            sleep_task = asyncio.create_task(asyncio.sleep(delay))
            market_card["body"]["elements"][1]["rows"] = rows = []
            sorting_map = {}
            for tw in self._tws:
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
                    key = symbol, tw.interval
                    if t - memories.get(key, -math.inf) < tw.interval:
                        continue
                    memories[key] = t
                    row = {}
                    rows.append(row)
                    f_symbol = format_symbol(symbol)
                    if symbol in self._positions:
                        ps = "-" == self._positions[symbol]["notional"][0]
                        f_ps = markdown_color("空", "red") if ps else markdown_color("多", "green")
                        row["symbol"] = f"{f_ps} {f_symbol}"
                    else:
                        row["symbol"] = f_symbol
                    row["timedelta"] = format_milliseconds(tw.interval)
                    row["change_percent"] = change_percent
                    sorting_map[row["symbol"]] = (
                        0 if symbol in self._positions else 1,
                        tw.interval,
                        -abs(change_percent),
                    )
            if 0 == len(rows):
                continue
            rows.sort(key=lambda x: sorting_map[x["symbol"]])
            await self._bot.send_interactive(market_card)


class OrderMonitor(BaseMonitor):

    def __init__(
        self,
        bot: Bot,
        *,
        key: str | None = None,
        secret: str | None = None,
        proxies: dict[str, str] | None = None,
        **kwargs,
    ) -> None:
        super().__init__()
        self._bot = bot
        self._client = UMFutures(
            key=key,
            secret=secret,
            proxies=proxies,
            **kwargs,
        )
        self._wsclient = UMFuturesWebsocketClient(
            on_message=self.on_message,
            on_open=self.on_open,
            on_close=self.on_close,
            on_error=self.on_error,
            on_ping=self.on_ping,
            on_pong=self.on_pong,
            is_combined=False,
            proxies=proxies,
        )
        self._listenkey = ""
        self._new_orders_by_id = {}
        self._nonnew_orders_dq = collections.deque()

    async def start(
        self,
    ) -> None:
        if self.running:
            return
        try:
            data = await restapi_wrapper(self._client.new_listen_key)
        except Exception as e:
            error_card = error_card_factory()
            error_card["body"]["elements"][1]["text"]["content"] = message = repr(e)
            logger.error(message)
            await self._bot.send_interactive(error_card)
        else:
            self._listenkey = data["listenKey"]
            self._wsclient.user_data(self._listenkey)
            logger.info(f"SUBSCRIBE: {self._listenkey}")
        await super().start()

    async def stop(
        self,
    ) -> None:
        if not self.running:
            return
        await super().stop()
        self._wsclient.stop()
        try:
            data = await restapi_wrapper(self._client.close_listen_key, self._listenkey)
        except Exception as e:
            error_card = error_card_factory()
            error_card["body"]["elements"][1]["text"]["content"] = message = repr(e)
            logger.error(message)
            await self._bot.send_interactive(error_card)

    def on_message(
        self,
        socket_manager: BinanceSocketManager,
        data: bytes | str,
    ) -> None:
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            logger.warning(f"on_message\n{repr(e)}\n{repr(data)}")
            return
        if isinstance(data, dict) and "ORDER_TRADE_UPDATE" == data.get("e"):
            logger.info(f"on_message\n{repr(data)}")
            if "NEW" == data["o"]["x"]:
                self._new_orders_by_id[data["o"]["i"]] = data
            else:
                self._nonnew_orders_dq.append(data)
        else:
            logger.info(f"on_message\n{repr(data)}")

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
        self._wsclient.user_data(self._listenkey)
        logger.info(f"SUBSCRIBE: {self._listenkey}")

    def on_ping(
        self,
        socket_manager: BinanceSocketManager,
        data: bytes | str,
    ) -> None:
        logger.debug(f"on_ping\n{repr(data)}")

    def on_pong(
        self,
        socket_manager: BinanceSocketManager,
    ) -> None:
        logger.debug(f"on_pong")

    async def monitor_listenkey(
        self,
    ) -> None:
        error_card = error_card_factory()

        delay = 60 * 1.0
        sleep_task = asyncio.create_task(asyncio.sleep(delay))
        while True:
            await sleep_task
            sleep_task = asyncio.create_task(asyncio.sleep(delay))
            try:
                data = await restapi_wrapper(self._client.new_listen_key)
            except Exception as e:
                error_card["body"]["elements"][1]["text"]["content"] = message = repr(e)
                logger.error(message)
                await self._bot.send_interactive(error_card)
                continue
            new_listenkey = data["listenKey"]
            if self._listenkey == new_listenkey:
                continue
            self._wsclient.user_data(self._listenkey, action="UNSUBSCRIBE")
            logger.info(f"UNSUBSCRIBE: {self._listenkey}")
            self._listenkey = new_listenkey
            self._wsclient.user_data(self._listenkey)
            logger.info(f"SUBSCRIBE: {self._listenkey}")

    async def monitor_order(
        self,
    ) -> None:
        order_card = order_card_factory()

        orders_csv = pathlib.Path(r"./data/orders.csv")
        delay = until_next_minute()
        sleep_task = asyncio.create_task(asyncio.sleep(delay))
        while True:
            await sleep_task
            delay = until_next_minute()
            sleep_task = asyncio.create_task(asyncio.sleep(delay))
            order_card["body"]["elements"][1]["rows"] = rows = []
            csv_rows = []
            orders = sorted(self._nonnew_orders_dq, key=lambda x: x["o"]["T"])
            self._nonnew_orders_dq.clear()
            for order in orders:
                timestamp = order["o"]["T"]
                order_id = order["o"]["i"]
                f_order_id = str(order_id)[:7]
                side = order["o"]["S"]
                f_side = markdown_color("买", "green") if "BUY" == side else markdown_color("卖", "red")
                symbol = order["o"]["s"]
                f_symbol = format_symbol(symbol)
                price = float(order["o"]["p"])
                quantity = float(order["o"]["q"])
                notional = quantity * price
                last_price = float(order["o"]["L"])
                last_quantity = float(order["o"]["l"])
                last_notional = last_quantity * last_price
                realized_profit = float(order["o"]["rp"])
                filled_quantity = float(order["o"]["z"])
                filled_percent = 100 * filled_quantity / quantity if 0 < quantity else 0.0
                slippage = last_price - price if "BUY" == side else price - last_price
                slippage_percent = 100 * slippage / price if 0 < price else 0.0
                commission = float(order["o"]["n"])
                commission_percent = 100 * commission / last_notional if 0 < last_notional else 0.0
                if order_id in self._new_orders_by_id:
                    delay = timestamp - self._new_orders_by_id[order_id]["o"]["T"]
                    f_delay = format_milliseconds(delay)
                else:
                    delay = None
                    f_delay = "--"
                role = "MAKER" if order["o"]["m"] else "TAKER"
                task = order["o"]["x"]
                status = order["o"]["X"]
                f_status = {"PARTIALLY_FILLED": "PARTIAL"}.get(status, status)
                order_type = order["o"]["o"]
                valid_type = order["o"]["f"]
                if order_id in self._new_orders_by_id and "PARTIALLY_FILLED" != status:
                    del self._new_orders_by_id[order_id]
                row = {}
                rows.append(row)
                row["timestamp"] = timestamp
                row["order_id"] = f_order_id
                row["side"] = f_side
                row["symbol"] = f_symbol
                row["last_quantity"] = last_quantity
                row["last_price"] = last_price
                row["last_notional"] = last_notional
                row["realized_profit"] = realized_profit
                row["filled_percent"] = filled_percent
                row["slippage_percent"] = slippage_percent
                row["delay"] = f_delay
                row["role"] = role
                row["task"] = task
                row["status"] = f_status
                row["order_type"] = order_type
                row["valid_type"] = valid_type
                csv_row = {}
                csv_rows.append(csv_row)
                csv_row["timestamp"] = timestamp
                csv_row["order_id"] = order_id
                csv_row["side"] = side
                csv_row["symbol"] = symbol
                csv_row["quantity"] = quantity
                csv_row["price"] = price
                csv_row["notional"] = notional
                csv_row["last_quantity"] = last_quantity
                csv_row["last_price"] = last_price
                csv_row["last_notional"] = last_notional
                csv_row["realized_profit"] = realized_profit
                csv_row["filled_quantity"] = filled_quantity
                csv_row["filled_percent"] = filled_percent
                csv_row["slippage"] = slippage
                csv_row["slippage_percent"] = slippage_percent
                csv_row["commission"] = commission
                csv_row["commission_percent"] = commission_percent
                csv_row["delay"] = delay
                csv_row["role"] = role
                csv_row["task"] = task
                csv_row["status"] = status
                csv_row["order_type"] = order_type
                csv_row["valid_type"] = valid_type
            if 0 == len(rows):
                continue
            task1 = asyncio.create_task(self._bot.send_interactive(order_card))
            task2 = asyncio.create_task(csv_appendrows(orders_csv, csv_rows))
            await task1
            await task2


class ExchangeMonitor(BaseMonitor):

    def __init__(
        self,
        bot: Bot,
        *,
        key: str | None = None,
        secret: str | None = None,
        proxies: dict[str, str] | None = None,
        minute: int = 0,
        **kwargs,
    ) -> None:
        super().__init__()
        self._bot = bot
        self._client = UMFutures(
            key=key,
            secret=secret,
            proxies=proxies,
            **kwargs,
        )
        self._positions = {}
        self._minute = minute

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
                data = await restapi_wrapper(self._client.get_position_risk)
            except Exception as e:
                error_card["body"]["elements"][1]["text"]["content"] = message = repr(e)
                logger.error(message)
                await self._bot.send_interactive(error_card)
                continue
            self._positions.clear()
            self._positions.update((x["symbol"], x) for x in data)

    async def monitor_exchange(
        self,
    ) -> None:
        at_all_element = at_all_element_factory()
        error_card = error_card_factory()
        exchange_card = exchange_card_factory()
        exchange_card["body"]["elements"].append(at_all_element)

        memories = {}
        perpetual_time = 4133404800000
        delay = until_next_hour(minute=self._minute)
        sleep_task = asyncio.create_task(asyncio.sleep(delay))
        while True:
            await sleep_task
            delay = until_next_hour(minute=self._minute)
            sleep_task = asyncio.create_task(asyncio.sleep(delay))
            exchange_card["body"]["elements"][1]["rows"] = rows = []
            try:
                task1 = asyncio.create_task(restapi_wrapper(self._client.exchange_info))
                task2 = asyncio.create_task(restapi_wrapper(self._client.time))
                data1 = await task1
                data2 = await task2
            except Exception as e:
                error_card["body"]["elements"][1]["text"]["content"] = message = repr(e)
                logger.error(message)
                await self._bot.send_interactive(error_card)
                continue
            symbols = data1["symbols"]
            server_time = data2["serverTime"]
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
                key = symbol, status, onboard_date, delivery_date
                if key in memories:
                    continue
                memories[key] = t
                row = {}
                rows.append(row)
                f_symbol = format_symbol(symbol)
                if symbol in self._positions:
                    ps = "-" == self._positions[symbol]["notional"][0]
                    f_ps = markdown_color("空", "red") if ps else markdown_color("多", "green")
                    row["symbol"] = f"{f_ps} {f_symbol}"
                else:
                    row["symbol"] = f_symbol
                row["status"] = status
                row["onboard_date"] = onboard_date
                row["delivery_date"] = delivery_date
            if 0 == len(rows):
                continue
            await self._bot.send_interactive(exchange_card)


class MonitorGroup[BaseMonitor]:

    def __init__(
        self,
        monitors: Iterable[BaseMonitor],
    ) -> None:
        self._monitors = list(monitors)

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
        for monitor in self._monitors:
            await monitor.start()
        logger.info(f"{self} started")

    async def stop(
        self,
    ) -> None:
        logger.info(f"{self} stopping")
        if not self.running:
            logger.warning(f"{self} have stopped")
            return
        for monitor in reversed(self._monitors):
            await monitor.stop()
        logger.info(f"{self} stopped")

    @property
    def running(
        self,
    ) -> bool:
        return any(monitor.running for monitor in self._monitors)
