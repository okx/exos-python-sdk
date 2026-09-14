"""Immutable signing models and wire enums."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, NoReturn

from ..exceptions import SigningError
from .validation import address, uint64, validate_action


class Chain(str, Enum):
    DEV = "Dev"
    TESTNET = "Testnet"
    MAINNET = "Mainnet"


class MarketType(str, Enum):
    PREDICTION = "prediction"
    SPOT = "spot"
    PERP = "perp"


class ActionGrouping(str, Enum):
    NA = "na"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class MarginMode(str, Enum):
    CROSS = "cross"
    ISOLATED = "isolated"


class PositionSide(str, Enum):
    NET = "net"
    LONG = "long"
    SHORT = "short"


class PositionMode(str, Enum):
    ONE_WAY = "oneWay"
    HEDGE = "hedge"


class IsolatedMarginDirection(str, Enum):
    CROSS_TO_ISOLATED = "crossToIso"
    ISOLATED_TO_CROSS = "isoToCross"


class OrderTimeInForce(str, Enum):
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    ALO = "alo"
    POST_ONLY = "alo"
    GTD = "gtd"


class PriceAmendType(str, Enum):
    """Price-limit behavior for limit orders."""

    NO_AMEND = "noAmend"
    CLAMP_TO_LIMIT = "clampToLimit"


class OrderSizeType(str, Enum):
    BASE = "base"
    QUOTE = "quote"


class TakeProfitStopLoss(str, Enum):
    TAKE_PROFIT = "tp"
    STOP_LOSS = "sl"


class TriggerPriceType(str, Enum):
    LAST = "last"
    MARK = "mark"
    INDEX = "index"


class Region(int, Enum):
    HK = 0
    US = 1
    EU = 2


class OrderSource(int, Enum):
    """Registered four-bit client-order origin values."""

    MANUAL = 2
    API = 3
    TRIGGER = 4
    LIQUIDATION = 5


class _FrozenDict(dict[Any, Any]):
    """A msgpack-compatible immutable mapping used by signed envelopes."""

    @staticmethod
    def _immutable() -> NoReturn:
        raise TypeError("signed transaction actions are immutable")

    def __setitem__(self, _key: Any, _value: Any) -> None:
        self._immutable()

    def __delitem__(self, _key: Any) -> None:
        self._immutable()

    def clear(self) -> None:
        self._immutable()

    def pop(self, _key: Any, _default: Any = None) -> Any:
        self._immutable()

    def popitem(self) -> tuple[Any, Any]:
        self._immutable()

    def setdefault(self, _key: Any, _default: Any = None) -> Any:
        self._immutable()

    def update(self, *_args: Any, **_kwargs: Any) -> None:
        self._immutable()


def freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        frozen = _FrozenDict()
        for key, item in value.items():
            dict.__setitem__(frozen, key, freeze(item))
        return frozen
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(freeze(item) for item in value)
    return value


def thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class Signature:
    r: str
    s: str
    v: int

    def __post_init__(self) -> None:
        for name, value in (("r", self.r), ("s", self.s)):
            try:
                valid = (
                    len(value) == 66
                    and value.startswith("0x")
                    and len(bytes.fromhex(value[2:])) == 32
                )
            except (TypeError, ValueError):
                valid = False
            if not valid:
                raise SigningError(f"signature {name} must be a 32-byte hex value")
        if self.v not in (0, 1):
            raise SigningError("signature v must be 0 or 1")

    def to_wire(self) -> dict[str, dict[str, str | int]]:
        return {"Ecdsa": {"r": self.r, "s": self.s, "v": self.v}}


@dataclass(frozen=True)
class SignedTransaction:
    action: Mapping[str, Any]
    nonce: int
    signature: Signature
    expires_after: int | None = None
    vault_address: str | None = None
    user: str | None = None
    tx_hash: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        uint64("nonce", self.nonce)
        if self.expires_after is not None:
            uint64("expires_after", self.expires_after)
        address("vault_address", self.vault_address)
        address("user", self.user)
        validate_action(self.action)
        object.__setattr__(self, "action", freeze(self.action))

    def to_wire(self) -> dict[str, Any]:
        value: dict[str, Any] = {"action": thaw(self.action), "nonce": self.nonce}
        if self.expires_after is not None:
            value["expiresAfter"] = self.expires_after
        if self.vault_address is not None:
            value["vaultAddress"] = self.vault_address
        value["signature"] = self.signature.to_wire()
        if self.user is not None:
            value["user"] = self.user
        return value
