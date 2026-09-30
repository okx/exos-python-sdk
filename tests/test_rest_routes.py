from typing import Any

import pytest

from exchangeos_sdk.api import (
    ACCOUNT_ENDPOINTS,
    MARKET_ENDPOINTS,
    TRADE_ENDPOINTS,
    AccountAPI,
    MarketAPI,
    TradeAPI,
)
from exchangeos_sdk.exceptions import ValidationError


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bool, dict[str, Any], Any]] = []

    def request(self, method, path, *, params=None, json_body=None, auth=True):
        self.calls.append((method, path, auth, params or {}, json_body))
        return {"path": path}


def routes(recorder: Recorder):
    return [(method, path, auth) for method, path, auth, _, _ in recorder.calls]


def test_market_inventory_contains_exactly_thirteen_public_routes() -> None:
    recorder = Recorder()
    api = MarketAPI(recorder)  # type: ignore[arg-type]
    api.token_info()
    api.instruments(market_type="perp")
    api.tickers(asset_id=602)
    api.order_book(602, depth=20)
    api.candles(602, bar="1m", limit=100, begin=1, end=2)
    api.mark_prices(asset_id=602)
    api.position_tiers(602)
    api.funding_rate_history(602)
    api.funding_rate(asset_id=602)
    api.open_interest(asset_id=602)
    api.price_limit(602)
    api.index_tickers(asset_id=602)
    api.security_fund("securityFund", asset_id=602)
    assert len(MARKET_ENDPOINTS) == 13 == len(set(MARKET_ENDPOINTS))
    assert routes(recorder) == [
        ("GET", f"/api/v5/exchangeos/market/{path}", False)
        for path in (
            "token-info",
            "instruments",
            "tickers",
            "order-book",
            "candles",
            "mark-prices",
            "position-tiers",
            "funding-rate-history",
            "funding-rate",
            "open-interest",
            "price-limit",
            "index-tickers",
            "security-fund",
        )
    ]
    assert recorder.calls[1][3] == {"marketType": "perp", "assetId": None}
    assert recorder.calls[12][3] == {"fundType": "securityFund", "assetId": 602}


def test_trade_inventory_contains_exactly_ten_authenticated_routes() -> None:
    recorder = Recorder()
    api = TradeAPI(recorder)  # type: ignore[arg-type]
    place_tx = {"action": {"type": "placeOrder", "orders": [{"marketType": "spot"}]}, "nonce": 1}
    cancel_tx = {"action": {"type": "cancel", "cancels": [{"marketType": "spot"}]}, "nonce": 2}
    noop_tx = {"action": {"type": "noop"}, "nonce": 3}
    modify_tx = {"action": {"type": "modify", "modifies": [{"oid": "1"}]}, "nonce": 3}
    cancel_all_tx = {"action": {"type": "cancelAll", "marketType": "spot"}, "nonce": 4}
    api.place_order(place_tx)
    api.cancel_order(cancel_tx)
    api.noop(noop_tx)
    api.modify_order(modify_tx)
    api.cancel_all_after(cancel_all_tx)
    api.transaction("0xhash")
    api.order(client_order_id="cloid", vault_address="0xvault")
    api.orders_pending(
        point_board=True, asset_id=602, cursor="next-0", limit=25, vault_address="0xvault"
    )
    api.orders_history(
        point_board=False,
        asset_id=602,
        state="filled",
        begin=1,
        end=2,
        cursor="next-1",
        limit=50,
    )
    api.fills(point_board=True, asset_id=602, begin=1, end=2, cursor="next-2", limit=50)
    assert len(TRADE_ENDPOINTS) == 10 == len(set(TRADE_ENDPOINTS))
    assert routes(recorder) == [
        ("POST", "/api/v5/exchangeos/trade/place-order", True),
        ("POST", "/api/v5/exchangeos/trade/cancel-order", True),
        ("POST", "/api/v5/exchangeos/trade/noop", True),
        ("POST", "/api/v5/exchangeos/trade/modify-order", True),
        ("POST", "/api/v5/exchangeos/trade/cancel-all-after", True),
        ("GET", "/api/v5/exchangeos/trade/transaction", True),
        ("GET", "/api/v5/exchangeos/trade/order", True),
        ("GET", "/api/v5/exchangeos/trade/orders-pending", True),
        ("GET", "/api/v5/exchangeos/trade/orders-history", True),
        ("GET", "/api/v5/exchangeos/trade/fills", True),
    ]
    assert recorder.calls[0][4] is place_tx
    assert recorder.calls[6][3] == {
        "oid": None,
        "clientOrderId": "cloid",
        "vaultAddress": "0xvault",
    }
    assert recorder.calls[7][3] == {
        "pointBoard": True,
        "assetId": 602,
        "cursor": "next-0",
        "limit": 25,
        "vaultAddress": "0xvault",
    }
    assert recorder.calls[8][3] == {
        "pointBoard": False,
        "assetId": 602,
        "state": "filled",
        "begin": 1,
        "end": 2,
        "cursor": "next-1",
        "limit": 50,
        "vaultAddress": None,
    }


