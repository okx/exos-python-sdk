from decimal import Decimal

import httpx

from exos_python_sdk import (
    AccountBalance,
    AccountPositionTier,
    BearerAuth,
    BillsPage,
    CancelAllAfterResult,
    Candle,
    Chain,
    Environment,
    ExchangeOSClient,
    FillDirection,
    FillsPage,
    Instrument,
    LeverageInfo,
    MaxSize,
    Order,
    OrderHistory,
    OrderHistoryPage,
    PendingOrders,
    PriceCandle,
    RestList,
    SecurityFundResult,
    SecurityFundType,
    Ticker,
    TokenInfo,
    TradeFee,
    TransactionReceipt,
    UserLimits,
)
from exos_python_sdk.websocket.messages import ChannelDataMessage, parse_message
from exos_python_sdk.websocket.payloads import (
    BalanceAndPosition,
    EstimatedPrice,
    FundingsPayload,
    PublicTrade,
    SettingUpdates,
    UserFillsPayload,
    UserOrderStatus,
)

TEST_ENVIRONMENT = Environment.custom(
    name="test",
    rest_url="http://localhost",
    websocket_url="ws://localhost/ws",
    signing_chain=Chain.TESTNET,
)


def client_for(data, *, path: str | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if path is not None:
            assert request.url.path == path
        return httpx.Response(200, json={"code": "0", "msg": "", "data": data})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    return ExchangeOSClient(
        environment=TEST_ENVIRONMENT, http_client=http, auth=BearerAuth("test-token")
    ), http


def test_market_endpoint_returns_concrete_models_and_nested_models() -> None:
    data = [
        {
            "assetId": "102",
            "marketType": "perp",
            "priceDecimals": "1",
            "upcChg": [{"param": "priceDecimals", "newValue": "2", "effTime": "1710086400000"}],
            "futureField": "kept",
        }
    ]
    client, http = client_for(data)
    result = client.market.instruments(asset_id=102)
    assert isinstance(result[0], Instrument)
    assert result[0].asset_id == "102"
    assert result[0].price_decimals == "1"
    assert result[0].upc_chg[0].new_value == "2"
    assert result[0].extra == {"futureField": "kept"}
    assert result[0].future_field == "kept"
    http.close()


def test_token_info_includes_optional_wei_decimals() -> None:
    client, http = client_for(
        [{"tokenId": "0", "tokenName": "USDS", "pointFlag": False, "weiDecimals": 6}]
    )
    result = client.market.token_info()
    assert isinstance(result[0], TokenInfo)
    assert result[0].wei_decimals == 6
    http.close()


def test_candle_rows_have_named_fields_without_losing_wire_values() -> None:
    row = ["1710000000000", "1", "2", "0.5", "1.5", "10", "15", "15", "1"]
    client, http = client_for([row])
    result = client.market.candles(asset_id=2)
    assert isinstance(result[0], Candle)
    assert result[0].open == "1"
    assert result[0].volume_currency_quote == "15"
    assert result[0].utc_datetime("ts").year == 2024
    http.close()


def test_transaction_receipt_and_statuses_are_recursively_typed() -> None:
    data = [
        {
            "txHash": "0xabc",
            "status": "ok",
            "response": {"type": "order", "data": {"statuses": [{"filled": {"avgPx": "1.25"}}]}},
        }
    ]
    client, http = client_for(data)
    result = client.trade.transaction("0xabc")
    receipt = result[0]
    assert isinstance(receipt, TransactionReceipt)
    assert receipt.tx_hash == "0xabc"
    assert receipt.response.data.statuses[0].filled.decimal("avgPx") == Decimal("1.25")
    http.close()


def test_transaction_receipt_confirmation_fields_are_optional() -> None:
    client, http = client_for([{"txHash": "0xpending"}])
    receipt = client.trade.transaction("0xpending")[0]
    assert isinstance(receipt, TransactionReceipt)
    assert receipt.tx_hash == "0xpending"
    assert receipt.block_height is None
    assert receipt.response is None
    http.close()


def test_private_rest_container_models_nested_orders_and_balances() -> None:
    pending_client, pending_http = client_for(
        [
            {
                "block_height": "11892975",
                "block_timestamp": "1785062091486",
                "data": [{"oid": "7", "assetStatus": "normal", "attachAlgoOrds": []}],
            }
        ]
    )
    pending = pending_client.trade.orders_pending()
    assert isinstance(pending[0], PendingOrders)
    assert pending[0].data[0].oid == "7"
    assert pending[0].block_height == "11892975"
    assert pending[0].block_timestamp == "1785062091486"
    assert pending[0].data[0].asset_status == "normal"
    assert pending[0].data[0].extra == {}
    pending_http.close()

    balance_client, balance_http = client_for([{"totalEq": "4.2", "details": [{"tokenId": "0"}]}])
    balances = balance_client.account.balance()
    assert isinstance(balances[0], AccountBalance)
    assert balances[0].details[0].token_id == "0"
    balance_http.close()


def test_trade_pages_type_the_page_and_nested_rows() -> None:
    cases = (
        (
            "orders_pending",
            PendingOrders,
            {
                "block_height": "11892975",
                "block_timestamp": "1785062091486",
                "data": [
                    {"oid": "7", "assetId": 602, "assetStatus": "normal", "attachAlgoOrds": []}
                ],
            },
        ),
        (
            "orders_history",
            OrderHistoryPage,
            {"oid": "8", "assetId": 602},
        ),
        ("fills", FillsPage, {"tradeId": "9", "assetId": 602}),
    )
    for method_name, page_type, row in cases:
        if method_name == "orders_pending":
            client, http = client_for([row])
        else:
            client, http = client_for([{"nextCursor": "opaque", "hasMore": True, "data": [row]}])
        result = getattr(client.trade, method_name)()
        assert isinstance(result[0], page_type)
        if method_name == "orders_pending":
            assert result[0].block_height == "11892975"
            assert result[0].block_timestamp == "1785062091486"
            assert result[0].data[0].asset_id == 602
        else:
            assert result[0].next_cursor == "opaque"
            assert result[0].has_more is True
            assert result[0].data[0].asset_id == 602
        http.close()


def test_trade_response_field_updates_are_typed() -> None:
    client, http = client_for(
        [
            {
                "nextCursor": None,
                "hasMore": False,
                "data": [
                    {
                        "tradeId": "9",
                        "assetId": "602",
                        "pnl": "-1.25",
                        "fillDir": "BackstopLiquidation",
                        "block_height": "12345678",
                        "block_timestamp": "1789462970000",
                    }
                ],
            }
        ],
        path="/api/v5/exchangeos/trade/fills",
    )
    fills = client.trade.fills()[0].data[0]
    assert fills.pnl == "-1.25"
    assert fills.fill_dir == FillDirection.BACKSTOP_LIQUIDATION.value
    assert fills.block_height == "12345678"
    assert fills.block_timestamp == "1789462970000"
    assert "closedPnl" not in fills
    http.close()


def test_order_and_pending_order_updated_fields() -> None:
    order_client, order_http = client_for(
        [
            {
                "oid": "7",
                "block_height": "12345678",
                "block_timestamp": "1789462970000",
            }
        ],
        path="/api/v5/exchangeos/trade/order",
    )
    order = order_client.trade.order(oid="7")[0]
    assert order.block_height == "12345678"
    assert order.block_timestamp == "1789462970000"
    assert "u_time" not in Order._wire_fields
    order_http.close()

    pending_client, pending_http = client_for(
        [
            {
                "block_height": "12345679",
                "block_timestamp": "1789462971000",
                "data": [{"oid": "8", "assetStatus": "normal"}],
            }
        ],
        path="/api/v5/exchangeos/trade/orders-pending",
    )
    pending_page = pending_client.trade.orders_pending()[0]
    pending = pending_page.data[0]
    assert pending_page.block_height == "12345679"
    assert pending_page.block_timestamp == "1789462971000"
    assert pending.asset_status == "normal"
    assert "avgPx" not in pending
    assert "avg_px" not in type(pending)._wire_fields
    assert "block_height" not in type(pending)._wire_fields
    assert "block_timestamp" not in type(pending)._wire_fields
    assert "error_code" not in OrderHistory._wire_fields
    assert "children" not in OrderHistory._wire_fields
    pending_http.close()


def test_bills_use_data_zero_cursor_page_and_numeric_account_asset_ids() -> None:
    bills_client, bills_http = client_for(
        [{"nextCursor": None, "hasMore": False, "data": [{"billId": "1", "assetId": 602}]}]
    )
    bills = bills_client.account.bills()
    assert isinstance(bills[0], BillsPage)
    assert bills[0].has_more is False
    assert bills[0].data[0].asset_id == 602
    bills_http.close()


def test_account_limits_returns_typed_nested_limit_snapshot() -> None:
    client, http = client_for(
        [
            {
                "actionLimit": {
                    "initial": "30000",
                    "remaining": "400",
                    "isThrottled": False,
                    "throttleIntervalMs": "5000",
                },
                "cancelAll": {"dailyLimit": "10", "remaining": "8"},
                "cancelExemption": {"limit": "62800", "remaining": "31800"},
                "openOrders": {"current": "12", "limit": "2000", "userOverride": ""},
                "block_height": "12345678",
                "block_timestamp": "1789462970000",
            }
        ],
        path="/api/v5/exchangeos/account/limits",
    )
    result = client.account.limits(vault_address="0xvault")
    limits = result[0]
    assert isinstance(limits, UserLimits)
    assert limits.action_limit.remaining == "400"
    assert limits.action_limit.is_throttled is False
    assert limits.cancel_all.daily_limit == "10"
    assert limits.cancel_exemption.remaining == "31800"
    assert limits.open_orders.user_override == ""
    assert limits.block_height == "12345678"
    assert limits.block_timestamp == "1789462970000"
    http.close()


def test_security_fund_returns_typed_nested_snapshot() -> None:
    client, http = client_for(
        [
            {
                "data": [
                    {
                        "assetId": "2",
                        "fundType": "securityFund",
                        "fundValue": "12000.50",
                        "block_timestamp": "1786636800000",
                        "history": [{"cTime": "1786636800000", "balance": "12000.50"}],
                    }
                ]
            }
        ],
        path="/api/v5/exchangeos/market/security-fund",
    )
    result = client.market.security_fund(SecurityFundType.SECURITY_FUND, asset_id="2")
    page = result[0]
    assert isinstance(page, SecurityFundResult)
    assert page.data[0].asset_id == "2"
    assert page.data[0].fund_type == "securityFund"
    assert page.data[0].fund_value == "12000.50"
    assert page.data[0].block_timestamp == "1786636800000"
    assert page.data[0].history[0].c_time == "1786636800000"
    assert page.data[0].history[0].balance == "12000.50"
    http.close()


def test_legacy_direct_funding_and_bills_pages_normalize_to_data_zero() -> None:
    cases = (
        ("/api/v5/exchangeos/market/funding-rate-history", "market", "funding_rate_history"),
        ("/api/v5/exchangeos/account/bills", "account", "bills"),
    )
    for path, namespace_name, method_name in cases:
        client, http = client_for({"nextCursor": None, "hasMore": False, "data": []}, path=path)
        namespace = getattr(client, namespace_name)
        args = (602,) if method_name == "funding_rate_history" else ()
        result = getattr(namespace, method_name)(*args)
        assert isinstance(result, RestList)
        assert result[0].has_more is False
        http.close()

    numeric_models = (
        ("max_size", MaxSize, {"assetId": 602}, (602,)),
        ("position_tiers", AccountPositionTier, {"assetId": 602}, (602,)),
        ("leverage_info", LeverageInfo, {"assetId": 602}, (602,)),
        ("trade_fee", TradeFee, {"assetId": 602}, (602,)),
    )
    for method_name, model_type, row, args in numeric_models:
        client, http = client_for([row])
        result = getattr(client.account, method_name)(*args)
        assert isinstance(result[0], model_type)
        assert result[0].asset_id == 602
        http.close()


def test_cancel_all_after_uses_expires_after_wire_name() -> None:
    client, http = client_for([{"serverTimestamp": "1000", "expiresAfter": "61000"}])
    result = client.trade.cancel_all_after(
        {"action": {"type": "cancelAll", "marketType": "perp"}, "nonce": 1}
    )
    assert isinstance(result[0], CancelAllAfterResult)
    assert result[0].server_timestamp == "1000"
    assert result[0].expires_after == "61000"
    assert {"serverTimestamp", "expiresAfter"}.issubset(type(result[0])._wire_fields)
    assert "code" not in type(result[0])._wire_fields
    assert "expireAt" not in result[0]
    http.close()


def channel(channel: str, data):
    message = parse_message({"arg": {"channel": channel}, "data": data})
    assert isinstance(message, ChannelDataMessage)
    return message.data


def test_public_websocket_payloads_are_channel_specific() -> None:
    tickers = channel("exchangeos-tickers", [{"assetId": 2, "lastPx": "1.1"}])
    assert isinstance(tickers[0], Ticker)
    assert tickers[0].last_px == "1.1"

    trades = channel(
        "exchangeos-trades",
        [{"assetId": 2, "fId": "10", "lId": "11", "px": "1", "sz": "3", "side": "buy", "ts": "4"}],
    )
    assert isinstance(trades[0], PublicTrade)
    assert trades[0].first_trade_id == "10"
    assert trades[0].price == "1"

    estimated = channel(
        "exchangeos-estimated-price",
        [
            {
                "assetId": "9102",
                "name": "UNI-USD-PERP",
                "marketType": "perp",
                "expTime": "1786636800000",
                "settlePx": "1.2345",
                "ts": "1786636700123",
            }
        ],
    )
    assert isinstance(estimated[0], EstimatedPrice)
    assert estimated[0].asset_id == "9102"
    assert estimated[0].name == "UNI-USD-PERP"
    assert estimated[0].market_type == "perp"
    assert estimated[0].exp_time == "1786636800000"
    assert estimated[0].settle_px == "1.2345"
    assert estimated[0].ts == "1786636700123"

    candles = channel(
        "exchangeos-mark-price-candle1m",
        [["1710000000000", "1", "2", "0.5", "1.5", "1"]],
    )
    assert isinstance(candles[0], PriceCandle)
    assert candles[0].close == "1.5"


def test_private_websocket_payload_shapes_follow_documented_containers() -> None:
    portfolio = channel(
        "exchangeos-balance-and-position",
        [
            {
                "totalEq": "9",
                "details": [{"tokenId": "0"}],
                "positions": [{"assetId": 2, "pos": "1"}],
            }
        ],
    )
    assert isinstance(portfolio[0], BalanceAndPosition)
    assert portfolio[0].positions[0].pos == "1"

    statuses = channel(
        "exchangeos-user-order-status",
        {"orderStatuses": [{"state": "open", "order": {"oid": "8"}}]},
    )
    assert isinstance(statuses, UserOrderStatus)
    assert statuses.order_statuses[0].order.oid == "8"

    fundings = channel(
        "exchangeos-user-fundings",
        {"fundings": [{"assetId": 2, "fundingFee": "-1"}]},
    )
    assert isinstance(fundings, FundingsPayload)
    assert fundings.fundings[0].funding_fee == "-1"

    settings = channel(
        "exchangeos-setting-updates",
        {"assetSetting": [{"assetId": 2, "leverage": "10"}]},
    )
    assert isinstance(settings, SettingUpdates)
    assert settings.asset_setting[0].leverage == "10"


def test_user_fills_channel_models_current_wrapper_and_pnl_fields() -> None:
    message = parse_message(
        {
            "arg": {
                "channel": "exchangeos-user-fills",
                "marketTypes": '["all"]',
                "pointBoard": "true",
            },
            "backend": "indexerpubsub",
            "block_height": "150845315",
            "block_timestamp": "1792120122626",
            "data": {
                "fills": [
                    {
                        "tradeId": "49680",
                        "assetId": "1602",
                        "price": "217.99",
                        "size": "0.019",
                        "pnl": "0.000000",
                        "rebateTokenId": "",
                        "fillDir": "Open",
                    }
                ]
            },
            "pTime": "1792120122678",
            "user": "0xuser",
        }
    )
    assert isinstance(message, ChannelDataMessage)
    assert isinstance(message.data, UserFillsPayload)
    fill = message.data.fills[0]
    assert fill.trade_id == "49680"
    assert fill.pnl == "0.000000"
    assert fill.rebate_token_id == ""
    assert fill.fill_dir == FillDirection.OPEN.value
    assert message.block_height == "150845315"
    assert message.block_timestamp == "1792120122626"


def test_user_fills_channel_accepts_legacy_bare_list_shape() -> None:
    fills = channel("exchangeos-user-fills", [{"tradeId": "1", "pnl": "0"}])
    assert fills[0].trade_id == "1"
    assert fills[0].pnl == "0"
