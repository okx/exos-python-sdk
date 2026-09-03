"""Cross-SDK action-inventory and EIP-712 compatibility tests.

These tests use the Java SDK as an external oracle. They are skipped when a
compiled Java SDK artifact is unavailable; set ``EXCHANGEOS_JAVA_SDK_JAR`` to
select the exact JAR in CI or local development.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from eth_keys import keys  # type: ignore[attr-defined]

from exchangeos_sdk import (
    Action,
    Cancel,
    CancelAll,
    Chain,
    CreateSubAccount,
    MarginMode,
    MarketType,
    Modify,
    Noop,
    PlaceOrder,
    PredictionMerge,
    PredictionRedeem,
    PredictionSplit,
    ReserveRequestWeight,
    SubAccountTransfer,
    UpdateIsolatedMargin,
    UpdateLeverage,
    UpdateMarginMode,
    UpdatePositionMode,
    cancel_item,
    modify_item,
    order_item,
    perp_market,
    sign_action,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
JAVA_PROBE_SOURCE = REPOSITORY_ROOT / "tests/java/ExchangeOSJavaCompatibilityProbe.java"
DEFAULT_JAVA_SDK_DIR = REPOSITORY_ROOT.parent / "tradezone-java-sdk"
DEFAULT_MAVEN_REPOSITORY = REPOSITORY_ROOT.parent / ".m2/repository/com/okx/trade-zone-sdk"
ACTION_CLASS = re.compile(
    r"public\s+(?:final\s+)?class\s+[\w.]+\.(\w+)\s+extends\s+"
    r"com\.okx\.tradezone\.model\.action\.Action\b"
)


@dataclass(frozen=True)
class JavaResult:
    address: str
    signing_hash: str
    signature: dict[str, Any]


@dataclass(frozen=True)
class JavaOracle:
    artifact: Path
    class_dir: Path

    def invoke(
        self,
        *,
        private_key: bytes,
        action: Mapping[str, Any],
        chain: Chain,
        nonce: int,
        expires_after: int | None = None,
        vault_address: str | None = None,
        user: str | None = None,
    ) -> JavaResult:
        private_key_hex = private_key.hex()
        stdin = "\n".join(
            (
                private_key_hex,
                json.dumps(dict(action), separators=(",", ":")),
                chain.value,
                str(nonce),
                "" if expires_after is None else str(expires_after),
                vault_address or "",
                user or "",
                "",
            )
        )
        result = subprocess.run(
            [
                "java",
                "-cp",
                os.pathsep.join(
                    (
                        str(self.class_dir),
                        str(self.artifact),
                    )
                ),
                "ExchangeOSJavaCompatibilityProbe",
            ],
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            sanitized = result.stderr.replace(private_key_hex, "<redacted>").strip()
            raise AssertionError(f"Java compatibility probe failed: {sanitized[-1200:]}")
        lines = result.stdout.splitlines()
        if len(lines) != 3:
            raise AssertionError(f"Java compatibility probe returned {len(lines)} lines")
        return JavaResult(lines[0], lines[1], json.loads(lines[2]))


def _normalized_ecdsa(signature: dict[str, Any]) -> tuple[int, int, int]:
    ecdsa = signature.get("Ecdsa")
    if not isinstance(ecdsa, dict):
        raise AssertionError("expected an Ecdsa signature")
    raw_v = ecdsa.get("v", ecdsa.get("yParity"))
    if isinstance(raw_v, str):
        v = int(raw_v, 0)
    elif isinstance(raw_v, int) and not isinstance(raw_v, bool):
        v = raw_v
    else:
        raise AssertionError("ECDSA recovery parity is missing or invalid")
    raw_r, raw_s = ecdsa.get("r"), ecdsa.get("s")
    if not isinstance(raw_r, str) or not isinstance(raw_s, str):
        raise AssertionError("ECDSA r/s values are missing or invalid")
    return int(raw_r, 0), int(raw_s, 0), v


def _action_samples() -> dict[str, Action]:
    perp_order = order_item(
        asset_id="1",
        side="buy",
        market_type=perp_market(MarginMode.CROSS),
        price="0.42",
        size="10",
    )
    return {
        "placeOrder": PlaceOrder([perp_order]),
        "cancel": Cancel([cancel_item(asset_id="1", market_type=MarketType.SPOT, oid="42")]),
        "cancelAll": CancelAll(asset_ids=["1"], market_type=MarketType.PERP),
        "modify": Modify([modify_item(oid="42", asset_id="1", price="0.43")]),
        "noop": Noop(),
        "updateLeverage": UpdateLeverage(asset_id="1", leverage="10"),
        "updateMarginMode": UpdateMarginMode(asset_id="1", margin_mode="cross"),
        "updatePositionMode": UpdatePositionMode("oneWay"),
        "updateIsolatedMargin": UpdateIsolatedMargin(
            asset_id="1", position_side="net", direction="crossToIso", amount="10"
        ),
        "createSubAccount": CreateSubAccount("compatibility-test"),
        "subAccountTransfer": SubAccountTransfer(
            sub_account_user="0x1111111111111111111111111111111111111111",
            is_deposit=True,
            token_id="1",
            amount="10",
        ),
        "reserveRequestWeight": ReserveRequestWeight(amount="10"),
        "predictionSplit": PredictionSplit("1", "10"),
        "predictionMerge": PredictionMerge("1", "10"),
        "predictionRedeem": PredictionRedeem("1"),
    }


def _spot_and_perp_action_samples() -> dict[str, Action]:
    spot_order = order_item(
        asset_id="1",
        side="buy",
        market_type=MarketType.SPOT,
        price="0.42",
        size="10",
    )
    perp_order = order_item(
        asset_id="2",
        side="sell",
        market_type=perp_market(MarginMode.ISOLATED),
        price="2500",
        size="0.5",
    )
    return {
        "placeOrder-spot": PlaceOrder([spot_order]),
        "placeOrder-perp": PlaceOrder([perp_order]),
        "cancel-spot": Cancel([cancel_item(asset_id="1", market_type=MarketType.SPOT, oid="42")]),
        "cancel-perp": Cancel([cancel_item(asset_id="2", market_type=MarketType.PERP, oid="43")]),
        "cancelAll-spot": CancelAll(asset_ids=["1"], market_type=MarketType.SPOT),
        "cancelAll-perp": CancelAll(asset_ids=["2"], market_type=MarketType.PERP),
    }


def _java_action_types(artifact: Path) -> set[str]:
    with zipfile.ZipFile(artifact) as archive:
        class_names = [
            entry.removesuffix(".class").replace("/", ".")
            for entry in archive.namelist()
            if entry.startswith("com/okx/tradezone/model/action/")
            and entry.endswith(".class")
            and "$" not in entry
        ]
    result = subprocess.run(
        ["javap", "-classpath", str(artifact), *class_names],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"could not inspect Java Action classes: {result.stderr[-1200:]}")
    return {
        class_name[:1].lower() + class_name[1:]
        for class_name in ACTION_CLASS.findall(result.stdout)
    }


def _find_java_sdk_artifact() -> Path | None:
    configured_jar = os.environ.get("EXCHANGEOS_JAVA_SDK_JAR")
    if configured_jar:
        return Path(configured_jar).expanduser()
    candidates = list(DEFAULT_JAVA_SDK_DIR.glob("target/trade-zone-sdk-*.jar"))
    if DEFAULT_MAVEN_REPOSITORY.is_dir():
        candidates.extend(DEFAULT_MAVEN_REPOSITORY.rglob("trade-zone-sdk-*.jar"))
    binary_jars = [
        candidate
        for candidate in candidates
        if not candidate.name.endswith(("-sources.jar", "-javadoc.jar"))
    ]
    return max(binary_jars, key=lambda candidate: candidate.stat().st_mtime, default=None)


def _ephemeral_private_key() -> bytes:
    while True:
        candidate = secrets.token_bytes(32)
        try:
            keys.PrivateKey(candidate)
        except Exception:  # pragma: no cover - invalid scalars are cryptographically improbable
            continue
        return candidate


def _assert_python_and_java_signatures_match(
    java_oracle: JavaOracle,
    action: Action,
    *,
    nonce: int = 1_700_000_000_123,
    expires_after: int | None = 1_700_000_060_123,
) -> None:
    private_key = _ephemeral_private_key()
    python_signed = sign_action(
        action,
        private_key,
        chain=Chain.TESTNET,
        nonce=nonce,
        expires_after=expires_after,
    )
    java = java_oracle.invoke(
        private_key=private_key,
        action=action,
        chain=Chain.TESTNET,
        nonce=nonce,
        expires_after=expires_after,
    )

    expected_address = keys.PrivateKey(private_key).public_key.to_checksum_address()
    assert java.address.lower() == expected_address.lower()
    assert java.signing_hash.lower() == python_signed.tx_hash
    assert _normalized_ecdsa(java.signature) == _normalized_ecdsa(python_signed.signature.to_wire())


@pytest.fixture(scope="session")
def java_oracle(tmp_path_factory: pytest.TempPathFactory) -> JavaOracle:
    artifact = _find_java_sdk_artifact()
    if artifact is None or not artifact.is_file():
        pytest.skip("Java SDK JAR unavailable; set EXCHANGEOS_JAVA_SDK_JAR")
    if not all(shutil.which(command) for command in ("java", "javac", "javap")):
        pytest.skip("Java 17 runtime, compiler, and javap are required for cross-SDK tests")

    class_dir = tmp_path_factory.mktemp("java-compatibility-probe")
    compile_result = subprocess.run(
        [
            "javac",
            "-cp",
            str(artifact),
            "-d",
            str(class_dir),
            str(JAVA_PROBE_SOURCE),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if compile_result.returncode != 0:
        raise AssertionError(f"could not compile Java compatibility probe: {compile_result.stderr}")
    return JavaOracle(artifact, class_dir)


def test_python_and_java_action_inventory(java_oracle: JavaOracle) -> None:
    """Snapshot the intentional scope difference and detect unreviewed drift."""

    samples = _action_samples()
    python_types = set(samples)
    java_types = _java_action_types(java_oracle.artifact)
    assert python_types == set(Action.types())
    assert python_types == {str(action["type"]) for action in samples.values()}

    assert python_types <= java_types, (
        "Python exposes Actions missing from the selected Java artifact: "
        f"{sorted(python_types - java_types)}"
    )


SIGNATURE_COMPATIBLE_ACTIONS = Action.types()


@pytest.mark.parametrize("action_type", SIGNATURE_COMPATIBLE_ACTIONS)
def test_python_and_java_signatures_match(java_oracle: JavaOracle, action_type: str) -> None:
    """Compare wallet, signing hash, and deterministic ECDSA signature byte-for-byte."""

    _assert_python_and_java_signatures_match(java_oracle, _action_samples()[action_type])


@pytest.mark.parametrize("sample_name", tuple(_spot_and_perp_action_samples()))
def test_python_and_java_spot_perp_signatures_match(
    java_oracle: JavaOracle, sample_name: str
) -> None:
    """Compare both Spot and Perps wire shapes without Prediction market samples."""

    _assert_python_and_java_signatures_match(
        java_oracle,
        _spot_and_perp_action_samples()[sample_name],
    )


def test_python_and_java_vault_address_signatures_match(java_oracle: JavaOracle) -> None:
    """Verify delegated-account signatures include vaultAddress in canonical bytes."""

    private_key = _ephemeral_private_key()
    action = _action_samples()["noop"]
    nonce = 1_700_000_000_123
    vault_address = "0x2222222222222222222222222222222222222222"
    python_signed = sign_action(
        action,
        private_key,
        chain=Chain.TESTNET,
        nonce=nonce,
        vault_address=vault_address,
    )
    java = java_oracle.invoke(
        private_key=private_key,
        action=action,
        chain=Chain.TESTNET,
        nonce=nonce,
        vault_address=vault_address,
    )
    assert java.signing_hash.lower() == python_signed.tx_hash
    assert _normalized_ecdsa(java.signature) == _normalized_ecdsa(python_signed.signature.to_wire())
