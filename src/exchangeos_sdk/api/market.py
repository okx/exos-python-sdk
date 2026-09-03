"""Public Spot and Perps market-data API."""

from ..exceptions import ValidationError
from ..models import (
    Candle,
    FundingRate,
    FundingRateHistoryPage,
    IndexTicker,
    Instrument,
    MarkPrice,
    OpenInterest,
    OrderBook,
    PositionTier,
    PriceLimit,
    RestList,
    RestMarketType,
    Ticker,
    TokenInfo,
)
from .base import ROOT, BaseAPI

MARKET_ENDPOINTS = (
    "token_info",
    "instruments",
    "tickers",
    "order_book",
    "candles",
    "mark_prices",
    "position_tiers",
    "funding_rate_history",
    "funding_rate",
    "open_interest",
    "price_limit",
    "index_tickers",
)


class MarketAPI(BaseAPI):
    """Public Spot and Perps market data."""

    _ROOT = f"{ROOT}/market"
    endpoint_names = MARKET_ENDPOINTS

    def token_info(self) -> RestList[TokenInfo]:
        return self._public_get(f"{self._ROOT}/token-info")

    def instruments(
        self,
        *,
        market_type: RestMarketType | str | None = None,
        asset_id: str | int | None = None,
    ) -> RestList[Instrument]:
        return self._public_get(
            f"{self._ROOT}/instruments", marketType=market_type, assetId=asset_id
        )

    def tickers(
        self,
        *,
        market_type: RestMarketType | str | None = None,
        asset_id: str | int | None = None,
    ) -> RestList[Ticker]:
        if market_type is None and asset_id is None:
            raise ValidationError("tickers requires market_type or asset_id")
        return self._public_get(f"{self._ROOT}/tickers", marketType=market_type, assetId=asset_id)

    def order_book(self, asset_id: str | int, *, depth: int | None = None) -> RestList[OrderBook]:
        return self._public_get(f"{self._ROOT}/order-book", assetId=asset_id, depth=depth)

    def candles(
        self,
        asset_id: str | int,
        *,
        bar: str | None = None,
        limit: int | None = None,
        begin: int | None = None,
        end: int | None = None,
    ) -> RestList[Candle]:
        return self._public_get(
            f"{self._ROOT}/candles",
            assetId=asset_id,
            bar=bar,
            limit=limit,
            begin=begin,
            end=end,
        )

    def mark_prices(self, *, asset_id: str | int | None = None) -> RestList[MarkPrice]:
        return self._public_get(f"{self._ROOT}/mark-prices", assetId=asset_id)

    def position_tiers(self, asset_id: str | int) -> RestList[PositionTier]:
        return self._public_get(f"{self._ROOT}/position-tiers", assetId=asset_id)

    def funding_rate_history(
        self,
        asset_id: str | int,
        *,
        begin: int | None = None,
        end: int | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> RestList[FundingRateHistoryPage]:
        return self._public_get(
            f"{self._ROOT}/funding-rate-history",
            assetId=asset_id,
            begin=begin,
            end=end,
            limit=limit,
            cursor=cursor,
        )

    def funding_rate(self, *, asset_id: str | int | None = None) -> RestList[FundingRate]:
        return self._public_get(f"{self._ROOT}/funding-rate", assetId=asset_id)

    def open_interest(self, *, asset_id: str | int | None = None) -> RestList[OpenInterest]:
        return self._public_get(f"{self._ROOT}/open-interest", assetId=asset_id)

    def price_limit(self, asset_id: str | int) -> RestList[PriceLimit]:
        return self._public_get(f"{self._ROOT}/price-limit", assetId=asset_id)

    def index_tickers(self, *, asset_id: str | int | None = None) -> RestList[IndexTicker]:
        return self._public_get(f"{self._ROOT}/index-tickers", assetId=asset_id)
