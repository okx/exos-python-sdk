"""Compatibility constructors for typed account Action variants."""

from typing import Any

from ..models import IsolatedMarginDirection, MarginMode, PositionMode, PositionSide
from .action import (
    CreateSubAccount,
    SubAccountTransfer,
    UpdateIsolatedMargin,
    UpdateLeverage,
    UpdateMarginMode,
    UpdatePositionMode,
)


def update_leverage_action(
    *,
    asset_id: str,
    leverage: str,
    position_side: str | PositionSide | None = None,
) -> dict[str, Any]:
    return UpdateLeverage(
        asset_id=asset_id, leverage=leverage, position_side=position_side
    ).to_wire()


def update_margin_mode_action(
    *, asset_id: str | int, margin_mode: str | MarginMode
) -> dict[str, Any]:
    return UpdateMarginMode(asset_id=asset_id, margin_mode=margin_mode).to_wire()


def update_position_mode_action(mode: str | PositionMode) -> dict[str, Any]:
    return UpdatePositionMode(mode=mode).to_wire()


def update_isolated_margin_action(
    *,
    asset_id: str,
    position_side: str | PositionSide,
    direction: str | IsolatedMarginDirection,
    amount: str,
) -> dict[str, Any]:
    return UpdateIsolatedMargin(
        asset_id=asset_id, position_side=position_side, direction=direction, amount=amount
    ).to_wire()


def create_sub_account_action(name: str) -> dict[str, Any]:
    return CreateSubAccount(name=name).to_wire()


def sub_account_transfer_action(
    *, sub_account_user: str, is_deposit: bool, token_id: str, amount: str
) -> dict[str, Any]:
    return SubAccountTransfer(
        sub_account_user=sub_account_user,
        is_deposit=is_deposit,
        token_id=token_id,
        amount=amount,
    ).to_wire()
