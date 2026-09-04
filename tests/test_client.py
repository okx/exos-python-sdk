import json

import httpx
import pytest

from exchangeos_sdk import (
    APIError,
    BearerAuth,
    Chain,
    ClientOptions,
    Credentials,
    Environment,
    ExchangeOSClient,
    RestMarketType,
    RetryPolicy,
)
from exchangeos_sdk.auth import sign_request
from exchangeos_sdk.exceptions import (
    AuthenticationError,
    ConfigurationError,
    RateLimitError,
    SerializationError,
    TransportError,
    ValidationError,
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


def test_public_market_request_uses_exchangeos_route_without_auth() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v5/exchangeos/market/instruments"
        assert request.url.params["marketType"] == "perp"
        assert "OK-ACCESS-KEY" not in request.headers
        return httpx.Response(
            200, json={"code": "0", "msg": "", "data": [{"markPx": "0.123456789012345678"}]}
        )

    client, http = make_client(handler)
    assert client.market.instruments(market_type=RestMarketType.PERP) == [
        {"markPx": "0.123456789012345678"}
    ]
    http.close()


def test_client_exposes_only_spot_and_perps_rest_resources() -> None:
    client, http = make_client(lambda _: httpx.Response(200, json={"code": "0", "data": []}))
    assert all(hasattr(client, resource) for resource in ("market", "trade", "account"))
    assert not hasattr(client, "outcomes")
    assert not hasattr(client, "prediction")
    http.close()


def test_query_is_included_in_request_signature() -> None:
    credentials = Credentials("id", "runtime-test-secret", "passphrase")

    def handler(request: httpx.Request) -> httpx.Response:
        signed_path = request.url.raw_path.decode("ascii")
        expected = sign_request(
            credentials.secret_key,
            request.headers["OK-ACCESS-TIMESTAMP"],
            "GET",
            signed_path,
        )
        assert request.headers["OK-ACCESS-SIGN"] == expected
        assert signed_path == "/api/v5/exchangeos/account/bills?tokenId=7&limit=25"
        return httpx.Response(200, json={"code": "0", "data": []})

    client, http = make_client(handler, auth=credentials)
    client.account.bills(token_id="7", limit=25)
    http.close()


def test_authenticated_body_is_exactly_the_signed_body() -> None:
    body = {
        "action": {
            "type": "cancelAll",
            "marketType": "perp",
            "size": "1.000000000000000001",
        },
        "nonce": 1,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["OK-ACCESS-KEY"] == "id"
        assert request.content.decode() == json.dumps(body, separators=(",", ":"))
        return httpx.Response(200, json={"code": "0", "data": [{"txHash": "0xresult"}]})

    client, http = make_client(handler, auth=Credentials("id", "runtime-test-secret", "passphrase"))
    assert client.trade.cancel_all_after(body) == [{"txHash": "0xresult"}]
    http.close()


def test_private_request_without_credentials_fails_before_io() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"code": "0", "data": []})

    client, http = make_client(handler)
    with pytest.raises(AuthenticationError):
        client.account.balance()
    assert calls == 0
    http.close()


def test_business_error_retains_request_metadata_and_unknown_data() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            headers={"X-Request-ID": "req-123"},
            json={
                "code": "80030",
                "msg": "illegal parameter",
                "data": {"newServerField": {"nested": True}},
                "futureEnvelopeField": "kept in response",
            },
        )

    client, http = make_client(handler)
    with pytest.raises(APIError) as caught:
        client.market.order_book("bad")
    error = caught.value
    assert error.code == "80030"
    assert error.status_code == 400
    assert error.request_id == "req-123"
    assert error.data == {"newServerField": {"nested": True}}
    assert error.response["futureEnvelopeField"] == "kept in response"
    assert "req-123" in str(error)
    http.close()


def test_rate_limit_error_retains_retry_after() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "1.5", "OK-Request-ID": "rate-id"},
            json={"code": "50011", "msg": "rate limited", "data": []},
        )

    client, http = make_client(handler, options=ClientOptions(retry=RetryPolicy(0)))
    with pytest.raises(RateLimitError) as caught:
        client.market.tickers(market_type="perp")
    assert caught.value.retry_after == 1.5
    assert caught.value.request_id == "rate-id"
    http.close()


