"""Exception hierarchy for the ExchangeOS SDK.

Exceptions retain protocol metadata useful for support and observability
without retaining credentials or request signatures.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


class ExchangeOSError(Exception):
    """Base class for every SDK-originated failure."""


class ConfigurationError(ExchangeOSError, ValueError):
    """Raised when client configuration is unsafe or inconsistent."""


class ValidationError(ExchangeOSError, ValueError):
    """Raised before I/O when request input is invalid."""


class TransportError(ExchangeOSError):
    """Raised for HTTP or WebSocket transport failures."""

    def __init__(self, message: str, *, method: str | None = None, path: str | None = None) -> None:
        self.method = method
        self.path = path
        super().__init__(message)


class SerializationError(ExchangeOSError):
    """Raised when a payload cannot be encoded or decoded."""


class SigningError(ExchangeOSError):
    """Raised for malformed actions or EIP-712 signing failures."""


class APIError(ExchangeOSError):
    """An exchangeOS business error response."""

    def __init__(
        self,
        code: int | str,
        message: str,
        *,
        status_code: int | None = None,
        request_id: str | None = None,
        data: Any = None,
        response: Any = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.request_id = request_id
        self.data = data
        self.response = response
        suffix = f" (request_id={request_id})" if request_id else ""
        super().__init__(f"ExchangeOS API error {code}: {message}{suffix}")


class RateLimitError(APIError):
    """An API error caused by HTTP 429 or an equivalent server response."""

    def __init__(self, *args: Any, retry_after: float | None = None, **kwargs: Any) -> None:
        self.retry_after = retry_after
        super().__init__(*args, **kwargs)


class AuthenticationError(APIError):
    """Raised when authentication is missing or rejected."""

    def __init__(
        self,
        message: str,
        *,
        code: int | str = "authentication_error",
        status_code: int | None = None,
        request_id: str | None = None,
        data: Any = None,
        response: Any = None,
    ) -> None:
        super().__init__(
            code,
            message,
            status_code=status_code,
            request_id=request_id,
            data=data,
            response=response,
        )


class WebSocketProtocolError(ExchangeOSError):
    """Raised when a WebSocket control or payload contract is invalid."""


class SequenceGapError(WebSocketProtocolError):
    """Represent an order-book sequence discontinuity."""

    def __init__(
        self,
        *,
        expected_previous_sequence_id: int,
        actual_previous_sequence_id: int,
        argument: Mapping[str, Any],
    ) -> None:
        self.expected_previous_sequence_id = expected_previous_sequence_id
        self.actual_previous_sequence_id = actual_previous_sequence_id
        self.argument = MappingProxyType(dict(argument))
        super().__init__(
            "WebSocket order-book sequence gap: "
            f"expected prevSeqId {expected_previous_sequence_id}, "
            f"received {actual_previous_sequence_id}"
        )


# Preferred spelling for new code; APIError remains compatible with the initial preview.
ApiError = APIError
