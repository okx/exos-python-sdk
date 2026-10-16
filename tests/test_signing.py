import secrets

import msgpack
import pytest
from eth_utils import keccak

import exchangeos_sdk.signing.client_order_id as client_order_id_module
import exchangeos_sdk.signing.protocol as signing_module
from exchangeos_sdk.exceptions import SigningError
from exchangeos_sdk.signing import (
    ActionGrouping,
    Cancel,
    CancelAll,
    Chain,
    IsolatedMarginDirection,
    MarginMode,
    MarketType,
    OrderSide,
    OrderSizeType,
    OrderSource,
    OrderTimeInForce,
    PlaceOrder,
    PositionMode,
    PositionSide,
    PredictionMerge,
    PredictionRedeem,
    PredictionSplit,
    PriceAmendType,
    Region,
    Signature,
    SignedTransaction,
    TakeProfitStopLoss,
    TriggerPriceType,
    cancel_action,
    cancel_all_action,
    cancel_item,
    connection_id,
    create_sub_account_action,
    domain_separator,
    generate_client_order_id,
    heartbeat_action,
    limit_order_type,
    modify_action,
    modify_item,
    order_item,
    perp_market,
    place_order_action,
    prediction_merge_action,
    prediction_redeem_action,
    prediction_split_action,
    recover_address,
    reserve_request_weight_action,
    serialize_unsigned_transaction,
    sign_action,
    sign_transaction,
    signing_hash,
    sub_account_transfer_action,
    trigger_order_type,
    unsigned_transaction,
    update_isolated_margin_action,
    update_leverage_action,
    update_margin_mode_action,
    update_position_mode_action,
    validate_client_order_id,
)
from exchangeos_sdk.signing.actions.action import build_action


def test_common_action_builder_preserves_type_first_and_validates_payload() -> None:
    assert list(build_action("predictionRedeem", marketId="1")) == ["type", "marketId"]
    with pytest.raises(SigningError, match="decimal string"):
        build_action("predictionSplit", marketId="1", size=1.0)


def test_typed_action_is_directly_signable_and_matches_legacy_builder() -> None:
    action = PredictionSplit(market_id="1", size="10")
    assert dict(action) == prediction_split_action("1", "10")
    signed = sign_action(action, secrets.token_bytes(32), nonce=1000)
    assert signed.action == action.to_wire()


def test_rust_action_variant_field_order_is_preserved() -> None:
    order = order_item(asset_id="1", side="buy", market_type="prediction", price="0.4", size="2")
    cancel = cancel_item(asset_id="1", market_type="prediction", oid="7")
    actions_and_keys = (
        (PredictionSplit("1", "2"), ["type", "marketId", "size"]),
        (PredictionMerge("1", "2"), ["type", "marketId", "size"]),
        (PredictionRedeem("1"), ["type", "marketId"]),
        (PlaceOrder([order]), ["type", "grouping", "orders"]),
        (Cancel([cancel]), ["type", "cancels"]),
        (CancelAll([], "spot"), ["type", "assetIds", "marketType"]),
    )
    for action, expected_keys in actions_and_keys:
        assert list(action.to_wire()) == expected_keys


def test_domain_separator_matches_rust_sdk_snapshot() -> None:
    assert (
        domain_separator().hex()
        == "0f8677bc4b76654f0e82c0daa2fd3feb46384b8f7e86a9a2dc1cb93c0d7871cb"
    )


def test_sample_place_order_hash_matches_rust_sdk() -> None:
    order = order_item(
        asset_id="100170100",
        side="buy",
        market_type="prediction",
        client_order_id="0x0197a98c91312671ca83f15ccbd5186f",
        price="0.41",
        size="1.0",
        order_type=limit_order_type("gtc"),
    )
    action = place_order_action([order])
    digest = signing_hash(
        action,
        1777392508038,
        expires_after=1777396108038,
        chain=Chain.MAINNET,
    )
    assert digest.hex() == "fd27f6d086ca25dcaacab0054f7c81560dcbf6fce174a4bf0dc9b0fe82dcb683"


