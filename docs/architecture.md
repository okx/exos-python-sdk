# Architecture

The SDK has a synchronous REST client and an asynchronous WebSocket transport.
REST is organized into three namespaces:

- `client.market` for ExchangeOS Spot and Perps market data.
- `client.trade` for signed ExchangeOS trading operations and order queries.
- `client.account` for signed account operations and private account queries.

One immutable `Environment` selects the matching REST URL, WebSocket URL, and
signing chain. The two transports share credentials and protocol errors but
have independent lifecycles.

## Package layout

```text
exchangeos_sdk/
├── client.py                 # REST transport and API composition
├── environment.py            # REST URL, WebSocket URL, and signing chain
├── config.py                 # Client options, retry, auth mode, and observability
├── auth.py                   # HMAC and WebSocket login authentication
├── exceptions.py             # Shared error hierarchy
├── models/
│   ├── rest.py               # Forward-compatible response containers/helpers
│   ├── responses.py          # Endpoint-specific typed REST payloads
│   └── enums.py              # Open REST enums that retain unknown values
├── api/
│   ├── base.py               # Shared REST request helpers
│   ├── market.py             # Public Spot/Perps market data
│   ├── trade.py              # Orders and fills
│   └── account.py            # Balances, positions, and settings
├── signing/
│   ├── models.py             # Signing enums and immutable signed envelopes
│   ├── validation.py         # Shared wire validation
│   ├── client_order_id.py    # Source-aware cloid generation
│   ├── actions/
│   │   ├── action.py         # All 15 typed Action variants and canonical fields
│   │   ├── trade.py          # Place/cancel/modify builders
│   │   ├── account.py        # Account-setting builders
│   │   └── outcomes.py       # Compatibility builders for legacy/protocol actions
│   └── protocol.py           # MessagePack, EIP-712, sign, and recover
└── websocket/
    ├── channels.py           # Channel inventory and matching
    ├── messages.py           # Internal protocol classification
    ├── payloads.py           # Internal channel payload helpers
    └── transport.py          # Connection, login, reconnect, and backpressure
```

Each package `__init__.py` re-exports its public names. Internal modules can be
tested and maintained by responsibility without exposing their implementation
details at the SDK root.

Outcomes-related code is limited to existing signing-protocol compatibility.
The SDK does not expose Outcomes REST APIs or WebSocket channels.

## Request flow

Public REST calls are sent without authentication headers. Private queries add
the OKX V5 HMAC headers. Signed writes carry an EIP-712 signed transaction in
the JSON body and are also sent through the authenticated REST transport.

Only idempotent reads are eligible for transport retries. A timed-out write is
ambiguous: the server may have accepted it even when the response was lost.
Applications should reconcile it with `txHash`, `clientOrderId`, a query method,
or a private WebSocket event.

## Signing flow

The signer serializes the unsigned transaction with canonical MessagePack,
hashes it to produce `connectionId`, and signs an EIP-712 `Agent` struct. The
domain chain ID is a protocol constant and is not the execution chain selected
by the application.

The action must not be mutated between signing and submission. Builders create
new action mappings so callers can retain their own input objects safely.

## WebSocket flow

Subscriptions live in a deduplicated registry. A private session authenticates
before replaying subscriptions. Unexpected disconnects use exponential backoff
with jitter; an explicit close stops the reconnect loop.

Messages are delivered to callbacks and async iterators as the original raw
JSON string. The transport parses a private copy only for login, heartbeat,
and order-book sequence handling, so unknown fields and messages remain intact.

Order-book consumers must treat a sequence gap as invalid local state. The SDK
emits a JSON sequence-gap event and requests a fresh snapshot instead of
applying later deltas to an incomplete book.
