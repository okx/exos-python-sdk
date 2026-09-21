"""Resilient async WebSocket transport for Spot and Perps ExchangeOS channels."""

from __future__ import annotations

import asyncio
import inspect
import json
import random
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import suppress
from typing import Any, Literal, cast

from ..auth import Credentials, websocket_login_args
from ..exceptions import AuthenticationError, TransportError, WebSocketProtocolError
from .channels import (
    BOOK_CHANNELS,
    PRIVATE_CHANNELS,
    PUBLIC_CHANNELS,
    matches_channel,
    subscription_key,
)

DEFAULT_WS_URL = "wss://ws.okx.com/ws/v5/exchangeos"

OverflowPolicy = Literal["drop_oldest", "drop_newest", "raise"]
EventHandler = Callable[[str, Mapping[str, Any]], Awaitable[None] | None]
MessageCallback = Callable[[str], Awaitable[None] | None]
Connector = Callable[..., Any]
_STOP = object()


class ExchangeOSWebSocket:
    """Async WebSocket session with authentication, replay and backpressure.

    Private subscriptions are sent only after login succeeds. Unexpected
    disconnects use jittered exponential backoff; calling :meth:`close` never
    reconnects. Valid messages are delivered as raw JSON strings.
    """

    def __init__(
        self,
        *,
        url: str = DEFAULT_WS_URL,
        credentials: Credentials | None = None,
        bearer_token: str | None = None,
        ping_interval: float = 25.0,
        pong_timeout: float = 10.0,
        reconnect_min: float = 3.0,
        reconnect_max: float = 30.0,
        max_reconnect_attempts: int | None = None,
        queue_size: int = 1_000,
        overflow_policy: OverflowPolicy = "drop_oldest",
        message_callback: MessageCallback | None = None,
        event_handler: EventHandler | None = None,
        connector: Connector | None = None,
    ) -> None:
        if not url.startswith(("wss://", "ws://localhost", "ws://127.0.0.1")):
            raise ValueError("WebSocket URL must use WSS (WS is allowed only for loopback tests)")
        if ping_interval <= 0 or pong_timeout <= 0:
            raise ValueError("heartbeat intervals must be positive")
        if reconnect_min < 0 or reconnect_max < reconnect_min:
            raise ValueError("invalid reconnect interval")
        if max_reconnect_attempts is not None and max_reconnect_attempts < 0:
            raise ValueError("max_reconnect_attempts cannot be negative")
        if queue_size <= 0:
            raise ValueError("queue_size must be positive")
        if overflow_policy not in {"drop_oldest", "drop_newest", "raise"}:
            raise ValueError("unsupported overflow_policy")
        self.url = url
        self.credentials = credentials
        self.bearer_token = bearer_token
        self.ping_interval = ping_interval
        self.pong_timeout = pong_timeout
        self.reconnect_min = reconnect_min
        self.reconnect_max = reconnect_max
        self.max_reconnect_attempts = max_reconnect_attempts
        self.overflow_policy = overflow_policy
        self.message_callback = message_callback
        self.event_handler = event_handler
        self._connector = connector
        self._subscriptions: dict[str, dict[str, Any]] = {}
        self._outbox: asyncio.Queue[Any] = asyncio.Queue(maxsize=queue_size)
        self._connected = asyncio.Event()
        self._authenticated = asyncio.Event()
        self._pong = asyncio.Event()
        self._closed = False
        self._ws: Any = None
        self._runner: asyncio.Task[None] | None = None
        self._book_sequences: dict[str, int] = {}
        self._connection_generation = 0
        self._ever_connected = False

    async def __aenter__(self) -> ExchangeOSWebSocket:
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    def __aiter__(self) -> AsyncIterator[str]:
        return self

    async def __anext__(self) -> str:
        if self._closed and self._outbox.empty():
            raise StopAsyncIteration
        item = await self._outbox.get()
        if item is _STOP:
            raise StopAsyncIteration
        return cast(str, item)

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    @property
    def authenticated(self) -> bool:
        return self._authenticated.is_set()

    @property
    def authentication_mode(self) -> Literal["none", "api-key-login", "bearer-upgrade"]:
        """Describe how private streams authenticate on each connection."""

        if self.bearer_token:
            return "bearer-upgrade"
        if self.credentials:
            return "api-key-login"
        return "none"

    @property
    def subscriptions(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(dict(item) for item in self._subscriptions.values())

    async def connect(self, *, timeout: float = 30.0) -> None:
        if self._runner is None or self._runner.done():
            self._closed = False
            self._runner = asyncio.create_task(self._run(), name="exchangeos-websocket")
        connected = asyncio.create_task(self._connected.wait())
        try:
            done, _ = await asyncio.wait(
                {connected, self._runner}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )
            if connected in done and connected.result():
                return
            if self._runner in done:
                error = self._runner.exception()
                if error is not None:
                    raise error
                raise TransportError("WebSocket stopped before connecting")
            raise TimeoutError
        except TimeoutError as exc:
            await self.close()
            raise TransportError("WebSocket connection timed out") from exc
        finally:
            connected.cancel()

    async def subscribe_public(
        self, channel: str, *, asset_id: str | int | None = None, **params: Any
    ) -> None:
        self._validate_channel(channel, private=False)
        if asset_id is not None:
            params["assetId"] = asset_id
        await self._subscribe_args(self._build_args(channel, [params] if params else None))

    async def subscribe_private(
        self, channel: str, *, vault_address: str | None = None, **params: Any
    ) -> None:
        self._validate_channel(channel, private=True)
        if not self.credentials:
            raise AuthenticationError(
                "ExchangeOS private WebSocket channels require CEX API credentials"
            )
        if not self._authenticated.is_set():
            raise AuthenticationError("private subscriptions require a completed WebSocket login")
        if vault_address is not None:
            params["vaultAddress"] = vault_address
        await self._subscribe_args(self._build_args(channel, [params] if params else None))

    async def subscribe(
        self, channel: str, params: Sequence[Mapping[str, Any]] | None = None
    ) -> None:
        """Compatibility API; channel inventory determines public/private access."""

        if matches_channel(channel, PRIVATE_CHANNELS):
            if not self.credentials:
                raise AuthenticationError(
                    "ExchangeOS private WebSocket channels require CEX API credentials"
                )
            if not self._authenticated.is_set():
                raise AuthenticationError(
                    "private subscriptions require a completed WebSocket login"
                )
        elif not matches_channel(channel, PUBLIC_CHANNELS):
            raise ValueError(f"unknown or non-canonical WebSocket channel: {channel}")
        await self._subscribe_args(self._build_args(channel, params))

    async def unsubscribe(
        self, channel: str, params: Sequence[Mapping[str, Any]] | None = None
    ) -> None:
        args = self._build_args(channel, params)
        for arg in args:
            self._subscriptions.pop(subscription_key(arg), None)
            self._book_sequences.pop(subscription_key(arg), None)
        await self._send({"op": "unsubscribe", "args": args})

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._connected.clear()
        self._authenticated.clear()
        if self._ws is not None:
            with suppress(Exception):
                await self._ws.close()
        if self._runner is not None:
            self._runner.cancel()
            # ``connect`` already reports a completed runner's failure. Closing
            # is cleanup and must remain idempotent after that failure.
            with suppress(asyncio.CancelledError, Exception):
                await self._runner
        self._runner = None
        self._force_queue(_STOP)

    @staticmethod
    def _build_args(
        channel: str, params: Sequence[Mapping[str, Any]] | None
    ) -> list[dict[str, Any]]:
        if not channel or " " in channel:
            raise ValueError("channel must be a non-empty canonical name without spaces")
        if not params:
            return [{"channel": channel}]
        return [{"channel": channel, **dict(param)} for param in params]

    @staticmethod
    def _validate_channel(channel: str, *, private: bool) -> None:
        patterns = PRIVATE_CHANNELS if private else PUBLIC_CHANNELS
        if not matches_channel(channel, patterns):
            visibility = "private" if private else "public"
            raise ValueError(f"unknown or non-canonical {visibility} channel: {channel}")

    async def _subscribe_args(self, args: Sequence[dict[str, Any]]) -> None:
        unique: list[dict[str, Any]] = []
        for arg in args:
            key = subscription_key(arg)
            if key not in self._subscriptions:
                self._subscriptions[key] = dict(arg)
                unique.append(arg)
        if unique:
            await self._send({"op": "subscribe", "args": unique})
            await self._emit("subscribed", {"count": len(unique), "replayed": False})

    async def _send(self, payload: Mapping[str, Any]) -> None:
        if not self._connected.is_set() or self._ws is None:
            raise TransportError("WebSocket is not connected")
        await self._ws.send(self._encode(payload))

    async def _run(self) -> None:
        delay = self.reconnect_min
        reconnects = 0
        while not self._closed:
            generation_before_session = self._connection_generation
            try:
                await self._session()
                if self._closed:
                    return
                raise TransportError("WebSocket connection closed")
            except asyncio.CancelledError:
                raise
            except AuthenticationError:
                self._connected.clear()
                self._authenticated.clear()
                raise
            except Exception as exc:
                self._connected.clear()
                self._authenticated.clear()
                self._ws = None
                if self._closed:
                    return
                # A successfully established session starts a new outage window.
                # The retry cap therefore applies to consecutive connection
                # failures, not to the entire lifetime of a long-running client.
                if self._connection_generation > generation_before_session:
                    reconnects = 0
                    delay = self.reconnect_min
                await self._deliver_raw(self._encode({"event": "transport-error", "msg": str(exc)}))
                if (
                    self.max_reconnect_attempts is not None
                    and reconnects >= self.max_reconnect_attempts
                ):
                    await self._emit("reconnect-exhausted", {"attempts": reconnects})
                    return
                reconnects += 1
                await self._emit("reconnecting", {"attempt": reconnects, "delay": delay})
                jitter = random.uniform(0, min(1.0, delay * 0.1))
                await asyncio.sleep(delay + jitter)
                delay = min(delay * 2, self.reconnect_max)

    async def _session(self) -> None:
        connector = self._connector
        if connector is None:
            try:
                from websockets.asyncio.client import connect
            except ImportError as exc:
                raise TransportError("install the SDK with its WebSocket dependency") from exc
            connector = connect
        headers = {"User-Agent": "EXCHANGEOS_PYTHON_SDK_0.1.0"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        async with connector(
            self.url, additional_headers=headers, ping_interval=None, close_timeout=5
        ) as ws:
            self._ws = ws
            self._book_sequences.clear()
            if self.credentials and not self.bearer_token:
                await self._login(ws)
            elif self.bearer_token:
                self._authenticated.set()
                await self._emit("authenticated", {"mode": "bearer", "transport": "http-upgrade"})
            if self._subscriptions:
                await ws.send(
                    self._encode({"op": "subscribe", "args": self._subscriptions.values()})
                )
                await self._emit(
                    "subscribed", {"count": len(self._subscriptions), "replayed": True}
                )
            self._connected.set()
            reconnected = self._ever_connected
            self._ever_connected = True
            self._connection_generation += 1
            event = "reconnected" if reconnected else "connected"
            await self._emit(event, {"replayed": len(self._subscriptions)})
            receiver = asyncio.create_task(self._receive(ws))
            heartbeat = asyncio.create_task(self._heartbeat(ws))
            done, pending = await asyncio.wait(
                {receiver, heartbeat}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            for task in pending:
                with suppress(asyncio.CancelledError):
                    await task
            for task in done:
                error = task.exception()
                if error is not None:
                    raise error
        self._connected.clear()
        self._authenticated.clear()
        self._ws = None

    async def _login(self, ws: Any) -> None:
        if self.credentials is None:
            raise AuthenticationError(
                "ExchangeOS private WebSocket channels require CEX API credentials"
            )
        login_args: dict[str, Any] = dict(websocket_login_args(self.credentials))
        operation = "login-wallet"
        expected_events = {"login-wallet"}
        await ws.send(
            self._encode({"op": operation, "args": [login_args]})
        )
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
            raw_text = self._raw_text(raw)
            response = json.loads(raw_text)
        except (TimeoutError, TypeError, json.JSONDecodeError) as exc:
            raise AuthenticationError("WebSocket login response was invalid or timed out") from exc
        if response.get("event") not in expected_events or str(response.get("code", "0")) != "0":
            raise AuthenticationError(
                f"WebSocket login failed: {response.get('msg', 'unknown error')}"
            )
        self._authenticated.set()
        await self._deliver_raw(raw_text)
        await self._emit("authenticated", {"mode": "api-key-login"})

    async def _receive(self, ws: Any) -> None:
        async for raw in ws:
            if raw == "pong":
                self._pong.set()
                continue
            try:
                raw_text = self._raw_text(raw)
                message = json.loads(raw_text)
            except (TypeError, json.JSONDecodeError) as exc:
                raise WebSocketProtocolError("invalid WebSocket JSON payload") from exc
            if not isinstance(message, dict):
                await self._deliver_raw(raw_text)
                continue
            if await self._check_orderbook_sequence(message):
                await self._deliver_raw(raw_text)

    async def _heartbeat(self, ws: Any) -> None:
        while True:
            await asyncio.sleep(self.ping_interval)
            self._pong.clear()
            await ws.send("ping")
            try:
                await asyncio.wait_for(self._pong.wait(), timeout=self.pong_timeout)
            except TimeoutError as exc:
                with suppress(Exception):
                    await ws.close()
                raise TransportError("WebSocket heartbeat timed out") from exc

    async def _check_orderbook_sequence(self, message: Mapping[str, Any]) -> bool:
        arg = message.get("arg")
        if not isinstance(arg, Mapping) or not self._is_book_channel(str(arg.get("channel", ""))):
            return True
        data = message.get("data")
        if not isinstance(data, list) or not data or not isinstance(data[0], Mapping):
            return True
        row = data[0]
        seq, prev = row.get("seqId"), row.get("prevSeqId")
        if not isinstance(seq, int):
            return True
        sub_arg = dict(arg)
        key = subscription_key(sub_arg)
        prior = self._book_sequences.get(key)
        is_snapshot = message.get("action") == "snapshot"
        if not is_snapshot and prior is not None and isinstance(prev, int) and prev != prior:
            self._book_sequences.pop(key, None)
            event = {
                "event": "sequence-gap",
                "arg": sub_arg,
                "expectedPrevSeqId": prior,
                "actualPrevSeqId": prev,
            }
            await self._deliver_raw(self._encode(event))
            await self._emit("gap", event)
            if self._ws is not None and key in self._subscriptions:
                await self._ws.send(self._encode({"op": "unsubscribe", "args": [sub_arg]}))
                await self._ws.send(self._encode({"op": "subscribe", "args": [sub_arg]}))
            return False
        self._book_sequences[key] = seq
        return True

    @staticmethod
    def _is_book_channel(channel: str) -> bool:
        return channel in BOOK_CHANNELS

    async def _deliver_raw(self, message: str) -> None:
        if self.message_callback is not None:
            try:
                result = self.message_callback(message)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                await self._emit("callback-error", {"error_type": type(exc).__name__})
        await self._queue_message(message)

    async def _queue_message(self, message: str) -> None:
        if not self._outbox.full():
            self._outbox.put_nowait(message)
            return
        await self._emit("queue-overflow", {"policy": self.overflow_policy})
        if self.overflow_policy == "drop_newest":
            return
        if self.overflow_policy == "raise":
            raise TransportError("WebSocket message queue overflow")
        with suppress(asyncio.QueueEmpty):
            self._outbox.get_nowait()
        self._outbox.put_nowait(message)

    def _force_queue(self, message: Any) -> None:
        if self._outbox.full():
            with suppress(asyncio.QueueEmpty):
                self._outbox.get_nowait()
        self._outbox.put_nowait(message)

    async def _emit(self, event: str, details: Mapping[str, Any]) -> None:
        if self.event_handler is None:
            return
        result = self.event_handler(event, details)
        if inspect.isawaitable(result):
            await result

    @staticmethod
    def _encode(payload: Mapping[str, Any]) -> str:
        return json.dumps(payload, separators=(",", ":"), default=list)

    @staticmethod
    def _raw_text(payload: Any) -> str:
        if isinstance(payload, str):
            return payload
        if isinstance(payload, bytes):
            try:
                return payload.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise WebSocketProtocolError("invalid WebSocket UTF-8 payload") from exc
        raise WebSocketProtocolError("WebSocket payload must be text or UTF-8 bytes")
