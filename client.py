import os
import time
import hmac
import hashlib
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

from .logging_config import setup_logger, log_api_request, log_api_response

load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
BASE_URL = os.getenv("BINANCE_FUTURES_BASE_URL", "https://testnet.binancefuture.com")

logger = setup_logger()


class BinanceClientError(Exception):
    pass


def _sign_params(params: Dict[str, Any], secret: str) -> str:
    qs = urlencode(params, doseq=True)
    return hmac.new(secret.encode(), qs.encode(), hashlib.sha256).hexdigest()


def _send_signed_request(method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if API_KEY is None or API_SECRET is None:
        raise BinanceClientError("API key and secret must be set in environment variables")

    params = params or {}
    params.update({"timestamp": int(time.time() * 1000)})
    signature = _sign_params(params, API_SECRET)
    params["signature"] = signature

    url = BASE_URL.rstrip("/") + path
    headers = {"X-MBX-APIKEY": API_KEY}

    # Log the request without sensitive fields
    log_api_request(logger, method, url, params={k: ("<redacted>" if k in ("signature",) else v) for k, v in params.items()})

    try:
        if method.upper() == "GET":
            resp = requests.get(url, params=params, headers=headers, timeout=10)
        elif method.upper() == "DELETE":
            resp = requests.delete(url, params=params, headers=headers, timeout=10)
        else:
            resp = requests.post(url, data=params, headers=headers, timeout=10)
    except requests.RequestException as exc:
        logger.exception("Network error while calling Binance API")
        raise BinanceClientError(f"Network error: {exc}") from exc

    # Log response
    try:
        body = resp.json()
    except ValueError:
        body = resp.text

    log_api_response(logger, resp.status_code, body)

    if not resp.ok:
        raise BinanceClientError(f"API error: status={resp.status_code} body={body}")

    return body


def get_ticker_price(symbol: str) -> Dict[str, Any]:
    """Fetch the latest price for a symbol (public endpoint)."""
    url = BASE_URL.rstrip("/") + "/fapi/v1/ticker/price"
    try:
        resp = requests.get(url, params={"symbol": symbol}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise BinanceClientError(f"Network error fetching ticker price: {exc}") from exc


def get_24h_ticker(symbol: str) -> Dict[str, Any]:
    """Fetch 24-hour ticker statistics (public endpoint)."""
    url = BASE_URL.rstrip("/") + "/fapi/v1/ticker/24hr"
    try:
        resp = requests.get(url, params={"symbol": symbol}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise BinanceClientError(f"Network error fetching 24h ticker: {exc}") from exc


def get_klines(symbol: str, interval: str = "15m", limit: int = 120) -> list:
    """Fetch OHLCV candlestick data (public endpoint)."""
    url = BASE_URL.rstrip("/") + "/fapi/v1/klines"
    try:
        resp = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise BinanceClientError(f"Network error fetching klines: {exc}") from exc


def create_order(symbol: str, side: str, order_type: str, quantity: float, price: Optional[float] = None) -> Dict[str, Any]:
    """Place an order on Binance Futures (USDT-M).

    order_type must be 'MARKET' or 'LIMIT'.
    """
    path = "/fapi/v1/order"

    params: Dict[str, Any] = {
        "symbol": symbol,
        "side": side.upper(),
        "type": order_type.upper(),
        "quantity": quantity,
    }

    if params["type"] == "LIMIT":
        if price is None:
            raise ValueError("price is required for LIMIT orders")
        params.update({"price": price, "timeInForce": "GTC"})

    return _send_signed_request("POST", path, params)


def query_order(symbol: str, order_id: int) -> Dict[str, Any]:
    path = "/fapi/v1/order"
    params = {"symbol": symbol, "orderId": order_id}
    return _send_signed_request("GET", path, params)


def cancel_order(symbol: str, order_id: int) -> Dict[str, Any]:
    path = "/fapi/v1/order"
    params = {"symbol": symbol, "orderId": order_id}
    return _send_signed_request("DELETE", path, params)