def test_sample_messagepack_and_connection_id_match_rust_sdk() -> None:
    order = order_item(
        asset_id="100170100",
        side="buy",
        market_type="prediction",
        client_order_id="0x0197a98c91312671ca83f15ccbd5186f",
        price="0.41",
        size="1.0",
        order_type=limit_order_type("gtc"),
    )
    action = place_order_action([order])
    encoded = serialize_unsigned_transaction(
        action,
        1777392508038,
        expires_after=1777396108038,
    )
    assert encoded.hex() == (
        "83a6616374696f6e83a474797065aa706c6163654f72646572a867726f7570696e67a26e61"
        "a66f72646572739188a761737365744964a9313030313730313030a473696465a3627579aa"
        "6d61726b657454797065aa70726564696374696f6ead636c69656e744f726465724964d922"
        "30783031393761393863393133313236373163613833663135636362643531383666a57072"
        "696365a4302e3431aa7265647563654f6e6c79c2a473697a65a3312e30a96f726465725479"
        "706581a56c696d697481a3746966a3677463a56e6f6e6365cf0000019dd4d95c86ac6578"
        "70697265734166746572cf0000019dd5104b06"
    )
    assert (
        connection_id(
            action,
            1777392508038,
            expires_after=1777396108038,
        ).hex()
        == "8108bf7f7b9dfe82ea0ad32148d1a2d3d9a732983bc65c5883cb05c7f5fdcd55"
    )


def test_sign_action_matches_cross_sdk_signature_fixture() -> None:
    # This public label deterministically derives a non-production test scalar;
    # no credential or reusable secret is stored in the repository.
    test_scalar = keccak(text="exchangeos-sdk-public-test-fixture-v1")
    order = order_item(
        asset_id="100170100",
        side="buy",
        market_type="prediction",
        client_order_id="0x0197a98c91312671ca83f15ccbd5186f",
        price="0.41",
        size="1.0",
        order_type=limit_order_type("gtc"),
    )
    signed = sign_action(
        place_order_action([order]),
        test_scalar,
        nonce=1777392508038,
        expires_after=1777396108038,
    )
    assert signed.signature == Signature(
        r="0x82035ab1dad05c40dec8ad3124f387ac90e1bfe1cdb2fcfddeb54b552c7123eb",
        s="0x02558e2f175bf19e0eaf569d50efcef6d12a5be5daa17dfb07c8da326394aab4",
        v=1,
    )


def test_sign_transaction_remains_compatible_with_sign_action() -> None:
    test_scalar = keccak(text="exchangeos-sdk-public-test-fixture-v1")
    action = heartbeat_action()
    assert sign_transaction(action, test_scalar, nonce=1) == sign_action(
        action, test_scalar, nonce=1
    )


def test_sign_and_recover_round_trip_with_runtime_key() -> None:
    raw_key = secrets.token_bytes(32)
    action = prediction_split_action("1", "10")
    signed = sign_transaction(action, raw_key, nonce=1000)
    assert signed.signature.v in {0, 1}
    assert recover_address(signed).startswith("0x")
    assert len(recover_address(signed)) == 42


def test_client_order_id_shape() -> None:
    value = generate_client_order_id()
    assert validate_client_order_id(value)
    assert value.startswith("0x03")
    assert len(value) == 34
    assert value == value.lower()


def test_cancel_item_requires_exactly_one_target() -> None:
    item = cancel_item(asset_id="2", market_type="prediction", oid="7")
    assert list(item) == ["assetId", "marketType", "oid"]


def test_rust_sample_signature_recovers_expected_signer() -> None:
    order = order_item(
        asset_id="100170100",
        side="buy",
        market_type="prediction",
        client_order_id="0x0197a98c91312671ca83f15ccbd5186f",
        price="0.41",
        size="1.0",
        order_type=limit_order_type("gtc"),
    )
    transaction = SignedTransaction(
        action=place_order_action([order]),
        nonce=1777392508038,
        expires_after=1777396108038,
        signature=Signature(
            r="0x563ad61b44c899649bc2f9381a80328655c7041355f25028a829315222a92813",
            s="0x73f29cd00db2c8d2658d50d87a1aad63de37a20dfb3004a83a5044d374fdc9ad",
            v=1,
        ),
    )
    assert recover_address(transaction) == "0x42b7281d1d9577213c442bd2a1af751f47b565ea"


