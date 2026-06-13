import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Optional, Sequence

from .market_data import Candle, MarketSnapshot, fetch_market_snapshot
from .store import load_trade_records, today_realized_pnl_usdt


POSITIVE_WORDS = {
    "bullish",
    "breakout",
    "buy",
    "surge",
    "upside",
    "positive",
    "growth",
    "adoption",
    "accumulation",
    "momentum",
    "rally",
    "strong",
    "support",
}
NEGATIVE_WORDS = {
    "bearish",
    "selloff",
    "dump",
    "downside",
    "negative",
    "risk",
    "fear",
    "liquidation",
    "resistance",
    "weak",
    "crash",
    "volatility",
    "panic",
}


@dataclass
class TechnicalSignals:
    rsi: float
    macd: float
    macd_signal: float
    macd_histogram: float
    atr_pct: float
    volatility_pct: float
    volume_change_pct: float
    trend_strength: float
    regime: str


@dataclass
class SentimentInsight:
    label: str
    bullish_pct: int
    neutral_pct: int
    bearish_pct: int
    confidence_pct: int
    score: float
    evidence: List[str]


@dataclass
class RiskPlan:
    stop_loss_pct: float
    take_profit_pct: float
    position_size_usdt: float
    position_size_qty: float
    portfolio_risk_score: int
    daily_loss_limit_usdt: float
    max_daily_loss_blocked: bool
    reason: str


@dataclass
class PredictionResult:
    direction: str
    confidence_pct: int
    probabilities: Dict[str, int]
    horizon: str
    rationale: List[str]


@dataclass
class CopilotReport:
    symbol: str
    interval: str
    current_price: float
    change_24h_pct: float
    technical: TechnicalSignals
    sentiment: SentimentInsight
    risk: RiskPlan
    strategy: str
    explanation: List[str]
    prediction: PredictionResult
    market_regime: str
    timestamp: str
    summary: str
    price_history: List[float] = None   # real close prices from Binance candles
    price_labels: List[str] = None      # candle index labels

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _ema(values: Sequence[float], period: int) -> List[float]:
    if not values:
        return []
    multiplier = 2 / (period + 1)
    ema_values = [values[0]]
    for value in values[1:]:
        ema_values.append((value - ema_values[-1]) * multiplier + ema_values[-1])
    return ema_values


