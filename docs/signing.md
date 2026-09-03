# EIP-712 signing

ExchangeOS writes carry a signed transaction envelope. Signing is local; the
SDK never sends a private key to the REST server.

## Protocol

1. Build the unsigned transaction in canonical insertion order: `action`,
   `nonce`, optional `expiresAfter`, optional `vaultAddress`, and optional `user`.
2. Encode that mapping with MessagePack without sorting keys.
3. Compute `connectionId = keccak256(messagepack_bytes)`.
4. Hash EIP-712 `Agent(string source,bytes32 connectionId)`.
5. Sign the digest with secp256k1 and emit `r`, `s`, and `v` (`0` or `1`).
6. Add the signature to the submission envelope.

The EIP-712 domain is:

| Field | Value |
|---|---|
| `name` | `Exchange` |
| `version` | `1` |
| `chainId` | `70000196` |
| `verifyingContract` | `0x0000000000000000000000000000000000000000` |

`vaultAddress` identifies a delegated submission account and is included in
the unsigned MessagePack, matching the Java SDK and the full TradeZone Rust
SDK. `user`, when supplied, is also included in the unsigned hash.

JSON and REST envelopes represent addresses as `0x`-prefixed strings. During
canonical MessagePack encoding, typed Address fields—including `vaultAddress`,
`user`, and `subAccountTransfer.subAccountUser`—are encoded as 20-byte binary
values, matching Rust serde. This conversion only affects signing bytes and
does not change the public JSON wire format.

## Typed actions and builders

Each supported signed action is an immutable dataclass with an explicit Python
constructor. Typed actions can be passed directly to `sign_action()`:

```python
from exchangeos_sdk import PositionMode, UpdatePositionMode, sign_action

action = UpdatePositionMode(mode=PositionMode.HEDGE)
signed = sign_action(action, private_key, nonce=1_700_000_000_000)
```

Every action exposes its wire discriminator through `action.type` and its
validated JSON/MessagePack mapping through `action.to_wire()`. Typed actions
also implement `Mapping`, so signing remains compatible with the existing
protocol functions.

All variants and their fields live in `signing/actions/action.py`, mirroring
the Rust SDK's internally tagged `Action` enum. Variant field order determines
the MessagePack bytes. In particular, `CancelAll.assetIds` is emitted even
when empty.

| Typed Action | Wire type | Constructor fields |
|---|---|---|
| `PlaceOrder` | `placeOrder` | `orders`, `grouping=ActionGrouping.NA`, `builder=None` |
| `Cancel` | `cancel` | `cancels` |
| `CancelAll` | `cancelAll` | `asset_ids`, `market_type` |
| `Modify` | `modify` | `modifies` |
| `CreateSubAccount` | `createSubAccount` | `name` |
| `SubAccountTransfer` | `subAccountTransfer` | `sub_account_user`, `is_deposit`, `token_id`, `amount` |
| `UpdateLeverage` | `updateLeverage` | `asset_id`, `leverage`, `position_side=None` |
| `UpdateMarginMode` | `updateMarginMode` | `asset_id`, `margin_mode` |
| `UpdatePositionMode` | `updatePositionMode` | `mode` |
| `UpdateIsolatedMargin` | `updateIsolatedMargin` | `asset_id`, `position_side`, `direction`, `amount` |
| `ReserveRequestWeight` | `reserveRequestWeight` | `amount`, `token_id=None` |
| `PredictionSplit` | `predictionSplit` | `market_id`, `size` |
| `PredictionMerge` | `predictionMerge` | `market_id`, `size` |
| `PredictionRedeem` | `predictionRedeem` | `market_id` |
| `Noop` | `noop` | none |

The final five entries preserve the existing Outcomes signing protocol only;
they do not imply Outcomes REST or WebSocket support.

Trade helper functions build order items, cancel items, modify items, Perps
market specifications, and limit/trigger order types. Account helpers cover
leverage, margin mode, position mode, isolated margin, subaccount creation, and
subaccount transfer. Outcomes helpers remain signing compatibility wrappers.

The existing `*_action()` functions remain available as compatibility helpers;
they construct the corresponding typed action and return `to_wire()`.

Heartbeat uses the Java SDK's canonical `{"type":"noop"}` action. Leverage
updates accept an optional `positionSide`; `marginMode` is configured through
the separate margin-mode action and is not part of the signed leverage action.

All price, size, amount, and leverage values should be decimal strings. Floats
are rejected before MessagePack encoding.

Fixed action parameters are available as signing enums, including
`MarketType`, `OrderSide`, `OrderTimeInForce`, `MarginMode`, `PositionSide`,
and `PositionMode`. Builders continue to accept their equivalent string values
for compatibility; both forms emit identical wire data and signatures. REST
response enums remain separate because they are forward-compatible and do not
define the closed signing protocol.

The two market-type enums intentionally have different scope:

- `exchangeos_sdk.RestMarketType` is for REST queries and contains only
  `SPOT` and `PERP`.
- `exchangeos_sdk.MarketType` is the closed signing enum and retains
  `PREDICTION` for protocol compatibility in addition to `SPOT` and `PERP`.

When `nonce` is omitted, the SDK allocates a process-local monotonically
increasing millisecond value. This prevents concurrent calls in one process
from reusing a nonce; callers coordinating across multiple processes should
supply their own nonce allocator.

## Client order IDs

`generate_client_order_id()` emits a fixed 34-character lowercase value:

```text
0x + region(1 hex) + source(1 hex) + secure random(30 hex)
```

The 30-character suffix contains 120 bits from `secrets.token_hex(15)`. New
SDK-generated IDs default to `Region.HK` and `OrderSource.API`, producing the
prefix `0x03`. Registered sources are Manual `2`, API `3`, Trigger `4`, and
Liquidation `5`. Second-nibble values `0` and `1` are reserved for legacy
Prediction testnet/mainnet IDs and are not generated by this SDK.

`validate_client_order_id()` accepts `0x` or `0X` and case-insensitive hex for
compatibility with the server parser. Generation always returns canonical
lowercase. Existing legacy IDs remain valid inputs.

## Low-level signing

`sign_action()` accepts a typed `Action` or any validated action mapping. Use a
raw mapping only when a new server action is available before a typed action
ships. Mapping key order is part of the signed bytes, so construct raw mappings
in protocol order.

It returns an immutable `SignedTransaction`. Pass that object directly to a
signed REST write or call `to_wire()` to obtain a fresh JSON-compatible
mapping. Optional `expires_after`, `vault_address`, and `user` values are part
of the signed bytes; changing any of them requires a new signature. The
`chain` argument selects the EIP-712 `Agent.source` value (`Dev`, `Testnet`, or
`Mainnet`) and does not change the fixed domain chain ID.

For application code, prefer `client.sign_action(...)`. It selects the source
from the client's `Environment`, which binds the signing chain to the REST and
WebSocket deployment and rejects a separate `chain` override:

```python
signed = client.sign_action(action, private_key, nonce=1_700_000_000_000)
receipt = client.trade.place_order(signed)
```

The module-level `sign_action()` remains available for protocol tooling and
independent signature verification.

`sign_transaction()` remains an equivalent compatibility alias for applications
written against pre-release versions of the SDK.

Compatibility helpers include `connection_id()`, `signing_hash()`, and
`recover_address()`. They are useful for fixtures and independent signature
verification.
