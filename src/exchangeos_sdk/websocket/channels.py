"""Canonical Spot and Perps ExchangeOS WebSocket channel inventory."""

import json
from collections.abc import Mapping, Sequence
from typing import Any

EXCHANGEOS_PUBLIC_CHANNELS = (
    "exchangeos-tickers",
    "exchangeos-trades",
    "exchangeos-candle{bar}",
    "exchangeos-mark-price",
    "exchangeos-mark-price-candle{bar}",
    "exchangeos-index-tickers",
    "exchangeos-index-candle{bar}",
    "exchangeos-funding-rate",
    "exchangeos-instruments",
    "exchangeos-open-interest",
    "exchangeos-price-limit",
    "exchangeos-books",
    "exchangeos-books5",
    "exchangeos-bbo-tbt",
    "exchangeos-books-grouped",
)
EXCHANGEOS_PRIVATE_CHANNELS = (
    "exchangeos-account",
    "exchangeos-balance-and-position",
    "exchangeos-balance-and-position-updates",
    "exchangeos-orders",
    "exchangeos-user-order-status",
    "exchangeos-user-fills",
    "exchangeos-user-fundings",
    "exchangeos-user-ledger-updates",
    "exchangeos-setting-updates",
    "exchangeos-notification",
)
PUBLIC_CHANNELS = EXCHANGEOS_PUBLIC_CHANNELS
PRIVATE_CHANNELS = EXCHANGEOS_PRIVATE_CHANNELS

BOOK_CHANNELS = frozenset({"exchangeos-books", "exchangeos-books5", "exchangeos-books-grouped"})


def matches_channel(channel: str, patterns: Sequence[str]) -> bool:
    for pattern in patterns:
        if pattern.endswith("{bar}"):
            prefix = pattern[:-5]
            if channel.startswith(prefix) and len(channel) > len(prefix):
                return True
        elif channel == pattern:
            return True
    return False


def subscription_key(arg: Mapping[str, Any]) -> str:
    """Return a deterministic key even when a future parameter is nested."""

    return json.dumps(arg, sort_keys=True, separators=(",", ":"), default=str)
