"""Compatibility constructors for typed Outcomes Action variants."""

from typing import Any

from .action import Noop, PredictionMerge, PredictionRedeem, PredictionSplit, ReserveRequestWeight


def reserve_request_weight_action(
    *, amount: str | int, token_id: str | int | None = None
) -> dict[str, Any]:
    return ReserveRequestWeight(amount=amount, token_id=token_id).to_wire()


def prediction_split_action(market_id: str, size: str) -> dict[str, Any]:
    return PredictionSplit(market_id=market_id, size=size).to_wire()


def prediction_merge_action(market_id: str, size: str) -> dict[str, Any]:
    return PredictionMerge(market_id=market_id, size=size).to_wire()


def prediction_redeem_action(market_id: str) -> dict[str, Any]:
    return PredictionRedeem(market_id=market_id).to_wire()


def heartbeat_action() -> dict[str, str]:
    return Noop().to_wire()
