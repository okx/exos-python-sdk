# REST API coverage

All methods are synchronous. Public methods need no credentials. Private
reads use OKX V5 request authentication, while private writes accept an
EIP-712 signed transaction envelope.

Create the client with either API credentials or a bearer token. The two modes
are mutually exclusive. Calling a private method without either one raises
`AuthenticationError` before network I/O.

```python
from exchangeos_sdk import BearerAuth, Credentials, ExchangeOSClient

credentials = Credentials(api_key="...", secret_key="...", passphrase="...")
client = ExchangeOSClient(auth=credentials)

# Alternative authentication mode:
bearer_client = ExchangeOSClient(auth=BearerAuth("..."))
```

The client returns the response envelope's `data` value as endpoint-specific
models such as `Ticker`, `Instrument`, `Order`, `Position`, and
`TransactionReceipt`, normally inside `RestList`. All object models subclass
`dict`, so existing container operations continue to work and unknown server
fields are retained in the mapping and exposed through `model.extra`.
Scalar `data` values retain their JSON type. API failures raise
`APIError` with the server code, message, HTTP status, request ID, response
data, and original decoded response.

## Response values

Price, quantity, asset value, fee, and PnL strings are never converted to
binary floating point. Use `model.decimal("price")` or `as_decimal(value)` when
arithmetic is needed. Millisecond timestamps also retain their original value;
use `model.utc_datetime("ts")` or `as_utc_datetime(value)` for a timezone-aware
UTC view.

Nested documented fields are typed too, for example
`receipt.response.data.statuses` and `balance.details`. Decimal and timestamp
helpers remain available on every typed object. Set
`ClientOptions(preserve_raw_response=True)` to attach the complete decoded API
envelope to the top-level model as `raw_response`.

Common model enums such as `OrderState`, `Side`, and `TimeInForce` retain an
unknown server string instead of failing to parse it.

All paginated methods use the unified `data[0]` envelope. Their result contains
one `FundingRateHistoryPage`, `BillsPage`, `PendingOrders`, `OrderHistoryPage`,
or `FillsPage`. Every page exposes `data`, `has_more`, and `next_cursor`.
Transitional deployments that return Funding/Bills pages directly are
normalized to the same SDK shape.

```python
from exchangeos_sdk import ClientOptions, ExchangeOSClient

with ExchangeOSClient(
    options=ClientOptions(preserve_raw_response=True)
) as client:
    tickers = client.market.tickers(asset_id=602)
    exact_price = tickers[0].decimal("lastPx")
    print(tickers[0].asset_id, tickers[0].last_px)
    envelope = tickers.raw_response
```

Typed attributes use Python `snake_case`; mapping keys keep the server's exact
wire spelling. For example, `ticker.last_px` and `ticker["lastPx"]` refer to the
same value. Candle rows are exposed as `Candle` objects with named fields while
the original string values remain unchanged.

## Parameter and wire names

Public Python methods use `snake_case`. The SDK serializes them to the OpenAPI
wire names below; callers should pass the Python name, not manually construct
the camelCase form.

| Python parameter | Wire name |
|---|---|
| `market_type` | `marketType` |
| `asset_id` | `assetId` |
| `vault_address` | `vaultAddress` |
| `client_order_id` | `clientOrderId` |
| `order_id` / `oid` | `oid` |
| `tx_hash` | `txHash` |
| `token_id` | `tokenId` |
| `flow_category` | `flowCategory` |
| `bill_type` | `billType` |
| `reduce_only` | `reduceOnly` |
| `position_side` | `positionSide` |
| `point_board` | `pointBoard` |
| `signed_transaction` | JSON request body |

Names already matching OpenAPI, including `depth`, `bar`, `limit`, `begin`,
`end`, `cursor`, `price`, and `state`, are unchanged. Response object attributes use
the same snake_case convention while mapping keys retain their wire spelling.

The SDK keeps request handling thin. It uses required Python arguments and
checks only structural combinations that cannot be expressed by a function
signature. Enum membership, identifier formats, numeric ranges, time windows,
account ownership, and other business rules are validated by ExchangeOS. A
rejected value raises `APIError` with the server's code and message, keeping the
deployed API as the single source of truth.

## Environment

`Environment` is the single deployment setting. It prevents a REST request
from accidentally using a WebSocket endpoint or signing source from another
network. `PRODUCTION` is selected by default.

