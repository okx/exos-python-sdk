# ExchangeOS Python SDK

## Overview

This repository contains the Python SDK for the ExchangeOS Spot and
Perps REST and WebSocket APIs. It provides synchronous REST resources, local
MessagePack + EIP-712 transaction signing, typed response models, and resilient
asynchronous WebSocket subscriptions.

#### Source code

https://github.com/okx/exos-python-sdk

#### API examples and tutorials

- REST market-data and account queries: [`examples/public_rest.ipynb`](examples/public_rest.ipynb)
- Signed order flow: [`examples/place_order.ipynb`](examples/place_order.ipynb)
- Order queries and cancellation: [`examples/order_queries.ipynb`](examples/order_queries.ipynb) and [`examples/cancel_order.ipynb`](examples/cancel_order.ipynb)
- WebSocket subscriptions: [`examples/websocket_stream.ipynb`](examples/websocket_stream.ipynb)

Keep the SDK and the ExchangeOS/TradeZone API documentation in sync when a
deployment adds fields or endpoints. See the [changelog](CHANGELOG.md) for
SDK-side compatibility notes.

### Features

- REST clients for market data, account queries, and signed trade/account actions.
- Public and private WebSocket channels with heartbeats, reconnect, and subscription replay.
- Local EIP-712 signing for supported actions.
- Typed, forward-compatible responses that preserve exact decimal values and unknown fields.
- Production and custom environments with configurable transport options.

### Quick start

#### Prerequisites

`python version: >=3.10`

#### Step 1: Obtain ExchangeOS credentials when a private operation needs them

