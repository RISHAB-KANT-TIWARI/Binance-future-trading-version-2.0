from dataclasses import dataclass
from typing import List

from .client import get_24h_ticker, get_klines, get_ticker_price


@dataclass
class Candle:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int


@dataclass
class MarketSnapshot:
    symbol: str
    interval: str
    current_price: float
    change_24h_pct: float
    volume_24h: float
    candles: List[Candle]


def _as_float(value: object) -> float:
    return float(value)


def _parse_candles(raw_candles: List[list]) -> List[Candle]:
    candles: List[Candle] = []
    for candle in raw_candles:
        candles.append(
            Candle(
                open_time=int(candle[0]),
                open=_as_float(candle[1]),
                high=_as_float(candle[2]),
                low=_as_float(candle[3]),
                close=_as_float(candle[4]),
                volume=_as_float(candle[5]),
                close_time=int(candle[6]),
            )
        )
    return candles


def fetch_market_snapshot(symbol: str, interval: str = "15m", limit: int = 120) -> MarketSnapshot:
    ticker = get_ticker_price(symbol)
    ticker_24h = get_24h_ticker(symbol)
    raw_candles = get_klines(symbol, interval=interval, limit=limit)

    return MarketSnapshot(
        symbol=symbol,
        interval=interval,
        current_price=_as_float(ticker["price"]),
        change_24h_pct=_as_float(ticker_24h.get("priceChangePercent", 0.0)),
        volume_24h=_as_float(ticker_24h.get("volume", 0.0)),
        candles=_parse_candles(raw_candles),
    )