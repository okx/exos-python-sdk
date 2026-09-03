"""Shared REST API plumbing."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from ..exceptions import ValidationError

if TYPE_CHECKING:
    from ..client import ExchangeOSClient

ROOT = "/api/v5/exchangeos"
ResponseT = TypeVar("ResponseT")


def signed_body(value: Any) -> Mapping[str, Any]:
    """Return a signed envelope without changing values or numeric strings."""

    if isinstance(value, Mapping):
        return value
    to_wire = getattr(value, "to_wire", None)
    if callable(to_wire):
        wire = to_wire()
        if isinstance(wire, Mapping):
            return wire
    raise ValidationError("signed_transaction must be a mapping or expose to_wire()")


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
        return cast(ResponseT, self._client.request("GET", path, params=params, auth=False))

    def _post(self, path: str, signed_transaction: Any) -> ResponseT:  # type: ignore[type-var]
        return cast(
            ResponseT,
            self._client.request(
                "POST",
                path,
                json_body=signed_body(signed_transaction),
                auth=True,
            ),
        )
