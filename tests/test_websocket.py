import asyncio
import json
from collections.abc import Sequence
from typing import Any

import pytest

from exos_python_sdk.auth import Credentials
from exos_python_sdk.exceptions import (
    AuthenticationError,
    TransportError,
    WebSocketProtocolError,
)
from exos_python_sdk.websocket import (
    EXCHANGEOS_PRIVATE_CHANNELS,
    EXCHANGEOS_PUBLIC_CHANNELS,
    ExchangeOSWebSocket,
)
from exos_python_sdk.websocket.messages import (
    ChannelDataMessage,
    ControlWebSocketMessage,
    RawWebSocketMessage,
    parse_message,
)


class FakeSocket:
    def __init__(self, incoming: Sequence[str] = ()) -> None:
        self.incoming: asyncio.Queue[Any] = asyncio.Queue()
        for item in incoming:
            self.incoming.put_nowait(item)
        self.sent: list[Any] = []
        self.closed = False

    async def send(self, payload: Any) -> None:
        self.sent.append(payload)
        if payload == "ping" and not self.closed:
            self.incoming.put_nowait("pong")

    async def recv(self) -> Any:
        return await self.incoming.get()

    async def close(self, *_: Any, **__: Any) -> None:
        self.closed = True
        self.incoming.put_nowait(StopAsyncIteration)

    def __aiter__(self) -> "FakeSocket":
        return self

    async def __anext__(self) -> Any:
        item = await self.incoming.get()
        if item is StopAsyncIteration:
            raise StopAsyncIteration
        return item


class FakeConnection:
    def __init__(self, socket: FakeSocket) -> None:
        self.socket = socket

    async def __aenter__(self) -> FakeSocket:
        return self.socket

    async def __aexit__(self, *_: Any) -> None:
        await self.socket.close()


class Connector:
    def __init__(self, sockets: Sequence[FakeSocket]) -> None:
        self.sockets = list(sockets)
        self.calls = 0
        self.kwargs: list[dict[str, Any]] = []

    def __call__(self, *_: Any, **kwargs: Any) -> FakeConnection:
        socket = self.sockets[min(self.calls, len(self.sockets) - 1)]
        self.calls += 1
        self.kwargs.append(kwargs)
        return FakeConnection(socket)


def frame(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"))


async def eventually(predicate: Any, *, timeout: float = 1.0) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0)


def test_channel_inventory_and_canonical_names() -> None:
    assert len(EXCHANGEOS_PUBLIC_CHANNELS) == 16
    assert len(EXCHANGEOS_PRIVATE_CHANNELS) == 9
    assert all(" " not in channel for channel in EXCHANGEOS_PUBLIC_CHANNELS)


def test_subscription_args_include_channel_first() -> None:
    assert ExchangeOSWebSocket._build_args("exchangeos-books", [{"assetId": "2"}]) == [
        {"channel": "exchangeos-books", "assetId": "2"}
    ]
    with pytest.raises(ValueError, match="without spaces"):
        ExchangeOSWebSocket._build_args("exchangeos- mark-price", None)