```python
from exchangeos_sdk import Chain, Environment, ExchangeOSClient

environment = Environment.custom(
    name="test",
    rest_url="https://test.example.com",
    websocket_url="wss://test.example.com/ws/v5/business",
    signing_chain=Chain.TESTNET,
)
client = ExchangeOSClient(environment=environment)
```

## Transport configuration

The SDK uses a ten-second default timeout. Pass a float for one shared timeout,
or an `httpx.Timeout` for phase-specific values. Transport settings live in
`ClientOptions` rather than expanding the primary constructor. When an
application supplies `http_client`, that caller-owned client must configure its
own timeout and proxy; combining those settings is rejected rather than ignored.

```python
import httpx

from exchangeos_sdk import ClientOptions, ExchangeOSClient

client = ExchangeOSClient(
    options=ClientOptions(
        timeout=httpx.Timeout(10.0, connect=2.0, read=10.0, write=5.0, pool=2.0),
        proxy="http://localhost:8080",
        user_agent="my-exchangeos-consumer/1.0",
    )
)
```

## Observability

Pass a `rest_event_hook` through `ClientOptions` to receive `request_start` and
`request_end` metadata.
End events contain latency, HTTP status, request ID, or a transport error type.
Events deliberately exclude query values, header values, bodies, and
credentials. Hooks are synchronous and failures are isolated from request
behavior.

`logging_policy` accepts `off` (the default), `metadata`, or `debug`. Both
enabled policies log only the same redacted metadata; debug mode never logs
payloads or authentication headers.

```python
from exchangeos_sdk import ClientOptions, ExchangeOSClient, RestEvent


def observe(event: RestEvent) -> None:
    print(event.name, event.status_code, event.latency_ms, event.request_id)


client = ExchangeOSClient(
    options=ClientOptions(rest_event_hook=observe, logging_policy="metadata")
)
```

## Market

`client.market` covers these public Spot and Perps routes:

| Method | Route | Python method |
|---|---|---|
| GET | `/api/v5/exchangeos/market/token-info` | `token_info()` |
| GET | `/api/v5/exchangeos/market/instruments` | `instruments()` |
| GET | `/api/v5/exchangeos/market/tickers` | `tickers()` |
| GET | `/api/v5/exchangeos/market/order-book` | `order_book()` |
| GET | `/api/v5/exchangeos/market/candles` | `candles()` |
| GET | `/api/v5/exchangeos/market/mark-prices` | `mark_prices()` |
| GET | `/api/v5/exchangeos/market/position-tiers` | `position_tiers()` |
| GET | `/api/v5/exchangeos/market/funding-rate-history` | `funding_rate_history()` |
| GET | `/api/v5/exchangeos/market/funding-rate` | `funding_rate()` |
| GET | `/api/v5/exchangeos/market/open-interest` | `open_interest()` |
| GET | `/api/v5/exchangeos/market/price-limit` | `price_limit()` |
| GET | `/api/v5/exchangeos/market/index-tickers` | `index_tickers()` |

Use `RestMarketType.SPOT` or `RestMarketType.PERP` for `instruments()` and
`tickers()`. Strings remain accepted for forward compatibility. `asset_id`
accepts a string or integer and is serialized as `assetId`. Instrument filters
`market_type` and `asset_id` are forwarded as supplied; their combination is
validated by ExchangeOS. A line-wide ticker query requires `market_type`; a
single-asset ticker query may use `asset_id` alone. When both ticker selectors
are supplied, the server verifies that the asset belongs to the requested
market type. `order_book()`, `candles()`, `position_tiers()`,
`funding_rate_history()`, and `price_limit()` require `asset_id` through their
Python signatures.

Candles and funding history use `begin`/`end`; the removed `before`/`after`
names are not accepted. Order-book `depth` must be between 1 and 400. Candle
`bar` accepts `1m`, `5m`, `15m`, `1H`, `4H`, or `1D`. Funding history also
accepts an opaque `cursor` and a page size from 1 through 100.

## Trade

