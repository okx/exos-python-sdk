"""Functional package boundaries keep established imports stable."""

import importlib.util

import exchangeos_sdk.api as api
import exchangeos_sdk.websocket as websocket
from exchangeos_sdk.api import AccountAPI, BaseAPI, MarketAPI, TradeAPI
from exchangeos_sdk.api.account import AccountAPI as AccountModuleAPI
from exchangeos_sdk.api.base import BaseAPI as BaseModuleAPI
from exchangeos_sdk.api.market import MarketAPI as MarketModuleAPI
from exchangeos_sdk.api.trade import TradeAPI as TradeModuleAPI
from exchangeos_sdk.signing import Action, OrderSource, generate_client_order_id, sign_transaction
from exchangeos_sdk.signing.actions.action import Action as ActionModule
from exchangeos_sdk.signing.client_order_id import (
    generate_client_order_id as generate_client_order_id_module,
)
from exchangeos_sdk.signing.protocol import sign_transaction as sign_transaction_module
from exchangeos_sdk.websocket import ExchangeOSWebSocket
from exchangeos_sdk.websocket.transport import ExchangeOSWebSocket as WebSocketTransport


def test_rest_api_reexports_are_stable() -> None:
    assert MarketAPI is MarketModuleAPI
    assert TradeAPI is TradeModuleAPI
    assert AccountAPI is AccountModuleAPI
    assert BaseAPI is BaseModuleAPI
    assert importlib.util.find_spec("exchangeos_sdk.resources") is None


def test_outcomes_rest_api_is_not_packaged_or_exported() -> None:
    assert not hasattr(api, "OutcomesAPI")
    assert importlib.util.find_spec("exchangeos_sdk.api.outcomes") is None


def test_signing_reexports_are_stable() -> None:
    assert Action is ActionModule
    assert generate_client_order_id is generate_client_order_id_module
    assert sign_transaction is sign_transaction_module
    assert generate_client_order_id(source=OrderSource.API).startswith("0x03")


def test_websocket_reexports_are_stable() -> None:
    assert ExchangeOSWebSocket is WebSocketTransport
    assert not hasattr(websocket, "RawWebSocketMessage")
