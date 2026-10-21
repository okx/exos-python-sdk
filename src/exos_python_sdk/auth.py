"""OKX v5 HMAC request authentication."""

from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone

from .exceptions import ConfigurationError


@dataclass(frozen=True, repr=False)
class Credentials:
    """API credentials. Values are deliberately excluded from ``repr``."""

    api_key: str
    secret_key: str
    passphrase: str

    def __post_init__(self) -> None:
        if not self.api_key or not self.secret_key or not self.passphrase:
            raise ConfigurationError("api_key, secret_key, and passphrase must all be non-empty")

    def __repr__(self) -> str:
        return "Credentials(api_key=<redacted>, secret_key=<redacted>, passphrase=<redacted>)"


def iso_timestamp() -> str:
    """Return an OKX-compatible UTC timestamp with millisecond precision."""

    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sign_request(
    secret_key: str, timestamp: str, method: str, request_path: str, body: str = ""
) -> str:
    """Compute ``Base64(HMAC-SHA256(ts + method + path + body))``."""

    prehash = f"{timestamp}{method.upper()}{request_path}{body}".encode()
    digest = hmac.new(secret_key.encode(), prehash, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def auth_headers(
    credentials: Credentials,
    method: str,
    request_path: str,
    body: str = "",
    *,
    timestamp: str | None = None,
) -> dict[str, str]:
    """Build the four ``OK-ACCESS-*`` headers for a prepared request."""

    ts = timestamp or iso_timestamp()
    return {
        "OK-ACCESS-KEY": credentials.api_key,
        "OK-ACCESS-SIGN": sign_request(credentials.secret_key, ts, method, request_path, body),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": credentials.passphrase,
    }


def websocket_login_args(
    credentials: Credentials, *, timestamp: str | None = None
) -> dict[str, str]:
    """Build one argument for the OKX WebSocket ``login`` operation."""

    ts = timestamp or str(int(datetime.now(timezone.utc).timestamp()))
    sign = sign_request(credentials.secret_key, ts, "GET", "/users/self/verify")
    return {
        "apiKey": credentials.api_key,
        "passphrase": credentials.passphrase,
        "timestamp": ts,
        "sign": sign,
    }