def test_estimated_price_requires_asset_id() -> None:
    assert ExchangeOSWebSocket._build_args("exchangeos-estimated-price", [{"assetId": "9102"}]) == [
        {"channel": "exchangeos-estimated-price", "assetId": "9102"}
    ]
    with pytest.raises(ValueError, match="requires parameter.*assetId"):
        ExchangeOSWebSocket._build_args("exchangeos-estimated-price", None)


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"url": "http://example.test"}, "must use WSS"),
        ({"url": "ws://localhost.example.com:9000"}, "must use WSS"),
        ({"url": "ws://127.0.0.1.example.com:9000"}, "must use WSS"),
        ({"ping_interval": 0}, "heartbeat intervals"),
        ({"pong_timeout": 0}, "heartbeat intervals"),
        ({"reconnect_min": -1}, "reconnect interval"),
        ({"reconnect_min": 2, "reconnect_max": 1}, "reconnect interval"),
        ({"max_reconnect_attempts": -1}, "cannot be negative"),
        ({"queue_size": 0}, "queue_size"),
        ({"overflow_policy": "invalid"}, "overflow_policy"),
    ],
)
def test_constructor_validation(kwargs: dict[str, Any], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        ExchangeOSWebSocket(**kwargs)


@pytest.mark.parametrize("url", ["ws://localhost:9000", "ws://127.0.0.1:9000", "ws://[::1]:9000"])
def test_constructor_allows_only_exact_loopback_hosts(url: str) -> None:
    ExchangeOSWebSocket(url=url)


def test_candle_family_and_subscription_key_properties() -> None:
    ExchangeOSWebSocket._validate_channel("exchangeos-candle1m", private=False)
    ExchangeOSWebSocket._validate_channel("exchangeos-candle1D", private=False)
    ws = ExchangeOSWebSocket()
    assert ws.subscriptions == ()
    assert ws.__aiter__() is ws
    with pytest.raises(ValueError, match="public channel"):
        ws._validate_channel("future-public", private=False)
    with pytest.raises(ValueError, match="private channel"):
        ws._validate_channel("exchangeos-tickers", private=True)
    with pytest.raises(ValueError, match="public channel"):
        ws._validate_channel("pm-candle1D", private=False)
    with pytest.raises(ValueError, match="private channel"):
        ws._validate_channel("exchangeos-notification", private=True)


@pytest.mark.parametrize(
    ("channel", "private"),
    [
        ("pm-books", False),
        ("pm-trades", False),
        ("pm-tickers", False),
        ("pm-event-status", False),
        ("pm-candle1m", False),
        ("pm-order", True),
        ("pm-position", True),
        ("pm-user-trade", True),
        ("pm-balance", True),
        ("pm-pnl", True),
    ],
)
def test_outcomes_channels_are_rejected(channel: str, private: bool) -> None:
    with pytest.raises(ValueError):
        ExchangeOSWebSocket._validate_channel(channel, private=private)


@pytest.mark.asyncio
async def test_public_subscribe_deduplicates_wire_frames() -> None:
    socket = FakeSocket()
    ws = ExchangeOSWebSocket(connector=Connector([socket]), ping_interval=60)
    await ws.connect()
    await ws.subscribe_public("exchangeos-tickers", asset_id=2)
    await ws.subscribe_public("exchangeos-tickers", asset_id=2)
    assert [json.loads(item) for item in socket.sent] == [
        {"op": "subscribe", "args": [{"channel": "exchangeos-tickers", "assetId": 2}]}
    ]
    await ws.close()


@pytest.mark.asyncio
async def test_estimated_price_subscription_uses_asset_id_wire_name() -> None:
    socket = FakeSocket()
    ws = ExchangeOSWebSocket(connector=Connector([socket]), ping_interval=60)
    await ws.connect()
    await ws.subscribe_public("exchangeos-estimated-price", asset_id="9102")
    assert [json.loads(item) for item in socket.sent] == [
        {
            "op": "subscribe",
            "args": [{"channel": "exchangeos-estimated-price", "assetId": "9102"}],
        }
    ]
    await ws.close()


@pytest.mark.asyncio
async def test_estimated_price_subscription_replays_after_reconnect(monkeypatch: Any) -> None:
    first, second = FakeSocket(), FakeSocket()
    connector = Connector([first, second])
    monkeypatch.setattr("exos_python_sdk.websocket.transport.random.uniform", lambda *_: 0)
    ws = ExchangeOSWebSocket(
        connector=connector,
        ping_interval=60,
        reconnect_min=0,
        reconnect_max=0,
    )
    await ws.connect()
    await ws.subscribe_public("exchangeos-estimated-price", asset_id="9102")
    await first.close()
    await eventually(lambda: connector.calls >= 2 and ws.connected)
    assert [json.loads(item) for item in second.sent] == [
        {
            "op": "subscribe",
            "args": [{"channel": "exchangeos-estimated-price", "assetId": "9102"}],
        }
    ]
    await ws.close()


@pytest.mark.asyncio
async def test_private_login_precedes_subscription_and_retains_vault() -> None:
    socket = FakeSocket([frame({"event": "login-wallet", "code": "0"})])
    credentials = Credentials(api_key="key", secret_key="secret", passphrase="pass")
    ws = ExchangeOSWebSocket(
        connector=Connector([socket]), credentials=credentials, ping_interval=60
    )
    await ws.connect()
    await ws.subscribe_private("exchangeos-user-order-status", vault_address="0x123", assetId=7)
    decoded = [json.loads(item) for item in socket.sent]
    assert decoded[0]["op"] == "login-wallet"
    assert decoded[1] == {
        "op": "subscribe",
        "args": [
            {
                "channel": "exchangeos-user-order-status",
                "assetId": 7,
                "vaultAddress": "0x123",
            }
        ],
    }
    assert ws.authenticated
    await ws.close()


@pytest.mark.asyncio
async def test_private_subscribe_without_auth_is_rejected() -> None:
    socket = FakeSocket()
    ws = ExchangeOSWebSocket(connector=Connector([socket]), ping_interval=60)
    await ws.connect()
    with pytest.raises(AuthenticationError):
        await ws.subscribe_private("exchangeos-orders")
    assert socket.sent == []
    await ws.close()


@pytest.mark.asyncio
async def test_reconnect_replays_once_with_vault(monkeypatch: Any) -> None:
    first = FakeSocket([frame({"event": "login-wallet", "code": "0"})])
    second = FakeSocket([frame({"event": "login-wallet", "code": "0"})])
    connector = Connector([first, second])
    credentials = Credentials(api_key="key", secret_key="secret", passphrase="pass")
    monkeypatch.setattr("exos_python_sdk.websocket.transport.random.uniform", lambda *_: 0)
    ws = ExchangeOSWebSocket(
        connector=connector,
        credentials=credentials,
        ping_interval=60,
        reconnect_min=0,
        reconnect_max=0,
    )
    await ws.connect()
    await ws.subscribe_private("exchangeos-account", vault_address="0xabc")
    await ws.subscribe_private("exchangeos-account", vault_address="0xabc")
    await first.close()
    await eventually(lambda: connector.calls >= 2 and ws.connected)
    replay = [json.loads(item) for item in second.sent]
    assert [item["op"] for item in replay] == ["login-wallet", "subscribe"]
    assert replay[1]["args"] == [{"channel": "exchangeos-account", "vaultAddress": "0xabc"}]
    await ws.close()


@pytest.mark.asyncio
async def test_one_hundred_disconnects_replay_exactly_once(monkeypatch: Any) -> None:
    sockets = [FakeSocket() for _ in range(101)]
    connector = Connector(sockets)
    monkeypatch.setattr("exos_python_sdk.websocket.transport.random.uniform", lambda *_: 0)
    ws = ExchangeOSWebSocket(
        connector=connector,
        ping_interval=60,
        reconnect_min=0,
        reconnect_max=0,
    )
    await ws.connect()
    await ws.subscribe_public("exchangeos-trades", asset_id=77)
    for index in range(100):
        await sockets[index].close()
        expected_calls = index + 2
        await eventually(
            lambda expected_calls=expected_calls: connector.calls >= expected_calls and ws.connected
        )
    for socket in sockets[1:]:
        frames = [json.loads(item) for item in socket.sent]
        assert frames == [
            {"op": "subscribe", "args": [{"channel": "exchangeos-trades", "assetId": 77}]}
        ]
    await ws.close()


@pytest.mark.asyncio
async def test_retry_cap_resets_after_each_successful_reconnect(monkeypatch: Any) -> None:
    sockets = [FakeSocket(), FakeSocket(), FakeSocket()]
    connector = Connector(sockets)
    monkeypatch.setattr("exos_python_sdk.websocket.transport.random.uniform", lambda *_: 0)
    ws = ExchangeOSWebSocket(
        connector=connector,
        ping_interval=60,
        reconnect_min=0,
        reconnect_max=0,
        max_reconnect_attempts=1,
    )
    await ws.connect()
    await sockets[0].close()
    await eventually(lambda: connector.calls == 2)
    await sockets[1].close()
    await eventually(lambda: connector.calls == 3 and ws.connected)
    assert ws._runner is not None and not ws._runner.done()
    await ws.close()


@pytest.mark.asyncio
async def test_retry_cap_stops_consecutive_connection_failures(monkeypatch: Any) -> None:
    socket = FakeSocket()

    class FailingConnection:
        async def __aenter__(self) -> FakeSocket:
            raise OSError("connect failed")

        async def __aexit__(self, *_: Any) -> None:
            return None

    calls = 0

    def connector(*_: Any, **__: Any) -> FakeConnection | FailingConnection:
        nonlocal calls
        calls += 1
        return FakeConnection(socket) if calls == 1 else FailingConnection()

    monkeypatch.setattr("exos_python_sdk.websocket.transport.random.uniform", lambda *_: 0)
    ws = ExchangeOSWebSocket(
        connector=connector,
        ping_interval=60,
        reconnect_min=0,
        reconnect_max=0,
        max_reconnect_attempts=1,
    )
    await ws.connect()
    await socket.close()
    await eventually(lambda: ws._runner is not None and ws._runner.done())
    assert calls == 2
    await ws.close()


@pytest.mark.asyncio
async def test_heartbeat_timeout_causes_reconnect(monkeypatch: Any) -> None:
    class SilentSocket(FakeSocket):
        async def send(self, payload: Any) -> None:
            self.sent.append(payload)

    first, second = SilentSocket(), FakeSocket()
    connector = Connector([first, second])
    monkeypatch.setattr("exos_python_sdk.websocket.transport.random.uniform", lambda *_: 0)
    ws = ExchangeOSWebSocket(
        connector=connector,
        ping_interval=0.001,
        pong_timeout=0.001,
        reconnect_min=0,
        reconnect_max=0,
    )
    await ws.connect()
    await eventually(lambda: connector.calls >= 2)
    assert "ping" in first.sent
    await ws.close()


@pytest.mark.asyncio
async def test_close_does_not_reconnect() -> None:
    socket = FakeSocket()
    connector = Connector([socket])
    ws = ExchangeOSWebSocket(connector=connector, ping_interval=60, reconnect_min=0)
    await ws.connect()
    await ws.close()
    await asyncio.sleep(0)
    assert connector.calls == 1
    assert socket.closed


@pytest.mark.asyncio
async def test_unknown_message_is_delivered_as_raw_json_string_callback() -> None:
    raw = frame({"arg": {"channel": "future-channel"}, "data": [{"new": True}]})
    received: list[str] = []
    socket = FakeSocket([raw])
    ws = ExchangeOSWebSocket(
        connector=Connector([socket]), ping_interval=60, message_callback=received.append
    )
    await ws.connect()
    message = await anext(ws)
    assert message == raw
    assert received == [raw]
    await ws.close()


@pytest.mark.asyncio
async def test_async_message_callback_receives_exact_wire_text() -> None:
    raw = frame(
        {
            "arg": {"channel": "exchangeos-trades", "assetId": "7"},
            "data": [{"px": "1.25"}],
            "futureField": {"nested": True},
        }
    )
    received: list[str] = []

    async def callback(message: str) -> None:
        received.append(message)

    socket = FakeSocket([raw])
    ws = ExchangeOSWebSocket(
        connector=Connector([socket]), ping_interval=60, message_callback=callback
    )
    await ws.connect()
    assert await anext(ws) == raw
    assert received == [raw]
    await ws.close()


@pytest.mark.asyncio
async def test_sequence_gap_emits_event_and_resubscribes() -> None:
    socket = FakeSocket()
    ws = ExchangeOSWebSocket(connector=Connector([socket]), ping_interval=60)
    await ws.connect()
    await ws.subscribe_public("exchangeos-books", asset_id=9)
    arg = {"channel": "exchangeos-books", "assetId": 9}
    socket.incoming.put_nowait(
        frame({"arg": arg, "action": "snapshot", "data": [{"seqId": 10, "prevSeqId": -1}]})
    )
    socket.incoming.put_nowait(
        frame({"arg": arg, "action": "update", "data": [{"seqId": 12, "prevSeqId": 8}]})
    )
    assert json.loads(await anext(ws))["action"] == "snapshot"
    gap = json.loads(await anext(ws))
    assert gap["event"] == "sequence-gap"
    assert gap["expectedPrevSeqId"] == 10
    assert gap["actualPrevSeqId"] == 8
    assert ws._outbox.empty()  # The discontinuous delta must never reach consumers.
    await eventually(lambda: len(socket.sent) >= 3)
    control = [json.loads(item) for item in socket.sent[-2:]]
    assert [item["op"] for item in control] == ["unsubscribe", "subscribe"]
    assert control[1]["args"] == [arg]
    await ws.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("policy", "expected"),
    [("drop_oldest", 2), ("drop_newest", 1)],
)
async def test_bounded_queue_overflow_policies(policy: str, expected: int) -> None:
    ws = ExchangeOSWebSocket(queue_size=1, overflow_policy=policy)  # type: ignore[arg-type]
    await ws._queue_message(frame({"value": 1}))
    await ws._queue_message(frame({"value": 2}))
    assert json.loads(await anext(ws))["value"] == expected


