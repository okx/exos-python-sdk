"""Typed, forward-compatible WebSocket message models."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ..exceptions import SequenceGapError
from .channels import PRIVATE_CHANNELS, PUBLIC_CHANNELS, matches_channel
from .payloads import parse_channel_payload

KNOWN_EVENTS = frozenset(
    {
        "login",
        "subscribe",
        "unsubscribe",
        "error",
        "notice",
        "transport-error",
        "sequence-gap",
    }
)


def _immutable_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    """Copy an envelope so later caller mutations cannot change a parsed message."""

    return MappingProxyType(dict(value))


@dataclass(frozen=True)
class WebSocketMessage(Mapping[str, Any]):
    """Mapping-compatible base for typed messages.

    ``raw`` contains the complete decoded envelope, including fields introduced
    by newer server versions.
    """

    raw: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw", _immutable_mapping(self.raw))

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.raw)

    def __len__(self) -> int:
        return len(self.raw)

    @property
    def extra(self) -> Mapping[str, Any]:
        """Return fields not represented by typed properties."""

        return MappingProxyType(
            {key: value for key, value in self.raw.items() if key not in self._known_fields}
        )

    @property
    def _known_fields(self) -> frozenset[str]:
        return frozenset()


@dataclass(frozen=True)
class ControlWebSocketMessage(WebSocketMessage):
    """A known login/subscription/notice/error control envelope."""

    event: str
    code: str | None = None
    message: str | None = None
    argument: Mapping[str, Any] | None = None

    @property
    def _known_fields(self) -> frozenset[str]:
        return frozenset({"event", "code", "msg", "arg"})


@dataclass(frozen=True)
class ChannelDataMessage(WebSocketMessage):
    """A data envelope for any known public or private channel."""

    channel: str
    argument: Mapping[str, Any]
    data: Any = None
    action: str | None = None

    @property
    def _known_fields(self) -> frozenset[str]:
        return frozenset({"arg", "data", "action"})


@dataclass(frozen=True)
class SequenceGapMessage(WebSocketMessage):
    """Recoverable order-book gap notification with a typed error."""

    argument: Mapping[str, Any]
    expected_previous_sequence_id: int
    actual_previous_sequence_id: int
    error: SequenceGapError

    @property
    def event(self) -> str:
        return "sequence-gap"

    @property
    def _known_fields(self) -> frozenset[str]:
        return frozenset({"event", "arg", "expectedPrevSeqId", "actualPrevSeqId"})


@dataclass(frozen=True)
class RawWebSocketMessage(WebSocketMessage):
    """Forward-compatible wrapper for an unknown channel or event."""

    reason: str


ParsedWebSocketMessage = (
    ControlWebSocketMessage | ChannelDataMessage | SequenceGapMessage | RawWebSocketMessage
)


def parse_message(message: Mapping[str, Any]) -> ParsedWebSocketMessage:
    """Classify a decoded envelope without dropping unknown fields."""

    raw = dict(message)
    event = message.get("event")
    if event is not None:
        if not isinstance(event, str) or event not in KNOWN_EVENTS:
            return RawWebSocketMessage(raw, "unknown event")
        if event == "sequence-gap":
            argument = message.get("arg")
            expected = message.get("expectedPrevSeqId")
            actual = message.get("actualPrevSeqId")
            if (
                isinstance(argument, Mapping)
                and isinstance(expected, int)
                and isinstance(actual, int)
            ):
                error = SequenceGapError(
                    expected_previous_sequence_id=expected,
                    actual_previous_sequence_id=actual,
                    argument=argument,
                )
                return SequenceGapMessage(raw, argument, expected, actual, error)
            return RawWebSocketMessage(raw, "invalid sequence-gap event")
        argument = message.get("arg")
        return ControlWebSocketMessage(
            raw,
            event,
            str(message["code"]) if message.get("code") is not None else None,
            str(message["msg"]) if message.get("msg") is not None else None,
            argument if isinstance(argument, Mapping) else None,
        )

    argument = message.get("arg")
    if isinstance(argument, Mapping):
        channel = argument.get("channel")
        if not isinstance(channel, str) or not matches_channel(
            channel, PUBLIC_CHANNELS + PRIVATE_CHANNELS
        ):
            return RawWebSocketMessage(raw, "unknown channel")
        action = message.get("action")
        return ChannelDataMessage(
            raw,
            channel,
            _immutable_mapping(argument),
            parse_channel_payload(channel, message.get("data")),
            action if isinstance(action, str) else None,
        )
    return RawWebSocketMessage(raw, "unknown event")