def test_unsigned_transaction_msgpack_preserves_canonical_order_and_optionals() -> None:
    user = "0x1111111111111111111111111111111111111111"
    vault = "0x2222222222222222222222222222222222222222"
    action = prediction_split_action("7", "10.5")
    encoded = serialize_unsigned_transaction(
        action, 100, expires_after=200, vault_address=vault, user=user
    )
    decoded = msgpack.unpackb(encoded, raw=False)
    assert list(decoded) == ["action", "nonce", "expiresAfter", "vaultAddress", "user"]
    assert decoded["vaultAddress"] == bytes.fromhex(vault[2:])
    assert decoded["user"] == bytes.fromhex(user[2:])
    assert list(decoded["action"]) == ["type", "marketId", "size"]
    assert serialize_unsigned_transaction(action, 100) != encoded
    assert connection_id(action, 100) != connection_id(action, 101)


def test_all_outcomes_actions_have_java_rust_wire_shapes() -> None:
    assert prediction_split_action("1", "2") == {
        "type": "predictionSplit",
        "marketId": "1",
        "size": "2",
    }
    assert prediction_merge_action("1", "2")["type"] == "predictionMerge"
    assert prediction_redeem_action("1") == {"type": "predictionRedeem", "marketId": "1"}
    assert reserve_request_weight_action(amount=50, token_id=0) == {
        "type": "reserveRequestWeight",
        "amount": "50",
        "tokenId": "0",
    }
    assert heartbeat_action() == {"type": "noop"}


def test_trade_action_builders_cover_limit_trigger_modify_and_cancel() -> None:
    trigger = trigger_order_type(
        is_market=False, trigger_price="50000", tpsl="tp", trigger_price_type="mark"
    )
    modify = modify_item(oid="9", asset_id="102", price="51000", order_type=trigger)
    assert modify_action([modify]) == {
        "type": "modify",
        "modifies": [{"oid": "9", "assetId": "102", "price": "51000", "orderType": trigger}],
    }
    cancel = cancel_item(asset_id="102", market_type="perp", oid="9")
    assert cancel_action([cancel]) == {"type": "cancel", "cancels": [cancel]}
    assert cancel_all_action(asset_ids=None, market_type="perp") == {
        "type": "cancelAll",
        "assetIds": [],
        "marketType": "perp",
    }


def test_account_actions_match_java_and_exchangeos_controller_discriminators() -> None:
    assert update_leverage_action(asset_id="102", position_side="long", leverage="20") == {
        "type": "updateLeverage",
        "assetId": "102",
        "leverage": "20",
        "positionSide": "long",
    }
    assert update_margin_mode_action(asset_id="102", margin_mode="isolated") == {
        "type": "updateMarginMode",
        "assetId": 102,
        "marginMode": "isolated",
    }
    assert update_position_mode_action("hedge") == {"type": "updatePositionMode", "mode": "hedge"}
    assert (
        update_isolated_margin_action(
            asset_id="102", position_side="net", direction="isoToCross", amount="0.28"
        )["type"]
        == "updateIsolatedMargin"
    )
    assert create_sub_account_action("trader-sub-1") == {
        "type": "createSubAccount",
        "name": "trader-sub-1",
    }
    assert sub_account_transfer_action(
        sub_account_user="0x1111111111111111111111111111111111111111",
        is_deposit=True,
        token_id="1",
        amount="100",
    ) == {
        "type": "subAccountTransfer",
        "subAccountUser": "0x1111111111111111111111111111111111111111",
        "isDeposit": True,
        "tokenId": "1",
        "amount": "100",
    }


def test_signed_envelope_includes_vault_in_agent_hash() -> None:
    key = secrets.token_bytes(32)
    vault = "0x2222222222222222222222222222222222222222"
    action = prediction_redeem_action("1")
    direct = signing_hash(action, 10, vault_address=vault)
    signed = sign_transaction(action, key, nonce=10, vault_address=vault)
    assert bytes.fromhex(signed.tx_hash.removeprefix("0x")) == direct
    assert direct != signing_hash(action, 10)
    assert list(signed.to_wire()) == ["action", "nonce", "vaultAddress", "signature"]
    assert signed.to_wire()["vaultAddress"] == vault


