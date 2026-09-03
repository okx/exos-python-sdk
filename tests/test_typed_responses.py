from decimal import Decimal

import httpx

from exchangeos_sdk import (
    AccountBalance,
    AccountPositionTier,
    BearerAuth,
    BillsPage,
    Candle,
    Chain,
    Environment,
    ExchangeOSClient,
    FillsPage,
    Instrument,
    LeverageInfo,
    MaxSize,
    OrderHistoryPage,
    PendingOrders,
    PriceCandle,
    RestList,
    Ticker,
    TradeFee,
    TransactionReceipt,
    WriteResult,
)
from exchangeos_sdk.websocket.messages import ChannelDataMessage, parse_message
from exchangeos_sdk.websocket.payloads import (
    BalanceAndPosition,
    FundingsPayload,
    PublicTrade,
    SettingUpdates,
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


def test_private_rest_container_models_nested_orders_and_balances() -> None:
    pending_client, pending_http = client_for(
        [{"nextCursor": None, "hasMore": False, "data": [{"oid": "7", "attachAlgoOrds": []}]}]
    )
    pending = pending_client.trade.orders_pending()
    assert isinstance(pending[0], PendingOrders)
    assert pending[0].data[0].oid == "7"
    assert pending[0].data[0].extra == {}
    pending_http.close()

    balance_client, balance_http = client_for([{"totalEq": "4.2", "details": [{"tokenId": "0"}]}])
    balances = balance_client.account.balance()
    assert isinstance(balances[0], AccountBalance)
    assert balances[0].details[0].token_id == "0"
    balance_http.close()


def test_trade_cursor_pages_type_the_page_and_nested_rows() -> None:
    cases = (
        (
            "orders_pending",
            PendingOrders,
            {"oid": "7", "assetId": 602, "attachAlgoOrds": []},
        ),
        (
            "orders_history",
            OrderHistoryPage,
            {"oid": "8", "assetId": 602, "children": []},
        ),
        ("fills", FillsPage, {"tradeId": "9", "assetId": 602}),
    )
    for method_name, page_type, row in cases:
        client, http = client_for([{"nextCursor": "opaque", "hasMore": True, "data": [row]}])
        result = getattr(client.trade, method_name)()
        assert isinstance(result[0], page_type)
        assert result[0].next_cursor == "opaque"
        assert result[0].has_more is True
        assert result[0].data[0].asset_id == 602
        http.close()


def test_bills_use_data_zero_cursor_page_and_numeric_account_asset_ids() -> None:
    bills_client, bills_http = client_for(
        [{"nextCursor": None, "hasMore": False, "data": [{"billId": "1", "assetId": 602}]}]
    )
    bills = bills_client.account.bills()
    assert isinstance(bills[0], BillsPage)
    assert bills[0].has_more is False
    assert bills[0].data[0].asset_id == 602
    bills_http.close()


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
    client, http = client_for([{"code": "0", "serverTimestamp": "1000", "expiresAfter": "61000"}])
    result = client.trade.cancel_all_after({"action": {"type": "noop"}, "nonce": 1})
    assert isinstance(result[0], WriteResult)
    assert result[0].expires_after == "61000"
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


def test_user_fills_channel_is_a_direct_list_not_an_invented_wrapper() -> None:
    fills = channel("exchangeos-user-fills", [{"tradeId": "1", "price": "2"}])
    assert fills[0].trade_id == "1"
