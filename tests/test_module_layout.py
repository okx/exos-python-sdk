"""Functional package boundaries keep established imports stable."""

import importlib.util

import exos_python_sdk.api as api
import exos_python_sdk.websocket as websocket
from exos_python_sdk.api import AccountAPI, BaseAPI, MarketAPI, TradeAPI
from exos_python_sdk.api.account import AccountAPI as AccountModuleAPI
from exos_python_sdk.api.base import BaseAPI as BaseModuleAPI
from exos_python_sdk.api.market import MarketAPI as MarketModuleAPI
from exos_python_sdk.api.trade import TradeAPI as TradeModuleAPI
from exos_python_sdk.signing import Action, OrderSource, generate_client_order_id, sign_transaction
from exos_python_sdk.signing.actions.action import Action as ActionModule
from exos_python_sdk.signing.client_order_id import (
    generate_client_order_id as generate_client_order_id_module,
)
from exos_python_sdk.signing.protocol import sign_transaction as sign_transaction_module
from exos_python_sdk.websocket import ExchangeOSWebSocket
from exos_python_sdk.websocket.transport import ExchangeOSWebSocket as WebSocketTransport


def test_rest_api_reexports_are_stable() -> None:
    assert MarketAPI is MarketModuleAPI
    assert TradeAPI is TradeModuleAPI
    assert AccountAPI is AccountModuleAPI
    assert BaseAPI is BaseModuleAPI
    assert importlib.util.find_spec("exos_python_sdk.resources") is None


def test_outcomes_rest_api_is_not_packaged_or_exported() -> None:
    assert not hasattr(api, "OutcomesAPI")
    assert importlib.util.find_spec("exos_python_sdk.api.outcomes") is None


def test_signing_reexports_are_stable() -> None:
    assert Action is ActionModule
    assert generate_client_order_id is generate_client_order_id_module
    assert sign_transaction is sign_transaction_module
    assert generate_client_order_id(source=OrderSource.API).startswith("0x03")


def test_websocket_reexports_are_stable() -> None:
    assert ExchangeOSWebSocket is WebSocketTransport
    assert not hasattr(websocket, "RawWebSocketMessage")