def _rsi(closes: Sequence[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains: List[float] = []
    losses: List[float] = []
    for index in range(1, len(closes)):
        delta = closes[index] - closes[index - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = mean(gains[:period])
    avg_loss = mean(losses[:period])
    if avg_loss == 0:
        return 100.0
    for index in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[index]) / period
        avg_loss = (avg_loss * (period - 1) + losses[index]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _macd(closes: Sequence[float]) -> tuple[float, float, float]:
    if len(closes) < 35:
        return 0.0, 0.0, 0.0
    ema_fast = _ema(closes, 12)
    ema_slow = _ema(closes, 26)
    macd_line = [fast - slow for fast, slow in zip(ema_fast[-len(ema_slow):], ema_slow)]
    signal_line = _ema(macd_line, 9)
    return macd_line[-1], signal_line[-1], macd_line[-1] - signal_line[-1]


def _atr_pct(candles: Sequence[Candle], period: int = 14) -> float:
    if len(candles) < period + 1:
        return 0.0
    true_ranges: List[float] = []
    for index in range(1, len(candles)):
        current = candles[index]
        previous = candles[index - 1]
        true_range = max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )
        true_ranges.append(true_range)
    return (mean(true_ranges[-period:]) / candles[-1].close) * 100 if true_ranges else 0.0


def _volatility_pct(closes: Sequence[float]) -> float:
    if len(closes) < 10:
        return 0.0
    mean_close = mean(closes[-20:])
    variance = mean([(close - mean_close) ** 2 for close in closes[-20:]])
    return _clamp((variance ** 0.5) / mean_close * 100, 0.0, 100.0) if mean_close else 0.0


def _volume_change_pct(candles: Sequence[Candle]) -> float:
    if len(candles) < 6:
        return 0.0
    recent = mean(candle.volume for candle in candles[-3:])
    prior = mean(candle.volume for candle in candles[-6:-3])
    if prior == 0:
        return 0.0
    return ((recent - prior) / prior) * 100


def detect_market_regime(rsi: float, macd_histogram: float, atr_pct: float, volatility_pct: float, trend_strength: float) -> str:
    if atr_pct >= 3.5 or volatility_pct >= 4.0:
        return "high volatility"
    if abs(trend_strength) >= 1.5 and abs(macd_histogram) > 0 and (rsi >= 55 or rsi <= 45):
        return "trending"
    return "sideways"


def analyze_technical_signals(snapshot: MarketSnapshot) -> TechnicalSignals:
    closes = [candle.close for candle in snapshot.candles]
    rsi = _rsi(closes)
    macd, macd_signal, macd_histogram = _macd(closes)
    atr_pct = _atr_pct(snapshot.candles)
    volatility_pct = _volatility_pct(closes)
    volume_change_pct = _volume_change_pct(snapshot.candles)
    trend_strength = ((closes[-1] - closes[-15]) / closes[-15] * 100) if len(closes) > 15 and closes[-15] else 0.0
    regime = detect_market_regime(rsi, macd_histogram, atr_pct, volatility_pct, trend_strength)
    return TechnicalSignals(
        rsi=rsi,
        macd=macd,
        macd_signal=macd_signal,
        macd_histogram=macd_histogram,
        atr_pct=atr_pct,
        volatility_pct=volatility_pct,
        volume_change_pct=volume_change_pct,
        trend_strength=trend_strength,
        regime=regime,
    )


def _score_text(text: str) -> float:
    lowered = text.lower()
    score = 0.0
    for word in POSITIVE_WORDS:
        if word in lowered:
            score += 1.0
    for word in NEGATIVE_WORDS:
        if word in lowered:
            score -= 1.0
    return score


def _collect_sentiment_texts(symbol: str) -> List[str]:
    texts = [text.strip() for text in os.getenv("COPILOT_SENTIMENT_TEXTS", "").split("||") if text.strip()]
    if texts:
        return texts
    return [
        f"{symbol} momentum driven market context with recent price action and volume flow.",
        f"{symbol} traders are watching trend strength, liquidity, and risk appetite.",
    ]


def analyze_sentiment(symbol: str, snapshot: MarketSnapshot, technical: TechnicalSignals) -> SentimentInsight:
    texts = _collect_sentiment_texts(symbol)
    textual_score = sum(_score_text(text) for text in texts)
    momentum_score = 0.0
    if snapshot.change_24h_pct > 0:
        momentum_score += min(snapshot.change_24h_pct / 4, 2.0)
    else:
        momentum_score += max(snapshot.change_24h_pct / 4, -2.0)
    momentum_score += _clamp(technical.volume_change_pct / 50, -1.5, 1.5)
    momentum_score += _clamp(technical.trend_strength / 3, -1.5, 1.5)
    score = textual_score + momentum_score

    bullish = _clamp(50 + score * 15, 0, 100)
    bearish = _clamp(50 - score * 15, 0, 100)
    neutral = _clamp(100 - abs(score) * 20, 0, 100)
    total = bullish + bearish + neutral or 1
    bullish_pct = int(round(bullish / total * 100))
    bearish_pct = int(round(bearish / total * 100))
    neutral_pct = max(0, 100 - bullish_pct - bearish_pct)

    if score >= 1.5:
        label = "Bullish"
    elif score <= -1.5:
        label = "Bearish"
    else:
        label = "Neutral"

    confidence = _clamp(55 + abs(score) * 12 + min(len(texts) * 4, 12), 50, 98)
    evidence = [f"Analyzed {len(texts)} sentiment inputs"]
    if snapshot.change_24h_pct:
        evidence.append(f"24h price change {snapshot.change_24h_pct:+.2f}%")
    if technical.volume_change_pct:
        evidence.append(f"Volume change {technical.volume_change_pct:+.2f}%")
    evidence.extend(texts[:3])

    return SentimentInsight(
        label=label,
        bullish_pct=bullish_pct,
        neutral_pct=neutral_pct,
        bearish_pct=bearish_pct,
        confidence_pct=int(round(confidence)),
        score=round(score, 2),
        evidence=evidence,
    )


def choose_strategy(technical: TechnicalSignals, sentiment: SentimentInsight) -> str:
    if technical.regime == "high volatility":
        return "defensive"
    if technical.regime == "trending":
        return "trend_following"
    if sentiment.label == "Bullish" and technical.rsi < 55:
        return "trend_following"
    return "range_trading"


def build_risk_plan(
    snapshot: MarketSnapshot,
    technical: TechnicalSignals,
    sentiment: SentimentInsight,
    strategy: str,
    account_balance_usdt: Optional[float] = None,
    risk_per_trade_pct: float = 1.0,
    max_daily_loss_pct: float = 3.0,
) -> RiskPlan:
    balance = account_balance_usdt or 1000.0
    stop_loss_pct = max(0.8, technical.atr_pct * 1.4)
    if strategy == "defensive":
        stop_loss_pct *= 0.8
    elif strategy == "trend_following":
        stop_loss_pct *= 1.1

    take_profit_pct = stop_loss_pct * (2.2 if strategy == "trend_following" else 1.5 if strategy == "range_trading" else 1.1)
    risk_budget = balance * (risk_per_trade_pct / 100)
    position_size_usdt = risk_budget / (stop_loss_pct / 100) if stop_loss_pct else 0.0
    position_size_qty = position_size_usdt / snapshot.current_price if snapshot.current_price else 0.0
    portfolio_risk_score = int(_clamp(technical.volatility_pct * 8 + abs(sentiment.score) * 8 + technical.atr_pct * 5, 0, 100))

    records = load_trade_records(limit=250)
    realized_pnl_today = today_realized_pnl_usdt(records)
    daily_loss_limit_usdt = balance * (max_daily_loss_pct / 100)
    max_daily_loss_blocked = realized_pnl_today <= -daily_loss_limit_usdt
    reason = "Daily loss limit reached" if max_daily_loss_blocked else f"Risk budget set from {risk_per_trade_pct:.2f}% per trade"

    return RiskPlan(
        stop_loss_pct=round(stop_loss_pct, 2),
        take_profit_pct=round(take_profit_pct, 2),
        position_size_usdt=round(position_size_usdt, 2),
        position_size_qty=round(position_size_qty, 6),
        portfolio_risk_score=portfolio_risk_score,
        daily_loss_limit_usdt=round(daily_loss_limit_usdt, 2),
        max_daily_loss_blocked=max_daily_loss_blocked,
        reason=reason,
    )


def build_explanation(symbol: str, side: str, technical: TechnicalSignals, sentiment: SentimentInsight, strategy: str, risk: RiskPlan) -> List[str]:
    explanations: List[str] = []
    if side.upper() == "BUY":
        if technical.rsi < 35:
            explanations.append(f"RSI is oversold at {technical.rsi:.1f}, which supports an accumulation setup.")
        elif technical.rsi < 55:
            explanations.append(f"RSI sits at {technical.rsi:.1f}, leaving room for upside continuation.")
        if technical.macd_histogram > 0:
            explanations.append("MACD is above signal, showing bullish momentum.")
        if sentiment.label == "Bullish":
            explanations.append(f"Sentiment is bullish with {sentiment.confidence_pct}% confidence.")
    else:
        if technical.rsi > 65:
            explanations.append(f"RSI is overbought at {technical.rsi:.1f}, which can justify profit-taking.")
        if technical.macd_histogram < 0:
            explanations.append("MACD momentum has weakened, favoring a defensive exit.")
        if sentiment.label == "Bearish":
            explanations.append(f"Sentiment is bearish with {sentiment.confidence_pct}% confidence.")

    if technical.volume_change_pct > 10:
        explanations.append(f"Volume increased by {technical.volume_change_pct:.1f}%, confirming stronger participation.")
    explanations.append(f"Strategy selected: {strategy.replace('_', ' ')} for the current {technical.regime} market.")
    explanations.append(f"Dynamic stop-loss {risk.stop_loss_pct:.2f}% and take-profit {risk.take_profit_pct:.2f}% are aligned to volatility.")
    return explanations


def predict_short_term(snapshot: MarketSnapshot, technical: TechnicalSignals, sentiment: SentimentInsight) -> PredictionResult:
    score = 0.0
    score += _clamp((technical.rsi - 50) / 12, -2.0, 2.0)
    score += _clamp(technical.macd_histogram * 120, -1.8, 1.8)
    score += _clamp(sentiment.score, -2.0, 2.0)
    score += _clamp(technical.trend_strength / 2.5, -1.5, 1.5)
    score += _clamp(technical.volume_change_pct / 60, -1.0, 1.0)

    if score >= 1.0:
        direction = "UP"
    elif score <= -1.0:
        direction = "DOWN"
    else:
        direction = "SIDEWAYS"

    confidence = int(round(_clamp(58 + abs(score) * 12 + sentiment.confidence_pct * 0.15, 50, 97)))
    probabilities = {
        "up": int(round(_clamp(40 + score * 12, 5, 90))),
        "down": int(round(_clamp(40 - score * 12, 5, 90))),
        "sideways": 0,
    }
    probabilities["sideways"] = max(0, 100 - probabilities["up"] - probabilities["down"])
    rationale = [
        f"RSI {technical.rsi:.1f}",
        f"MACD histogram {technical.macd_histogram:.4f}",
        f"Sentiment {sentiment.label} ({sentiment.confidence_pct}%)",
    ]
    return PredictionResult(
        direction=direction,
        confidence_pct=confidence,
        probabilities=probabilities,
        horizon="next 1-4 candles",
        rationale=rationale,
    )


def build_copilot_report(symbol: str, interval: str = "15m", limit: int = 120, account_balance_usdt: Optional[float] = None) -> CopilotReport:
    snapshot = fetch_market_snapshot(symbol=symbol, interval=interval, limit=limit)
    technical = analyze_technical_signals(snapshot)
    sentiment = analyze_sentiment(symbol, snapshot, technical)
    strategy = choose_strategy(technical, sentiment)
    risk = build_risk_plan(snapshot, technical, sentiment, strategy, account_balance_usdt=account_balance_usdt)
    explanation = build_explanation(symbol, "BUY", technical, sentiment, strategy, risk)
    prediction = predict_short_term(snapshot, technical, sentiment)
    summary = f"{symbol} is {sentiment.label.lower()} with {prediction.direction.lower()} bias. Market regime: {technical.regime}. Strategy: {strategy.replace('_', ' ')}."

    # Extract last 60 real candles for the dashboard price chart
    chart_candles = snapshot.candles[-60:]
    price_history = [round(c.close, 4) for c in chart_candles]
    price_labels  = [str(i + 1) for i in range(len(chart_candles))]

    return CopilotReport(
        symbol=symbol,
        interval=interval,
        current_price=snapshot.current_price,
        change_24h_pct=snapshot.change_24h_pct,
        technical=technical,
        sentiment=sentiment,
        risk=risk,
        strategy=strategy,
        explanation=explanation,
        prediction=prediction,
        market_regime=technical.regime,
        timestamp=datetime.now(timezone.utc).isoformat(),
        summary=summary,
        price_history=price_history,
        price_labels=price_labels,
    )


def assistant_reply(question: str, report: CopilotReport) -> str:
    query = question.lower().strip()
    if not query:
        return "Ask about price direction, risk, sentiment, strategy, or why a trade was placed."

    if any(token in query for token in ("why did the bot buy", "why buy", "why enter", "why did you buy")):
        return f"The bot would buy {report.symbol} because {', '.join(report.explanation[:3])}. Current prediction: {report.prediction.direction} with {report.prediction.confidence_pct}% confidence."

    if any(token in query for token in ("analyze", "analysis", "today", "market")):
        return f"{report.symbol} trades at {report.current_price:.4f} with 24h change {report.change_24h_pct:+.2f}%. Sentiment is {report.sentiment.label} ({report.sentiment.confidence_pct}%). Market regime: {report.market_regime}. Strategy: {report.strategy.replace('_', ' ')}."

    if "risk" in query:
        status = "blocked" if report.risk.max_daily_loss_blocked else "active"
        return f"Risk level is {report.risk.portfolio_risk_score}/100. Stop-loss {report.risk.stop_loss_pct:.2f}%, take-profit {report.risk.take_profit_pct:.2f}%, position size {report.risk.position_size_usdt:.2f} USDT ({report.risk.position_size_qty:.6f} {report.symbol}). Daily loss guard is {status}."

    if "sentiment" in query or "news" in query or "social" in query:
        return f"Sentiment is {report.sentiment.label} with {report.sentiment.confidence_pct}% confidence. Bullish {report.sentiment.bullish_pct}%, neutral {report.sentiment.neutral_pct}%, bearish {report.sentiment.bearish_pct}%."

    if "predict" in query or "direction" in query:
        return f"Short-term outlook is {report.prediction.direction} with {report.prediction.confidence_pct}% confidence. Probabilities: up {report.prediction.probabilities['up']}%, down {report.prediction.probabilities['down']}%, sideways {report.prediction.probabilities['sideways']}%."

    if "strategy" in query:
        return f"Current strategy is {report.strategy.replace('_', ' ')} because the market regime is {report.market_regime}."

    return report.summary


def report_to_dict(report: CopilotReport) -> Dict[str, object]:
    return report.to_dict()