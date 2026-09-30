"""Forward-compatible enums for common REST string values."""

from __future__ import annotations

from enum import Enum
from typing import Any


class OpenStringEnum(str, Enum):
    """String enum that retains server values introduced by future API versions."""

    @classmethod
    def _missing_(cls, value: object) -> Any:
        if not isinstance(value, str):
            return None
        member = str.__new__(cls, value)
        member._name_ = "_UNKNOWN"
        member._value_ = value
        return member

    def __str__(self) -> str:
        return str.__str__(self)


class MarketType(OpenStringEnum):
    SPOT = "spot"
    PERP = "perp"


class SecurityFundType(OpenStringEnum):
    SECURITY_VAULT = "securityVault"
    SECURITY_FUND = "securityFund"
    SUPPLEMENTARY_FUND = "supplementaryFund"


class OrderState(OpenStringEnum):
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    MODIFIED = "modified"
    FILLED = "filled"
    TRIGGERED = "triggered"
    TRIGGERED_AND_FAILED = "triggered_and_failed"
    FAILED = "failed"
    CANCELED = "canceled"
    PART_FILLED_CANCELED = "part_filled_canceled"


class Side(OpenStringEnum):
    BUY = "buy"
    SELL = "sell"


class TimeInForce(OpenStringEnum):
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    ALO = "alo"
    GTD = "gtd"
    POST_ONLY = "alo"
