# REST API coverage

All methods are synchronous. Public methods work without credentials; when
credentials or a bearer token are configured, public REST methods authenticate
the request as well. Private reads use the configured API credentials or bearer
token, while
private writes accept an EIP-712 signed transaction envelope.

Create the client with either API credentials or a bearer token. The two modes
are mutually exclusive. Calling a private method without either one raises
`AuthenticationError` before network I/O.

```python
from exos_python_sdk import BearerAuth, Credentials, ExchangeOSClient

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
Unknown camelCase fields are also available through their snake_case attribute
name (for example, a future `newField` can be read as `model.new_field`), so
additive OpenAPI/TradeZone response changes do not require an SDK release.
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

Collection methods use the unified `data[0]` envelope. Their result contains
one `FundingRateHistoryPage`, `BillsPage`, `PendingOrders`, `OrderHistoryPage`,
or `FillsPage`. Funding, bills, order-history, and fills pages expose `data`,
`has_more`, and `next_cursor`. Pending orders expose `block_height`,
`block_timestamp`, and `data`; the block metadata describes the snapshot
returned by that response.
Transitional deployments that return Funding/Bills pages directly are
normalized to the same SDK shape.

## Pagination

Pagination results are list-compatible because the ExchangeOS response envelope
contains the page at `data[0]`. Select that first page before reading records or
the next cursor:

```python
with ExchangeOSClient(auth=credentials) as client:
    result = client.trade.orders_history(asset_id="2", limit=50)

page = result[0]
for order in page.data:
    print(order.order_id, order.state)

if page.has_more:
    next_result = client.trade.orders_history(asset_id="2", cursor=page.next_cursor)
```

```python
from exos_python_sdk import ClientOptions, ExchangeOSClient

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

In the endpoint tables below:

- **Required** means the Python method cannot be called without that value.
- **Optional** means `None` is omitted from the request.
- **Conditional** means the method accepts the value optionally, but the
  ExchangeOS backend applies a rule based on another parameter or the account.
- **Exactly one** means the backend requires one of the listed identifiers.

`Wire name` is the exact query-string or JSON field name sent to ExchangeOS. It
is not a second argument name that callers need to provide. For example:

```python
client.market.order_book(asset_id="2", depth=20)
```

sends query parameters equivalent to `assetId=2&depth=20`. The same naming
direction applies to signed action JSON (`client_order_id` becomes
`clientOrderId`). For responses, mapping keys keep their wire spelling while
typed attributes use `snake_case`, so `ticker["lastPx"]` and
`ticker.last_px` refer to the same value.

| Python parameter | Wire name |
|---|---|
| `market_type` | `marketType` |
| `fund_type` | `fundType` |
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

## Error handling

All SDK exceptions inherit from `ExchangeOSError`. Catch the most specific
error first:

```python
from exos_python_sdk import (
    APIError,
    AuthenticationError,
    RateLimitError,
    SigningError,
    TransportError,
    ValidationError,
)

try:
    tickers = client.market.tickers(asset_id="2")
except RateLimitError as error:
    # HTTP 429. `retry_after` is populated from Retry-After when available.
    wait_seconds = error.retry_after or 1.0
    print(f"Rate limited; retry after {wait_seconds}s (request_id={error.request_id})")
except AuthenticationError as error:
    # Correct or refresh API credentials / bearer token before retrying.
    print(error.code, error.message, error.request_id)
except APIError as error:
    # ExchangeOS business or request error.
    print(error.code, error.message, error.status_code, error.request_id)
except TransportError as error:
    # Network/HTTP transport failure. Retry only when application policy permits it.
    print(error.method, error.path)
except (ValidationError, SigningError) as error:
    # Local input or signing error; no request was sent.
    print(error)
```

`APIError` exposes `code`, `message`, `status_code`, `request_id`, `data`, and
the decoded response envelope as `response`. `AuthenticationError` and
`RateLimitError` are `APIError` subclasses, so they must be caught first.

