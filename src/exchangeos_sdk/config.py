"""Public client configuration and observability types."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias

import httpx

from .auth import Credentials

DEFAULT_USER_AGENT = "EXCHANGEOS_PYTHON_SDK_0.1.0"


class LoggingPolicy(str, Enum):
    """Safe SDK logging levels. Payloads and authentication data are never logged."""

    OFF = "off"
    METADATA = "metadata"
    DEBUG = "debug"


@dataclass(frozen=True, slots=True)
class RestEvent:
    """Credential-free REST lifecycle event suitable for metrics or tracing."""

    name: str
    method: str
    path: str
    latency_ms: float | None = None
    status_code: int | None = None
    request_id: str | None = None
    error_type: str | None = None
    request_body_bytes: int = 0
    auth_mode: str = "none"


RestEventHook: TypeAlias = Callable[[RestEvent], None]


@dataclass(frozen=True, slots=True)
class BearerAuth:
    """Bearer authentication with a redacted representation."""

    token: str = field(repr=False)


ClientAuth: TypeAlias = Credentials | BearerAuth


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry policy for idempotent REST reads; writes are never retried."""

    max_retries: int = 2
    backoff: float = 0.25


@dataclass(frozen=True, slots=True)
class ClientOptions:
    """Advanced REST behavior kept out of the primary client constructor.

    ``timeout=None`` selects the SDK's ten-second default for an owned HTTP
    client. A caller-supplied ``http_client`` owns timeout and proxy settings,
    so setting either option together with it is rejected.
    """

    timeout: float | httpx.Timeout | None = None
    proxy: str | None = None
    user_agent: str = DEFAULT_USER_AGENT
    accept_language: str | None = None
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    preserve_raw_response: bool = False
    rest_event_hook: RestEventHook | None = None
    logging_policy: LoggingPolicy | str = LoggingPolicy.OFF