def test_signing_snapshots_and_freezes_action_against_mutation() -> None:
    source = prediction_split_action("1", "10")
    signed = sign_transaction(source, secrets.token_bytes(32), nonce=1000)
    source["size"] = "999"
    assert signed.action["size"] == "10"
    with pytest.raises(TypeError, match="immutable"):
        signed.action["size"] = "999"  # type: ignore[index]
    wire = signed.to_wire()
    wire["action"]["size"] = "888"
    assert signed.action["size"] == "10"


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: signing_hash({"type": "x", "price": 0.1}, 1), "decimal string"),
        (lambda: signing_hash({}, 1), "action.type"),
        (lambda: signing_hash({"type": "x"}, -1), "unsigned 64-bit"),
        (lambda: limit_order_type("gtd"), "requires expires_after"),
        (lambda: modify_item(oid="1", asset_id="2"), "requires price"),
        (lambda: update_position_mode_action("dual"), "must be one of"),
    ],
)
def test_validation_rejects_ambiguous_or_invalid_wire_values(call, message: str) -> None:
    with pytest.raises(SigningError, match=message):
        call()


def test_private_key_never_appears_in_error_or_transaction_repr() -> None:
    secret = "not-a-valid-private-key"
    with pytest.raises(SigningError) as caught:
        sign_transaction(heartbeat_action(), secret, nonce=1)
    assert secret not in str(caught.value)

    signed = sign_transaction(heartbeat_action(), secrets.token_bytes(32), nonce=1)
    assert "tx_hash" not in repr(signed)
    assert "private" not in repr(signed).lower()


def test_signature_and_address_validation_are_strict() -> None:
    with pytest.raises(SigningError, match="signature v"):
        Signature("0x" + "00" * 32, "0x" + "00" * 32, 27)
    with pytest.raises(SigningError, match="vault_address"):
        sign_transaction(heartbeat_action(), secrets.token_bytes(32), nonce=1, vault_address="0x1")


def test_builder_inputs_are_copied_before_action_mutation() -> None:
    order = order_item(asset_id="1", side="buy", market_type="spot", price="2", size="3")
    action = place_order_action([order])
    order["price"] = "900"
    assert action["orders"][0]["price"] == "2"


def test_unsigned_transaction_public_helper_returns_fresh_data() -> None:
    action = prediction_redeem_action("1")
    tx = unsigned_transaction(action, 1)
    tx["action"]["marketId"] = "2"
    assert action["marketId"] == "1"


def test_enum_inputs_and_client_order_id_regions() -> None:
    assert cancel_all_action(asset_ids=[], market_type=MarketType.SPOT)["marketType"] == "spot"
    assert generate_client_order_id(Region.US).startswith("0x13")
    assert generate_client_order_id(Region.EU).startswith("0x23")
    assert generate_client_order_id(source=OrderSource.MANUAL).startswith("0x02")
    assert generate_client_order_id(source=OrderSource.TRIGGER).startswith("0x04")
    assert generate_client_order_id(source=OrderSource.LIQUIDATION).startswith("0x05")
    with pytest.raises(SigningError, match="Region"):
        generate_client_order_id(0)  # type: ignore[arg-type]
    with pytest.raises(SigningError, match="OrderSource"):
        generate_client_order_id(source=1)  # type: ignore[arg-type]


def test_action_enums_emit_the_same_wire_values_as_string_inputs() -> None:
    enum_order = order_item(
        asset_id="1",
        side=OrderSide.BUY,
        market_type=MarketType.SPOT,
        client_order_id="0x03333333333333333333333333333333",
        price="2",
        size="3",
        size_type=OrderSizeType.QUOTE,
        order_type=limit_order_type(OrderTimeInForce.POST_ONLY),
    )
    string_order = order_item(
        asset_id="1",
        side="buy",
        market_type="spot",
        client_order_id="0x03333333333333333333333333333333",
        price="2",
        size="3",
        size_type="quote",
        order_type=limit_order_type("alo"),
    )
    assert enum_order == string_order
    assert place_order_action([enum_order], grouping=ActionGrouping.NA) == place_order_action(
        [string_order], grouping="na"
    )
    assert perp_market(MarginMode.ISOLATED, PositionSide.LONG) == {
        "perp": {"marginMode": "isolated", "positionSide": "long"}
    }
    assert trigger_order_type(
        is_market=True,
        trigger_price="2",
        tpsl=TakeProfitStopLoss.STOP_LOSS,
        trigger_price_type=TriggerPriceType.INDEX,
    ) == trigger_order_type(
        is_market=True,
        trigger_price="2",
        tpsl="sl",
        trigger_price_type="index",
    )
    assert (
        update_margin_mode_action(asset_id=1, margin_mode=MarginMode.CROSS)["marginMode"] == "cross"
    )
    assert update_position_mode_action(PositionMode.ONE_WAY)["mode"] == "oneWay"
    assert (
        update_isolated_margin_action(
            asset_id="1",
            position_side=PositionSide.SHORT,
            direction=IsolatedMarginDirection.CROSS_TO_ISOLATED,
            amount="1",
        )["direction"]
        == "crossToIso"
    )


