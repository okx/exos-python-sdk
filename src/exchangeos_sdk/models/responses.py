"""Typed REST payloads for the ExchangeOS Spot and Perps OpenAPI.

The classes deliberately remain ``dict`` compatible.  Numeric and timestamp
fields retain their documented wire strings; use ``decimal()`` and
``utc_datetime()`` when conversion is useful.
"""

from __future__ import annotations

from typing import Any, ClassVar

from .rest import TypedRestObject


class TokenInfo(TypedRestObject):
    token_id: str
    token_name: str
    point_flag: bool


class UpcomingParameterChange(TypedRestObject):
    param: str
    new_value: str
    eff_time: str


class Instrument(TypedRestObject):
    asset_id: str
    market_type: str
    name: str
    uly: str
    price_decimals: str
    size_decimals: str
    buy_lmt: str
    sell_lmt: str
    state: str
    settle_token_id: str
    list_time: str
    exp_time: str
    upc_chg: list[UpcomingParameterChange]
    leverage: str
    position_tier_id: str
    margin_modes: list[str]
    base_token_id: str
    quote_token_id: str

    _nested_lists: ClassVar = {"upcChg": UpcomingParameterChange}


class Ticker(TypedRestObject):
    asset_id: str
    last_px: str
    last_sz: str
    ask_px: str
    ask_sz: str
    bid_px: str
    bid_sz: str
    open24h: str
    high24h: str
    low24h: str
    vol24h: str
    vol_ccy24h: str
    sod_utc0: str
    sod_utc8: str
    ts: str


class OrderBook(TypedRestObject):
    bids: list[list[str]]
    asks: list[list[str]]
    ts: str


class Candle(TypedRestObject):
    """Named view over the documented nine-element candle wire row."""

    ts: str
    open: str
    high: str
    low: str
    close: str
    volume: str
    volume_currency: str
    volume_currency_quote: str
    confirm: str

    @classmethod
    def from_row(cls, row: list[Any]) -> Candle:
        names = (
            "ts",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "volumeCurrency",
            "volumeCurrencyQuote",
            "confirm",
        )
        return cls({name: value for name, value in zip(names, row, strict=False)})


class PriceCandle(TypedRestObject):
    """Named view over a six-element mark/index-price candle row."""

    ts: str
    open: str
    high: str
    low: str
    close: str
    confirm: str

    @classmethod
    def from_row(cls, row: list[Any]) -> PriceCandle:
        names = ("ts", "open", "high", "low", "close", "confirm")
        return cls({name: value for name, value in zip(names, row, strict=False)})


class MarkPrice(TypedRestObject):
    asset_id: str
    mark_px: str
    ts: str


class Tier(TypedRestObject):
    leverage: str
    max_position_allowed: str


class _PositionTierBase(TypedRestObject):
    position_tier_id: str
    base_position_value0: str
    base_mmr0: str
    base_imr0: str
    mmr_change_rate: str
    imr_change_rate: str
    max_position_value: str
    imr_curve_pos_value_grid: str
    max_leverage: str
    tiers: list[Tier]

    _aliases: ClassVar = {
        "base_mmr0": "baseMMR0",
        "base_imr0": "baseIMR0",
    }
    _nested_lists: ClassVar = {"tiers": Tier}


class PositionTier(_PositionTierBase):
    asset_id: str


class AccountPositionTier(_PositionTierBase):
    asset_id: str
    role_id: str


class FundingRateHistory(TypedRestObject):
    asset_id: str
    funding_rate: str
    funding_time: str


class FundingRateHistoryPage(TypedRestObject):
    data: list[FundingRateHistory]
    has_more: bool
    next_cursor: str

    _nested_lists: ClassVar = {"data": FundingRateHistory}


class FundingRate(TypedRestObject):
    asset_id: str
    funding_rate: str
    funding_time: str
    next_funding_time: str
    settlement_interval: str
    min_funding_rate: str
    max_funding_rate: str
    interest_rate: str
    impact_base_notional: str
    damper_value: str
    multiplier_factor: str
    funding_switch: bool


class OpenInterest(TypedRestObject):
    asset_id: str
    oi_ccy: str
    oi_usd: str
    ts: str

    _aliases: ClassVar = {"oi_ccy": "oiCcy", "oi_usd": "oiUsd"}


class PriceLimit(TypedRestObject):
    asset_id: str
    buy_lmt: str
    sell_lmt: str
    ts: str


class IndexTicker(TypedRestObject):
    asset_id: str
    uly: str
    idx_px: str
    open24h: str
    high24h: str
    low24h: str
    sod_utc0: str
    sod_utc8: str
    ts: str


class BalanceDetail(TypedRestObject):
    token_id: str
    collateral_enabled: bool
    eq: str
    eq_usd: str
    iso_eq: str
    cash_bal: str
    avail_bal: str
    avail_eq: str
    frozen_mgn: str
    spot_frozen: str
    perp_frozen: str
    mmr: str
    mgn_ratio: str
    frozen_mgn_ratio: str
    acc_avg_px: str
    spot_upl: str
    spot_upl_ratio: str
    entry_cost: str
    upl: str
    iso_upl: str
    last_px: str
    token_px: str
    total_lever: str


