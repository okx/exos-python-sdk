import base64
import hashlib
import hmac

import pytest

from exos_python_sdk.auth import Credentials, auth_headers, sign_request
from exos_python_sdk.exceptions import ConfigurationError


def test_request_signature_matches_protocol_formula() -> None:
    secret = "runtime-test-secret"
    timestamp = "2026-08-21T00:00:00.000Z"
    expected = base64.b64encode(
        hmac.new(
            secret.encode(),
            f"{timestamp}GET/api/v5/exchangeos/account/balance".encode(),
            hashlib.sha256,
        ).digest()
    ).decode()
    assert sign_request(secret, timestamp, "GET", "/api/v5/exchangeos/account/balance") == expected


def test_credentials_repr_redacts_every_value() -> None:
    credentials = Credentials("visible-id", "runtime-test-secret", "runtime-test-passphrase")
    rendered = repr(credentials)
    assert "visible-id" not in rendered
    assert "runtime-test-secret" not in rendered
    assert "runtime-test-passphrase" not in rendered


def test_auth_headers_use_prepared_path_and_body() -> None:
    credentials = Credentials("id", "runtime-test-secret", "passphrase")
    headers = auth_headers(
        credentials,
        "POST",
        "/api/v5/exchangeos/trade/place-order?x=1",
        '{"x":1}',
        timestamp="2026-08-21T00:00:00.000Z",
    )
    assert headers["OK-ACCESS-SIGN"] == sign_request(
        "runtime-test-secret",
        "2026-08-21T00:00:00.000Z",
        "POST",
        "/api/v5/exchangeos/trade/place-order?x=1",
        '{"x":1}',
    )


@pytest.mark.parametrize(
    "values", [("", "secret", "pass"), ("id", "", "pass"), ("id", "secret", "")]
)
def test_credentials_reject_incomplete_configuration(values) -> None:
    with pytest.raises(ConfigurationError):
        Credentials(*values)
