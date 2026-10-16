# Changelog

Notable changes to ExchangeOS Python SDK releases are recorded here.

## 0.3.0

- Add typed `GET /account/limits`, `GET /market/security-fund`, and signed
  `POST /trade/noop` support from the latest ExchangeOS OpenAPI controllers.
- Add the public `exchangeos-estimated-price` WebSocket channel with required
  `assetId`, reconnect replay, and typed payload parsing.
- Align typed REST and WebSocket response models with the current TradeZone
  contract, including fill metadata and optional transaction confirmations.
- Make `order_item()` generate a valid API client order ID when omitted.

## 0.1.0

Planned first public release:

- Synchronous REST namespaces for Spot, Perps, account, and trade routes.
- Canonical MessagePack and EIP-712 action signing with local key handling.
- Public and private WebSocket subscriptions with reconnect and replay support.
- Python 3.10+ support, verified in CI on Python 3.10 through 3.13.

The release date will be added when the package passes the PRD release gates.