@pytest.mark.asyncio
async def test_bounded_queue_raise_policy() -> None:
    ws = ExchangeOSWebSocket(queue_size=1, overflow_policy="raise")
    await ws._queue_message(frame({"value": 1}))
    with pytest.raises(TransportError, match="queue overflow"):
        await ws._queue_message(frame({"value": 2}))


@pytest.mark.asyncio
async def test_close_wakes_waiting_iterator() -> None:
    ws = ExchangeOSWebSocket()
    pending = asyncio.create_task(anext(ws))
    await asyncio.sleep(0)
    await ws.close()
    with pytest.raises(StopAsyncIteration):
        await pending


@pytest.mark.asyncio
async def test_context_manager_and_closed_iterator() -> None:
    socket = FakeSocket()
    ws = ExchangeOSWebSocket(connector=Connector([socket]), ping_interval=60)
    async with ws as entered:
        assert entered is ws
        assert ws.connected
    assert not ws.connected
    with pytest.raises(StopAsyncIteration):
        await anext(ws)
    await ws.close()  # Idempotent.


@pytest.mark.asyncio
async def test_connect_timeout_closes_runner() -> None:
    class HangingConnection:
        async def __aenter__(self) -> FakeSocket:
            await asyncio.Future()
            raise AssertionError("unreachable")

        async def __aexit__(self, *_: Any) -> None:
            return None

    ws = ExchangeOSWebSocket(connector=lambda *_args, **_kwargs: HangingConnection())
    with pytest.raises(TransportError, match="timed out"):
        await ws.connect(timeout=0.001)
    assert ws._runner is None


