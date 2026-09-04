"""Authenticated account API."""

from typing import Any

from ..models import (
    AccountBalance,
    AccountDetail,
    AccountPositionTier,
    BillsPage,
    LeverageInfo,
    MaxSize,
    Position,
    RestList,
    TradeFee,
    TransactionReceipt,
)
from .base import ROOT, BaseAPI

ACCOUNT_ENDPOINTS = (
    "account_transfer",
    "create_sub_account",
    "set_leverage",
    "set_margin_mode",
    "set_position_mode",
    "adjust_isolated_margin",
    "balance",
    "positions",
    "max_size",
    "position_tiers",
    "leverage_info",
    "trade_fee",
    "bills",
    "detail",
)


class AccountAPI(BaseAPI):
    """Authenticated account reads and signed account writes."""

    _ROOT = f"{ROOT}/account"
    endpoint_names = ACCOUNT_ENDPOINTS

    def account_transfer(self, signed_transaction: Any) -> RestList[TransactionReceipt]:
        return self._post(
            f"{self._ROOT}/account-transfer",
            signed_transaction,
            expected_action_type="subAccountTransfer",
        )

    def create_sub_account(self, signed_transaction: Any) -> RestList[TransactionReceipt]:
        return self._post(
            f"{self._ROOT}/create-sub-account",
            signed_transaction,
            expected_action_type="createSubAccount",
        )

    def set_leverage(self, signed_transaction: Any) -> RestList[TransactionReceipt]:
        return self._post(
            f"{self._ROOT}/set-leverage",
            signed_transaction,
            expected_action_type="updateLeverage",
        )

    def set_margin_mode(self, signed_transaction: Any) -> RestList[TransactionReceipt]:
        return self._post(
            f"{self._ROOT}/set-margin-mode",
            signed_transaction,
            expected_action_type="updateMarginMode",
        )

    def set_position_mode(self, signed_transaction: Any) -> RestList[TransactionReceipt]:
        return self._post(
            f"{self._ROOT}/set-position-mode",
            signed_transaction,
            expected_action_type="updatePositionMode",
        )

    def adjust_isolated_margin(self, signed_transaction: Any) -> RestList[TransactionReceipt]:
        return self._post(
            f"{self._ROOT}/adjust-isolated-margin",
            signed_transaction,
            expected_action_type="updateIsolatedMargin",
        )

    def balance(
        self, *, vault_address: str | None = None, point_board: bool | None = None
    ) -> RestList[AccountBalance]:
        return self._get(
            f"{self._ROOT}/balance", vaultAddress=vault_address, pointBoard=point_board
        )

    def positions(
        self,
        *,
        asset_id: str | int | None = None,
        vault_address: str | None = None,
        point_board: bool | None = None,
    ) -> RestList[Position]:
        return self._get(
            f"{self._ROOT}/positions",
            assetId=asset_id,
            vaultAddress=vault_address,
            pointBoard=point_board,
        )

    def max_size(
        self,
        asset_id: str | int,
        *,
        price: str | None = None,
        leverage: str | None = None,
        reduce_only: bool | str | None = None,
        vault_address: str | None = None,
    ) -> RestList[MaxSize]:
        reduce_only_wire = (
            str(reduce_only).lower() if isinstance(reduce_only, bool) else reduce_only
        )
        return self._get(
            f"{self._ROOT}/max-size",
            assetId=asset_id,
            price=price,
            leverage=leverage,
            reduceOnly=reduce_only_wire,
            vaultAddress=vault_address,
        )

    def position_tiers(
        self, asset_id: str | int, *, vault_address: str | None = None
    ) -> RestList[AccountPositionTier]:
        return self._get(
            f"{self._ROOT}/position-tiers", assetId=asset_id, vaultAddress=vault_address
        )

    def leverage_info(
        self,
        asset_id: str | int,
        *,
        position_side: str | None = None,
        vault_address: str | None = None,
    ) -> RestList[LeverageInfo]:
        return self._get(
            f"{self._ROOT}/leverage-info",
            assetId=asset_id,
            positionSide=position_side,
            vaultAddress=vault_address,
        )

    def trade_fee(self, asset_id: str | int) -> RestList[TradeFee]:
        return self._get(f"{self._ROOT}/trade-fee", assetId=asset_id)

    def bills(
        self,
        *,
        token_id: str | None = None,
        asset_id: str | int | None = None,
        flow_category: str | None = None,
        bill_type: str | None = None,
        begin: str | int | None = None,
        end: str | int | None = None,
        cursor: str | None = None,
        limit: int | None = None,
        vault_address: str | None = None,
        point_board: bool | None = None,
    ) -> RestList[BillsPage]:
        return self._get(
            f"{self._ROOT}/bills",
            tokenId=token_id,
            assetId=asset_id,
            flowCategory=flow_category,
            billType=bill_type,
            begin=begin,
            end=end,
            cursor=cursor,
            limit=limit,
            vaultAddress=vault_address,
            pointBoard=point_board,
        )

    def detail(self) -> RestList[AccountDetail]:
        return self._get(f"{self._ROOT}/detail")
