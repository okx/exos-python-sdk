from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest

from exos_python_sdk import (
    Chain,
    ClientOptions,
    Environment,
    ExchangeOSClient,
    LoggingPolicy,
    RestList,
    RestObject,
    RetryPolicy,
    Ticker,
)
from exos_python_sdk.exceptions import ConfigurationError, TransportError, ValidationError
from exos_python_sdk.models import (
    FillDir,
    FillDirection,
    MarketType,
    OrderState,
    TimeInForce,
    as_decimal,
    as_utc_datetime,
)

TEST_ENVIRONMENT = Environment.custom(
    name="test",
    rest_url="http://localhost",
    websocket_url="ws://localhost/ws",
    signing_chain=Chain.TESTNET,
)


def make_client(handler, **kwargs):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = ExchangeOSClient(environment=TEST_ENVIRONMENT, http_client=http, **kwargs)
    return client, http


def test_response_models_preserve_precision_unknown_fields_and_raw_envelope() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"X-Request-ID": "response-model"},
            json={
                "code": "0",
                "data": [
                    {
                        "price": "0.000000000000000001",
                        "ts": 1_700_000_000_123,
                        "future": {"serverAdded": True},
                    }
                ],
                "futureEnvelope": "preserved",
            },
        )

    client, http = make_client(handler, options=ClientOptions(preserve_raw_response=True))
    result = client.market.tickers(market_type="perp")
    assert isinstance(result, RestList)
    assert isinstance(result[0], RestObject)
    assert result[0]["price"] == "0.000000000000000001"
    assert result[0].decimal("price") == Decimal("0.000000000000000001")
    assert result[0]["ts"] == 1_700_000_000_123
    assert result[0].utc_datetime("ts") == datetime(
        2023, 11, 14, 22, 13, 20, 123000, tzinfo=timezone.utc
    )
    assert result[0]["future"] == {"serverAdded": True}
    assert result.raw_response is not None
    assert result.raw_response["futureEnvelope"] == "preserved"
    http.close()


def test_typed_response_models_remain_builtin_container_compatible() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "0", "data": [{"value": "1.2"}]})

    client, http = make_client(handler)
    result = client.market.tickers(market_type="perp")
    assert isinstance(result, list)
    assert isinstance(result[0], Ticker)
    assert isinstance(result[0], dict)
    http.close()


def test_decimal_and_timestamp_helpers_reject_lossy_or_invalid_values() -> None:
    assert as_decimal("1234567890.123456789012345678") == Decimal("1234567890.123456789012345678")
    assert as_utc_datetime(0) == datetime(1970, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValidationError):
        as_decimal(0.1)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        as_utc_datetime("not-a-timestamp")


def test_open_enums_retain_unknown_server_strings() -> None:
    assert MarketType("future-market") == "future-market"
    assert MarketType("future-market").value == "future-market"
    assert str(MarketType("future-market")) == "future-market"
    assert OrderState("new-server-state").value == "new-server-state"


def test_rest_order_enums_match_the_openapi_wire_vocabulary() -> None:
    assert {state.value for state in OrderState} == {
        "open",
        "partially_filled",
        "modified",
        "filled",
        "triggered",
        "triggered_and_failed",
        "failed",
        "canceled",
        "part_filled_canceled",
    }
    assert {value.value for value in TimeInForce} == {"gtc", "ioc", "fok", "alo", "gtd"}
    assert TimeInForce.POST_ONLY is TimeInForce.ALO


def test_fill_direction_enum_matches_websocket_wire_vocabulary() -> None:
    expected = {
        "Buy",
        "Sell",
        "BuySplit",
        "SellMerge",
        "BackstopLiquidation",
        "BackstopLiquidator",
        "Adl",
        "AdlOpponent",
        "AdlPreviousPrice",
        "AdlOpponentPreviousPrice",
        "NetLiquidation",
        "NetAdl",
        "Settlement",
        "Open",
        "Close",
        "ReverseOpen",
        "DecimalAdjustSettle",
        "DecimalAdjustTakeover",
    }
    assert {direction.value for direction in FillDirection} == expected
    assert FillDir is FillDirection
    assert FillDirection("future-direction").value == "future-direction"


