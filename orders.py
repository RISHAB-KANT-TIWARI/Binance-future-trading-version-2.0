from typing import Any, Dict, Optional

from .client import cancel_order as cancel_order_api, create_order, query_order as query_order_api


def place_market_order(symbol: str, side: str, quantity: float) -> Dict[str, Any]:
    return create_order(symbol=symbol, side=side, order_type="MARKET", quantity=quantity)


def place_limit_order(symbol: str, side: str, quantity: float, price: float) -> Dict[str, Any]:
    return create_order(symbol=symbol, side=side, order_type="LIMIT", quantity=quantity, price=price)


def query_order(symbol: str, order_id: int) -> Dict[str, Any]:
    return query_order_api(symbol=symbol, order_id=order_id)


def cancel_order(symbol: str, order_id: int) -> Dict[str, Any]:
    return cancel_order_api(symbol=symbol, order_id=order_id)


def build_order_payload(symbol: str, side: str, order_type: str, quantity: float, price: Optional[float] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "symbol": symbol,
        "side": side.upper(),
        "type": order_type.upper(),
        "quantity": quantity,
    }

    if payload["type"] == "LIMIT":
        payload["price"] = price
        payload["timeInForce"] = "GTC"

    return payload