def test_account_inventory_contains_exactly_fifteen_authenticated_routes() -> None:
    recorder = Recorder()
    api = AccountAPI(recorder)  # type: ignore[arg-type]
    api.account_transfer({"action": {"type": "subAccountTransfer"}, "nonce": 1})
    api.create_sub_account({"action": {"type": "createSubAccount"}, "nonce": 2})
    api.set_leverage({"action": {"type": "updateLeverage"}, "nonce": 3})
    api.set_margin_mode({"action": {"type": "updateMarginMode"}, "nonce": 4})
    api.set_position_mode({"action": {"type": "updatePositionMode"}, "nonce": 5})
    api.adjust_isolated_margin({"action": {"type": "updateIsolatedMargin"}, "nonce": 6})
    api.balance(vault_address="0xvault", point_board=True)
    api.positions(asset_id=602, vault_address="0xvault", point_board=False)
    api.max_size(602, price="0.123456789012345678", reduce_only=True)
    api.position_tiers(602, vault_address="0xvault")
    api.leverage_info(602, position_side="long", vault_address="0xvault")
    api.trade_fee(602)
    api.limits(vault_address="0xvault")
    api.bills(
        token_id="1",
        flow_category="trade",
        begin=1,
        end=2,
        cursor="next",
        limit=25,
        point_board=True,
    )
    api.detail()
    assert len(ACCOUNT_ENDPOINTS) == 15 == len(set(ACCOUNT_ENDPOINTS))
    assert routes(recorder) == [
        (verb, f"/api/v5/exchangeos/account/{path}", True)
        for verb, path in (
            ("POST", "account-transfer"),
            ("POST", "create-sub-account"),
            ("POST", "set-leverage"),
            ("POST", "set-margin-mode"),
            ("POST", "set-position-mode"),
            ("POST", "adjust-isolated-margin"),
            ("GET", "balance"),
            ("GET", "positions"),
            ("GET", "max-size"),
            ("GET", "position-tiers"),
            ("GET", "leverage-info"),
            ("GET", "trade-fee"),
            ("GET", "limits"),
            ("GET", "bills"),
            ("GET", "detail"),
        )
    ]
    assert recorder.calls[8][3]["price"] == "0.123456789012345678"
    assert recorder.calls[8][3]["reduceOnly"] == "true"
    assert recorder.calls[6][3] == {"vaultAddress": "0xvault", "pointBoard": True}
    assert recorder.calls[7][3] == {
        "assetId": 602,
        "vaultAddress": "0xvault",
        "pointBoard": False,
    }
    assert recorder.calls[12][3] == {"vaultAddress": "0xvault"}
    assert recorder.calls[13][3] == {
        "tokenId": "1",
        "assetId": None,
        "flowCategory": "trade",
        "billType": None,
        "begin": 1,
        "end": 2,
        "cursor": "next",
        "limit": 25,
        "vaultAddress": None,
        "pointBoard": True,
    }


def test_trade_order_forwards_identifier_combinations_to_backend() -> None:
    recorder = Recorder()
    api = TradeAPI(recorder)  # type: ignore[arg-type]
    api.order()
    api.order(oid="1", client_order_id="cloid")
    assert len(recorder.calls) == 2
    assert recorder.calls[0][3] == {"oid": None, "clientOrderId": None, "vaultAddress": None}
    assert recorder.calls[1][3] == {"oid": "1", "clientOrderId": "cloid", "vaultAddress": None}


def test_tickers_forwards_missing_selector_to_backend() -> None:
    recorder = Recorder()
    market = MarketAPI(recorder)  # type: ignore[arg-type]

    market.tickers()
    assert recorder.calls[0][3] == {"marketType": None, "assetId": None}


def test_instruments_forwards_market_type_and_asset_id_together() -> None:
    recorder = Recorder()
    market = MarketAPI(recorder)  # type: ignore[arg-type]

    market.instruments(market_type="spot", asset_id="252201")
    assert recorder.calls[0][3] == {"marketType": "spot", "assetId": "252201"}


