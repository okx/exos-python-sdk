"""REST values that preserve the server wire representation.

The API intentionally keeps decimal values as strings and timestamps as their
original integers.  Helpers provide convenient conversions without changing
the stored values.  ``RestObject`` and ``RestList`` subclass the built-in
containers, so existing code that expects dictionaries and lists remains
compatible while callers can opt into model helpers and raw-envelope access.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar, Generic, TypeAlias, TypeVar

from ..exceptions import ValidationError

JsonScalar: TypeAlias = str | int | float | bool | None


def as_decimal(value: str | int | Decimal) -> Decimal:
    """Convert an exact wire value to ``Decimal`` without passing through float."""

    if isinstance(value, (bool, float)):
        raise ValidationError("decimal values must be strings, integers, or Decimal instances")
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"invalid decimal value: {value!r}") from exc


def as_utc_datetime(value: int | str) -> datetime:
    """Convert a Unix millisecond timestamp to a timezone-aware UTC datetime."""

    if isinstance(value, bool):
        raise ValidationError("timestamp must be an integer number of milliseconds")
    try:
        milliseconds = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"invalid millisecond timestamp: {value!r}") from exc
    try:
        return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise ValidationError(f"millisecond timestamp is out of range: {value!r}") from exc


class RestObject(dict[str, Any]):
    """Mapping response model that accepts and preserves unknown fields."""

    raw_response: dict[str, Any] | None

    def __init__(
        self, *args: Any, raw_response: dict[str, Any] | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.raw_response = raw_response

    def decimal(self, field: str) -> Decimal:
        """Read ``field`` as Decimal while leaving the underlying string unchanged."""

        value = self[field]
        if not isinstance(value, (str, int, Decimal)) or isinstance(value, bool):
            raise ValidationError(f"field {field!r} is not an exact decimal value")
        return as_decimal(value)

    def utc_datetime(self, field: str) -> datetime:
        """Read a millisecond field as UTC without changing the stored integer."""

        value = self[field]
        if not isinstance(value, (str, int)) or isinstance(value, bool):
            raise ValidationError(f"field {field!r} is not a millisecond timestamp")
        return as_utc_datetime(value)

    @property
    def extra(self) -> dict[str, Any]:
        """Fields not declared by a concrete typed response model."""

        known: frozenset[str] = getattr(type(self), "_wire_fields", frozenset())
        return {key: value for key, value in self.items() if key not in known}


class TypedRestObject(RestObject):
    """Dictionary-compatible endpoint model with typed attribute access.

    Wire keys and values are preserved exactly.  Python attributes use
    ``snake_case`` while unknown server fields remain available through normal
    mapping access and :attr:`extra`.
    """

    _aliases: ClassVar[dict[str, str]] = {}
    _nested: ClassVar[dict[str, type[TypedRestObject]]] = {}
    _nested_lists: ClassVar[dict[str, type[TypedRestObject]]] = {}
    _wire_fields: ClassVar[frozenset[str]] = frozenset()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        aliases: dict[str, str] = {}
        nested: dict[str, type[TypedRestObject]] = {}
        nested_lists: dict[str, type[TypedRestObject]] = {}
        annotations: dict[str, Any] = {}
        for base in reversed(cls.__mro__):
            aliases.update(base.__dict__.get("_aliases", {}))
            nested.update(base.__dict__.get("_nested", {}))
            nested_lists.update(base.__dict__.get("_nested_lists", {}))
            annotations.update(base.__dict__.get("__annotations__", {}))
        cls._aliases = aliases
        cls._nested = nested
        cls._nested_lists = nested_lists
        fields: set[str] = set()
        for name in annotations:
            if not name.startswith("_"):
                fields.add(aliases.get(name, _snake_to_camel(name)))
        fields.update(nested)
        fields.update(nested_lists)
        cls._wire_fields = frozenset(fields)

    def __getattr__(self, name: str) -> Any:
        wire_name = self._aliases.get(name, _snake_to_camel(name))
        try:
            return self[wire_name]
        except KeyError as exc:
            raise AttributeError(name) from exc


RestItem = TypeVar("RestItem")


class RestList(list[RestItem], Generic[RestItem]):
    """List response model with optional access to the original envelope."""

    raw_response: dict[str, Any] | None

    def __init__(
        self, values: list[RestItem], *, raw_response: dict[str, Any] | None = None
    ) -> None:
        super().__init__(values)
        self.raw_response = raw_response


RestData: TypeAlias = RestObject | RestList[Any] | dict[str, Any] | list[Any] | JsonScalar


# Namespace-specific public names make resource return contracts discoverable
# while retaining one forward-compatible representation until schemas are
# stabilized by the OpenAPI document.
MarketResponse: TypeAlias = RestData
TradeResponse: TypeAlias = RestData
AccountResponse: TypeAlias = RestData


RestModel = TypeVar("RestModel", bound=TypedRestObject)


def parse_rest_data(
    value: Any,
    *,
    raw_response: dict[str, Any] | None = None,
    model: type[RestModel] | None = None,
) -> RestData:
    """Recursively model JSON data without coercing decimal strings or timestamps."""

    if isinstance(value, dict):
        model_type: type[RestObject] = model or RestObject
        nested = getattr(model_type, "_nested", {})
        nested_lists = getattr(model_type, "_nested_lists", {})
        parsed: dict[str, Any] = {}
        for key, item in value.items():
            child_model = nested.get(key)
            list_model = nested_lists.get(key)
            parsed[key] = parse_rest_data(
                item,
                model=child_model or list_model,
            )
        return model_type(parsed, raw_response=raw_response)
    if isinstance(value, list):
        return RestList(
            [parse_rest_data(item, model=model) for item in value],
            raw_response=raw_response,
        )
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValidationError(f"unsupported REST response value: {type(value).__name__}")


def _snake_to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)