class AccountBalance(TypedRestObject):
    total_eq: str
    notional_usd: str
    position_mode: str
    block_height: str
    block_timestamp: str
    details: list[BalanceDetail]

    _aliases: ClassVar = {"block_height": "block_height", "block_timestamp": "block_timestamp"}
    _nested_lists: ClassVar = {"details": BalanceDetail}


class CloseOrderAlgo(TypedRestObject):
    oid: str
    asset_id: str
    asset_status: str
    side: str
    position_side: str
    margin_mode: str
    price: str
    size: str
    reduce_only: bool
    trigger_px: str
    trigger_price_type: str
    trigger_cond: str
    is_market: bool
    tpsl: str
    parent_order_id: str
    is_active: bool
    tp_limit: bool


class Position(TypedRestObject):
    asset_id: str
    asset_status: str
    position_side: str
    margin_mode: str
    leverage: str
    pos: str
    avg_px: str
    mark_px: str
    position_value: str
    upl: str
    upl_ratio: str
    liq_px: str
    imr: str
    margin: str
    mmr: str
    mgn_ratio: str
    realized_pnl: str
    fee: str
    funding_fee: str
    block_height: str
    block_timestamp: str
    close_order_algo: list[CloseOrderAlgo]

    _aliases: ClassVar = {"block_height": "block_height", "block_timestamp": "block_timestamp"}
    _nested_lists: ClassVar = {"closeOrderAlgo": CloseOrderAlgo}


class MaxSize(TypedRestObject):
    asset_id: str
    max_buy_sz: str
    max_sell_sz: str
    avail: str
    long_avail_pos: str
    short_avail_pos: str


class LeverageInfo(TypedRestObject):
    asset_id: str
    position_side: str
    leverage: str
    max_leverage: str
    margin_mode: str


class TradeFee(TypedRestObject):
    asset_id: str
    taker: str
    maker: str


class Bill(TypedRestObject):
    bill_id: str
    token_id: str
    margin_mode: str
    asset_id: str
    bal_chg: str
    bal: str
    flow_category: str
    bill_type: str
    source: str
    destination: str
    oid: str
    trade_id: str
    c_time: str

    _aliases: ClassVar = {"source": "from", "destination": "to"}


class BillsPage(TypedRestObject):
    next_cursor: str | None
    has_more: bool
    data: list[Bill]

    _nested_lists: ClassVar = {"data": Bill}


class SubAccount(TypedRestObject):
    address: str
    position_mode: str


class Agent(TypedRestObject):
    address: str
    status: str
    expiry: str


class AccountDetail(TypedRestObject):
    user: str
    parent_account: str
    sub_accounts: list[SubAccount]
    level: str
    position_mode: str
    ip: str
    agents: list[Agent]

    _nested_lists: ClassVar = {"subAccounts": SubAccount, "agents": Agent}


class ExecutionStatus(TypedRestObject):
    resting: TypedRestObject
    filled: TypedRestObject
    error: TypedRestObject
    success_with_adjustment: TypedRestObject

    _nested: ClassVar = {
        "resting": TypedRestObject,
        "filled": TypedRestObject,
        "error": TypedRestObject,
        "successWithAdjustment": TypedRestObject,
    }


class TransactionData(TypedRestObject):
    statuses: list[ExecutionStatus]

    _nested_lists: ClassVar = {"statuses": ExecutionStatus}


class TransactionResponse(TypedRestObject):
    type: str
    data: TransactionData
    code: str
    message: str

    _nested: ClassVar = {"data": TransactionData}


class TransactionReceipt(TypedRestObject):
    tx_hash: str
    block_height: str
    block_hash: str
    tx_index: str
    status: str
    response: TransactionResponse

    _nested: ClassVar = {"response": TransactionResponse}


class Order(TypedRestObject):
    oid: str
    client_order_id: str
    asset_id: str
    side: str
    margin_mode: str
    reduce_only: bool
    order_type: str
    tif: str
    price: str
    size: str
    acc_fill_sz: str
    avg_px: str
    state: str
    trigger_px: str
    trigger_price_type: str
    is_market: bool
    tpsl: str
    grouping: str
    parent_order_id: str
    cancel_reason: str
    c_time: str
    u_time: str
    tx_hash: str


class AttachedAlgoOrder(TypedRestObject):
    oid: str
    asset_id: str
    side: str
    position_side: str
    margin_mode: str
    leverage: str
    price: str
    size: str
    reduce_only: bool
    trigger_px: str
    trigger_price_type: str
    trigger_cond: str
    is_market: bool
    tpsl: str
    parent_order_id: str
    is_active: bool
    tp_limit: bool