@pytest.mark.asyncio
async def test_connect_propagates_runner_error_and_normal_early_stop() -> None:
    class Failed(ExchangeOSWebSocket):
        async def _run(self) -> None:
            raise AuthenticationError("denied")

    with pytest.raises(AuthenticationError, match="denied"):
        await Failed().connect()

    class Stopped(ExchangeOSWebSocket):
        async def _run(self) -> None:
            return

    with pytest.raises(TransportError, match="stopped before connecting"):
        await Stopped().connect()


@pytest.mark.asyncio
async def test_compat_subscribe_validation_and_unsubscribe() -> None:
    socket = FakeSocket()
    ws = ExchangeOSWebSocket(connector=Connector([socket]), ping_interval=60)
    await ws.connect()
    await ws.subscribe("exchangeos-trades", [{"assetId": 1}])
    assert ws.subscriptions == ({"channel": "exchangeos-trades", "assetId": 1},)
    await ws.unsubscribe("exchangeos-trades", [{"assetId": 1}])
    assert ws.subscriptions == ()
    assert json.loads(socket.sent[-1])["op"] == "unsubscribe"
    with pytest.raises(AuthenticationError):
        await ws.subscribe("exchangeos-account")
    with pytest.raises(ValueError, match="unknown"):
        await ws.subscribe("future-channel")
    await ws.close()


