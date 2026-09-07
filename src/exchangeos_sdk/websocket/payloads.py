"""Typed payload models for documented ExchangeOS WebSocket channels."""

from __future__ import annotations

from typing import Any, ClassVar

from ..models.responses import (
    AccountBalance,
    BalanceDetail,
    Candle,
    Fill,
    FundingRate,
    IndexTicker,
    Instrument,
    MarkPrice,
    OpenInterest,
    Order,
    OrderBook,
    Position,
    PriceCandle,
    PriceLimit,
    Ticker,
)
from ..models.rest import RestData, RestList, TypedRestObject, parse_rest_data


class PublicTrade(TypedRestObject):
    asset_id: str
    first_trade_id: str
    last_trade_id: str
    price: str
    size: str
    side: str
    ts: str

    _aliases: ClassVar = {
        "first_trade_id": "fId",
        "last_trade_id": "lId",
        "price": "px",
        "size": "sz",
    }


class UserFunding(TypedRestObject):
    asset_id: int
    funding_fee: str
    funding_rate: str
    margin_mode: str
    position_side: str
    pos: str


class OrderStatusEvent(TypedRestObject):
    state: str
    builder: str
    order: Order
    message: str

    _nested: ClassVar = {"order": Order}


class UserOrderStatus(TypedRestObject):
    order_statuses: list[OrderStatusEvent]

    _nested_lists: ClassVar = {"orderStatuses": OrderStatusEvent}


class LedgerUpdate(TypedRestObject):
    """Discriminated ledger delta; variant keys remain forward compatible."""

    users: list[str]


class AccountInfo(TypedRestObject):
    role_id: str
    position_mode: str


class AccountChannelPayload(TypedRestObject):
    account: AccountInfo
    details: TypedRestObject

    _nested: ClassVar = {"account": AccountInfo, "details": TypedRestObject}


class BalanceAndPosition(AccountBalance):
    positions: list[Position]
    _nested_lists: ClassVar = {"details": BalanceDetail, "positions": Position}


class OrdersPayload(TypedRestObject):
    orders: list[Order]
    _nested_lists: ClassVar = {"orders": Order}


class FundingsPayload(TypedRestObject):
    fundings: list[UserFunding]
    _nested_lists: ClassVar = {"fundings": UserFunding}


class LedgerUpdatesPayload(TypedRestObject):
    ledger_updates: list[LedgerUpdate]
    _nested_lists: ClassVar = {"ledgerUpdates": LedgerUpdate}


class AccountSetting(TypedRestObject):
    role_id: str
    position_mode: str


class AssetSetting(TypedRestObject):
    asset_id: int
    position_side: str
    leverage: str
    margin_mode: str


class SettingUpdates(TypedRestObject):
    account_setting: AccountSetting
    asset_setting: list[AssetSetting]

    _aliases: ClassVar = {"account_setting": "accSetting"}
    _nested: ClassVar = {"accSetting": AccountSetting}
    _nested_lists: ClassVar = {"assetSetting": AssetSetting}


CHANNEL_PAYLOAD_MODELS: dict[str, type[TypedRestObject]] = {
    "exchangeos-tickers": Ticker,
    "exchangeos-trades": PublicTrade,
    "exchangeos-mark-price": MarkPrice,
    "exchangeos-index-tickers": IndexTicker,
    "exchangeos-funding-rate": FundingRate,
    "exchangeos-instruments": Instrument,
    "exchangeos-open-interest": OpenInterest,
    "exchangeos-price-limit": PriceLimit,
    "exchangeos-books": OrderBook,
    "exchangeos-books5": OrderBook,
    "exchangeos-bbo-tbt": OrderBook,
    "exchangeos-books-grouped": OrderBook,
    "exchangeos-account": AccountChannelPayload,
    "exchangeos-balance-and-position": BalanceAndPosition,
    "exchangeos-balance-and-position-updates": BalanceAndPosition,
    "exchangeos-orders": OrdersPayload,
    "exchangeos-user-order-status": UserOrderStatus,
    "exchangeos-user-fills": Fill,
    "exchangeos-user-fundings": FundingsPayload,
    "exchangeos-user-ledger-updates": LedgerUpdatesPayload,
    "exchangeos-setting-updates": SettingUpdates,
}


def parse_channel_payload(channel: str, data: Any) -> RestData:
    """Parse a known channel without coercing or dropping wire values."""

    if (
        channel.startswith("exchangeos-candle")
        or channel.startswith("exchangeos-mark-price-candle")
        or channel.startswith("exchangeos-index-candle")
    ):
        if channel.startswith("exchangeos-candle") and isinstance(data, list):
            return RestList(
                [
                    Candle.from_row(row) if isinstance(row, list) else parse_rest_data(row)
                    for row in data
                ]
            )
        if isinstance(data, list):
            return RestList(
                [
                    PriceCandle.from_row(row) if isinstance(row, list) else parse_rest_data(row)
                    for row in data
                ]
            )
        return parse_rest_data(data)
    return parse_rest_data(data, model=CHANNEL_PAYLOAD_MODELS.get(channel))


__all__ = [
    "AccountChannelPayload",
    "AccountInfo",
    "AssetSetting",
    "BalanceAndPosition",
    "FundingsPayload",
    "LedgerUpdate",
    "LedgerUpdatesPayload",
    "OrdersPayload",
    "PublicTrade",
    "SettingUpdates",
    "UserFunding",
    "UserOrderStatus",
    "parse_channel_payload",
]