def test_rejected_credentials_raise_authentication_error_with_metadata() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            headers={"X-Request-ID": "auth-id"},
            json={"code": "50113", "msg": "invalid signature", "data": None},
        )

    client, http = make_client(
        handler,
        auth=Credentials("id", "runtime-test-secret", "passphrase"),
        options=ClientOptions(retry=RetryPolicy(0)),
    )
    with pytest.raises(AuthenticationError) as caught:
        client.account.balance()
    assert isinstance(caught.value, APIError)
    assert caught.value.code == "50113"
    assert caught.value.request_id == "auth-id"
    http.close()


def test_read_transport_error_retries_but_write_never_retries() -> None:
    read_calls = 0

    def read_handler(request: httpx.Request) -> httpx.Response:
        nonlocal read_calls
        read_calls += 1
        if read_calls == 1:
            raise httpx.ConnectError("temporary", request=request)
        return httpx.Response(200, json={"code": "0", "data": []})

    client, http = make_client(
        read_handler, options=ClientOptions(retry=RetryPolicy(max_retries=1, backoff=0))
    )
    client.market.tickers(market_type="perp")
    assert read_calls == 2
    http.close()

    write_calls = 0

    def write_handler(request: httpx.Request) -> httpx.Response:
        nonlocal write_calls
        write_calls += 1
        raise httpx.ReadTimeout("unknown outcome", request=request)

    client, http = make_client(
        write_handler,
        auth=Credentials("id", "runtime-test-secret", "passphrase"),
        options=ClientOptions(retry=RetryPolicy(max_retries=9, backoff=0)),
    )
    with pytest.raises(TransportError) as caught:
        client.trade.place_order(
            {"action": {"type": "placeOrder", "orders": [{"marketType": "spot"}]}, "nonce": 1}
        )
    assert write_calls == 1
    assert caught.value.method == "POST"
    http.close()


def test_non_json_response_is_serialization_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="upstream unavailable")

    client, http = make_client(handler, options=ClientOptions(retry=RetryPolicy(0)))
    with pytest.raises(SerializationError):
        client.market.tickers(market_type="perp")
    http.close()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"environment": "production"},
        {"options": ClientOptions(timeout=0)},
        {"options": ClientOptions(retry=RetryPolicy(-1))},
        {"auth": BearerAuth("")},
        {"auth": "unsupported"},
    ],
)
def test_invalid_configuration_is_rejected(kwargs) -> None:
    with pytest.raises(ConfigurationError):
        ExchangeOSClient(**kwargs)


def test_client_repr_does_not_expose_credentials_or_bearer() -> None:
    client = ExchangeOSClient(
        auth=Credentials("visible-id", "runtime-test-secret", "runtime-test-passphrase")
    )
    rendered = repr(client)
    assert "visible-id" not in rendered
    assert "runtime-test" not in rendered


def test_websocket_factory_inherits_client_auth_and_forwards_options() -> None:
    credentials = Credentials("id", "runtime-test-secret", "passphrase")
    client = ExchangeOSClient(environment=TEST_ENVIRONMENT, auth=credentials)
    websocket = client.websocket(queue_size=17)
    assert websocket.credentials is credentials
    assert websocket.bearer_token is None
    assert websocket.url == "ws://localhost/ws"
    assert websocket._outbox.maxsize == 17


def test_environment_supplies_rest_websocket_and_signing_chain(monkeypatch) -> None:
    captured = {}
    sentinel = object()

    def fake_sign(action, private_key, **kwargs):
        captured.update(action=action, private_key=private_key, **kwargs)
        return sentinel

    monkeypatch.setattr("exchangeos_sdk.client.sign_transaction_action", fake_sign)
    client = ExchangeOSClient(environment=TEST_ENVIRONMENT)
    assert client.base_url == "http://localhost"
    assert client.websocket().url == "ws://localhost/ws"
    assert client.sign_action({"type": "noop"}, b"unused", nonce=7) is sentinel
    assert captured["chain"] is Chain.TESTNET
    assert captured["nonce"] == 7
    with pytest.raises(ConfigurationError, match="selected by the client environment"):
        client.sign_action({"type": "noop"}, b"unused", chain=Chain.MAINNET)
    client.close()