@pytest.mark.asyncio
async def test_private_compat_requires_completed_login() -> None:
    credentials = Credentials(api_key="key", secret_key="secret", passphrase="pass")
    ws = ExchangeOSWebSocket(credentials=credentials)
    with pytest.raises(AuthenticationError, match="completed"):
        await ws.subscribe("exchangeos-account")


@pytest.mark.asyncio
async def test_send_while_disconnected_and_public_without_asset() -> None:
    ws = ExchangeOSWebSocket()
    with pytest.raises(TransportError, match="not connected"):
        await ws._send({"op": "subscribe"})
    socket = FakeSocket()
    connected = ExchangeOSWebSocket(connector=Connector([socket]), ping_interval=60)
    await connected.connect()
    await connected.subscribe_public("exchangeos-instruments")
    assert json.loads(socket.sent[-1])["args"] == [{"channel": "exchangeos-instruments"}]
    await connected.close()


@pytest.mark.asyncio
async def test_bearer_auth_cannot_subscribe_private_channels() -> None:
    socket = FakeSocket()
    connector = Connector([socket])
    ws = ExchangeOSWebSocket(
        connector=connector, bearer_token="opaque-test-value", ping_interval=60
    )
    await ws.connect()
    assert ws.authenticated
    assert ws.authentication_mode == "bearer-upgrade"
    with pytest.raises(AuthenticationError, match="API credentials"):
        await ws.subscribe_private("exchangeos-account")
    assert connector.kwargs[0]["additional_headers"]["Authorization"].startswith("Bearer ")
    await ws.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    ["not-json", frame({"event": "login-wallet", "code": "1", "msg": "denied"})],
)
async def test_login_failure_is_not_retried(response: str) -> None:
    socket = FakeSocket([response])
    connector = Connector([socket])
    credentials = Credentials(api_key="key", secret_key="secret", passphrase="pass")
    ws = ExchangeOSWebSocket(connector=connector, credentials=credentials)
    with pytest.raises(AuthenticationError):
        await ws.connect()
    assert connector.calls == 1
    await ws.close()


