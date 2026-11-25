"""Shared REST API plumbing."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from ..exceptions import ValidationError

if TYPE_CHECKING:
    from ..client import ExchangeOSClient

ROOT = "/api/v5/exchangeos"
ResponseT = TypeVar("ResponseT")


def signed_body(value: Any) -> Mapping[str, Any]:
    """Return a signed envelope without changing its signed values."""

    if isinstance(value, Mapping):
        body = value
    else:
        to_wire = getattr(value, "to_wire", None)
        if not callable(to_wire):
            raise ValidationError("signed_transaction must be a mapping or expose to_wire()")
        body = to_wire()
        if not isinstance(body, Mapping):
            raise ValidationError("signed_transaction must be a mapping or expose to_wire()")
    return body


def reject_signed_fields(body: Mapping[str, Any], fields: Collection[str]) -> None:
    """Reject endpoint-incompatible fields without rewriting a signed body."""

    for field in fields:
        if field in body:
            raise ValidationError(f"signed_transaction must not include {field!r}")


def signed_action(body: Mapping[str, Any], expected_type: str) -> Mapping[str, Any]:
    """Return an envelope action after confirming its endpoint-specific type."""

    action = body.get("action")
    if not isinstance(action, Mapping):
        raise ValidationError("signed_transaction.action must be a mapping")
    if action.get("type") != expected_type:
        raise ValidationError(f"signed_transaction action must have type {expected_type!r}")
    return action


def path_id(value: str, name: str) -> str:
    if not value or not all(char.isalnum() or char in "_-" for char in value):
        raise ValidationError(f"{name} must contain only letters, digits, '_' or '-'")
    return value


class BaseAPI:
    """Base class for public, authenticated, and signed REST calls."""

    def __init__(self, client: ExchangeOSClient) -> None:
        self._client = client

    def _get(self, path: str, **params: Any) -> ResponseT:  # type: ignore[type-var]
        return cast(ResponseT, self._client.request("GET", path, params=params, auth=True))

    def _public_get(self, path: str, **params: Any) -> ResponseT:  # type: ignore[type-var]
        # Public endpoints work without credentials, but authenticate when the
        # caller supplied credentials so the server can apply account-scoped
        # limits, attribution, or richer response behavior.
        has_auth = bool(
            getattr(self._client, "credentials", None)
            or getattr(self._client, "bearer_token", None)
        )
        return cast(ResponseT, self._client.request("GET", path, params=params, auth=has_auth))

    def _post(
        self,
        path: str,
        signed_transaction: Any,
        *,
        expected_action_type: str,
        action_validator: Callable[[Mapping[str, Any]], None] | None = None,
        reject_fields: Collection[str] = (),
    ) -> ResponseT:  # type: ignore[type-var]
        body = signed_body(signed_transaction)
        reject_signed_fields(body, reject_fields)
        action = signed_action(body, expected_action_type)
        if action_validator is not None:
            action_validator(action)
        return cast(
            ResponseT,
            self._client.request(
                "POST",
                path,
                json_body=body,
                auth=True,
            ),
        )
