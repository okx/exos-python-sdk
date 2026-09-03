# Security guidance

## Credentials and signing keys

Load API credentials and signing keys from the application's secret provider.
Do not commit them to source control or place them in command-line arguments.
The SDK does not generate, persist, or manage private keys.

Credential and signature-related objects redact secrets from `repr`. Exceptions
and normal logs must not contain an API secret, passphrase, private key, REST
prehash, or complete authentication header set. Applications should apply the
same rule to custom hooks and HTTP debugging middleware.

`ClientOptions.logging_policy` never logs request/response bodies or header
values, including in `debug` mode. Debug metadata is limited to method, route,
status, latency, request ID, body byte count, and authentication mode.

## Network endpoints

Production REST and WebSocket endpoints must use TLS. Plain HTTP or WebSocket
URLs are accepted only for explicit loopback test servers. Redirect following is
disabled so credentials are not forwarded to a different origin.

Use one `Environment` to select the REST URL, WebSocket URL, and signing chain.
Avoid maintaining three unrelated deployment settings in application code.

## Ambiguous writes

The SDK does not automatically retry signed writes. A connection failure or
timeout does not prove that a write failed. Reconcile the request by transaction
hash, client order ID, REST query, or private push before sending another write.

## Numeric precision

Prices, quantities, balances, rates, and PnL values remain decimal strings on
the wire. Convert them with `decimal.Decimal` when arithmetic is required. Do
not convert them through binary `float` before signing or submitting an action.

## Logging WebSocket payloads

Private push messages can contain account and order data. Payload logging is not
enabled by default. If an application enables it, the application owns access
control, redaction, retention, and deletion of those logs.