@pytest.mark.asyncio
async def test_login_method_without_credentials() -> None:
    ws = ExchangeOSWebSocket()
    with pytest.raises(AuthenticationError):
        await ws._login(FakeSocket())


@pytest.mark.asyncio
async def test_receiver_handles_pong_non_object_and_invalid_json() -> None:
    ws = ExchangeOSWebSocket(queue_size=4)
    socket = FakeSocket(["pong", "[]"])
    socket.incoming.put_nowait(StopAsyncIteration)
    await ws._receive(socket)
    assert ws._pong.is_set()
    raw = await anext(ws)
    assert raw == "[]"

    invalid = FakeSocket(["{"])
    with pytest.raises(WebSocketProtocolError, match="invalid WebSocket JSON"):
        await ws._receive(invalid)


@pytest.mark.asyncio
async def test_sequence_guard_and_gap_without_live_subscription() -> None:
    ws = ExchangeOSWebSocket()
    await ws._check_orderbook_sequence({})
    arg = {"channel": "exchangeos-books", "assetId": 4}
    await ws._check_orderbook_sequence({"arg": arg, "data": []})
    await ws._check_orderbook_sequence({"arg": arg, "data": [{"seqId": "bad"}]})
    await ws._check_orderbook_sequence({"arg": arg, "action": "snapshot", "data": [{"seqId": 5}]})
    await ws._check_orderbook_sequence(
        {"arg": arg, "action": "update", "data": [{"seqId": 7, "prevSeqId": 2}]}
    )
    assert json.loads(await anext(ws))["event"] == "sequence-gap"


def test_parser_known_control_channel_and_missing_envelope() -> None:
    notice = parse_message({"event": "notice", "msg": "maintenance", "future": 1})
    assert isinstance(notice, ControlWebSocketMessage)
    assert notice.event == "notice"
    assert notice.message == "maintenance"
    assert notice.extra == {"future": 1}
    assert notice["event"] == "notice"
    known = {"arg": {"channel": "exchangeos-trades"}, "data": []}
    parsed = parse_message(known)
    assert isinstance(parsed, ChannelDataMessage)
    assert dict(parsed) == known
    missing = parse_message({"data": []})
    assert isinstance(missing, RawWebSocketMessage)


@pytest.mark.asyncio
async def test_event_handlers_and_force_queue_full() -> None:
    sync_events: list[str] = []
    sync_ws = ExchangeOSWebSocket(event_handler=lambda event, _details: sync_events.append(event))
    await sync_ws._emit("connected", {})
    assert sync_events == ["connected"]

    async_events: list[str] = []

    async def handler(event: str, _details: Any) -> None:
        async_events.append(event)

    async_ws = ExchangeOSWebSocket(queue_size=1, event_handler=handler)
    async_ws._force_queue(frame({"old": True}))
    async_ws._force_queue(frame({"new": True}))
    assert await anext(async_ws) == frame({"new": True})
    await async_ws._emit("authenticated", {})
    assert async_events == ["authenticated"]


@pytest.mark.asyncio
async def test_lifecycle_hooks_include_subscribed_and_reconnected(monkeypatch: Any) -> None:
    first, second = FakeSocket(), FakeSocket()
    connector = Connector([first, second])
    events: list[tuple[str, dict[str, Any]]] = []

    def handler(event: str, details: Any) -> None:
        events.append((event, dict(details)))

    monkeypatch.setattr("exos_python_sdk.websocket.transport.random.uniform", lambda *_: 0)
    ws = ExchangeOSWebSocket(
        connector=connector,
        event_handler=handler,
        ping_interval=60,
        reconnect_min=0,
        reconnect_max=0,
    )
    await ws.connect()
    await ws.subscribe_public("exchangeos-trades", asset_id=7)
    await first.close()
    await eventually(lambda: connector.calls == 2 and ws.connected)
    names = [event for event, _ in events]
    assert names.count("connected") == 1
    assert "reconnecting" in names
    assert names.count("subscribed") == 2
    assert names.count("reconnected") == 1
    assert ("subscribed", {"count": 1, "replayed": False}) in events
    assert ("subscribed", {"count": 1, "replayed": True}) in events
    await ws.close()


def test_authentication_mode_is_explicit() -> None:
    assert ExchangeOSWebSocket().authentication_mode == "none"
    credentials = Credentials(api_key="key", secret_key="secret", passphrase="pass")
    assert ExchangeOSWebSocket(credentials=credentials).authentication_mode == "api-key-login"
