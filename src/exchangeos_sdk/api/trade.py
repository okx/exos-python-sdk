"""Authenticated Spot and Perps trade API."""

from typing import Any

from ..exceptions import ValidationError
from ..models import (
    FillsPage,
    Order,
    OrderHistoryPage,
    OrderState,
    PendingOrders,
    RestList,
    TransactionReceipt,
    WriteResult,
)
from .base import ROOT, BaseAPI

TRADE_ENDPOINTS = (
    "place_order",
    "cancel_order",
    "modify_order",
    "cancel_all_after",
    "transaction",
    "order",
    "orders_pending",
    "orders_history",
    "fills",
)


class TradeAPI(BaseAPI):
    """Authenticated Spot and Perps trade operations."""

    _ROOT = f"{ROOT}/trade"
    endpoint_names = TRADE_ENDPOINTS

    def place_order(self, signed_transaction: Any) -> RestList[TransactionReceipt]:
        return self._post(f"{self._ROOT}/place-order", signed_transaction)

    def cancel_order(self, signed_transaction: Any) -> RestList[TransactionReceipt]:
        return self._post(f"{self._ROOT}/cancel-order", signed_transaction)

    def modify_order(self, signed_transaction: Any) -> RestList[TransactionReceipt]:
        return self._post(f"{self._ROOT}/modify-order", signed_transaction)

    def cancel_all_after(self, signed_transaction: Any) -> RestList[WriteResult]:
        return self._post(f"{self._ROOT}/cancel-all-after", signed_transaction)

    def transaction(self, tx_hash: str) -> RestList[TransactionReceipt]:
        return self._get(f"{self._ROOT}/transaction", txHash=tx_hash)

    def order(
        self,
        *,
        oid: str | None = None,
        client_order_id: str | None = None,
        vault_address: str | None = None,
    ) -> RestList[Order]:
        has_oid = oid is not None and bool(oid.strip())
        has_client_order_id = client_order_id is not None and bool(client_order_id.strip())
        if has_oid == has_client_order_id:
            raise ValidationError("exactly one of oid or client_order_id is required")
        return self._get(
            f"{self._ROOT}/order",
            oid=oid,
            clientOrderId=client_order_id,
            vaultAddress=vault_address,
        )

    def orders_pending(
        self,
        *,
        point_board: bool | None = None,
        asset_id: str | int | None = None,
        cursor: str | None = None,
        limit: int | None = None,
        vault_address: str | None = None,
    ) -> RestList[PendingOrders]:
        return self._get(
            f"{self._ROOT}/orders-pending",
            pointBoard=point_board,
            assetId=asset_id,
            cursor=cursor,
            limit=limit,
            vaultAddress=vault_address,
        )

    def orders_history(
        self,
        *,
        point_board: bool | None = None,
        asset_id: str | int | None = None,
        state: OrderState | str | None = None,
        begin: int | None = None,
        end: int | None = None,
        cursor: str | None = None,
        limit: int | None = None,
        vault_address: str | None = None,
    ) -> RestList[OrderHistoryPage]:
        return self._get(
            f"{self._ROOT}/orders-history",
            pointBoard=point_board,
            assetId=asset_id,
            state=state,
            begin=begin,
            end=end,
            cursor=cursor,
            limit=limit,
            vaultAddress=vault_address,
        )

    def fills(
        self,
        *,
        point_board: bool | None = None,
        asset_id: str | int | None = None,
        begin: int | None = None,
        end: int | None = None,
        cursor: str | None = None,
        limit: int | None = None,
        vault_address: str | None = None,
    ) -> RestList[FillsPage]:
        return self._get(
            f"{self._ROOT}/fills",
            pointBoard=point_board,
            assetId=asset_id,
            begin=begin,
            end=end,
            cursor=cursor,
            limit=limit,
            vaultAddress=vault_address,
        )

    pending_orders = orders_pending
    order_history = orders_history
