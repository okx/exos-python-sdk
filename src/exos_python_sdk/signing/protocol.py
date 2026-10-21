"""Canonical MessagePack and EIP-712 transaction signing."""

from __future__ import annotations

import copy
import threading
import time
from collections.abc import Mapping
from typing import Any, cast

import msgpack  # type: ignore[import-untyped]
from eth_abi import encode  # type: ignore[attr-defined]
from eth_keys import keys  # type: ignore[attr-defined]
from eth_utils import keccak  # type: ignore[attr-defined]

from ..exceptions import SigningError
from .models import Chain, Signature, SignedTransaction, thaw
from .validation import address, uint64, validate_action

DOMAIN_NAME = "Exchange"
DOMAIN_VERSION = "1"
DOMAIN_CHAIN_ID = 70_000_196
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

_nonce_lock = threading.Lock()
_last_auto_nonce = 0

_ACTION_ADDRESS_FIELDS: dict[str, tuple[str, ...]] = {
    "subAccountTransfer": ("subAccountUser",),
}


def now_millis() -> int:
    return time.time_ns() // 1_000_000


def _next_nonce() -> int:
    """Return a process-local, monotonically increasing millisecond nonce."""

    global _last_auto_nonce
    with _nonce_lock:
        _last_auto_nonce = max(now_millis(), _last_auto_nonce + 1)
        return _last_auto_nonce


def _address_bytes(name: str, value: str) -> bytes:
    validated = address(name, value)
    assert validated is not None
    return bytes.fromhex(validated[2:])


def _canonical_action(action: Mapping[str, Any]) -> dict[str, Any]:
    canonical = cast(dict[str, Any], thaw(action))
    action_type = canonical.get("type")
    if isinstance(action_type, str):
        for field in _ACTION_ADDRESS_FIELDS.get(action_type, ()):
            value = canonical.get(field)
            if isinstance(value, str):
                canonical[field] = _address_bytes(f"action.{field}", value)
    return canonical


def unsigned_transaction(
    action: Mapping[str, Any],
    nonce: int,
    *,
    expires_after: int | None = None,
    vault_address: str | None = None,
    user: str | None = None,
) -> dict[str, Any]:
    validate_action(action)
    transaction: dict[str, Any] = {
        "action": _canonical_action(action),
        "nonce": uint64("nonce", nonce),
    }
    if expires_after is not None:
        transaction["expiresAfter"] = uint64("expires_after", expires_after)
    if vault_address is not None:
        transaction["vaultAddress"] = _address_bytes("vault_address", vault_address)
    if user is not None:
        transaction["user"] = _address_bytes("user", user)
    return transaction


def serialize_unsigned_transaction(
    action: Mapping[str, Any],
    nonce: int,
    *,
    expires_after: int | None = None,
    vault_address: str | None = None,
    user: str | None = None,
) -> bytes:
    try:
        return bytes(
            msgpack.packb(
                unsigned_transaction(
                    action,
                    nonce,
                    expires_after=expires_after,
                    vault_address=vault_address,
                    user=user,
                ),
                use_bin_type=True,
            )
        )
    except (OverflowError, TypeError, ValueError) as exc:
        raise SigningError("action could not be encoded as canonical MessagePack") from exc


def connection_id(
    action: Mapping[str, Any],
    nonce: int,
    *,
    expires_after: int | None = None,
    vault_address: str | None = None,
    user: str | None = None,
) -> bytes:
    return keccak(
        serialize_unsigned_transaction(
            action,
            nonce,
            expires_after=expires_after,
            vault_address=vault_address,
            user=user,
        )
    )


def domain_separator(chain_id: int = DOMAIN_CHAIN_ID) -> bytes:
    uint64("chain_id", chain_id)
    type_hash = keccak(
        text="EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    )
    return keccak(
        encode(
            ["bytes32", "bytes32", "bytes32", "uint256", "address"],
            [
                type_hash,
                keccak(text=DOMAIN_NAME),
                keccak(text=DOMAIN_VERSION),
                chain_id,
                ZERO_ADDRESS,
            ],
        )
    )


def signing_hash(
    action: Mapping[str, Any],
    nonce: int,
    *,
    expires_after: int | None = None,
    vault_address: str | None = None,
    user: str | None = None,
    chain: Chain = Chain.MAINNET,
) -> bytes:
    if not isinstance(chain, Chain):
        raise SigningError("chain must be a Chain")
    conn_id = connection_id(
        action,
        nonce,
        expires_after=expires_after,
        vault_address=vault_address,
        user=user,
    )
    type_hash = keccak(text="Agent(string source,bytes32 connectionId)")
    struct_hash = keccak(
        encode(["bytes32", "bytes32", "bytes32"], [type_hash, keccak(text=chain.value), conn_id])
    )
    return keccak(b"\x19\x01" + domain_separator() + struct_hash)


def sign_action(
    action: Mapping[str, Any],
    private_key: str | bytes,
    *,
    nonce: int | None = None,
    expires_after: int | None = None,
    vault_address: str | None = None,
    user: str | None = None,
    chain: Chain = Chain.MAINNET,
) -> SignedTransaction:
    """Sign an action locally without retaining or rendering the private key."""

    actual_nonce = _next_nonce() if nonce is None else uint64("nonce", nonce)
    address("vault_address", vault_address)
    try:
        raw_key = (
            bytes.fromhex(private_key.removeprefix("0x"))
            if isinstance(private_key, str)
            else bytes(private_key)
        )
        if len(raw_key) != 32:
            raise ValueError
        key = keys.PrivateKey(raw_key)
    except (ValueError, TypeError) as exc:
        raise SigningError("private key must be a valid 32-byte secp256k1 scalar") from exc
    digest = signing_hash(
        action,
        actual_nonce,
        expires_after=expires_after,
        vault_address=vault_address,
        user=user,
        chain=chain,
    )
    signature = key.sign_msg_hash(digest)
    return SignedTransaction(
        action=copy.deepcopy(dict(action)),
        nonce=actual_nonce,
        expires_after=expires_after,
        vault_address=vault_address,
        user=user,
        signature=Signature(r=f"0x{signature.r:064x}", s=f"0x{signature.s:064x}", v=signature.v),
        tx_hash=f"0x{digest.hex()}",
    )


def sign_transaction(
    action: Mapping[str, Any],
    private_key: str | bytes,
    *,
    nonce: int | None = None,
    expires_after: int | None = None,
    vault_address: str | None = None,
    user: str | None = None,
    chain: Chain = Chain.MAINNET,
) -> SignedTransaction:
    """Compatibility alias for :func:`sign_action`."""

    return sign_action(
        action,
        private_key,
        nonce=nonce,
        expires_after=expires_after,
        vault_address=vault_address,
        user=user,
        chain=chain,
    )


def recover_address(transaction: SignedTransaction, *, chain: Chain = Chain.MAINNET) -> str:
    digest = signing_hash(
        transaction.action,
        transaction.nonce,
        expires_after=transaction.expires_after,
        vault_address=transaction.vault_address,
        user=transaction.user,
        chain=chain,
    )
    try:
        signature = keys.Signature(
            vrs=(
                transaction.signature.v,
                int(transaction.signature.r, 16),
                int(transaction.signature.s, 16),
            )
        )
        return signature.recover_public_key_from_msg_hash(digest).to_checksum_address().lower()
    except Exception as exc:
        raise SigningError("signature recovery failed") from exc
