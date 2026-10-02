from __future__ import annotations

import exchangeos_sdk as sdk


def test_public_api_exports_primary_client_and_transports() -> None:
    assert sdk.ExchangeOSClient.__name__ == "ExchangeOSClient"
    assert sdk.ExchangeOSWebSocket.__name__ == "ExchangeOSWebSocket"
    assert sdk.Credentials.__name__ == "Credentials"
    assert sdk.__version__ == "0.2.0"
    assert not hasattr(sdk, "OutcomesResponse")


def test_public_api_exports_documented_signing_builders() -> None:
    expected = {
        "place_order_action",
        "cancel_action",
        "cancel_all_action",
        "modify_action",
        "update_leverage_action",
        "update_margin_mode_action",
        "update_position_mode_action",
        "update_isolated_margin_action",
        "create_sub_account_action",
        "sub_account_transfer_action",
        "reserve_request_weight_action",
        "prediction_split_action",
        "prediction_merge_action",
        "prediction_redeem_action",
        "heartbeat_action",
        "sign_action",
        "sign_transaction",
    }
    assert expected <= set(sdk.__all__)
    assert all(callable(getattr(sdk, name)) for name in expected)


def test_public_api_exports_signing_wire_enums() -> None:
    expected = {
        "ActionGrouping",
        "IsolatedMarginDirection",
        "MarginMode",
        "MarketType",
        "OrderSide",
        "OrderSizeType",
        "OrderTimeInForce",
        "PriceAmendType",
        "PositionMode",
        "PositionSide",
        "TakeProfitStopLoss",
        "TriggerPriceType",
    }
    assert expected <= set(sdk.__all__)
    assert sdk.MarketType.PERP.value == "perp"
    assert sdk.OrderTimeInForce.POST_ONLY.value == "alo"
    assert sdk.PriceAmendType.CLAMP_TO_LIMIT.value == "clampToLimit"


def test_action_is_the_public_signing_inventory() -> None:
    assert set(sdk.Action.types()) == {
        "placeOrder",
        "cancel",
        "cancelAll",
        "modify",
        "noop",
        "createSubAccount",
        "subAccountTransfer",
        "updateLeverage",
        "updateMarginMode",
        "updatePositionMode",
        "updateIsolatedMargin",
        "reserveRequestWeight",
        "predictionSplit",
        "predictionMerge",
        "predictionRedeem",
    }
    action = sdk.PredictionSplit(market_id="1", size="10")
    assert action.type == "predictionSplit"
    assert action.to_wire() == {"type": "predictionSplit", "marketId": "1", "size": "10"}


def test_action_variants_follow_rust_tagged_union_layout() -> None:
    rust_variants = (
        "predictionSplit",
        "predictionMerge",
        "predictionRedeem",
        "placeOrder",
        "cancel",
        "cancelAll",
    )
    assert sdk.Action.types()[: len(rust_variants)] == rust_variants
    assert all(
        variant.__module__ == "exchangeos_sdk.signing.actions.action"
        for variant in (
            sdk.PredictionSplit,
            sdk.PredictionMerge,
            sdk.PredictionRedeem,
            sdk.PlaceOrder,
            sdk.Cancel,
            sdk.CancelAll,
            sdk.Modify,
            sdk.Noop,
            sdk.CreateSubAccount,
            sdk.SubAccountTransfer,
            sdk.UpdateLeverage,
            sdk.UpdateMarginMode,
            sdk.UpdatePositionMode,
            sdk.UpdateIsolatedMargin,
            sdk.ReserveRequestWeight,
        )
    )


def test_channel_families_are_public_and_disjoint_by_privacy() -> None:
    assert len(sdk.EXCHANGEOS_PUBLIC_CHANNELS) == 16
    assert len(sdk.EXCHANGEOS_PRIVATE_CHANNELS) == 9
    assert not hasattr(sdk, "OUTCOMES_PUBLIC_CHANNELS")
    assert not hasattr(sdk, "OUTCOMES_PRIVATE_CHANNELS")
    assert set(sdk.PUBLIC_CHANNELS).isdisjoint(sdk.PRIVATE_CHANNELS)


def test_rest_market_type_excludes_prediction() -> None:
    assert {member.value for member in sdk.RestMarketType} == {"spot", "perp"}


def test_raw_websocket_callback_and_environment_are_public() -> None:
    assert {"Environment", "PRODUCTION", "MessageCallback"} <= set(sdk.__all__)
    assert sdk.PRODUCTION.signing_chain is sdk.Chain.MAINNET
    for removed in (
        "WebSocketMessage",
        "ChannelDataMessage",
        "ControlWebSocketMessage",
        "SequenceGapMessage",
        "RawWebSocketMessage",
        "ParsedWebSocketMessage",
    ):
        assert not hasattr(sdk, removed)


def test_error_alias_is_backward_compatible() -> None:
    assert sdk.ApiError is sdk.APIError
    assert issubclass(sdk.RateLimitError, sdk.APIError)
    assert issubclass(sdk.SequenceGapError, sdk.WebSocketProtocolError)