@pytest.mark.parametrize(
    "value",
    [None, 12, "", "0x1", "0x" + "0" * 31 + "G"],
)
def test_client_order_id_rejects_invalid_values(value) -> None:
    assert not validate_client_order_id(value)


def test_client_order_id_parser_compatibility_accepts_uppercase() -> None:
    assert validate_client_order_id("0X03" + "A" * 30)


def test_client_order_id_uses_120_bits_of_secure_randomness(monkeypatch) -> None:
    calls: list[int] = []

    def token_hex(size: int) -> str:
        calls.append(size)
        return "a3f1b2c4d5e678901234abcdef0123"

    monkeypatch.setattr(client_order_id_module.secrets, "token_hex", token_hex)
    assert generate_client_order_id() == "0x03a3f1b2c4d5e678901234abcdef0123"
    assert calls == [15]


def test_ten_thousand_generated_client_order_ids_are_unique() -> None:
    values = {generate_client_order_id() for _ in range(10_000)}
    assert len(values) == 10_000


def test_perp_market_variants_and_validation() -> None:
    assert perp_market() == {"perp": {"marginMode": "cross"}}
    assert perp_market("isolated", "long") == {
        "perp": {"marginMode": "isolated", "positionSide": "long"}
    }
    assert perp_market("cross", "net") == {"perp": {"marginMode": "cross"}}
    with pytest.raises(SigningError, match="margin_mode"):
        perp_market("portfolio")
    with pytest.raises(SigningError, match="position_side"):
        perp_market("isolated", "net-short")


def test_limit_order_type_all_option_branches() -> None:
    assert limit_order_type("gtd", expires_after=123) == {
        "limit": {"tif": {"gtd": {"expiresAfter": 123}}}
    }
    assert limit_order_type("alo") == {"limit": {"tif": "alo"}}
    assert limit_order_type("postOnly") == {"limit": {"tif": "alo"}}
    with pytest.raises(SigningError, match="only valid for gtd"):
        limit_order_type("gtc", expires_after=123)
    with pytest.raises(SigningError, match="unsigned 64-bit"):
        limit_order_type("gtd", expires_after=-1)


def test_trigger_order_type_optional_fields_and_validation() -> None:
    value = trigger_order_type(
        is_market=True,
        trigger_price="1",
        tpsl="sl",
        trigger_price_type="index",
        parent_order_id="5",
        is_tp_limit=True,
    )
    assert value["trigger"]["parentOrderId"] == "5"
    assert value["trigger"]["isTpLimit"] is True
    with pytest.raises(SigningError, match="is_market"):
        trigger_order_type(is_market=1, trigger_price="1", tpsl="tp")  # type: ignore[arg-type]
    with pytest.raises(SigningError, match="is_tp_limit"):
        trigger_order_type(
            is_market=False,
            trigger_price="1",
            tpsl="tp",
            is_tp_limit="yes",  # type: ignore[arg-type]
        )


def test_order_item_perp_quote_and_validation_branches() -> None:
    item = order_item(
        asset_id="2",
        side="SELL",
        market_type=perp_market("isolated", "short"),
        price="5",
        size="7",
        reduce_only=True,
        size_type="quote",
    )
    assert item["side"] == "sell"
    assert item["sizeType"] == "quote"
    assert item["marketType"]["perp"]["positionSide"] == "short"


