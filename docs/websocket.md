# WebSocket transport

The default endpoint is the ExchangeOS business WebSocket. Production URLs
must use `wss://`; plain `ws://` is accepted only for loopback tests.

Use `ExchangeOSClient.websocket()` to inherit the client's credentials or
bearer token and Environment URL, or construct `ExchangeOSWebSocket` directly.
The REST client and WebSocket have independent lifecycles.

```python
async with client.websocket(
    reconnect_min=3.0,
    reconnect_max=30.0,
    max_reconnect_attempts=None,
    queue_size=1_000,
    overflow_policy="drop_oldest",
) as ws:
    await ws.subscribe_public("exchangeos-tickers", asset_id=602)
    await ws.subscribe_private("exchangeos-orders", vault_address="0x...")

    async for raw_json in ws:
        print(raw_json)
```

ExchangeOS DEX private channels with CEX API credentials use the
`login-wallet` protocol automatically:

```python
async with client.websocket() as ws:
    await ws.subscribe_private("exchangeos-account")
```

Messages are delivered as raw JSON strings. A callback can be registered when
the stream is created; synchronous and asynchronous callbacks are supported:

```python
def on_message(raw_json: str) -> None:
    print(raw_json)


async with client.websocket(message_callback=on_message) as ws:
    await ws.subscribe_public("exchangeos-tickers", asset_id=602)
    await ws.wait_closed()
```

For a small channel-specific handler, decode the raw message at the application
boundary. This preserves all new server fields while making the channel branch
explicit:

```python
import json


def on_message(raw_json: str) -> None:
    message = json.loads(raw_json)
    if message.get("arg", {}).get("channel") != "exchangeos-tickers":
        return
    for ticker in message.get("data", []):
        print(ticker["assetId"], ticker["lastPx"])
```

## Channel coverage

Public unified channels:

```text
exchangeos-tickers
exchangeos-trades
exchangeos-candle{bar}
exchangeos-mark-price
exchangeos-mark-price-candle{bar}
exchangeos-index-tickers
exchangeos-index-candle{bar}
exchangeos-estimated-price
exchangeos-funding-rate
exchangeos-instruments
exchangeos-open-interest
exchangeos-price-limit
exchangeos-books
exchangeos-books5
exchangeos-bbo-tbt
exchangeos-books-grouped
```

Private unified channels:

```text
exchangeos-account
exchangeos-balance-and-position
exchangeos-balance-and-position-updates
exchangeos-orders
exchangeos-user-order-status
exchangeos-user-fills
exchangeos-user-fundings
exchangeos-user-ledger-updates
exchangeos-setting-updates
```

`exchangeos-user-fills` data is returned as a `UserFillsPayload` containing a
`fills` list of `UserFill` models. The rows use `pnl`, `rebateTokenId`, and
`fillDir` with the same PascalCase direction vocabulary as REST fill history.
The message envelope carries `block_height` and `block_timestamp`.

Replace `{bar}` with the server interval, for example
`exchangeos-candle1m`.

`exchangeos-estimated-price` publishes estimated settlement data while a
perpetual is delisting. It requires `asset_id` and sends a current snapshot
after subscription. Each `data[]` item contains `assetId`, `name`,
`marketType`, `expTime`, `settlePx`, and `ts`. If no estimate is available,
`settlePx` is an empty string. Updates use an approximately 200 ms minimum
aggregation window; normal public WebSocket ping/pong keeps an otherwise idle
subscription alive.

```python
await ws.subscribe_public("exchangeos-estimated-price", asset_id="9102")
```

`subscribe_public()` accepts `asset_id` plus arbitrary channel parameters.
`subscribe_private()` accepts `vault_address` plus arbitrary channel
parameters. Parameter names passed through `**params` must use the server wire
form, for example `assetId`. Exact duplicate arguments are registered and sent
only once.

The compatibility method `subscribe(channel, params=[...])` determines access
from the canonical channel inventory. `unsubscribe()` removes the same
argument set from the replay registry. Use the dedicated public/private methods
for new code because they make authentication requirements explicit.

## Reconnect behavior

An unexpected disconnect clears connection/authentication state, emits a
transport event, waits with jittered exponential backoff, reconnects, authenticates,
and replays the deduplicated subscription registry. `max_reconnect_attempts`
limits consecutive connection failures. A successfully established session
starts a new retry window and resets the backoff, so later independent outages
still recover.

Private subscriptions require a completed login. `vault_address` is stored in
the subscription key, so parent and subaccount subscriptions remain distinct
and survive reconnects.

API-key credentials use the ExchangeOS `login-wallet` operation automatically.
Private ExchangeOS channels therefore require CEX API credentials; Web3 API
keys are not accepted by this client. A bearer token is instead authenticated by the HTTP WebSocket
upgrade on every connection; the SDK does not invent a second application-level
login operation for that mode. `authentication_mode` reports
`api-key-login`, `bearer-upgrade`, or `none`.

## Backpressure

`queue_size` bounds memory use. `overflow_policy` accepts:

- `drop_oldest`: keep the newest stream state.
- `drop_newest`: preserve queued messages.
- `raise`: treat queue exhaustion as an error.

Use `event_handler` to observe `connected`, `authenticated`, `subscribed`,
`reconnecting`, `reconnected`, `reconnect-exhausted`, `gap`, and
`queue-overflow` lifecycle events without parsing those states from normal
business messages. A replayed subscription has `replayed=True` in the hook
details. Handlers can be synchronous or asynchronous.

The `raise` overflow policy raises `TransportError` inside the connection
session, which activates the configured reconnect policy. Transport failures
are also emitted into the message iterator as a raw JSON `transport-error`
control event.

## Raw messages and books

Every valid incoming frame is passed through as its original JSON string. This
keeps unknown channels, event shapes, and additive fields available without a
client release. Applications that need objects can call `json.loads(raw_json)`
at their boundary.

For order books, the SDK internally records `seqId` per subscription. If a
later `prevSeqId` does not match, it emits a raw JSON `sequence-gap` event and
performs an unsubscribe/subscribe cycle so the server sends a fresh snapshot.
The discontinuous delta is discarded. Invalid JSON frames raise
`WebSocketProtocolError` and trigger the configured reconnect policy.
