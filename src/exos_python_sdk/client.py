"""Synchronous ExchangeOS REST client."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import httpx

from .auth import Credentials, auth_headers
from .config import (
    BearerAuth,
    ClientAuth,
    ClientOptions,
    LoggingPolicy,
    RestEvent,
    RetryPolicy,
)
from .environment import PRODUCTION, Environment
from .exceptions import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    RateLimitError,
    SerializationError,
    TransportError,
    ValidationError,
)
from .models.responses import REST_RESPONSE_MODELS, Candle
from .models.rest import RestData, RestList, parse_rest_data
from .signing.models import SignedTransaction
from .signing.protocol import sign_action as sign_transaction_action

if TYPE_CHECKING:
    from .websocket import ExchangeOSWebSocket

_LOGGER = logging.getLogger("exos_python_sdk.rest")


def _safe_proxy_url(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.hostname) and parsed.scheme in {"http", "https"}


class ExchangeOSClient:
    """Unified synchronous client for Spot and Perps REST resources.

    The client never retries a write. Read retries are limited to transport
    failures and HTTP 429 responses, and can be disabled with
    ``ClientOptions(retry=RetryPolicy(max_retries=0))``.
    """

    def __init__(
        self,
        *,
        environment: Environment = PRODUCTION,
        auth: ClientAuth | None = None,
        options: ClientOptions | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        if options is not None and not isinstance(options, ClientOptions):
            raise ConfigurationError("options must be ClientOptions or None")
        selected_options = options or ClientOptions()
        if not isinstance(environment, Environment):
            raise ConfigurationError("environment must be an Environment")
        if auth is not None and not isinstance(auth, (Credentials, BearerAuth)):
            raise ConfigurationError("auth must be Credentials, BearerAuth, or None")
        if isinstance(auth, BearerAuth) and (
            not isinstance(auth.token, str)
            or not auth.token
            or "\n" in auth.token
            or "\r" in auth.token
        ):
            raise ConfigurationError("bearer token must be a non-empty single-line string")
        if not isinstance(selected_options.retry, RetryPolicy):
            raise ConfigurationError("retry must be RetryPolicy")
        if selected_options.proxy is not None and not _safe_proxy_url(selected_options.proxy):
            raise ConfigurationError("proxy must be an absolute HTTP or HTTPS URL")
        if selected_options.timeout is not None:
            if isinstance(selected_options.timeout, bool) or not isinstance(
                selected_options.timeout, (int, float, httpx.Timeout)
            ):
                raise ConfigurationError("timeout must be a positive number or httpx.Timeout")
            if isinstance(selected_options.timeout, (int, float)) and selected_options.timeout <= 0:
                raise ConfigurationError("timeout must be greater than zero")
        if selected_options.retry.max_retries < 0 or selected_options.retry.backoff < 0:
            raise ConfigurationError("retry settings cannot be negative")
        if (
            not selected_options.user_agent
            or "\n" in selected_options.user_agent
            or "\r" in selected_options.user_agent
        ):
            raise ConfigurationError("user_agent must be non-empty and contain no newlines")
        try:
            selected_logging_policy = LoggingPolicy(selected_options.logging_policy)
        except ValueError as exc:
            raise ConfigurationError(
                "logging_policy must be 'off', 'metadata', or 'debug'"
            ) from exc
        if http_client is not None and (
            selected_options.timeout is not None or selected_options.proxy is not None
        ):
            raise ConfigurationError(
                "timeout and proxy must be configured on a caller-supplied http_client"
            )
        self.credentials = auth if isinstance(auth, Credentials) else None
        self.bearer_token = auth.token if isinstance(auth, BearerAuth) else None
        self.environment = environment
        self.base_url = environment.rest_url.rstrip("/")
        self.options = selected_options
        self.max_read_retries = selected_options.retry.max_retries
        self.retry_backoff = selected_options.retry.backoff
        self.preserve_raw_response = selected_options.preserve_raw_response
        self.rest_event_hook = selected_options.rest_event_hook
        self.logging_policy = selected_logging_policy
        self._user_agent = selected_options.user_agent
        self._accept_language = selected_options.accept_language
        headers = {"User-Agent": selected_options.user_agent}
        if selected_options.accept_language:
            headers["Accept-Language"] = selected_options.accept_language
        self._owns_http = http_client is None
        http_timeout = selected_options.timeout or 10.0
        self._http = http_client or httpx.Client(
            timeout=http_timeout,
            proxy=selected_options.proxy,
            headers=headers,
            follow_redirects=False,
        )

        from .api import AccountAPI, MarketAPI, TradeAPI

        self.market = MarketAPI(self)
        self.account = AccountAPI(self)
        self.trade = TradeAPI(self)

    def __repr__(self) -> str:
        mode = "bearer" if self.bearer_token else "api-key" if self.credentials else "none"
        return f"ExchangeOSClient(environment={self.environment.name!r}, auth={mode!r})"

    def __enter__(self) -> ExchangeOSClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def websocket(self, **kwargs: Any) -> ExchangeOSWebSocket:
        """Create a WebSocket session using this client's authentication by default.

        Explicit ``credentials`` or ``bearer_token`` keyword arguments override
        the inherited value, which is useful when REST and streaming identities
        are intentionally separated.
        """

        from .websocket import ExchangeOSWebSocket

        if "url" in kwargs:
            raise ConfigurationError("WebSocket URL is selected by the client environment")
        if "credentials" not in kwargs and "bearer_token" not in kwargs:
            kwargs["credentials"] = self.credentials
            kwargs["bearer_token"] = self.bearer_token
        kwargs["url"] = self.environment.websocket_url
        return ExchangeOSWebSocket(**kwargs)

    def sign_action(
        self,
        action: Mapping[str, Any],
        private_key: str | bytes,
        **kwargs: Any,
    ) -> SignedTransaction:
        """Sign an action with this client's environment-selected signing source."""

        if "chain" in kwargs:
            raise ConfigurationError("chain is selected by the client environment")
        return sign_transaction_action(
            action,
            private_key,
            chain=self.environment.signing_chain,
            **kwargs,
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | list[Any] | None = None,
        auth: bool = True,
    ) -> RestData:
        """Call any exchangeOS endpoint and unwrap its ``data`` envelope."""

        if not path.startswith("/"):
            raise ValidationError("path must be absolute")
        body = ""
        if json_body is not None:
            try:
                body = json.dumps(json_body, separators=(",", ":"), ensure_ascii=False)
            except (TypeError, ValueError) as exc:
                raise SerializationError(str(exc)) from exc
        request = self._http.build_request(
            method.upper(),
            f"{self.base_url}{path}",
            params={k: v for k, v in (params or {}).items() if v is not None},
            content=body.encode() if json_body is not None else None,
            headers={"Content-Type": "application/json"} if json_body is not None else None,
        )
        request.headers["User-Agent"] = self._user_agent
        if self._accept_language:
            request.headers["Accept-Language"] = self._accept_language
        if auth:
            if self.bearer_token:
                request.headers["Authorization"] = f"Bearer {self.bearer_token}"
            elif self.credentials:
                signed_path = request.url.raw_path.decode("ascii")
                request.headers.update(auth_headers(self.credentials, method, signed_path, body))
            else:
                raise AuthenticationError(
                    "this endpoint requires API credentials or a bearer token"
                )
        idempotent = method.upper() in {"GET", "HEAD"}
        attempts = self.max_read_retries + 1 if idempotent else 1
        response: httpx.Response | None = None
        started_at = time.monotonic()
        auth_mode = "bearer" if self.bearer_token else "api-key" if self.credentials else "none"
        request_body_bytes = len(body.encode())
        request_auth_mode = auth_mode if auth else "none"
        self._emit_rest_event(
            RestEvent(
                "request_start",
                method.upper(),
                path,
                request_body_bytes=request_body_bytes,
                auth_mode=request_auth_mode,
            )
        )
        for attempt in range(attempts):
            try:
                response = self._http.send(request)
            except httpx.HTTPError as exc:
                if attempt + 1 < attempts:
                    time.sleep(self.retry_backoff * (2**attempt))
                    continue
                error = TransportError(
                    f"HTTP {method.upper()} request failed",
                    method=method.upper(),
                    path=path,
                )
                self._emit_rest_event(
                    RestEvent(
                        "request_end",
                        method.upper(),
                        path,
                        latency_ms=(time.monotonic() - started_at) * 1000,
                        error_type=type(error).__name__,
                        request_body_bytes=request_body_bytes,
                        auth_mode=request_auth_mode,
                    )
                )
                raise error from exc
            if response.status_code != 429 or attempt + 1 >= attempts:
                break
            retry_after = _retry_after_seconds(response)
            time.sleep(
                retry_after if retry_after is not None else self.retry_backoff * (2**attempt)
            )
        assert response is not None
        self._emit_rest_event(
            RestEvent(
                "request_end",
                method.upper(),
                path,
                latency_ms=(time.monotonic() - started_at) * 1000,
                status_code=response.status_code,
                request_id=_request_id(response),
                request_body_bytes=request_body_bytes,
                auth_mode=request_auth_mode,
            )
        )
        try:
            payload = response.json()
        except ValueError as exc:
            snippet = response.text[:512]
            raise SerializationError(
                f"HTTP {response.status_code} returned non-JSON content: {snippet!r}"
            ) from exc
        if not isinstance(payload, dict):
            raise SerializationError("response envelope must be a JSON object")
        code = payload.get("code", "0" if response.is_success else response.status_code)
        if not response.is_success or str(code) != "0":
            request_id = _request_id(response)
            if response.status_code in {401, 403}:
                raise AuthenticationError(
                    str(payload.get("msg", payload.get("message", "authentication failed"))),
                    code=code,
                    status_code=response.status_code,
                    request_id=request_id,
                    data=payload.get("data"),
                    response=payload,
                )
            error_type = RateLimitError if response.status_code == 429 else APIError
            kwargs: dict[str, Any] = {}
            if error_type is RateLimitError:
                kwargs["retry_after"] = _retry_after_seconds(response)
            raise error_type(
                code,
                str(payload.get("msg", payload.get("message", "request failed"))),
                status_code=response.status_code,
                request_id=request_id,
                data=payload.get("data"),
                response=payload,
                **kwargs,
            )
        data = payload.get("data")
        raw_response = payload if self.preserve_raw_response else None
        if path in {
            "/api/v5/exchangeos/market/funding-rate-history",
            "/api/v5/exchangeos/account/bills",
        } and isinstance(data, dict):
            # Transitional deployments returned the page object directly. The
            # public SDK contract follows the unified OpenAPI data[0] envelope.
            data = [data]
        if path == "/api/v5/exchangeos/market/candles" and isinstance(data, list):
            return RestList(
                [
                    Candle.from_row(row) if isinstance(row, list) else parse_rest_data(row)
                    for row in data
                ],
                raw_response=raw_response,
            )
        return parse_rest_data(
            data,
            raw_response=raw_response,
            model=REST_RESPONSE_MODELS.get(path),
        )

    def _emit_rest_event(self, event: RestEvent) -> None:
        """Emit safe metadata; hook failures never alter request semantics."""

        if self.logging_policy is not LoggingPolicy.OFF:
            log = _LOGGER.debug if self.logging_policy is LoggingPolicy.DEBUG else _LOGGER.info
            log(
                "REST %s method=%s path=%s status=%s latency_ms=%s request_id=%s "
                "error=%s body_bytes=%s auth_mode=%s",
                event.name,
                event.method,
                event.path,
                event.status_code,
                event.latency_ms,
                event.request_id,
                event.error_type,
                event.request_body_bytes,
                event.auth_mode,
            )
        if self.rest_event_hook is None:
            return
        try:
            self.rest_event_hook(event)
        except Exception:  # pragma: no cover - user instrumentation must be isolated
            return


def _request_id(response: httpx.Response) -> str | None:
    for name in ("OK-Request-ID", "X-Request-ID", "Request-ID", "Trace-ID"):
        if value := response.headers.get(name):
            return str(value)
    return None


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
