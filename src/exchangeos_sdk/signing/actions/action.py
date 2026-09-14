"""Typed Action variants used by the EIP-712 signing pipeline.

Each frozen dataclass is the Python equivalent of a Rust ``Action`` enum
variant. ``to_wire()`` declaration order is part of the signing protocol.
"""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar

from ...exceptions import SigningError
from ..models import (
    ActionGrouping,
    IsolatedMarginDirection,
    MarginMode,
    MarketType,
    PositionMode,
    PositionSide,
)
from ..validation import address, choice, string_value, uint64, validate_action


class Action(Mapping[str, Any], ABC):
    """Base type for the supported tagged Action variants."""

    TYPE: ClassVar[str]
    _registry: ClassVar[dict[str, type[Action]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        action_type = cls.__dict__.get("TYPE")
        if action_type is None:
            return
        existing = Action._registry.get(action_type)
        if existing is not None and existing is not cls:
            raise TypeError(f"duplicate action type {action_type!r}")
        Action._registry[action_type] = cls

    @classmethod
    def types(cls) -> tuple[str, ...]:
        """Return registered wire types in variant declaration order."""

        return tuple(cls._registry)

    @property
    def type(self) -> str:
        return self.TYPE

    @abstractmethod
    def to_wire(self) -> dict[str, Any]:
        """Return the validated tagged mapping in canonical field order."""

    def __getitem__(self, key: str) -> Any:
        return self.to_wire()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_wire())

    def __len__(self) -> int:
        return len(self.to_wire())


def build_action(action_type: str, **payload: Any) -> dict[str, Any]:
    """Build and validate an internally tagged action mapping."""

    result = {"type": action_type, **payload}
    validate_action(result)
    return result


@dataclass(frozen=True)
class PredictionSplit(Action):
    market_id: str
    size: str

    TYPE: ClassVar[str] = "predictionSplit"

    def __post_init__(self) -> None:
        self.to_wire()

    def to_wire(self) -> dict[str, Any]:
        return build_action(
            self.type,
            marketId=string_value("market_id", self.market_id),
            size=string_value("size", self.size),
        )


@dataclass(frozen=True)
class PredictionMerge(Action):
    market_id: str
    size: str

    TYPE: ClassVar[str] = "predictionMerge"

    def __post_init__(self) -> None:
        self.to_wire()

    def to_wire(self) -> dict[str, Any]:
        return build_action(
            self.type,
            marketId=string_value("market_id", self.market_id),
            size=string_value("size", self.size),
        )


@dataclass(frozen=True)
class PredictionRedeem(Action):
    market_id: str

    TYPE: ClassVar[str] = "predictionRedeem"

    def __post_init__(self) -> None:
        self.to_wire()

    def to_wire(self) -> dict[str, Any]:
        return build_action(self.type, marketId=string_value("market_id", self.market_id))


@dataclass(frozen=True)
class PlaceOrder(Action):
    orders: Sequence[Mapping[str, Any]]
    grouping: str | ActionGrouping = ActionGrouping.NA
    builder: Mapping[str, Any] | None = None

    TYPE: ClassVar[str] = "placeOrder"

    def __post_init__(self) -> None:
        self.to_wire()

    def to_wire(self) -> dict[str, Any]:
        if not self.orders:
            raise SigningError("orders must not be empty")
        payload: dict[str, Any] = {
            "grouping": choice("grouping", self.grouping, ActionGrouping),
            "orders": [copy.deepcopy(dict(item)) for item in self.orders],
        }
        if self.builder is not None:
            payload["builder"] = copy.deepcopy(dict(self.builder))
        return build_action(self.type, **payload)


@dataclass(frozen=True)
class Cancel(Action):
    cancels: Sequence[Mapping[str, Any]]

    TYPE: ClassVar[str] = "cancel"

    def __post_init__(self) -> None:
        self.to_wire()

    def to_wire(self) -> dict[str, Any]:
        if not self.cancels:
            raise SigningError("cancels must not be empty")
        return build_action(self.type, cancels=[copy.deepcopy(dict(item)) for item in self.cancels])


@dataclass(frozen=True)
class CancelAll(Action):
    asset_ids: Sequence[str]
    market_type: str | MarketType

    TYPE: ClassVar[str] = "cancelAll"

    def __post_init__(self) -> None:
        self.to_wire()

    def to_wire(self) -> dict[str, Any]:
        return build_action(
            self.type,
            assetIds=[string_value("asset_id", item) for item in self.asset_ids],
            marketType=choice(
                "market_type",
                self.market_type,
                {MarketType.SPOT.value, MarketType.PERP.value},
            ),
        )


@dataclass(frozen=True)
class Modify(Action):
    modifies: Sequence[Mapping[str, Any]]

    TYPE: ClassVar[str] = "modify"

    def __post_init__(self) -> None:
        self.to_wire()

    def to_wire(self) -> dict[str, Any]:
        if not self.modifies:
            raise SigningError("modifies must not be empty")
        return build_action(
            self.type, modifies=[copy.deepcopy(dict(item)) for item in self.modifies]
        )


@dataclass(frozen=True)
class Noop(Action):
    TYPE: ClassVar[str] = "noop"

    def to_wire(self) -> dict[str, Any]:
        return build_action(self.type)


@dataclass(frozen=True)
class CreateSubAccount(Action):
    name: str

    TYPE: ClassVar[str] = "createSubAccount"

    def __post_init__(self) -> None:
        self.to_wire()

    def to_wire(self) -> dict[str, Any]:
        return build_action(self.type, name=string_value("name", self.name))


@dataclass(frozen=True)
class SubAccountTransfer(Action):
    sub_account_user: str
    is_deposit: bool
    token_id: str
    amount: str

    TYPE: ClassVar[str] = "subAccountTransfer"

    def __post_init__(self) -> None:
        self.to_wire()

    def to_wire(self) -> dict[str, Any]:
        if not isinstance(self.is_deposit, bool):
            raise SigningError("is_deposit must be bool")
        return build_action(
            self.type,
            subAccountUser=address("sub_account_user", self.sub_account_user),
            isDeposit=self.is_deposit,
            tokenId=string_value("token_id", self.token_id),
            amount=string_value("amount", self.amount),
        )


@dataclass(frozen=True)
class UpdateLeverage(Action):
    asset_id: str
    leverage: str
    position_side: str | PositionSide | None = None

    TYPE: ClassVar[str] = "updateLeverage"

    def __post_init__(self) -> None:
        self.to_wire()

    def to_wire(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "assetId": string_value("asset_id", self.asset_id),
            "leverage": string_value("leverage", self.leverage),
        }
        if self.position_side is not None:
            payload["positionSide"] = choice("position_side", self.position_side, PositionSide)
        return build_action(self.type, **payload)


@dataclass(frozen=True)
class UpdateMarginMode(Action):
    asset_id: str | int
    margin_mode: str | MarginMode

    TYPE: ClassVar[str] = "updateMarginMode"

    def __post_init__(self) -> None:
        self.to_wire()

    def to_wire(self) -> dict[str, Any]:
        if isinstance(self.asset_id, bool):
            raise SigningError("asset_id must be an unsigned 64-bit integer")
        try:
            numeric_asset_id = int(self.asset_id)
        except (TypeError, ValueError) as exc:
            raise SigningError("asset_id must be an unsigned 64-bit integer") from exc
        return build_action(
            self.type,
            assetId=uint64("asset_id", numeric_asset_id),
            marginMode=choice("margin_mode", self.margin_mode, MarginMode),
        )


@dataclass(frozen=True)
class UpdatePositionMode(Action):
    mode: str | PositionMode

    TYPE: ClassVar[str] = "updatePositionMode"

    def __post_init__(self) -> None:
        self.to_wire()

    def to_wire(self) -> dict[str, Any]:
        return build_action(self.type, mode=choice("mode", self.mode, PositionMode))


@dataclass(frozen=True)
class UpdateIsolatedMargin(Action):
    asset_id: str
    position_side: str | PositionSide
    direction: str | IsolatedMarginDirection
    amount: str

    TYPE: ClassVar[str] = "updateIsolatedMargin"

    def __post_init__(self) -> None:
        self.to_wire()

    def to_wire(self) -> dict[str, Any]:
        return build_action(
            self.type,
            assetId=string_value("asset_id", self.asset_id),
            positionSide=choice("position_side", self.position_side, PositionSide),
            direction=choice("direction", self.direction, IsolatedMarginDirection),
            amount=string_value("amount", self.amount),
        )


@dataclass(frozen=True)
class ReserveRequestWeight(Action):
    amount: str | int
    token_id: str | int | None = None

    TYPE: ClassVar[str] = "reserveRequestWeight"

    def __post_init__(self) -> None:
        self.to_wire()

    def to_wire(self) -> dict[str, Any]:
        if (
            isinstance(self.amount, bool)
            or not isinstance(self.amount, (str, int))
            or not str(self.amount)
        ):
            raise SigningError("amount must be a decimal string or integer")
        payload = {"amount": str(self.amount)}
        if self.token_id is not None:
            if (
                isinstance(self.token_id, bool)
                or not isinstance(self.token_id, (str, int))
                or not str(self.token_id)
            ):
                raise SigningError("token_id must be a decimal string or integer")
            payload["tokenId"] = str(self.token_id)
        return build_action(self.type, **payload)


__all__ = [
    "Action",
    "Cancel",
    "CancelAll",
    "CreateSubAccount",
    "Modify",
    "Noop",
    "PlaceOrder",
    "PredictionMerge",
    "PredictionRedeem",
    "PredictionSplit",
    "ReserveRequestWeight",
    "SubAccountTransfer",
    "UpdateIsolatedMargin",
    "UpdateLeverage",
    "UpdateMarginMode",
    "UpdatePositionMode",
]