| Method | Route | Python method |
|---|---|---|
| POST | `/api/v5/exchangeos/trade/place-order` | `place_order()` |
| POST | `/api/v5/exchangeos/trade/cancel-order` | `cancel_order()` |
| POST | `/api/v5/exchangeos/trade/modify-order` | `modify_order()` |
| POST | `/api/v5/exchangeos/trade/cancel-all-after` | `cancel_all_after()` |
| GET | `/api/v5/exchangeos/trade/transaction` | `transaction()` |
| GET | `/api/v5/exchangeos/trade/order` | `order()` |
| GET | `/api/v5/exchangeos/trade/orders-pending` | `orders_pending()` |
| GET | `/api/v5/exchangeos/trade/orders-history` | `orders_history()` |
| GET | `/api/v5/exchangeos/trade/fills` | `fills()` |

Signed write methods accept either a `SignedTransaction` or a mapping in its
wire shape. OpenAPI defaults omitted write `mode` to synchronous receipt mode,
which is the SDK contract. `orders_pending()` is also available as
`pending_orders`, and `orders_history()` as `order_history` for compatibility.

`order()` requires exactly one of `oid` or `client_order_id`; the SDK checks
this structural choice before network I/O. Identifier formats and Trade list
query values are validated by the server.

Pending orders, history, and fills accept `point_board`, `cursor`, and `limit`.
History and fills use the exclusive time bounds `begin` and `end`; legacy
`before` and `after` are rejected by the server.

```python
order = client.trade.order(client_order_id="0x...")
fills = client.trade.fills(asset_id=602, limit=100, vault_address="0x...")
fills_page = fills[0]
for fill in fills_page.data:
    print(fill.trade_id)
```

## Account

| Method | Route | Python method |
|---|---|---|
| POST | `/api/v5/exchangeos/account/account-transfer` | `account_transfer()` |
| POST | `/api/v5/exchangeos/account/create-sub-account` | `create_sub_account()` |
| POST | `/api/v5/exchangeos/account/set-leverage` | `set_leverage()` |
| POST | `/api/v5/exchangeos/account/set-margin-mode` | `set_margin_mode()` |
| POST | `/api/v5/exchangeos/account/set-position-mode` | `set_position_mode()` |
| POST | `/api/v5/exchangeos/account/adjust-isolated-margin` | `adjust_isolated_margin()` |
| GET | `/api/v5/exchangeos/account/balance` | `balance()` |
| GET | `/api/v5/exchangeos/account/positions` | `positions()` |
| GET | `/api/v5/exchangeos/account/max-size` | `max_size()` |
| GET | `/api/v5/exchangeos/account/position-tiers` | `position_tiers()` |
| GET | `/api/v5/exchangeos/account/leverage-info` | `leverage_info()` |
| GET | `/api/v5/exchangeos/account/trade-fee` | `trade_fee()` |
| GET | `/api/v5/exchangeos/account/bills` | `bills()` |
| GET | `/api/v5/exchangeos/account/detail` | `detail()` |

`vault_address` is accepted only by documented subaccount-aware reads. Account
`detail()` and `trade_fee()` always use the authenticated parent account.
The required positional arguments are:

- `max_size(asset_id, ...)`
- `position_tiers(asset_id, ...)`
- `leverage_info(asset_id, ...)`
- `trade_fee(asset_id)`

`max_size(reduce_only=True)` serializes the query value as lowercase `true`.
Account write methods accept the same signed-transaction forms as Trade writes.
`balance()`, `positions()`, and `bills()` accept the optional `point_board`
selector. Bills use `begin`, `end`, and opaque `cursor` pagination and return a
single `BillsPage` at result index zero. The Bills service treats `limit <= 0`
as its default page size and caps larger values at 100, so the SDK forwards
those values instead of applying the stricter Trade/Funding page validation.

## Custom requests and WebSocket composition

`client.request()` is the low-level escape hatch for an ExchangeOS route that
ships before a typed namespace method. `path` must be absolute; set
`auth=False` only for a public endpoint. The method still unwraps the `data`
envelope and applies the same typed response parsing as namespace methods.

`client.websocket()` creates an independent `ExchangeOSWebSocket` and inherits
the REST client's credentials or bearer token unless either value is explicitly
overridden. Its URL always comes from the same Environment and cannot be
overridden separately. Closing one transport does not close the other.

## Retry behavior

GET and HEAD requests can retry transport failures and HTTP 429 responses.
`ClientOptions(retry=RetryPolicy(...))` controls that behavior. POST requests
are sent once because retrying an ambiguous signed write can duplicate an order
or account operation.
