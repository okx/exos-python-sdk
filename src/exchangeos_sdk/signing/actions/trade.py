"""Trade item helpers and compatibility action constructors."""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

from ...exceptions import SigningError
from ..client_order_id import validate_client_order_id
from ..models import (
    ActionGrouping,
    MarginMode,
    MarketType,
    OrderSide,
    OrderSizeType,
    OrderTimeInForce,
    PositionSide,
    PriceAmendType,
    TakeProfitStopLoss,
    TriggerPriceType,
)
from ..validation import choice, string_value, uint64, validate_msgpack, wire_value
from .action import Cancel, CancelAll, Modify, PlaceOrder


def perp_market(
    margin_mode: str | MarginMode = MarginMode.CROSS,
    position_side: str | PositionSide | None = None,
) -> dict[str, Any]:
    spec = {"marginMode": choice("margin_mode", margin_mode, MarginMode)}
    if position_side is not None:
        position_side_value = choice("position_side", position_side, PositionSide)
        if position_side_value != PositionSide.NET.value:
            spec["positionSide"] = position_side_value
    return {MarketType.PERP.value: spec}


def limit_order_type(
    tif: str | OrderTimeInForce = OrderTimeInForce.GTC,
    *,
    expires_after: int | None = None,
) -> dict[str, Any]:
    # ``postOnly`` was used by an early SDK draft; retain it as an input alias
    # while emitting the current chain value ``alo``.
    if tif == "postOnly":
        tif = OrderTimeInForce.ALO.value
    tif = choice("tif", tif, OrderTimeInForce)
    if tif == OrderTimeInForce.GTD.value:
        if expires_after is None:
            raise SigningError("gtd requires expires_after")
        return {
            "limit": {
                "tif": {
                    OrderTimeInForce.GTD.value: {
                        "expiresAfter": uint64("expires_after", expires_after)
                    }
                }
            }
        }
    if expires_after is not None:
        raise SigningError("expires_after is only valid for gtd")
    return {"limit": {"tif": tif}}


def trigger_order_type(
    *,
    is_market: bool,
    trigger_price: str,
    tpsl: str | TakeProfitStopLoss,
    trigger_price_type: str | TriggerPriceType = TriggerPriceType.MARK,
    parent_order_id: str | None = None,
    is_tp_limit: bool | None = None,
) -> dict[str, Any]:
    if not isinstance(is_market, bool):
        raise SigningError("is_market must be bool")
    trigger: dict[str, Any] = {
        "isMarket": is_market,
        "triggerPx": string_value("trigger_price", trigger_price),
        "tpsl": choice("tpsl", tpsl, TakeProfitStopLoss),
        "triggerPriceType": choice("trigger_price_type", trigger_price_type, TriggerPriceType),
    }
    if parent_order_id is not None:
        trigger["parentOrderId"] = string_value("parent_order_id", parent_order_id)
    if is_tp_limit is not None:
        if not isinstance(is_tp_limit, bool):
            raise SigningError("is_tp_limit must be bool")
        trigger["isTpLimit"] = is_tp_limit
    return {"trigger": trigger}


def order_item(
    *,
    asset_id: str,
    side: str | OrderSide,
    market_type: str | MarketType | Mapping[str, Any],
    price: str,
    size: str,
    order_type: Mapping[str, Any] | None = None,
    reduce_only: bool = False,
    client_order_id: str | None = None,
    size_type: str | OrderSizeType = OrderSizeType.BASE,
    price_amend_type: str | PriceAmendType | None = None,
) -> dict[str, Any]:
    if not isinstance(reduce_only, bool):
        raise SigningError("reduce_only must be bool")
    if isinstance(market_type, Mapping):
        market: Any = copy.deepcopy(dict(market_type))
        perp_key = MarketType.PERP.value
        if set(market) != {perp_key} or not isinstance(market[perp_key], Mapping):
            raise SigningError("object market_type must be a perp market specification")
    else:
        market = choice("market_type", market_type, MarketType)
    item: dict[str, Any] = {
        "assetId": string_value("asset_id", asset_id),
        "side": choice("side", wire_value(side).lower(), OrderSide),
    }
    item["marketType"] = market
    if client_order_id is not None:
        if not validate_client_order_id(client_order_id):
            raise SigningError(
                "client_order_id must be a 34-character 0x-prefixed hexadecimal value"
            )
        item["clientOrderId"] = client_order_id
    item.update(
        price=string_value("price", price),
        reduceOnly=reduce_only,
        size=string_value("size", size),
    )
    size_type = choice("size_type", size_type, OrderSizeType)
    if size_type != OrderSizeType.BASE.value:
        item["sizeType"] = size_type
    item["orderType"] = copy.deepcopy(dict(order_type or limit_order_type()))
    if price_amend_type is not None:
        amend = choice("price_amend_type", price_amend_type, PriceAmendType)
        if amend != PriceAmendType.NO_AMEND.value:
            item["priceAmendType"] = amend
    validate_msgpack(item)
    return item


def cancel_item(
    *,
    asset_id: str,
    market_type: str | MarketType | Mapping[str, Any] | None = None,
    oid: str | None = None,
    client_order_id: str | None = None,
) -> dict[str, Any]:
    if (oid is None) == (client_order_id is None):
        raise SigningError("provide exactly one of oid or client_order_id")
    if isinstance(market_type, Mapping):
        market: Any = copy.deepcopy(dict(market_type))
    elif market_type is not None:
        market = choice("market_type", market_type, MarketType)
    item: dict[str, Any] = {"assetId": string_value("asset_id", asset_id)}
    if market_type is not None:
        item["marketType"] = market
    if oid is not None:
        item["oid"] = string_value("oid", oid)
    else:
        if not validate_client_order_id(client_order_id or ""):
            raise SigningError(
                "client_order_id must be a 34-character 0x-prefixed hexadecimal value"
            )
        item["clientOrderId"] = client_order_id
    return item


def modify_item(
    *,
    oid: str | None = None,
    asset_id: str,
    price: str | None = None,
    size: str | None = None,
    order_type: Mapping[str, Any] | None = None,
    client_order_id: str | None = None,
) -> dict[str, Any]:
    if (oid is None) == (client_order_id is None):
        raise SigningError("provide exactly one of oid or client_order_id")
    if price is None and size is None and order_type is None:
        raise SigningError("modify item requires price, size, or order_type")
    item: dict[str, Any] = {}
    if oid is not None:
        item["oid"] = string_value("oid", oid)
    else:
        if not validate_client_order_id(client_order_id or ""):
            raise SigningError(
                "client_order_id must be a 34-character 0x-prefixed hexadecimal value"
            )
        item["clientOrderId"] = client_order_id
    item["assetId"] = string_value("asset_id", asset_id)
    if price is not None:
        item["price"] = string_value("price", price)
    if size is not None:
        item["size"] = string_value("size", size)
    if order_type is not None:
        item["orderType"] = copy.deepcopy(dict(order_type))
    return item


def place_order_action(
    orders: Sequence[Mapping[str, Any]],
    *,
    grouping: str | ActionGrouping = ActionGrouping.NA,
    builder: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return PlaceOrder(orders=orders, grouping=grouping, builder=builder).to_wire()


def cancel_action(cancels: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return Cancel(cancels=cancels).to_wire()


def cancel_all_action(
    *, asset_ids: Sequence[str] | None = (), market_type: str | MarketType
) -> dict[str, Any]:
    return CancelAll(asset_ids=asset_ids or (), market_type=market_type).to_wire()


def modify_action(modifies: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return Modify(modifies=modifies).to_wire()
