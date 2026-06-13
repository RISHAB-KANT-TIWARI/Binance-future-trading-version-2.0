from typing import Optional


VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT"}


def validate_symbol(symbol: str) -> str:
    if not symbol or not symbol.strip():
        raise ValueError("symbol is required")
    return symbol.strip().upper()


def validate_side(side: str) -> str:
    if not side or side.upper() not in VALID_SIDES:
        raise ValueError("side must be BUY or SELL")
    return side.upper()


def validate_order_type(order_type: str) -> str:
    if not order_type or order_type.upper() not in VALID_ORDER_TYPES:
        raise ValueError("order type must be MARKET or LIMIT")
    return order_type.upper()


def validate_quantity(quantity: float) -> float:
    if quantity is None:
        raise ValueError("quantity is required")
    if quantity <= 0:
        raise ValueError("quantity must be greater than zero")
    return quantity


def validate_price(price: Optional[float], order_type: str) -> Optional[float]:
    if order_type == "LIMIT":
        if price is None:
            raise ValueError("price is required for LIMIT orders")
        if price <= 0:
            raise ValueError("price must be greater than zero")
        return price
    return price


def validate_order_id(order_id: int) -> int:
    if order_id is None:
        raise ValueError("order ID is required")
    try:
        order_id_int = int(order_id)
    except (TypeError, ValueError):
        raise ValueError("order ID must be a number")
    if order_id_int <= 0:
        raise ValueError("order ID must be a positive integer")
    return order_id_int