class PendingOrder(TypedRestObject):
    oid: str
    block_height: str
    block_timestamp: str
    client_order_id: str
    asset_id: str
    side: str
    position_side: str
    margin_mode: str
    leverage: str
    order_type: str
    tif: str
    price: str
    size: str
    acc_fill_sz: str
    avg_px: str
    state: str
    reduce_only: bool
    parent_order_id: str
    attach_algo_ords: list[AttachedAlgoOrder]
    trigger_px: str
    trigger_price_type: str
    trigger_cond: str
    is_market: bool
    tpsl: str
    tp_limit: bool

    _aliases: ClassVar = {"block_height": "block_height", "block_timestamp": "block_timestamp"}
    _nested_lists: ClassVar = {"attachAlgoOrds": AttachedAlgoOrder}


class PendingOrders(TypedRestObject):
    next_cursor: str | None
    has_more: bool
    data: list[PendingOrder]

    _nested_lists: ClassVar = {"data": PendingOrder}


class OrderHistory(TypedRestObject):
    oid: str
    client_order_id: str
    asset_id: str
    side: str
    position_side: str
    margin_mode: str
    order_type: str
    tif: str
    price: str
    size: str
    acc_fill_sz: str
    avg_px: str
    state: str
    reduce_only: bool
    parent_order_id: str
    trigger_px: str
    trigger_price_type: str
    trigger_cond: str
    is_market: bool
    tpsl: str
    tp_limit: bool
    cancel_reason: str
    error_code: str
    children: list[str]
    block_height: str
    block_timestamp: str

    _aliases: ClassVar = {"block_height": "block_height", "block_timestamp": "block_timestamp"}


class Fill(TypedRestObject):
    trade_id: str
    oid: str
    client_order_id: str
    asset_id: str
    side: str
    exec_type: str
    price: str
    size: str
    fee: str
    fee_token_id: str
    rebate: str
    rebate_token_id: str
    closed_pnl: str
    fill_dir: str
    start_position: str
    block_timestamp: str

    _aliases: ClassVar = {"block_timestamp": "block_timestamp"}


class OrderHistoryPage(TypedRestObject):
    next_cursor: str | None
    has_more: bool
    data: list[OrderHistory]

    _nested_lists: ClassVar = {"data": OrderHistory}


class FillsPage(TypedRestObject):
    next_cursor: str | None
    has_more: bool
    data: list[Fill]

    _nested_lists: ClassVar = {"data": Fill}


class WriteResult(TypedRestObject):
    code: str
    msg: str
    tx_hash: str
    server_timestamp: str
    expires_after: str


REST_RESPONSE_MODELS: dict[str, type[TypedRestObject]] = {
    "/api/v5/exchangeos/market/token-info": TokenInfo,
    "/api/v5/exchangeos/market/instruments": Instrument,
    "/api/v5/exchangeos/market/tickers": Ticker,
    "/api/v5/exchangeos/market/order-book": OrderBook,
    "/api/v5/exchangeos/market/mark-prices": MarkPrice,
    "/api/v5/exchangeos/market/position-tiers": PositionTier,
    "/api/v5/exchangeos/market/funding-rate-history": FundingRateHistoryPage,
    "/api/v5/exchangeos/market/funding-rate": FundingRate,
    "/api/v5/exchangeos/market/open-interest": OpenInterest,
    "/api/v5/exchangeos/market/price-limit": PriceLimit,
    "/api/v5/exchangeos/market/index-tickers": IndexTicker,
    "/api/v5/exchangeos/account/balance": AccountBalance,
    "/api/v5/exchangeos/account/positions": Position,
    "/api/v5/exchangeos/account/max-size": MaxSize,
    "/api/v5/exchangeos/account/position-tiers": AccountPositionTier,
    "/api/v5/exchangeos/account/leverage-info": LeverageInfo,
    "/api/v5/exchangeos/account/trade-fee": TradeFee,
    "/api/v5/exchangeos/account/bills": BillsPage,
    "/api/v5/exchangeos/account/detail": AccountDetail,
    "/api/v5/exchangeos/trade/transaction": TransactionReceipt,
    "/api/v5/exchangeos/trade/order": Order,
    "/api/v5/exchangeos/trade/orders-pending": PendingOrders,
    "/api/v5/exchangeos/trade/orders-history": OrderHistoryPage,
    "/api/v5/exchangeos/trade/fills": FillsPage,
    "/api/v5/exchangeos/trade/place-order": TransactionReceipt,
    "/api/v5/exchangeos/trade/cancel-order": TransactionReceipt,
    "/api/v5/exchangeos/trade/modify-order": TransactionReceipt,
    "/api/v5/exchangeos/trade/cancel-all-after": WriteResult,
    "/api/v5/exchangeos/account/account-transfer": TransactionReceipt,
    "/api/v5/exchangeos/account/create-sub-account": TransactionReceipt,
    "/api/v5/exchangeos/account/set-leverage": TransactionReceipt,
    "/api/v5/exchangeos/account/set-margin-mode": TransactionReceipt,
    "/api/v5/exchangeos/account/set-position-mode": TransactionReceipt,
    "/api/v5/exchangeos/account/adjust-isolated-margin": TransactionReceipt,
}


__all__ = [name for name, value in globals().items() if isinstance(value, type)]
