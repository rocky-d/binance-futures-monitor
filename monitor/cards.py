import copy

__all__ = [
    "local_datetime_element_factory",
    "at_all_element_factory",
    "launch_card_factory",
    "finish_card_factory",
    "error_card_factory",
    "position_card_factory",
    "market_card_factory",
    "order_card_factory",
    "exchange_card_factory",
]

LOCAL_DATETIME_ELEMENT = {
    "tag": "markdown",
    "content": "<local_datetime format_type='date_num'></local_datetime>"
    + " <local_datetime format_type='time_sec'></local_datetime>"
    + " <local_datetime format_type='timezone'></local_datetime>",
}

AT_ALL_ELEMENT = {
    "tag": "markdown",
    "content": "<at id=all></at>",
}

LAUNCH_CARD = {
    "schema": "2.0",
    "config": {
        "width_mode": "compact",
    },
    "header": {
        "template": "green",
        "title": {
            "tag": "plain_text",
            "content": "监控启动",
        },
    },
    "body": {
        "elements": [
            LOCAL_DATETIME_ELEMENT,
        ],
    },
}

FINISH_CARD = {
    "schema": "2.0",
    "config": {
        "width_mode": "compact",
    },
    "header": {
        "template": "green",
        "title": {
            "tag": "plain_text",
            "content": "监控结束",
        },
    },
    "body": {
        "elements": [
            LOCAL_DATETIME_ELEMENT,
        ],
    },
}

ERROR_CARD = {
    "schema": "2.0",
    "config": {
        "width_mode": "fill",
    },
    "header": {
        "template": "red",
        "title": {
            "tag": "plain_text",
            "content": "错误",
        },
    },
    "body": {
        "elements": [
            LOCAL_DATETIME_ELEMENT,
            {
                "tag": "div",
                "text": {
                    "tag": "plain_text",
                    "content": "",
                },
            },
            AT_ALL_ELEMENT,
        ],
    },
}

POSITION_CARD = {
    "schema": "2.0",
    "config": {
        "width_mode": "fill",
    },
    "header": {
        "template": "blue",
        "title": {
            "tag": "plain_text",
            "content": "仓位推送",
        },
    },
    "body": {
        "elements": [
            LOCAL_DATETIME_ELEMENT,
            {
                "tag": "table",
                "freeze_first_column": False,
                "page_size": 10,
                "row_height": "auto",
                "row_max_height": "60px",
                "header_style": {},
                "rows": [],
                "columns": [
                    {
                        "name": "indicator",
                        "display_name": "指标",
                        "data_type": "markdown",
                        "width": "80px",
                    },
                    {
                        "name": "notional",
                        "display_name": "名义价值(U)",
                        "data_type": "number",
                        "format": {
                            "precision": 2,
                            "separator": False,
                        },
                        "width": "120px",
                    },
                    {
                        "name": "unrealized_profit",
                        "display_name": "未实现盈亏(U)",
                        "data_type": "number",
                        "format": {
                            "precision": 2,
                            "separator": False,
                        },
                        "width": "120px",
                    },
                    {
                        "name": "pnl1h",
                        "display_name": "近1h盈亏(U)",
                        "data_type": "number",
                        "format": {
                            "precision": 2,
                            "separator": False,
                        },
                        "width": "120px",
                    },
                    {
                        "name": "drawdown_percent",
                        "display_name": "当前回撤(%)",
                        "data_type": "number",
                        "format": {
                            "precision": 2,
                            "separator": False,
                        },
                        "width": "120px",
                    },
                ],
            },
            {
                "tag": "table",
                "freeze_first_column": False,
                "page_size": 10,
                "row_height": "auto",
                "row_max_height": "60px",
                "header_style": {},
                "rows": [],
                "columns": [
                    {
                        "name": "position",
                        "display_name": "持仓",
                        "data_type": "markdown",
                        "width": "165px",
                    },
                    {
                        "name": "position_amt",
                        "display_name": "数量",
                        "data_type": "number",
                        "format": {
                            "precision": 2,
                            "separator": False,
                        },
                        "width": "90px",
                    },
                    {
                        "name": "notional",
                        "display_name": "价值(U)",
                        "data_type": "number",
                        "format": {
                            "precision": 2,
                            "separator": False,
                        },
                        "width": "90px",
                    },
                    {
                        "name": "notional_percent",
                        "display_name": "价值(%)",
                        "data_type": "number",
                        "format": {
                            "precision": 2,
                            "separator": False,
                        },
                        "width": "90px",
                    },
                    {
                        "name": "unrealized_profit",
                        "display_name": "盈亏(U)",
                        "data_type": "number",
                        "format": {
                            "precision": 2,
                            "separator": False,
                        },
                        "width": "90px",
                    },
                    {
                        "name": "unrealized_profit_percent",
                        "display_name": "盈亏(%)",
                        "data_type": "number",
                        "format": {
                            "precision": 2,
                            "separator": False,
                        },
                        "width": "90px",
                    },
                    {
                        "name": "entry_price",
                        "display_name": "开仓价格(U)",
                        "data_type": "number",
                        "format": {
                            "precision": 5,
                            "separator": False,
                        },
                        "width": "120px",
                    },
                    {
                        "name": "mark_price",
                        "display_name": "标记价格(U)",
                        "data_type": "number",
                        "format": {
                            "precision": 5,
                            "separator": False,
                        },
                        "width": "120px",
                    },
                    {
                        "name": "change1h_percent",
                        "display_name": "近1h涨跌(%)",
                        "data_type": "number",
                        "format": {
                            "precision": 2,
                            "separator": False,
                        },
                        "width": "120px",
                    },
                    {
                        "name": "change12h_percent",
                        "display_name": "近12h涨跌(%)",
                        "data_type": "number",
                        "format": {
                            "precision": 2,
                            "separator": False,
                        },
                        "width": "120px",
                    },
                ],
            },
        ],
    },
}

