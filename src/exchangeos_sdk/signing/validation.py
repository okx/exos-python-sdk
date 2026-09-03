"""Validation shared by signing models, action builders, and protocol code."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from enum import Enum
from typing import Any

from ..exceptions import SigningError

UINT64_MAX = 2**64 - 1


def wire_value(value: str | Enum) -> str:
    return str(value.value if isinstance(value, Enum) else value)


def string_value(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise SigningError(f"{name} must be a non-empty string")
    return value


def choice(
    name: str,
    value: str | Enum,
    allowed: Collection[str] | type[Enum],
) -> str:
    if isinstance(allowed, type) and issubclass(allowed, Enum):
        allowed_values = {wire_value(member) for member in allowed}
    else:
        allowed_values = set(allowed)
    result = wire_value(value)
    if result not in allowed_values:
        raise SigningError(f"{name} must be one of {sorted(allowed_values)}")
    return result


def uint64(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= UINT64_MAX:
        raise SigningError(f"{name} must be an unsigned 64-bit integer")
    return int(value)


def address(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    try:
        valid = len(value) == 42 and value.startswith("0x") and len(bytes.fromhex(value[2:])) == 20
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise SigningError(f"{name} must be a 20-byte 0x-prefixed hex address")
    return value


def validate_msgpack(value: Any, path: str = "action") -> None:
    if value is None or isinstance(value, (str, bytes, bool)):
        return
    if isinstance(value, int):
        if not -(2**63) <= value <= UINT64_MAX:
            raise SigningError(f"{path} integer is outside MessagePack 64-bit range")
        return
    if isinstance(value, float):
        raise SigningError(f"{path} must use a decimal string instead of float")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise SigningError(f"{path} keys must be strings")
            validate_msgpack(item, f"{path}.{key}")
        return
    if isinstance(value, Sequence):
        for index, item in enumerate(value):
            validate_msgpack(item, f"{path}[{index}]")
        return
    raise SigningError(f"{path} contains unsupported value type {type(value).__name__}")


def validate_action(action: Mapping[str, Any]) -> None:
    if not isinstance(action, Mapping):
        raise SigningError("action must be a mapping")
    string_value("action.type", action.get("type"))
    validate_msgpack(action)