- Register for an account: [https://www.okx.com/account/register](https://www.okx.com/account/register)
- Apply for an API key: [https://web3.okx.com/zh-hans/onchainos/dev-docs/exchangeos/quickstart](https://web3.okx.com/zh-hans/onchainos/dev-docs/exchangeos/quickstart)

Public REST methods and public WebSocket channels can be used without
credentials. Private REST operations use API credentials or a bearer token;
private WebSocket channels use API credentials:

- API key
- Secret key
- Passphrase

Signed writes additionally require an authorized Agent private key. The API
credentials authenticate the request; the Agent private key signs the action.
They are separate values and must not be interchanged.

#### Step 2: Install `exos-python-sdk`

Install the published package:

```bash
python -m pip install exos-python-sdk
```

For a source checkout, install the package in editable mode. Notebook support
is an optional extra:

```bash
python -m pip install -e '.[notebook]'
```

### API Credentials

#### Option 1: Pass credentials directly

Use `Credentials` when creating a client. Load the values from a secret
provider or environment variables rather than putting real secrets in source
control:

```python
from exos_python_sdk import Credentials, ExchangeOSClient

# Replace these placeholders with credentials supplied by your secret provider.
credentials = Credentials(
    api_key="your-api-key",
    secret_key="your-api-secret",
    passphrase="your-passphrase",
)

with ExchangeOSClient(auth=credentials) as client:
    balance = client.account.balance()
    print(balance)
```

#### Option 2: Use environment variables (recommended)

Create a local `.env` file or configure these variables in your shell. Never
commit the file or print its contents:

```bash
EXCHANGEOS_API_KEY=your-api-key
EXCHANGEOS_API_SECRET=your-api-secret
EXCHANGEOS_API_PASSPHRASE=your-passphrase
EXCHANGEOS_AGENT_PRIVATE_KEY=your-authorized-agent-private-key
```

Then read them from Python:

```python
import os

from exos_python_sdk import Credentials, ExchangeOSClient

credentials = Credentials(
    api_key=os.environ["EXCHANGEOS_API_KEY"],
    secret_key=os.environ["EXCHANGEOS_API_SECRET"],
    passphrase=os.environ["EXCHANGEOS_API_PASSPHRASE"],
)

with ExchangeOSClient(auth=credentials) as client:
    instruments = client.market.instruments()
    positions = client.account.positions()
    print({"instruments": len(instruments), "positions": len(positions)})
```

Public-only requests do not require `Credentials`:

```python
from exos_python_sdk import ExchangeOSClient, RestMarketType

with ExchangeOSClient() as client:
    instruments = client.market.instruments(market_type=RestMarketType.PERP)
    tickers = client.market.tickers(market_type=RestMarketType.PERP)
    print({"instruments": len(instruments), "tickers": len(tickers)})
```

#### Production environment

The client connects to the Production ExchangeOS deployment by default:

```python
from exos_python_sdk import ExchangeOSClient

with ExchangeOSClient() as client:
    print(client.market.instruments())
```

The SDK also supports custom deployments through `Environment.custom(...)`;
those settings are intentionally not part of the quick-start example.

### Development Setup

For contributors or local development:

```bash
# Clone the repository
git clone https://github.com/okx/exos-python-sdk.git
cd exos-python-sdk

# Optional but recommended: create an isolated environment
python -m venv .venv
source .venv/bin/activate

# Install development dependencies
python -m pip install --upgrade pip
python -m pip install -e '.[test,notebook]'

# Run the test suite
python -m pytest
```

The editable install includes the SDK, test dependencies, and notebook support.
The virtual environment is optional, and the default tests use mocked
transports without credentials or network access. Live REST checks are opt-in:

```bash
EXCHANGEOS_RUN_LIVE_TESTS=1 python -m pytest tests/test_public_rest_endpoints.py -m live
```

### Step 3: Run examples

- Set the variables required by the example in the shell that launches VS Code
  or Jupyter:

```bash
export EXCHANGEOS_API_KEY='...'
export EXCHANGEOS_API_SECRET='...'
export EXCHANGEOS_API_PASSPHRASE='...'
export EXCHANGEOS_AGENT_PRIVATE_KEY='...'
```

- REST API
  - Public market data: run [`examples/public_rest.ipynb`](examples/public_rest.ipynb).
  - Account queries: run [`examples/account_queries.ipynb`](examples/account_queries.ipynb).
  - Signed order placement: run [`examples/sign_transaction.ipynb`](examples/sign_transaction.ipynb) first, then [`examples/place_order.ipynb`](examples/place_order.ipynb).
  - Order history, pending orders, fills, and cancellation: run [`examples/order_queries.ipynb`](examples/order_queries.ipynb) and [`examples/cancel_order.ipynb`](examples/cancel_order.ipynb).
- WebSocket API
  - Run [`examples/websocket_stream.ipynb`](examples/websocket_stream.ipynb) for a long-lived public stream.
  - Add API credentials in the environment to subscribe to private channels.
- Review the environment, asset, price, size, and order side before running a
  signed write. The SDK signs locally, but the action is sent to ExchangeOS
  only when the corresponding trade method is called.

`order_item()` generates a valid API `clientOrderId` when it is omitted. Supply
`client_order_id` only when an external system has already assigned the ID.

```python
import os

from exos_python_sdk import (
    Credentials,
    ExchangeOSClient,
    MarginMode,
    OrderSide,
    OrderTimeInForce,
    PlaceOrder,
    limit_order_type,
    order_item,
    perp_market,
)

credentials = Credentials(
    api_key=os.environ["EXCHANGEOS_API_KEY"],
    secret_key=os.environ["EXCHANGEOS_API_SECRET"],
    passphrase=os.environ["EXCHANGEOS_API_PASSPHRASE"],
)
order = order_item(
    asset_id="your-asset-id",
    side=OrderSide.BUY,
    market_type=perp_market(MarginMode.CROSS),
    price="your-order-price",
    size="your-order-size",
    order_type=limit_order_type(OrderTimeInForce.GTC),
)
action = PlaceOrder(orders=[order])

with ExchangeOSClient(auth=credentials) as client:
    signed_transaction = client.sign_action(
        action,
        os.environ["EXCHANGEOS_AGENT_PRIVATE_KEY"],
    )
    result = client.trade.place_order(signed_transaction)

print({"clientOrderId": order["clientOrderId"], "response": result})
```

### Notes

- To learn more about ExchangeOS API, visit the official [ExchangeOS API documentation](https://web3.okx.com/zh-hans/onchainos/dev-docs/open-api-conventions).
- REST methods are synchronous. WebSocket sessions are asynchronous and run on Python `asyncio`; the SDK uses [`websockets`](https://websockets.readthedocs.io/en/stable/) internally.
- Public REST endpoints and WebSocket channels do not require credentials. Private endpoints and channels use API credentials.
- Signed writes are never retried automatically. Check the order or transaction state before retrying.
- See the [REST](docs/rest-api.md), [WebSocket](docs/websocket.md), and [signing](docs/signing.md) guides for SDK-specific details.

Never commit `.env` files, API secrets, passphrases, or Agent private keys.
