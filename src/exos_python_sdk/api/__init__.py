"""REST API namespaces grouped by domain."""

from .account import ACCOUNT_ENDPOINTS, AccountAPI
from .base import ROOT, BaseAPI
from .market import MARKET_ENDPOINTS, MarketAPI
from .trade import TRADE_ENDPOINTS, TradeAPI

__all__ = [
    "ACCOUNT_ENDPOINTS",
    "MARKET_ENDPOINTS",
    "ROOT",
    "TRADE_ENDPOINTS",
    "AccountAPI",
    "BaseAPI",
    "MarketAPI",
    "TradeAPI",
]