def test_order_item_price_amend_type_is_emitted_when_requested() -> None:
    item = order_item(
        asset_id="1",
        side="buy",
        market_type="spot",
        price="2",
        size="3",
        price_amend_type=PriceAmendType.CLAMP_TO_LIMIT,
    )
    assert item["priceAmendType"] == "clampToLimit"
    assert list(item)[-2:] == ["orderType", "priceAmendType"]
    assert "priceAmendType" not in order_item(
        asset_id="1",
        side="buy",
        market_type="spot",
        price="2",
        size="3",
        price_amend_type=PriceAmendType.NO_AMEND,
    )

    with pytest.raises(SigningError, match="reduce_only"):
        order_item(asset_id="1", side="buy", market_type="spot", price="2", size="3", reduce_only=1)
    with pytest.raises(SigningError, match="perp market"):
        order_item(asset_id="1", side="buy", market_type={"spot": {}}, price="2", size="3")
    with pytest.raises(SigningError, match="client_order_id"):
        order_item(
            asset_id="1",
            side="buy",
            market_type="spot",
            price="2",
            size="3",
            client_order_id="bad",
        )


def test_order_item_allows_omitted_client_order_id() -> None:
    item = order_item(asset_id="1", side="buy", market_type="spot", price="2", size="3")
    assert validate_client_order_id(item["clientOrderId"])
    assert item["clientOrderId"].startswith("0x03")


def test_place_and_cancel_action_optional_and_empty_branches() -> None:
    order = order_item(asset_id="1", side="buy", market_type="spot", price="2", size="3")
    assert (
        place_order_action([order], builder={"address": "maker", "fee": "0.001"})["builder"]["fee"]
        == "0.001"
    )
    with pytest.raises(SigningError, match="orders"):
        place_order_action([])
    with pytest.raises(SigningError, match="cancels"):
        cancel_action([])
    with pytest.raises(SigningError, match="exactly one"):
        cancel_item(asset_id="1", market_type="spot")
    with pytest.raises(SigningError, match="exactly one"):
        cancel_item(asset_id="1", market_type="spot", oid="1", client_order_id="x")
    with pytest.raises(SigningError, match="client_order_id"):
        cancel_item(asset_id="1", market_type="spot", client_order_id="bad")
    cloid = "0x0197a98c91312671ca83f15ccbd5186f"
    assert (
        cancel_item(asset_id="1", market_type=perp_market(), client_order_id=cloid)["clientOrderId"]
        == cloid
    )
    assert cancel_item(asset_id="1", oid="7") == {"assetId": "1", "oid": "7"}


def test_modify_all_optional_fields_and_empty_action() -> None:
    assert modify_item(oid="1", asset_id="2", size="3") == {
        "oid": "1",
        "assetId": "2",
        "size": "3",
    }
    client_order_id = "0x0197a98c91312671ca83f15ccbd5186f"
    assert modify_item(
        client_order_id=client_order_id,
        asset_id="2",
        price="4",
    ) == {
        "clientOrderId": client_order_id,
        "assetId": "2",
        "price": "4",
    }
    assert modify_item(oid="1", asset_id="2", order_type=limit_order_type())["orderType"]
    with pytest.raises(SigningError, match="exactly one"):
        modify_item(asset_id="2", size="3")
    with pytest.raises(SigningError, match="exactly one"):
        modify_item(oid="1", client_order_id=client_order_id, asset_id="2", size="3")
    with pytest.raises(SigningError, match="client_order_id"):
        modify_item(client_order_id="bad", asset_id="2", size="3")
    with pytest.raises(SigningError, match="modifies"):
        modify_action([])


def test_account_builder_legacy_and_invalid_branches() -> None:
    assert update_leverage_action(asset_id="2", leverage="10", position_side="net") == {
        "type": "updateLeverage",
        "assetId": "2",
        "leverage": "10",
        "positionSide": "net",
    }
    with pytest.raises(SigningError, match="is_deposit"):
        sub_account_transfer_action(
            sub_account_user="0x1111111111111111111111111111111111111111",
            is_deposit=1,
            token_id="0",
            amount="2",  # type: ignore[arg-type]
        )
    with pytest.raises(SigningError, match="direction"):
        update_isolated_margin_action(
            asset_id="1", position_side="net", direction="sideways", amount="2"
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"amount": True},
        {"amount": ""},
        {"amount": "1", "token_id": True},
        {"amount": "1", "token_id": ""},
    ],
)
def test_reserve_request_weight_rejects_invalid_values(kwargs) -> None:
    with pytest.raises(SigningError):
        reserve_request_weight_action(**kwargs)
    assert reserve_request_weight_action(amount="1") == {
        "type": "reserveRequestWeight",
        "amount": "1",
    }


