"""Deployment configuration shared by REST, WebSocket, and transaction signing."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from .exceptions import ConfigurationError
from .signing.models import Chain


@dataclass(frozen=True, slots=True)
class Environment:
    """An immutable set of endpoints and the matching signing source."""

    name: str
    rest_url: str
    websocket_url: str
    signing_chain: Chain

    def __post_init__(self) -> None:
        if not self.name:
            raise ConfigurationError("environment name must not be empty")
        if not _safe_rest_url(self.rest_url):
            raise ConfigurationError(
                "environment REST URL must use HTTPS (HTTP is allowed only for loopback tests)"
            )
        if not _safe_websocket_url(self.websocket_url):
            raise ConfigurationError(
                "environment WebSocket URL must use WSS (WS is allowed only for loopback tests)"
            )
        if not isinstance(self.signing_chain, Chain):
            raise ConfigurationError("environment signing_chain must be a Chain")

    @classmethod
    def custom(
        cls,
        *,
        name: str,
        rest_url: str,
        websocket_url: str,
        signing_chain: Chain,
    ) -> Environment:
        """Create an explicit non-production environment without guessing endpoints."""

        return cls(name, rest_url.rstrip("/"), websocket_url, signing_chain)


def _safe_rest_url(value: str) -> bool:
    parsed = urlparse(value)
    return (
        bool(parsed.hostname)
        and not parsed.username
        and not parsed.password
        and (
            parsed.scheme == "https"
            or (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"})
        )
    )


def _safe_websocket_url(value: str) -> bool:
    parsed = urlparse(value)
    return (
        bool(parsed.hostname)
        and not parsed.username
        and not parsed.password
        and (
            parsed.scheme == "wss"
            or (parsed.scheme == "ws" and parsed.hostname in {"localhost", "127.0.0.1", "::1"})
        )
    )


PRODUCTION = Environment(
    name="production",
    rest_url="https://www.okx.com",
    websocket_url="wss://ws.okx.com/ws/v5/exchangeos",
    signing_chain=Chain.MAINNET,
)


__all__ = ["Environment", "PRODUCTION"]
