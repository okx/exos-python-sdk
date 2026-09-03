from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
import pytest

from exchangeos_sdk import (
    Chain,
    Environment,
    ExchangeOSClient,
    FundingRateHistoryPage,
    RestList,
    RestMarketType,
)
from exchangeos_sdk.api import MARKET_ENDPOINTS


@dataclass(frozen=True)
class PublicEndpointCase:
    method_name: str
    path: str
    kwargs: dict[str, Any]
    query: dict[str, str]


PUBLIC_ENDPOINT_CASES = (
    PublicEndpointCase("token_info", "token-info", {}, {}),
    PublicEndpointCase(
        "instruments",
        "instruments",
        {"market_type": RestMarketType.PERP},
        {"marketType": "perp"},
    ),
    PublicEndpointCase(
        "tickers",
        "tickers",
        {"market_type": RestMarketType.PERP, "asset_id": 2},
        {"marketType": "perp", "assetId": "2"},
    ),
    PublicEndpointCase(
        "order_book",
        "order-book",
        {"asset_id": 2, "depth": 5},
        {"assetId": "2", "depth": "5"},
    ),
    PublicEndpointCase(
        "candles",
        "candles",
        {"asset_id": 2, "bar": "1m", "limit": 1},
        {"assetId": "2", "bar": "1m", "limit": "1"},
    ),
    PublicEndpointCase("mark_prices", "mark-prices", {"asset_id": 2}, {"assetId": "2"}),
    PublicEndpointCase("position_tiers", "position-tiers", {"asset_id": 2}, {"assetId": "2"}),
    PublicEndpointCase(
        "funding_rate_history",
        "funding-rate-history",
        {"asset_id": 2, "limit": 1},
        {"assetId": "2", "limit": "1"},
    ),
    PublicEndpointCase("funding_rate", "funding-rate", {"asset_id": 2}, {"assetId": "2"}),
    PublicEndpointCase("open_interest", "open-interest", {"asset_id": 2}, {"assetId": "2"}),
    PublicEndpointCase("price_limit", "price-limit", {"asset_id": 2}, {"assetId": "2"}),
    PublicEndpointCase("index_tickers", "index-tickers", {"asset_id": 2}, {"assetId": "2"}),
)

AUTH_HEADERS = {
    "authorization",
    "ok-access-key",
    "ok-access-sign",
    "ok-access-timestamp",
    "ok-access-passphrase",
}

TEST_ENVIRONMENT = Environment.custom(
    name="test",
    rest_url="http://localhost",
    websocket_url="ws://localhost/ws",
    signing_chain=Chain.TESTNET,
)


def test_public_endpoint_cases_cover_the_complete_market_inventory() -> None:
    assert {case.method_name for case in PUBLIC_ENDPOINT_CASES} == set(MARKET_ENDPOINTS)


@pytest.mark.parametrize("case", PUBLIC_ENDPOINT_CASES, ids=lambda case: case.method_name)
def test_every_public_endpoint_is_called_without_authentication(
    case: PublicEndpointCase,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == f"/api/v5/exchangeos/market/{case.path}"
        assert dict(request.url.params) == case.query
        assert AUTH_HEADERS.isdisjoint({name.lower() for name in request.headers})
        data: Any = []
        if case.method_name == "funding_rate_history":
            data = [{"data": [], "hasMore": False, "nextCursor": ""}]
        return httpx.Response(200, json={"code": "0", "msg": "", "data": data})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = ExchangeOSClient(environment=TEST_ENVIRONMENT, http_client=http)
    try:
        result = getattr(client.market, case.method_name)(**case.kwargs)
    finally:
        http.close()

    if case.method_name == "funding_rate_history":
        assert isinstance(result[0], FundingRateHistoryPage)
        assert isinstance(result[0].data, RestList)
    else:
        assert isinstance(result, RestList)


LIVE_PUBLIC_ENDPOINT_CASES = tuple(
    PublicEndpointCase(
        case.method_name,
        case.path,
        {
            key: int(os.getenv("EXCHANGEOS_TEST_ASSET_ID", "2")) if key == "asset_id" else value
            for key, value in case.kwargs.items()
            if key != "market_type"
        },
        {},
    )
    for case in PUBLIC_ENDPOINT_CASES
)


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("EXCHANGEOS_RUN_LIVE_TESTS") != "1",
    reason="set EXCHANGEOS_RUN_LIVE_TESTS=1 to call the public beta API",
)
@pytest.mark.parametrize("case", LIVE_PUBLIC_ENDPOINT_CASES, ids=lambda case: case.method_name)
def test_live_public_endpoint_needs_no_token_or_credentials(
    case: PublicEndpointCase,
) -> None:
    environment = Environment.custom(
        name="live-test",
        rest_url=os.getenv("EXCHANGEOS_TEST_BASE_URL", "https://beta.okex.org"),
        websocket_url=os.getenv("EXCHANGEOS_TEST_WS_URL", "wss://ws.okx.com:8443/ws/v5/business"),
        signing_chain=Chain.TESTNET,
    )
    with ExchangeOSClient(environment=environment) as client:
        result = getattr(client.market, case.method_name)(**case.kwargs)

    if case.method_name == "funding_rate_history":
        assert isinstance(result[0], FundingRateHistoryPage)
        assert isinstance(result[0].data, RestList)
    else:
        assert isinstance(result, RestList)