MARKET_CARD = {
    "schema": "2.0",
    "config": {
        "width_mode": "fill",
    },
    "header": {
        "template": "blue",
        "title": {
            "tag": "plain_text",
            "content": "行情推送",
        },
    },
    "body": {
        "elements": [
            LOCAL_DATETIME_ELEMENT,
            {
                "tag": "table",
                "freeze_first_column": False,
                "page_size": 10,
                "row_height": "auto",
                "row_max_height": "60px",
                "header_style": {},
                "rows": [],
                "columns": [
                    {
                        "name": "symbol",
                        "display_name": "交易对",
                        "data_type": "markdown",
                        "width": "160px",
                    },
                    {
                        "name": "timedelta",
                        "display_name": "时段",
                        "data_type": "markdown",
                        "width": "80px",
                    },
                    {
                        "name": "change_percent",
                        "display_name": "涨跌(%)",
                        "data_type": "number",
                        "format": {
                            "precision": 2,
                            "separator": False,
                        },
                        "width": "80px",
                    },
                ],
            },
        ],
    },
}

ORDER_CARD = {
    "schema": "2.0",
    "config": {
        "width_mode": "fill",
    },
    "header": {
        "template": "blue",
        "title": {
            "tag": "plain_text",
            "content": "订单推送",
        },
    },
    "body": {
        "elements": [
            LOCAL_DATETIME_ELEMENT,
            {
                "tag": "table",
                "freeze_first_column": False,
                "page_size": 10,
                "row_height": "auto",
                "row_max_height": "60px",
                "header_style": {},
                "rows": [],
                "columns": [
                    {
                        "name": "timestamp",
                        "display_name": "时间",
                        "data_type": "date",
                        "date_format": "YY-MM-DD HH:mm:ss",
                        "width": "140px",
                    },
                    {
                        "name": "order_id",
                        "display_name": "订单ID",
                        "data_type": "number",
                        "format": {
                            "precision": 0,
                            "separator": False,
                        },
                        "width": "120px",
                    },
                    {
                        "name": "side",
                        "display_name": "方向",
                        "data_type": "markdown",
                        "width": "80px",
                    },
                    {
                        "name": "symbol",
                        "display_name": "交易对",
                        "data_type": "markdown",
                        "width": "160px",
                    },
                    {
                        "name": "last_quantity",
                        "display_name": "数量",
                        "data_type": "number",
                        "format": {
                            "precision": 2,
                            "separator": False,
                        },
                        "width": "80px",
                    },
                    {
                        "name": "last_price",
                        "display_name": "价格(U)",
                        "data_type": "number",
                        "format": {
                            "precision": 5,
                            "separator": False,
                        },
                        "width": "80px",
                    },
                    {
                        "name": "last_notional",
                        "display_name": "价值(U)",
                        "data_type": "number",
                        "format": {
                            "precision": 2,
                            "separator": False,
                        },
                        "width": "80px",
                    },
                    {
                        "name": "slippage",
                        "display_name": "滑点(U)",
                        "data_type": "number",
                        "format": {
                            "precision": 5,
                            "separator": False,
                        },
                        "width": "80px",
                    },
                    {
                        "name": "slippage_percent",
                        "display_name": "滑点(%)",
                        "data_type": "number",
                        "format": {
                            "precision": 2,
                            "separator": False,
                        },
                        "width": "80px",
                    },
                    {
                        "name": "commission",
                        "display_name": "手续费(U)",
                        "data_type": "number",
                        "format": {
                            "precision": 5,
                            "separator": False,
                        },
                        "width": "100px",
                    },
                    {
                        "name": "commission_percent",
                        "display_name": "手续费(%)",
                        "data_type": "number",
                        "format": {
                            "precision": 2,
                            "separator": False,
                        },
                        "width": "100px",
                    },
                    {
                        "name": "realized_profit",
                        "display_name": "实现盈亏(U)",
                        "data_type": "number",
                        "format": {
                            "precision": 5,
                            "separator": False,
                        },
                        "width": "100px",
                    },
                    {
                        "name": "filled_percent",
                        "display_name": "已成交(%)",
                        "data_type": "number",
                        "format": {
                            "precision": 2,
                            "separator": False,
                        },
                        "width": "100px",
                    },
                    {
                        "name": "delay",
                        "display_name": "延迟",
                        "data_type": "markdown",
                        "width": "80px",
                    },
                    {
                        "name": "role",
                        "display_name": "角色",
                        "data_type": "markdown",
                        "width": "80px",
                    },
                    {
                        "name": "task",
                        "display_name": "任务",
                        "data_type": "markdown",
                        "width": "80px",
                    },
                    {
                        "name": "status",
                        "display_name": "状态",
                        "data_type": "markdown",
                        "width": "80px",
                    },
                    {
                        "name": "order_type",
                        "display_name": "订单类型",
                        "data_type": "markdown",
                        "width": "80px",
                    },
                    {
                        "name": "valid_type",
                        "display_name": "生效类型",
                        "data_type": "markdown",
                        "width": "80px",
                    },
                ],
            },
        ],
    },
}

