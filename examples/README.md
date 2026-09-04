# ExchangeOS SDK notebooks

The SDK supports Python 3.10–3.13.

Install the SDK and notebook kernel support into the Python environment selected
by VS Code or Jupyter:

```bash
python -m pip install -e '.[notebook]'
```

Select that same Python environment when prompted to choose a notebook kernel,
then run the cells in order. REST calls are synchronous. The WebSocket notebook
uses async cells because a streaming connection remains asynchronous.

## Authentication

Private REST and WebSocket calls use API credentials. Signed writes additionally
use an authorized Agent private key; the two credential types are independent.
Load sensitive values from a secret manager in production and never commit them
to source control.

## Suggested flow

Run the examples from the repository root in this order:

| Step | Example | Purpose | Sends a write |
|---|---|---|---|
| 1 | `public_rest.ipynb` | Query Spot/Perps instruments and tickers; handle REST failures | No |
| 2 | `account_queries.ipynb` | Check balances and positions | No |
| 3 | `place_order.ipynb` | Build, sign, and submit a Perps limit order | **Yes** |
| 4 | `order_queries.ipynb` | Check pending orders, history, and fills | No |
| 5 | `cancel_order.ipynb` | Sign and submit one cancellation | **Yes** |
| 6 | `websocket_stream.ipynb` | Stream public and private raw JSON messages | No |

Every notebook lists its required environment variables before executable
cells. Public REST needs no credentials. Private REST and WebSocket operations
use API credentials, while signed writes additionally require an authorized
Agent private key.

The default `PRODUCTION` environment keeps REST, WebSocket, and signing chain
settings together. For another deployment, create one complete
`Environment.custom(...)` configuration instead of overriding those values
independently.

Review the environment, account, asset, price, size, and target order before
running either write notebook. Never commit credentials, `.env` files, or
notebook outputs containing account data.
