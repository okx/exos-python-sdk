# ExchangeOS Python SDK

Python SDK for the ExchangeOS Spot and Perps APIs. It covers 38 synchronous
REST routes, local MessagePack + EIP-712 transaction signing, and resilient
asynchronous public/private WebSocket subscriptions.

## Features

- `client.market`: 13 public Spot and Perps market-data methods.
- `client.trade`: 5 signed writes and 5 authenticated order queries.
- `client.account`: 6 signed writes and 9 authenticated account queries.
- Local MessagePack and EIP-712 signing for supported transaction Actions.
- 16 ExchangeOS public and 9 ExchangeOS private WebSocket channels.
- Heartbeats, bounded queues, sequence-gap recovery, reconnect backoff, and subscription replay.
- Decimal prices and quantities remain strings throughout the wire path.
- Forward-compatible REST models preserve unknown fields and expose Decimal/UTC helpers.
- Per-phase HTTP timeouts, proxy/User-Agent configuration, and safe lifecycle hooks.
- One `Environment` binds the REST URL, WebSocket URL, and signing chain.

Python 3.10+ is required. CI verifies Python 3.10–3.13.

The source tree is organized by capability: REST namespaces live under
`api/`, action builders and EIP-712 internals under `signing/`, and
channel definitions, message parsing, and transport state under `websocket/`.
See the [architecture guide](docs/architecture.md) for the module map.

## Install

```bash
python -m pip install exchangeos-sdk
```

For local development:

```bash
python -m pip install -e '.[test]'
```

## Quick start

```python
from exchangeos_sdk import ExchangeOSClient, RestMarketType

with ExchangeOSClient() as client:
    instruments = client.market.instruments(market_type=RestMarketType.PERP)
    print(instruments)
```

Public market-data methods need no credentials. Private REST and WebSocket
operations use API credentials:

```python
import os

from exchangeos_sdk import Credentials, ExchangeOSClient

credentials = Credentials(
    api_key=os.environ["EXCHANGEOS_API_KEY"],
    secret_key=os.environ["EXCHANGEOS_API_SECRET"],
    passphrase=os.environ["EXCHANGEOS_API_PASSPHRASE"],
)
client = ExchangeOSClient(auth=credentials)
```

### Which credentials do I need?

| Task | Required credential | Notes |
|---|---|---|
| Public REST or public WebSocket | None | Start here to verify installation; configured REST credentials may still be sent for public REST calls. |
| Private REST reads or private WebSocket | CEX API key, secret, and passphrase | Passed as `Credentials`. |
| Local transaction signing | Authorized Agent private key | Passed only to `client.sign_action(...)`; no network request is made. |
| Submit a signed transaction | CEX API credentials and a `SignedTransaction` | The submitting process need not hold the Agent private key. |

The API credentials and Agent private key have separate purposes; do not
interchange them. The SDK does not read or persist either value.

### Which market-type enum should I use?

Use `RestMarketType` for REST query arguments and `MarketType` only when
constructing a signed Action:

```python
from exchangeos_sdk import MarketType, RestMarketType

# REST query
client.market.tickers(market_type=RestMarketType.PERP)

# Signed Action field
order = order_item(..., market_type=MarketType.SPOT)
```

`MarketType.PREDICTION` exists only for legacy standalone signing compatibility;
this SDK submits signed Spot and Perps actions only.

`PRODUCTION` is the default deployment. A custom deployment must provide its
REST URL, WebSocket URL, and signing chain together:

```python
from exchangeos_sdk import Chain, Environment, ExchangeOSClient

test_environment = Environment.custom(
    name="test",
    rest_url="https://test.example.com",
    websocket_url="wss://test.example.com/ws/v5/business",
    signing_chain=Chain.TESTNET,
)
client = ExchangeOSClient(environment=test_environment)
```

Do not override those values independently: one `Environment` ensures REST,
WebSocket, and local signing all target the same deployment. Its
`signing_chain` selects the signing source (`Dev`, `Testnet`, or `Mainnet`)
inside the EIP-712 message; the EIP-712 domain's protocol chain ID remains
fixed. [Signing](docs/signing.md#protocol) explains the two
values in detail. Applications should load credentials from a secret provider
or environment variables.

REST `data` values use dict/list-compatible models that retain unknown fields
and exact decimal strings. Signed writes accept locally generated EIP-712
`SignedTransaction` objects and are never retried automatically. Use
`client.sign_action(...)` to apply the chain selected by the same Environment.
WebSocket sessions deliver raw JSON strings to callbacks and async iterators,
and support public/private subscriptions, heartbeat, bounded queues,
automatic reconnect, subscription replay, and order-book sequence-gap
recovery.

For complete runnable flows, including order signing, placement, cancellation,
private queries, and WebSocket subscriptions, see the
[examples guide](examples/README.md).

## Errors

All SDK failures derive from `ExchangeOSError`. Common subclasses include:

- `ConfigurationError` and `ValidationError` for failures before network I/O.
- `AuthenticationError`, `APIError`, and `RateLimitError` for server responses.
- `TransportError` and `WebSocketProtocolError` for transport/protocol failures.
- `SigningError` and `SequenceGapError` for signing and order-book integrity failures.

`APIError` retains the server code, message, HTTP status, request ID, decoded
data, and decoded response. Secret material is excluded from credential reprs
and signing errors.

## Documentation

- [Architecture](docs/architecture.md)
- [REST coverage](docs/rest-api.md)
- [Signing](docs/signing.md)
- [WebSocket](docs/websocket.md)
- [Security guidance](docs/security.md)
- [Protocol compatibility](docs/compatibility.md)
- [Release notes](CHANGELOG.md)

## Examples

- [`examples/public_rest.ipynb`](examples/public_rest.ipynb): public Spot and Perps
  instruments and tickers.
- [`examples/account_queries.ipynb`](examples/account_queries.ipynb): authenticated
  balance and position queries.
- [`examples/sign_transaction.ipynb`](examples/sign_transaction.ipynb): local Perps
  action construction and EIP-712 signing without a REST submission.
- [`examples/place_order.ipynb`](examples/place_order.ipynb): signed Perps limit-order
  submission using REST and EIP-712 authentication.
- [`examples/order_queries.ipynb`](examples/order_queries.ipynb): pending orders,
  order history, and fill queries.
- [`examples/cancel_order.ipynb`](examples/cancel_order.ipynb): signed Spot or Perps
  order cancellation by order ID or client order ID.
- [`examples/websocket_stream.ipynb`](examples/websocket_stream.ipynb): raw JSON
  ticker, order, and account subscriptions.

See the [examples guide](examples/README.md) for prerequisites, environment
variables, and the recommended execution order.

Never commit `.env` files or print API secrets and Agent private keys.

## Development

```bash
python -m pytest --cov=exchangeos_sdk --cov-report=term-missing
python -m ruff check src tests
python -m ruff format --check src tests
python -m mypy src
python -m build
python -m twine check dist/*
```

The mocked test suite verifies every public REST endpoint without credentials
or network access. To run the same coverage against the public beta API (also
without credentials), use:

```bash
EXCHANGEOS_RUN_LIVE_TESTS=1 python -m pytest tests/test_public_rest_endpoints.py -m live
```

`EXCHANGEOS_TEST_BASE_URL` and `EXCHANGEOS_TEST_ASSET_ID` may optionally select
another deployment or public asset. They are test inputs, not credentials.

The test suite syntax-checks every Python block in this README and every code
cell in the example notebooks without credentials or network access. CI installs
both the wheel and source distribution into fresh virtual environments before
publishing build artifacts.