EXCHANGE_CARD = {
    "schema": "2.0",
    "config": {
        "width_mode": "fill",
    },
    "header": {
        "template": "blue",
        "title": {
            "tag": "plain_text",
            "content": "交易所推送",
        },
    },
    "body": {
        "elements": [
            LOCAL_DATETIME_ELEMENT,
            {
                "tag": "table",
                "freeze_first_column": False,
                "page_size": 10,
                "row_height": "auto",
                "row_max_height": "60px",
                "header_style": {},
                "rows": [],
                "columns": [
                    {
                        "name": "symbol",
                        "display_name": "交易对",
                        "data_type": "markdown",
                        "width": "160px",
                    },
                    {
                        "name": "status",
                        "display_name": "当前状态",
                        "data_type": "markdown",
                        "width": "100px",
                    },
                    {
                        "name": "onboard_date",
                        "display_name": "上架时间",
                        "data_type": "date",
                        "date_format": "YYYY-MM-DD HH:mm:ss",
                        "width": "160px",
                    },
                    {
                        "name": "delivery_date",
                        "display_name": "下架时间",
                        "data_type": "date",
                        "date_format": "YYYY-MM-DD HH:mm:ss",
                        "width": "160px",
                    },
                ],
            },
        ],
    },
}

local_datetime_element_factory = lambda: copy.deepcopy(LOCAL_DATETIME_ELEMENT)
at_all_element_factory = lambda: copy.deepcopy(AT_ALL_ELEMENT)
launch_card_factory = lambda: copy.deepcopy(LAUNCH_CARD)
finish_card_factory = lambda: copy.deepcopy(FINISH_CARD)
error_card_factory = lambda: copy.deepcopy(ERROR_CARD)
position_card_factory = lambda: copy.deepcopy(POSITION_CARD)
market_card_factory = lambda: copy.deepcopy(MARKET_CARD)
order_card_factory = lambda: copy.deepcopy(ORDER_CARD)
exchange_card_factory = lambda: copy.deepcopy(EXCHANGE_CARD)