The SDK retries idempotent reads according to `RetryPolicy`; it never retries
writes. Do not blindly retry a signed POST after `TransportError`, because the
transaction might have reached ExchangeOS. Instead, use the transaction hash
or related order state to determine the outcome before constructing a new
transaction. In production logs, prefer the error code, status, and request ID
over the complete `response`, which can contain account-specific data.

## Environment

`Environment` is the single deployment setting. It prevents a REST request
from accidentally using a WebSocket endpoint or signing source from another
network. `PRODUCTION` is selected by default. For a non-production deployment,
set all three values together; do not override an endpoint or signing source
on its own.

```python
import os

from exos_python_sdk import Chain, Environment, ExchangeOSClient

environment = Environment.custom(
    name="custom",
    rest_url=os.environ["EXCHANGEOS_REST_URL"],
    websocket_url=os.environ["EXCHANGEOS_WS_URL"],
    signing_chain=Chain.TESTNET,
)
client = ExchangeOSClient(environment=environment)
```

Set the URL environment variables to the endpoints supplied by your deployment.
Change `signing_chain` to match that deployment.

`signing_chain` selects the EIP-712 `Agent.source` value. It is intentionally
chosen by the Environment and cannot be separately overridden in
`client.sign_action(...)`; the protocol EIP-712 domain chain ID is fixed. See
[Signing](signing.md#protocol) for the protocol details.

## Transport configuration

The SDK uses a ten-second default timeout. Pass a float for one shared timeout,
or an `httpx.Timeout` for phase-specific values. Transport settings live in
`ClientOptions` rather than expanding the primary constructor. When an
application supplies `http_client`, that caller-owned client must configure its
own timeout and proxy; combining those settings is rejected rather than ignored.

```python
import httpx

from exos_python_sdk import ClientOptions, ExchangeOSClient

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
from exos_python_sdk import ClientOptions, ExchangeOSClient, RestEvent


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
| GET | `/api/v5/exchangeos/market/security-fund` | `security_fund()` |

### Market parameters

All Market methods are public. The required and optional parameters exposed by
the SDK are:

| Python method | Required | Optional / conditional | Wire names |
|---|---|---|---|
| `token_info()` | — | — | — |
| `instruments()` | — | `market_type`, `asset_id` | `marketType`, `assetId` |
| `tickers()` | — | `market_type`, `asset_id` | `marketType`, `assetId` |
| `order_book(asset_id)` | `asset_id` | `depth` | `assetId`, `depth` |
| `candles(asset_id)` | `asset_id` | `bar`, `limit`, `begin`, `end` | `assetId`, `bar`, `limit`, `begin`, `end` |
| `mark_prices()` | — | `asset_id` | `assetId` |
| `position_tiers(asset_id)` | `asset_id` | — | `assetId` |
| `funding_rate_history(asset_id)` | `asset_id` | `begin`, `end`, `limit`, `cursor` | `assetId`, `begin`, `end`, `limit`, `cursor` |
| `funding_rate()` | — | `asset_id` | `assetId` |
| `open_interest()` | — | `asset_id` | `assetId` |
| `price_limit(asset_id)` | `asset_id` | — | `assetId` |
| `index_tickers()` | — | `asset_id` | `assetId` |
| `security_fund(fund_type)` | `fund_type` | `asset_id` is conditional | `fundType`, `assetId` |

`security_fund()` requires `asset_id` for `SECURITY_FUND` and requires it to be
omitted for `SECURITY_VAULT` and `SUPPLEMENTARY_FUND`; the backend remains the
source of truth for that conditional rule.

`token_info()` exposes the optional `wei_decimals` precision field as an
integer; it remains `None` when the backend has no precision value.

Use `RestMarketType.SPOT` or `RestMarketType.PERP` for `instruments()` and
`tickers()`. Strings remain accepted for forward compatibility. `asset_id`
accepts a string or integer and is serialized as `assetId`. Instrument filters
`market_type` and `asset_id` are forwarded as supplied so the OpenAPI backend
can apply the current selector rules. A line-wide ticker query typically uses
`market_type`; a single-asset ticker query may use `asset_id` alone. When both
ticker selectors are supplied, the server verifies that the asset belongs to
the requested market type. `order_book()`, `candles()`, `position_tiers()`,
`funding_rate_history()`, and `price_limit()` require `asset_id` through their
Python signatures.

`security_fund()` accepts `SecurityFundType.SECURITY_VAULT`,
`SecurityFundType.SECURITY_FUND`, or `SecurityFundType.SUPPLEMENTARY_FUND`.
Pass `asset_id` only with `SECURITY_FUND`; ExchangeOS requires it for that
type and rejects it for the other two. The response follows the server's
nested wrapper: `result[0].data[0]` is the fund record, and its `history`
contains at most seven daily balance snapshots.

Candles and funding history use `begin`/`end`; the removed `before`/`after`
names are not accepted. Order-book `depth` must be between 1 and 400. Candle
`bar` accepts `1m`, `5m`, `15m`, `1H`, `4H`, or `1D`. Funding history also
accepts an opaque `cursor` and a page size from 1 through 100.

## Trade

| Method | Route | Python method |
|---|---|---|
| POST | `/api/v5/exchangeos/trade/place-order` | `place_order()` |
| POST | `/api/v5/exchangeos/trade/cancel-order` | `cancel_order()` |
| POST | `/api/v5/exchangeos/trade/noop` | `noop()` |
| POST | `/api/v5/exchangeos/trade/modify-order` | `modify_order()` |
| POST | `/api/v5/exchangeos/trade/cancel-all-after` | `cancel_all_after()` |
| GET | `/api/v5/exchangeos/trade/transaction` | `transaction()` |
| GET | `/api/v5/exchangeos/trade/order` | `order()` |
| GET | `/api/v5/exchangeos/trade/orders-pending` | `orders_pending()` |
| GET | `/api/v5/exchangeos/trade/orders-history` | `orders_history()` |
| GET | `/api/v5/exchangeos/trade/fills` | `fills()` |

### Trade parameters

Signed trade writes take one required `signed_transaction` body. The
action-specific fields are documented in [Signing](signing.md); they are not
passed as separate REST method arguments.

| Python method | Required | Optional / conditional | Wire names |
|---|---|---|---|
| `place_order(signed_transaction)` | `signed_transaction` | — | JSON body |
| `cancel_order(signed_transaction)` | `signed_transaction` | — | JSON body |
| `noop(signed_transaction)` | `signed_transaction` | — | JSON body |
| `modify_order(signed_transaction)` | `signed_transaction` | — | JSON body |
| `cancel_all_after(signed_transaction)` | `signed_transaction` | — | JSON body |
| `transaction(tx_hash)` | `tx_hash` | — | `txHash` |
| `order()` | exactly one of `oid` / `client_order_id` | `vault_address` | `oid`, `clientOrderId`, `vaultAddress` |
| `orders_pending()` | — | `point_board`, `asset_id`, `vault_address` | `pointBoard`, `assetId`, `vaultAddress` |
| `orders_history()` | — | `point_board`, `asset_id`, `state`, `begin`, `end`, `cursor`, `limit`, `vault_address` | `pointBoard`, `assetId`, `state`, `begin`, `end`, `cursor`, `limit`, `vaultAddress` |
| `fills()` | — | `point_board`, `asset_id`, `begin`, `end`, `cursor`, `limit`, `vault_address` | `pointBoard`, `assetId`, `begin`, `end`, `cursor`, `limit`, `vaultAddress` |

The `order()` method accepts both identifiers in its Python signature so the
request can be built flexibly, but ExchangeOS requires exactly one of them.
`cancel_all_after()` has no separate `expires_after` argument: put
`nonce`, `expiresAfter`, and the `cancelAll` action in the signed transaction
as described in [Signing](signing.md).

Signed write methods accept either a `SignedTransaction` or a mapping in its
wire shape. OpenAPI defaults omitted write `mode` to synchronous receipt mode,
which is the SDK contract. `orders_pending()` is also available as
`pending_orders`, and `orders_history()` as `order_history` for compatibility.
`noop()` accepts a signed `Noop` action, waits for the canonical receipt, and
invalidates that transaction nonce without placing or canceling an order.

For typed actions, `order_item()` requires `market_type` (`spot` or `perp`).
When `client_order_id` is omitted, the helper generates a valid API client
order ID and includes it in the signed action. Raw signed mappings are
forwarded unchanged; the OpenAPI backend validates required fields such as
`marketType` and `clientOrderId`.

For `cancel`, a cancellation may also omit `marketType` according to the
current ExchangeOS API contract. `cancelAll` continues to require
`marketType` and only Spot/Perps market types are supported by the SDK trade
surface. Batch-size limits are validated by the OpenAPI backend.

`order()` forwards `oid` and `client_order_id` as supplied; the OpenAPI backend
currently applies the rule that exactly one identifier must be provided.
Identifier formats and Trade list query values are likewise validated by the
server, keeping the SDK compatible with future API changes.

Pending orders accept `point_board`, `asset_id`, and `vault_address`.
Order history and fills additionally accept `cursor` and `limit`.
The pending-order response places `block_height` and `block_timestamp` on the
page wrapper and includes `assetStatus` and `leverage` on each order. Pending
orders do not expose `avgPx`.
Typed REST fill rows expose realized PnL as `pnl`, include `block_height`, and
use the PascalCase `fillDir` vocabulary shared with the WebSocket stream.
History and fills use the exclusive time bounds `begin` and `end`; legacy
`before` and `after` are rejected by the server.

`cancel_all_after()` returns a dedicated `CancelAllAfterResult` containing only
`server_timestamp` and `expires_after`. Confirmed transaction receipts expose
the block and response fields; asynchronous or not-yet-confirmed responses may
contain only `tx_hash`, so those confirmation fields are optional.

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
| GET | `/api/v5/exchangeos/account/limits` | `limits()` |
| GET | `/api/v5/exchangeos/account/bills` | `bills()` |
| GET | `/api/v5/exchangeos/account/detail` | `detail()` |

### Account parameters

Account writes use a required signed transaction body. Account reads use the
following query parameters:

| Python method | Required | Optional / conditional | Wire names |
|---|---|---|---|
| `account_transfer(signed_transaction)` | `signed_transaction` | — | JSON body |
| `create_sub_account(signed_transaction)` | `signed_transaction` | — | JSON body |
| `set_leverage(signed_transaction)` | `signed_transaction` | — | JSON body |
| `set_margin_mode(signed_transaction)` | `signed_transaction` | — | JSON body |
| `set_position_mode(signed_transaction)` | `signed_transaction` | — | JSON body |
| `adjust_isolated_margin(signed_transaction)` | `signed_transaction` | — | JSON body |
| `balance()` | — | `vault_address`, `point_board` | `vaultAddress`, `pointBoard` |
| `positions()` | — | `asset_id`, `vault_address`, `point_board` | `assetId`, `vaultAddress`, `pointBoard` |
| `max_size(asset_id)` | `asset_id` | `price`, `leverage`, `reduce_only`, `vault_address` | `assetId`, `price`, `leverage`, `reduceOnly`, `vaultAddress` |
| `position_tiers(asset_id)` | `asset_id` | `vault_address` | `assetId`, `vaultAddress` |
| `leverage_info(asset_id)` | `asset_id` | `position_side`, `vault_address` | `assetId`, `positionSide`, `vaultAddress` |
| `trade_fee(asset_id)` | `asset_id` | — | `assetId` |
| `limits()` | — | `vault_address` | `vaultAddress` |
| `bills()` | — | `token_id`, `asset_id`, `flow_category`, `bill_type`, `begin`, `end`, `cursor`, `limit`, `vault_address`, `point_board` | `tokenId`, `assetId`, `flowCategory`, `billType`, `begin`, `end`, `cursor`, `limit`, `vaultAddress`, `pointBoard` |
| `detail()` | — | — | — |

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
`limits(vault_address=...)` returns the action, daily CancelAll, cancellation
exemption, and open-order limits for the authenticated parent account or owned
subaccount. Numeric values remain exact decimal strings.

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