def test_rest_hook_receives_safe_start_and_end_metadata() -> None:
    events = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == "hook-test/1"
        return httpx.Response(
            200,
            headers={"X-Request-ID": "hook-request"},
            json={"code": "0", "data": []},
        )

    def hook(event) -> None:
        events.append(event)

    client, http = make_client(
        handler,
        options=ClientOptions(rest_event_hook=hook, user_agent="hook-test/1"),
    )
    client.market.tickers(asset_id="payload-marker")
    assert [event.name for event in events] == ["request_start", "request_end"]
    assert events[0].method == "GET"
    assert events[0].path == "/api/v5/exchangeos/market/tickers"
    assert events[0].request_body_bytes == 0
    assert events[0].auth_mode == "none"
    assert events[1].status_code == 200
    assert events[1].request_id == "hook-request"
    assert events[1].latency_ms is not None
    assert "payload-marker" not in repr(events)
    http.close()


def test_rest_hook_marks_terminal_transport_error() -> None:
    events = []

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client, http = make_client(
        handler,
        options=ClientOptions(retry=RetryPolicy(0), rest_event_hook=events.append),
    )
    with pytest.raises(TransportError):
        client.market.tickers(market_type="perp")
    assert [event.name for event in events] == ["request_start", "request_end"]
    assert events[-1].error_type == "TransportError"
    assert events[-1].status_code is None
    http.close()


def test_owned_client_applies_httpx_timeout_proxy_and_user_agent() -> None:
    client = ExchangeOSClient(
        environment=TEST_ENVIRONMENT,
        options=ClientOptions(
            timeout=httpx.Timeout(9, connect=1, read=2, write=3, pool=4),
            proxy="http://localhost:8080",
            user_agent="example-client/2",
        ),
    )
    assert client._http.timeout.connect == 1
    assert client._http.timeout.read == 2
    assert client._http.timeout.write == 3
    assert client._http.timeout.pool == 4
    assert client._http.headers["User-Agent"] == "example-client/2"
    client.close()


@pytest.mark.parametrize(
    "options",
    [
        ClientOptions(timeout=0),
        ClientOptions(timeout=True),
        ClientOptions(timeout="10"),  # type: ignore[arg-type]
        ClientOptions(user_agent=""),
        ClientOptions(user_agent="bad\nheader"),
        ClientOptions(logging_policy="verbose"),
        ClientOptions(proxy="not-an-absolute-url"),
        ClientOptions(retry=RetryPolicy(max_retries=-1)),
        ClientOptions(retry=RetryPolicy(backoff=-1)),
    ],
)
def test_extended_client_configuration_is_validated(options) -> None:
    with pytest.raises(ConfigurationError):
        ExchangeOSClient(options=options)


def test_caller_owned_http_client_rejects_ignored_transport_options() -> None:
    http = httpx.Client()
    try:
        with pytest.raises(ConfigurationError, match="caller-supplied"):
            ExchangeOSClient(http_client=http, options=ClientOptions(timeout=2))
        with pytest.raises(ConfigurationError, match="caller-supplied"):
            ExchangeOSClient(
                http_client=http,
                options=ClientOptions(proxy="http://localhost:8080"),
            )
    finally:
        http.close()


def test_metadata_logging_never_contains_query_values_or_response_payload(caplog) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "0", "data": {"marker": "response-marker"}})

    client, http = make_client(handler, options=ClientOptions(logging_policy=LoggingPolicy.DEBUG))
    with caplog.at_level("DEBUG", logger="exos_python_sdk.rest"):
        client.market.tickers(asset_id="query-marker")
    rendered = caplog.text
    assert "request_start" in rendered
    assert "request_end" in rendered
    assert "body_bytes=0" in rendered
    assert "auth_mode=none" in rendered
    assert "query-marker" not in rendered
    assert "response-marker" not in rendered
    http.close()