def test_msgpack_validation_rejects_keys_ranges_types_and_non_mapping_action() -> None:
    invalid = [
        {"type": "x", 1: "value"},
        {"type": "x", "value": 2**65},
        {"type": "x", "value": object()},
    ]
    for action in invalid:
        with pytest.raises(SigningError):
            signing_hash(action, 1)
    with pytest.raises(SigningError, match="action must be a mapping"):
        signing_hash(["x"], 1)  # type: ignore[arg-type]
    with pytest.raises(SigningError, match="unsigned 64-bit"):
        unsigned_transaction(heartbeat_action(), True)


def test_serialization_wraps_encoder_errors_without_action_data(monkeypatch) -> None:
    secret_marker = "marker-that-must-not-leak"

    def fail(*_args, **_kwargs):
        raise ValueError(secret_marker)

    monkeypatch.setattr(signing_module.msgpack, "packb", fail)
    with pytest.raises(SigningError) as caught:
        serialize_unsigned_transaction({"type": "noop"}, 1)
    assert secret_marker not in str(caught.value)


def test_signed_transaction_all_optionals_and_boundary_validation() -> None:
    key = secrets.token_bytes(32)
    user = "0x1111111111111111111111111111111111111111"
    vault = "0x2222222222222222222222222222222222222222"
    signed = sign_transaction(
        heartbeat_action(),
        key,
        nonce=2**64 - 1,
        expires_after=2**64 - 1,
        vault_address=vault,
        user=user,
        chain=Chain.DEV,
    )
    assert list(signed.to_wire()) == [
        "action",
        "nonce",
        "expiresAfter",
        "vaultAddress",
        "signature",
        "user",
    ]
    assert signed.to_wire()["user"] == user
    with pytest.raises(SigningError, match="expires_after"):
        sign_transaction(heartbeat_action(), key, nonce=1, expires_after=2**64)
    with pytest.raises(SigningError, match="user"):
        sign_transaction(heartbeat_action(), key, nonce=1, user="0xxyz")
    with pytest.raises(SigningError, match="chain"):
        signing_hash(heartbeat_action(), 1, chain="Mainnet")  # type: ignore[arg-type]
    with pytest.raises(SigningError, match="chain_id"):
        domain_separator(-1)


def test_auto_nonce_hex_key_and_invalid_key_type(monkeypatch) -> None:
    monkeypatch.setattr(signing_module, "_last_auto_nonce", 0)
    monkeypatch.setattr(signing_module.time, "time_ns", lambda: 123_000_000)
    raw_key = secrets.token_bytes(32)
    signed = sign_transaction(heartbeat_action(), "0x" + raw_key.hex())
    assert signed.nonce == 123
    assert sign_transaction(heartbeat_action(), raw_key).nonce == 124
    with pytest.raises(SigningError, match="private key"):
        sign_transaction(heartbeat_action(), object(), nonce=1)  # type: ignore[arg-type]
    with pytest.raises(SigningError, match="private key"):
        sign_transaction(heartbeat_action(), b"short", nonce=1)


def test_signature_hex_and_recovery_failure_paths() -> None:
    with pytest.raises(SigningError, match="signature r"):
        Signature("not-hex", "0x" + "00" * 32, 0)
    with pytest.raises(SigningError, match="signature s"):
        Signature("0x" + "00" * 32, "0x" + "GG" * 32, 0)
    transaction = SignedTransaction(
        action=heartbeat_action(),
        nonce=1,
        signature=Signature("0x" + "00" * 32, "0x" + "00" * 32, 0),
    )
    with pytest.raises(SigningError, match="recovery failed"):
        recover_address(transaction)


def test_immutable_action_rejects_all_common_mutators() -> None:
    signed = sign_transaction(
        {"type": "x", "nested": {"a": 1}, "items": [1, 2]},
        secrets.token_bytes(32),
        nonce=1,
    )
    with pytest.raises(TypeError, match="immutable"):
        signed.action.update({"type": "y"})  # type: ignore[attr-defined]
    with pytest.raises(TypeError, match="immutable"):
        signed.action.pop("type")  # type: ignore[attr-defined]
    with pytest.raises(TypeError, match="immutable"):
        signed.action.clear()  # type: ignore[attr-defined]
    assert isinstance(signed.action["items"], tuple)
    assert signed.to_wire()["action"]["items"] == [1, 2]