def test_websocket_factory_explicit_identity_does_not_mix_client_credentials() -> None:
    client = ExchangeOSClient(
        environment=TEST_ENVIRONMENT,
        auth=Credentials("id", "runtime-test-secret", "passphrase"),
    )
    websocket = client.websocket(bearer_token="stream-token")
    assert websocket.credentials is None
    assert websocket.bearer_token == "stream-token"


def test_websocket_factory_rejects_url_outside_environment() -> None:
    client = ExchangeOSClient(environment=TEST_ENVIRONMENT)
    with pytest.raises(ConfigurationError, match="selected by the client environment"):
        client.websocket(url="wss://other.example/ws")


def test_owned_http_client_context_closes_and_sets_language() -> None:
    client = ExchangeOSClient(
        environment=TEST_ENVIRONMENT, options=ClientOptions(accept_language="zh-HK")
    )
    with client as entered:
        assert entered is client
        assert client._http.headers["Accept-Language"] == "zh-HK"
        assert not client._http.is_closed
    assert client._http.is_closed


def test_close_does_not_close_caller_owned_http_client() -> None:
    http = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200)))
    client = ExchangeOSClient(environment=TEST_ENVIRONMENT, http_client=http)
    client.close()
    assert not http.is_closed
    http.close()


def test_bearer_authentication_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer runtime-token"
        assert "OK-ACCESS-KEY" not in request.headers
        return httpx.Response(200, json={"data": {"ok": True}})

    client, http = make_client(handler, auth=BearerAuth("runtime-token"))
    assert client.account.balance() == {"ok": True}
    http.close()


def test_invalid_path_and_unserializable_body_fail_before_io() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200)

    client, http = make_client(handler)
    with pytest.raises(ValidationError):
        client.request("GET", "relative", auth=False)
    circular: list[object] = []
    circular.append(circular)
    with pytest.raises(SerializationError):
        client.request("POST", "/write", json_body=circular, auth=False)
    assert calls == 0
    http.close()


def test_read_retry_exhaustion_retains_safe_context(monkeypatch) -> None:
    calls = 0
    sleeps = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("contains-sensitive-query=value", request=request)

    def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("exchangeos_sdk.client.time.sleep", fake_sleep)
    client, http = make_client(
        handler, options=ClientOptions(retry=RetryPolicy(max_retries=2, backoff=0.5))
    )
    with pytest.raises(TransportError) as caught:
        client.request("GET", "/read", params={"secret": "value"}, auth=False)
    assert calls == 3
    assert sleeps == [0.5, 1.0]
    assert caught.value.method == "GET"
    assert caught.value.path == "/read"
    assert "sensitive" not in str(caught.value)
    http.close()


def test_429_invalid_retry_after_uses_backoff_then_succeeds(monkeypatch) -> None:
    calls = 0
    sleeps = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "not-a-number"},
                json={"code": "50011", "msg": "rate limited"},
            )
        return httpx.Response(200, json={"code": "0", "data": ["recovered"]})

    def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("exchangeos_sdk.client.time.sleep", fake_sleep)
    client, http = make_client(
        handler, options=ClientOptions(retry=RetryPolicy(max_retries=1, backoff=0.25))
    )
    assert client.market.tickers(market_type="perp") == ["recovered"]
    assert calls == 2
    assert sleeps == [0.25]
    http.close()


def test_non_object_json_envelope_is_rejected() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"code": "0"}])

    client, http = make_client(handler)
    with pytest.raises(SerializationError, match="JSON object"):
        client.market.tickers(market_type="perp")
    http.close()


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("OK-Request-ID", "ok-id"),
        ("X-Request-ID", "x-id"),
        ("Request-ID", "request-id"),
        ("Trace-ID", "trace-id"),
        (None, None),
    ],
)
def test_api_error_request_id_header_variants(header, expected) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        headers = {header: expected} if header is not None else {}
        return httpx.Response(400, headers=headers, json={"message": "failed"})

    client, http = make_client(handler)
    with pytest.raises(APIError) as caught:
        client.market.tickers(market_type="perp")
    assert caught.value.code == 400
    assert caught.value.message == "failed"
    assert caught.value.request_id == expected
    http.close()


def test_429_without_retry_after_exposes_none() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"code": "50011", "msg": "slow down"})

    client, http = make_client(handler, options=ClientOptions(retry=RetryPolicy(0)))
    with pytest.raises(RateLimitError) as caught:
        client.market.tickers(market_type="perp")
    assert caught.value.retry_after is None
    http.close()
