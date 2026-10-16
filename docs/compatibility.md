# Protocol compatibility

## Java SDK cross-check

`tests/test_java_sdk_compatibility.py` compares the Python SDK with the Java SDK in two ways:

- verifies every Python Action type is present in the selected Java artifact, so an SDK scope
  change requires review;
- generates an ephemeral secp256k1 key in memory and compares the derived wallet address, signing
  hash, and deterministic ECDSA `r/s/v` for every currently compatible shared Action.

The private key is never stored in a fixture, repository file, subprocess argument, or test output.
It is passed to the Java probe through stdin and discarded when that process exits.

The test automatically discovers a built sibling Java SDK JAR or the newest local Maven artifact.
To select the exact artifact explicitly:

```bash
EXCHANGEOS_JAVA_SDK_JAR=/path/to/trade-zone-sdk.jar pytest -q tests/test_java_sdk_compatibility.py
```

The test uses one JAR for Java classes, Action inventory, and JNI native libraries. This prevents a
stale `target/classes` directory from silently combining different protocol versions. If the JAR or
Java 17 toolchain is unavailable, pytest reports the cross-SDK tests as skipped.

Shared Action signatures, including delegated-account signatures with `vaultAddress`, must pass
without compatibility exceptions.

`Action.types()` is the authoritative 15-type Python signing inventory. Twelve
types serve ExchangeOS trading, account, and protocol operations; three
`Prediction*` types remain for existing Outcomes signing-protocol
compatibility. The compatibility inventory does not add Outcomes REST
resources or WebSocket channels.

## REST routes

The REST contract contains only the Spot and Perps `market`, `trade`, and
`account` namespaces. PredictionController and `/api/v5/predictions/*` routes
are not part of this package. The Rust Outcomes SDK remains a signing fixture
reference only.

Client order IDs follow `0x{region}{source}{30 hex random characters}`. The
source nibble uses Manual `2`, API `3`, Trigger `4`, and Liquidation `5`;
legacy Prediction values `0` and `1` remain accepted and decode as unknown.

## WebSocket channels

The SDK supports only the unified `exchangeos-*` channel family. Outcomes
`pm-*` channels are rejected during subscription validation.

The canonical unified names are `exchangeos-mark-price` and
`exchangeos-instruments`. Whitespace shown in some source-document headings is
not part of either channel name.

The public WebSocket delivery contract is a raw JSON string callback or async
iterator. Applications own optional decoding into domain objects. The SDK may
parse a private copy for authentication, heartbeat, and sequence recovery but
does not replace the delivered server frame with a typed wrapper.

## Versioning

Adding an optional response field, enum value, endpoint, or channel is
backward-compatible. Removing or renaming a public method, changing a request
field's wire representation, or changing signing bytes requires a major-version
release once the package reaches `1.0.0`.