def test_tickers_supports_market_or_single_asset_queries() -> None:
    recorder = Recorder()
    market = MarketAPI(recorder)  # type: ignore[arg-type]

    market.tickers(asset_id=602)
    market.tickers(market_type="perp")
    market.tickers(market_type="perp", asset_id=602)
    assert len(recorder.calls) == 3
    assert recorder.calls[0][3] == {"marketType": None, "assetId": 602}
    assert recorder.calls[1][3] == {"marketType": "perp", "assetId": None}
    assert recorder.calls[2][3] == {"marketType": "perp", "assetId": 602}


def test_business_parameter_values_are_forwarded_to_the_server() -> None:
    recorder = Recorder()
    market = MarketAPI(recorder)  # type: ignore[arg-type]
    trade = TradeAPI(recorder)  # type: ignore[arg-type]
    account = AccountAPI(recorder)  # type: ignore[arg-type]

    market.order_book("server-validates", depth=401)
    market.candles(602, bar="future-bar", begin=2, end=1)
    market.funding_rate_history(602, limit=101, cursor=" ")
    trade.transaction("server-validates")
    trade.orders_history(asset_id="future-id", state="future-state", begin=2, end=1)
    account.bills(limit=0, cursor=" ")

    assert len(recorder.calls) == 6
    assert recorder.calls[0][3] == {"assetId": "server-validates", "depth": 401}
    assert recorder.calls[2][3]["limit"] == 101
    assert recorder.calls[4][3]["state"] == "future-state"
    assert recorder.calls[5][3]["limit"] == 0
    assert recorder.calls[5][3]["cursor"] == " "


def test_write_body_must_be_mapping_or_signed_transaction() -> None:
    recorder = Recorder()
    api = TradeAPI(recorder)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        api.place_order(object())
    assert recorder.calls == []


def test_write_body_accepts_to_wire_without_coercing_values() -> None:
    class Signed:
        def to_wire(self):
            return {
                "action": {
                    "type": "placeOrder",
                    "orders": [{"marketType": "spot", "price": "0.000000000000000001"}],
                },
                "nonce": 7,
            }

    recorder = Recorder()
    api = TradeAPI(recorder)  # type: ignore[arg-type]
    api.place_order(Signed())
    assert recorder.calls[0][4]["action"]["orders"][0]["price"] == "0.000000000000000001"


def test_place_order_forwards_missing_market_type_to_backend() -> None:
    class Signed:
        def to_wire(self):
            return {
                "action": {
                    "type": "placeOrder",
                    "orders": [{"assetId": "1", "price": "2", "size": "3"}],
                },
                "nonce": 7,
            }

    recorder = Recorder()
    api = TradeAPI(recorder)  # type: ignore[arg-type]
    api.place_order(Signed())
    assert "marketType" not in recorder.calls[0][4]["action"]["orders"][0]


def test_cancel_order_allows_omitted_market_type() -> None:
    class Signed:
        def to_wire(self):
            return {
                "action": {
                    "type": "cancel",
                    "cancels": [{"assetId": "1", "oid": "7"}],
                },
                "nonce": 7,
            }

    recorder = Recorder()
    api = TradeAPI(recorder)  # type: ignore[arg-type]
    api.cancel_order(Signed())
    assert "marketType" not in recorder.calls[0][4]["action"]["cancels"][0]


def test_write_body_rejects_invalid_to_wire_result() -> None:
    class InvalidSigned:
        def to_wire(self):
            return ["not", "an", "envelope"]

    recorder = Recorder()
    api = TradeAPI(recorder)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        api.place_order(InvalidSigned())
    assert recorder.calls == []


@pytest.mark.parametrize(
    ("method", "transaction"),
    (
        (
            "place_order",
            {
                "action": {
                    "type": "placeOrder",
                    "orders": [{"marketType": "prediction"}],
                },
                "nonce": 1,
            },
        ),
        (
            "cancel_order",
            {"action": {"type": "cancel", "cancels": [{"marketType": "prediction"}]}, "nonce": 1},
        ),
        (
            "cancel_all_after",
            {"action": {"type": "cancelAll", "marketType": "prediction"}, "nonce": 1},
        ),
    ),
)
def test_trade_writes_forward_market_types_to_backend(
    method: str, transaction: dict[str, Any]
) -> None:
    recorder = Recorder()
    api = TradeAPI(recorder)  # type: ignore[arg-type]

    getattr(api, method)(transaction)
    assert recorder.calls[0][4] == transaction


def test_signed_rest_writes_reject_an_action_for_another_endpoint_before_io() -> None:
    recorder = Recorder()
    account = AccountAPI(recorder)  # type: ignore[arg-type]
    trade = TradeAPI(recorder)  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="createSubAccount"):
        account.create_sub_account({"action": {"type": "predictionSplit"}, "nonce": 1})
    with pytest.raises(ValidationError, match="noop"):
        trade.noop({"action": {"type": "placeOrder"}, "nonce": 2})

    assert recorder.calls == []
