import json
import sys
import time
import os
from typing import Optional

import typer

from bot.client import API_KEY, API_SECRET, BinanceClientError
from bot.orders import (
    build_order_payload,
    cancel_order as cancel_order_api,
    place_limit_order,
    place_market_order,
    query_order as query_order_api,
)
from bot.validators import (
    validate_order_type,
    validate_order_id,
    validate_price,
    validate_quantity,
    validate_side,
    validate_symbol,
)

# Force UTF-8 output on Windows so emoji/box chars render correctly
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

app = typer.Typer(help="TradeMind AI -- Binance Futures Trading Copilot")

SEP = "=" * 52
SEP2 = "-" * 52


# -----------------------------------------------
# Helpers
# -----------------------------------------------

def _has_api_credentials() -> bool:
    return bool(API_KEY and API_SECRET)


def _print_order_result(response: dict) -> None:
    typer.echo("\nOrder result:")
    typer.echo(f"  orderId    : {response.get('orderId', 'N/A')}")
    typer.echo(f"  status     : {response.get('status', 'N/A')}")
    typer.echo(f"  executedQty: {response.get('executedQty', 'N/A')}")
    typer.echo(f"  avgPrice   : {response.get('avgPrice', 'N/A')}")
    typer.echo(f"  symbol     : {response.get('symbol', 'N/A')}")


def _risk_label(score: int) -> str:
    if score <= 30:
        return "Low"
    if score <= 60:
        return "Medium"
    return "High"


def _trend_from_report(report) -> str:
    ts = report.technical.trend_strength
    if ts > 0.5:
        return "Bullish"
    if ts < -0.5:
        return "Bearish"
    return "Neutral"


def _recommendation(report) -> str:
    pred = report.prediction.direction
    sentiment = report.sentiment.label
    if pred == "UP" and sentiment in ("Bullish", "Neutral"):
        return "BUY"
    if pred == "DOWN" and sentiment in ("Bearish", "Neutral"):
        return "SELL"
    if report.risk.max_daily_loss_blocked:
        return "HOLD (daily loss limit reached)"
    return "HOLD"


# -----------------------------------------------
# FEATURE 1: AI Market Report
# -----------------------------------------------

@app.command("market-report")
def market_report(
    symbol: str = typer.Argument("BTCUSDT", help="Trading symbol, e.g. BTCUSDT"),
    interval: str = typer.Option("15m", help="Candle interval"),
) -> None:
    """Generate a full AI market analysis report for a symbol."""
    from bot.ai_engine import build_copilot_report

    typer.echo(f"\n{SEP}")
    typer.secho("   TradeMind AI Market Report", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"{SEP}\n")
    typer.echo(f"  Analyzing {symbol.upper()} on {interval} candles -- please wait...")

    try:
        report = build_copilot_report(symbol.upper(), interval=interval)
    except BinanceClientError as exc:
        typer.secho(f"\n  [ERROR] {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    trend = _trend_from_report(report)
    risk_label = _risk_label(report.risk.portfolio_risk_score)
    rec = _recommendation(report)
    rec_color = (
        typer.colors.GREEN if rec == "BUY"
        else typer.colors.RED if rec == "SELL"
        else typer.colors.YELLOW
    )

    typer.echo(f"\n{SEP}")
    typer.echo(f"  Symbol          : {report.symbol}")
    typer.echo(f"  Current Price   : ${report.current_price:,.4f}  ({report.change_24h_pct:+.2f}% 24h)")
    typer.echo(f"  Trend           : {trend}")
    typer.echo(f"  Risk Level      : {risk_label}  ({report.risk.portfolio_risk_score}/100)")
    typer.echo(f"  Confidence Score: {report.prediction.confidence_pct}%")
    typer.echo(f"  Market Sentiment: {report.sentiment.label}  "
               f"(Bullish {report.sentiment.bullish_pct}% | "
               f"Neutral {report.sentiment.neutral_pct}% | "
               f"Bearish {report.sentiment.bearish_pct}%)")
    typer.echo(f"  Market Regime   : {report.market_regime}")
    typer.echo(f"  Strategy        : {report.strategy.replace('_', ' ').title()}")
    typer.echo(f"{SEP}\n")

    typer.secho("  [Reasoning]", bold=True)
    tech = report.technical
    typer.echo(f"  - MACD Analysis  : MACD={tech.macd:.4f}  Signal={tech.macd_signal:.4f}  "
               f"Histogram={tech.macd_histogram:.4f}")
    rsi_state = "Oversold" if tech.rsi < 30 else "Overbought" if tech.rsi > 70 else "Neutral"
    typer.echo(f"  - RSI Analysis   : RSI={tech.rsi:.1f}  ({rsi_state})")
    typer.echo(f"  - Volume Analysis: Volume change {tech.volume_change_pct:+.1f}%")
    typer.echo(f"  - Trend Analysis : Trend strength {tech.trend_strength:+.2f}%  |  ATR {tech.atr_pct:.2f}%")
    typer.echo(f"\n  [Details]")
    for line in report.explanation:
        typer.echo(f"    -> {line}")

    typer.echo(f"\n{SEP}")
    typer.secho(f"  Final Recommendation: ", nl=False, bold=True)
    typer.secho(f" {rec} ", fg=rec_color, bold=True)
    typer.echo(f"{SEP}\n")


# -----------------------------------------------
# FEATURE 3: Sentiment Analysis
# -----------------------------------------------

@app.command("sentiment")
def sentiment_cmd(
    symbol: str = typer.Argument("BTCUSDT", help="Trading symbol"),
    interval: str = typer.Option("15m", help="Candle interval"),
) -> None:
    """Show AI sentiment breakdown: bullish / neutral / bearish scores."""
    from bot.ai_engine import build_copilot_report

    typer.echo(f"\n{SEP}")
    typer.secho("   TradeMind AI -- Sentiment Analysis", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"{SEP}\n")

    try:
        report = build_copilot_report(symbol.upper(), interval=interval)
    except BinanceClientError as exc:
        typer.secho(f"  [ERROR] {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    sent = report.sentiment

    def _bar(pct: int) -> str:
        filled = int(pct / 4)
        return "[" + "#" * filled + "-" * (25 - filled) + "]"

    typer.echo(f"  Symbol            : {symbol.upper()}")
    typer.echo(f"  News Sentiment    : {sent.label}")
    typer.echo(f"  Social Sentiment  : {sent.label}")
    typer.echo(f"  Confidence        : {sent.confidence_pct}%\n")

    typer.secho(f"  Bullish  {sent.bullish_pct:>3}%  ", nl=False)
    typer.secho(_bar(sent.bullish_pct), fg=typer.colors.GREEN)

    typer.secho(f"  Neutral  {sent.neutral_pct:>3}%  ", nl=False)
    typer.secho(_bar(sent.neutral_pct), fg=typer.colors.YELLOW)

    typer.secho(f"  Bearish  {sent.bearish_pct:>3}%  ", nl=False)
    typer.secho(_bar(sent.bearish_pct), fg=typer.colors.RED)

    overall_color = (
        typer.colors.GREEN if sent.label == "Bullish"
        else typer.colors.RED if sent.label == "Bearish"
        else typer.colors.YELLOW
    )
    typer.echo(f"\n  Overall Sentiment : ", nl=False)
    typer.secho(sent.label, fg=overall_color, bold=True)

    typer.secho("\n  [Evidence]", bold=True)
    for ev in sent.evidence:
        typer.echo(f"    * {ev}")
    typer.echo(f"\n{SEP}\n")


# -----------------------------------------------
# FEATURE 4: Risk Intelligence
# -----------------------------------------------

@app.command("risk")
def risk_cmd(
    symbol: str = typer.Argument("BTCUSDT", help="Trading symbol"),
    balance: float = typer.Option(1000.0, help="Account balance in USDT"),
    interval: str = typer.Option("15m", help="Candle interval"),
) -> None:
    """Show AI risk intelligence: score, position size, volatility, exposure."""
    from bot.ai_engine import build_copilot_report

    typer.echo(f"\n{SEP}")
    typer.secho("   TradeMind AI -- Risk Intelligence", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"{SEP}\n")

    try:
        report = build_copilot_report(symbol.upper(), interval=interval, account_balance_usdt=balance)
    except BinanceClientError as exc:
        typer.secho(f"  [ERROR] {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    risk = report.risk
    tech = report.technical
    risk_label = _risk_label(risk.portfolio_risk_score)
    risk_color = (
        typer.colors.GREEN if risk.portfolio_risk_score <= 30
        else typer.colors.YELLOW if risk.portfolio_risk_score <= 60
        else typer.colors.RED
    )
    guard_status = "BLOCKED" if risk.max_daily_loss_blocked else "ACTIVE"

    typer.echo(f"  Symbol            : {symbol.upper()}")
    typer.echo(f"  Account Balance   : ${balance:,.2f} USDT\n")

    typer.secho(f"  Risk Level        : ", nl=False, bold=True)
    typer.secho(risk_label, fg=risk_color, bold=True)
    typer.echo(f"  Portfolio Risk    : {risk.portfolio_risk_score}/100")

    typer.echo(f"\n  Market Volatility : {tech.volatility_pct:.2f}%")
    typer.echo(f"  ATR (14)          : {tech.atr_pct:.2f}%")
    typer.echo(f"  Regime            : {report.market_regime}")

    typer.secho(f"\n  Suggested Position:", bold=True)
    base = symbol.upper().replace("USDT", "")
    typer.echo(f"    {risk.position_size_qty:.6f} {base}  (~${risk.position_size_usdt:.2f} USDT)")
    typer.echo(f"\n  Stop-loss         : {risk.stop_loss_pct:.2f}%")
    typer.echo(f"  Take-profit       : {risk.take_profit_pct:.2f}%")
    typer.echo(f"  Daily Loss Cap    : ${risk.daily_loss_limit_usdt:.2f} USDT  [{guard_status}]")
    typer.echo(f"\n  Reason            : {risk.reason}")
    typer.echo(f"\n{SEP}\n")


# -----------------------------------------------
# FEATURE 2 + 5: Explainable AI / AI Assistant
# -----------------------------------------------

@app.command("ask")
def ask(
    question: str = typer.Argument("", help="Your question for the AI Trading Assistant"),
    symbol: str = typer.Option("BTCUSDT", help="Symbol context"),
    interval: str = typer.Option("15m", help="Candle interval"),
) -> None:
    """Ask the AI Trading Assistant anything about the market, trades, or risk."""
    from bot.ai_engine import build_copilot_report, assistant_reply

    if not question:
        question = typer.prompt("What would you like to ask the AI Copilot?")

    typer.echo(f"\n{SEP}")
    typer.secho("   TradeMind AI Trading Assistant", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"{SEP}\n")
    typer.echo(f"  Q: {question}\n")
    typer.echo("  [Thinking...]\n")

    try:
        report = build_copilot_report(symbol.upper(), interval=interval)
    except BinanceClientError as exc:
        typer.secho(f"  [ERROR] {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    answer = assistant_reply(question, report)
    typer.secho(f"  A: {answer}", fg=typer.colors.BRIGHT_WHITE)

    # Show explainable trade card if trade-related question
    q_lower = question.lower()
    if any(t in q_lower for t in ("buy", "sell", "trade", "enter", "why")):
        rec = _recommendation(report)
        risk_label = _risk_label(report.risk.portfolio_risk_score)
        typer.echo(f"\n{SEP2}")
        typer.secho("  Trade Explanation Card", bold=True)
        typer.echo(f"{SEP2}")
        typer.echo(f"  Action     : {rec} {symbol.upper()}")
        typer.secho("  Reasons:", bold=True)
        tech = report.technical
        reasons = []
        if tech.rsi < 35:
            reasons.append("[+] RSI Oversold")
        elif tech.rsi > 65:
            reasons.append("[+] RSI Overbought")
        if tech.macd_histogram > 0:
            reasons.append("[+] MACD Bullish Crossover")
        elif tech.macd_histogram < 0:
            reasons.append("[+] MACD Bearish Momentum")
        if report.sentiment.label == "Bullish":
            reasons.append("[+] Positive Market Sentiment")
        elif report.sentiment.label == "Bearish":
            reasons.append("[+] Negative Market Sentiment")
        if tech.volume_change_pct > 10:
            reasons.append("[+] Increasing Volume")
        for r in (reasons or ["[~] Mixed signals -- use caution"]):
            typer.secho(f"    {r}", fg=typer.colors.GREEN)
        typer.echo(f"  Confidence : {report.prediction.confidence_pct}%")
        typer.echo(f"  Risk Level : {risk_label}")
    typer.echo(f"\n{SEP}\n")


@app.command("explain")
def explain(
    symbol: str = typer.Argument("BTCUSDT", help="Trading symbol"),
    side: str = typer.Option("BUY", help="BUY or SELL"),
    interval: str = typer.Option("15m", help="Candle interval"),
) -> None:
    """Show explainable AI trade explanation for a given symbol and direction."""
    from bot.ai_engine import build_copilot_report

    typer.echo(f"\n{SEP}")
    typer.secho("   TradeMind AI -- Trade Explanation", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"{SEP}\n")

    try:
        report = build_copilot_report(symbol.upper(), interval=interval)
    except BinanceClientError as exc:
        typer.secho(f"  [ERROR] {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    tech = report.technical
    sent = report.sentiment
    risk = report.risk
    risk_label = _risk_label(risk.portfolio_risk_score)

    reasons = []
    if side.upper() == "BUY":
        if tech.rsi < 35:
            reasons.append("[+] RSI Oversold")
        if tech.macd_histogram > 0:
            reasons.append("[+] MACD Bullish Crossover")
        if sent.label == "Bullish":
            reasons.append("[+] Positive Market Sentiment")
    else:
        if tech.rsi > 65:
            reasons.append("[+] RSI Overbought")
        if tech.macd_histogram < 0:
            reasons.append("[+] MACD Bearish Signal")
        if sent.label == "Bearish":
            reasons.append("[+] Negative Market Sentiment")
    if tech.volume_change_pct > 10:
        reasons.append("[+] Increasing Volume")

    typer.secho(f"  Action     : {side.upper()} {symbol.upper()}", bold=True)
    typer.secho("  Reasons:", bold=True)
    for r in (reasons or ["[~] Mixed signals -- use caution"]):
        typer.secho(f"    {r}", fg=typer.colors.GREEN)
    typer.echo(f"\n  Confidence : {report.prediction.confidence_pct}%")
    typer.echo(f"  Risk Level : {risk_label}")
    typer.echo(f"\n  [Detailed reasoning]")
    for line in report.explanation:
        typer.echo(f"    -> {line}")
    typer.echo(f"\n{SEP}\n")


# -----------------------------------------------
# FEATURE 6: Hackathon Dashboard
# -----------------------------------------------

@app.command("dashboard")
def dashboard_cmd(
    symbol: str = typer.Argument("BTCUSDT", help="Trading symbol"),
    interval: str = typer.Option("15m", help="Candle interval"),
    no_browser: bool = typer.Option(False, help="Skip opening browser"),
) -> None:
    """Generate and open the AI Hackathon Dashboard in your browser."""
    from bot.ai_engine import build_copilot_report
    from bot.dashboard import render_dashboard

    typer.echo(f"\n  Generating TradeMind AI Dashboard for {symbol.upper()}...")

    try:
        report = build_copilot_report(symbol.upper(), interval=interval)
    except BinanceClientError as exc:
        typer.secho(f"  [ERROR] {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    path = render_dashboard(report, open_browser=not no_browser)
    typer.secho(f"  [OK] Dashboard written to: {path}", fg=typer.colors.GREEN)
    if not no_browser:
        typer.secho("  [OK] Opening in browser...", fg=typer.colors.GREEN)


# -----------------------------------------------
# FEATURE 7: Hackathon Demo Mode
# -----------------------------------------------

@app.command("demo")
def demo(
    symbol: str = typer.Argument("BTCUSDT", help="Trading symbol"),
    interval: str = typer.Option("15m", help="Candle interval"),
    live: bool = typer.Option(False, help="Auto-refresh every 30 seconds"),
) -> None:
    """Hackathon demo screen -- live AI analysis for judging."""
    from bot.ai_engine import build_copilot_report

    def _run_once(sym: str, iv: str) -> None:
        try:
            report = build_copilot_report(sym.upper(), interval=iv)
        except BinanceClientError as exc:
            typer.secho(f"  [ERROR] {exc}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        trend = _trend_from_report(report)
        rec = _recommendation(report)
        risk_label = _risk_label(report.risk.portfolio_risk_score)

        rec_color = (
            typer.colors.GREEN if rec == "BUY"
            else typer.colors.RED if rec.startswith("SELL")
            else typer.colors.YELLOW
        )
        trend_color = (
            typer.colors.GREEN if trend == "Bullish"
            else typer.colors.RED if trend == "Bearish"
            else typer.colors.YELLOW
        )
        sent_color = (
            typer.colors.GREEN if report.sentiment.label == "Bullish"
            else typer.colors.RED if report.sentiment.label == "Bearish"
            else typer.colors.YELLOW
        )
        risk_color = (
            typer.colors.GREEN if risk_label == "Low"
            else typer.colors.YELLOW if risk_label == "Medium"
            else typer.colors.RED
        )

        typer.echo(f"\n{SEP}")
        typer.secho("   T R A D E M I N D   A I   C O P I L O T", fg=typer.colors.CYAN, bold=True)
        typer.echo(f"{SEP}\n")

        typer.echo(f"   Symbol          :  {sym.upper()}")
        typer.echo(f"   Price           :  ${report.current_price:,.4f}  ({report.change_24h_pct:+.2f}%)")

        typer.secho(f"\n   Current Trend   :  ", nl=False)
        typer.secho(trend, fg=trend_color, bold=True)

        typer.secho(f"   Confidence      :  ", nl=False)
        typer.secho(f"{report.prediction.confidence_pct}%", bold=True)

        typer.secho(f"   Risk            :  ", nl=False)
        typer.secho(risk_label, fg=risk_color, bold=True)

        typer.secho(f"   Sentiment       :  ", nl=False)
        typer.secho(report.sentiment.label, fg=sent_color, bold=True)
        typer.echo(
            f"     Bullish {report.sentiment.bullish_pct}%  "
            f"Neutral {report.sentiment.neutral_pct}%  "
            f"Bearish {report.sentiment.bearish_pct}%"
        )

        typer.secho(f"\n   Recommendation  :  ", nl=False)
        typer.secho(rec, fg=rec_color, bold=True)

        typer.secho("\n   Reason:", bold=True)
        tech = report.technical
        demo_reasons = []
        if report.sentiment.label == "Bullish":
            demo_reasons.append("- Positive sentiment")
        if tech.macd_histogram > 0:
            demo_reasons.append("- Bullish MACD")
        if tech.volume_change_pct > 5:
            demo_reasons.append("- Strong volume")
        if report.risk.portfolio_risk_score < 60:
            demo_reasons.append("- Healthy risk profile")
        if tech.rsi < 35:
            demo_reasons.append("- RSI oversold (buy signal)")
        if tech.trend_strength > 0:
            demo_reasons.append("- Positive trend momentum")
        for r in (demo_reasons or ["- Mixed market conditions"]):
            typer.echo(f"     {r}")

        base = sym.upper().replace("USDT", "")
        typer.echo(f"\n   Market Regime   :  {report.market_regime.title()}")
        typer.echo(f"   Strategy        :  {report.strategy.replace('_', ' ').title()}")
        typer.echo(
            f"   Position Size   :  {report.risk.position_size_qty:.6f} {base}"
            f"  (~${report.risk.position_size_usdt:.2f})"
        )
        typer.echo(f"\n{SEP}\n")

    _run_once(symbol, interval)

    if live:
        typer.secho(
            "  [LIVE] Refreshing every 30s -- press Ctrl+C to stop.\n",
            fg=typer.colors.YELLOW,
        )
        try:
            while True:
                time.sleep(30)
                _run_once(symbol, interval)
        except KeyboardInterrupt:
            typer.secho("\n  Live mode stopped.", fg=typer.colors.YELLOW)


# -----------------------------------------------
# Existing Commands (preserved)
# -----------------------------------------------

@app.command()
def place_order(
    symbol: str = typer.Option(..., help="Trading symbol, e.g. BTCUSDT"),
    side: str = typer.Option(..., help="Order side: BUY or SELL"),
    order_type: str = typer.Option(..., help="Order type: MARKET or LIMIT"),
    quantity: float = typer.Option(..., help="Order quantity"),
    price: Optional[float] = typer.Option(None, help="Limit price (required for LIMIT orders)"),
    dry_run: bool = typer.Option(False, help="Show order payload without sending"),
) -> None:
    """Place a BUY or SELL order on Binance Futures Testnet."""
    try:
        symbol_valid = validate_symbol(symbol)
        side_valid = validate_side(side)
        order_type_valid = validate_order_type(order_type)
        quantity_valid = validate_quantity(quantity)
        price_valid = validate_price(price, order_type_valid)
    except ValueError as exc:
        typer.secho(f"Input error: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    payload = build_order_payload(symbol_valid, side_valid, order_type_valid, quantity_valid, price_valid)
    has_api_credentials = _has_api_credentials()

    typer.echo("Order request summary:")
    typer.echo(f"  symbol  : {payload['symbol']}")
    typer.echo(f"  side    : {payload['side']}")
    typer.echo(f"  type    : {payload['type']}")
    typer.echo(f"  quantity: {payload['quantity']}")
    if payload["type"] == "LIMIT":
        typer.echo(f"  price   : {payload['price']}")

    if dry_run or not has_api_credentials:
        if not has_api_credentials:
            typer.secho("API credentials not found. Running in dry-run mode.", fg=typer.colors.YELLOW)
        typer.echo("Dry run payload:")
        typer.echo(json.dumps(payload, indent=2))
        raise typer.Exit(code=0)

    try:
        if order_type_valid == "MARKET":
            response = place_market_order(symbol_valid, side_valid, quantity_valid)
        else:
            response = place_limit_order(symbol_valid, side_valid, quantity_valid, price_valid)
        typer.secho("Order submitted successfully.", fg=typer.colors.GREEN)
        _print_order_result(response)
    except BinanceClientError as exc:
        typer.secho(f"API error: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def query_order(
    symbol: str = typer.Option(..., help="Trading symbol, e.g. BTCUSDT"),
    order_id: int = typer.Option(..., help="Order ID to query"),
) -> None:
    """Query the status of an order."""
    try:
        symbol_valid = validate_symbol(symbol)
        order_id_valid = validate_order_id(order_id)
    except ValueError as exc:
        typer.secho(f"Input error: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    try:
        response = query_order_api(symbol_valid, order_id_valid)
        typer.secho("Order query successful.", fg=typer.colors.GREEN)
        _print_order_result(response)
        typer.echo(f"  type   : {response.get('type', 'N/A')}")
        typer.echo(f"  side   : {response.get('side', 'N/A')}")
        typer.echo(f"  origQty: {response.get('origQty', 'N/A')}")
        typer.echo(f"  price  : {response.get('price', 'N/A')}")
    except BinanceClientError as exc:
        typer.secho(f"API error: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def cancel_order(
    symbol: str = typer.Option(..., help="Trading symbol, e.g. BTCUSDT"),
    order_id: int = typer.Option(..., help="Order ID to cancel"),
) -> None:
    """Cancel an open order."""
    try:
        symbol_valid = validate_symbol(symbol)
        order_id_valid = validate_order_id(order_id)
    except ValueError as exc:
        typer.secho(f"Input error: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    try:
        response = cancel_order_api(symbol_valid, order_id_valid)
        typer.secho("Order canceled successfully.", fg=typer.colors.GREEN)
        _print_order_result(response)
        typer.echo(f"  type   : {response.get('type', 'N/A')}")
        typer.echo(f"  side   : {response.get('side', 'N/A')}")
        typer.echo(f"  origQty: {response.get('origQty', 'N/A')}")
        typer.echo(f"  price  : {response.get('price', 'N/A')}")
    except BinanceClientError as exc:
        typer.secho(f"API error: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def interactive_order() -> None:
    """Run an interactive order prompt."""
    typer.secho("Interactive Binance Futures Testnet order", fg=typer.colors.CYAN)
    symbol = typer.prompt("Symbol", default="BTCUSDT")
    side = typer.prompt("Side (BUY/SELL)", default="BUY")
    order_type = typer.prompt("Order type (MARKET/LIMIT)", default="MARKET")
    quantity_text = typer.prompt("Quantity", default="0.001")

    try:
        symbol_valid = validate_symbol(symbol)
        side_valid = validate_side(side)
        order_type_valid = validate_order_type(order_type)
        quantity_valid = validate_quantity(float(quantity_text))
    except ValueError as exc:
        typer.secho(f"Input error: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    price_valid = None
    if order_type_valid == "LIMIT":
        price_text = typer.prompt("Limit price", default="68000")
        try:
            price_valid = validate_price(float(price_text), order_type_valid)
        except ValueError as exc:
            typer.secho(f"Input error: {exc}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    dry_run = typer.confirm("Dry run only?", default=True)
    payload = build_order_payload(symbol_valid, side_valid, order_type_valid, quantity_valid, price_valid)
    has_api_credentials = _has_api_credentials()

    typer.echo("Order request summary:")
    typer.echo(f"  symbol  : {payload['symbol']}")
    typer.echo(f"  side    : {payload['side']}")
    typer.echo(f"  type    : {payload['type']}")
    typer.echo(f"  quantity: {payload['quantity']}")
    if payload["type"] == "LIMIT":
        typer.echo(f"  price   : {payload['price']}")

    if dry_run or not has_api_credentials:
        if not has_api_credentials:
            typer.secho("API credentials not found. Running in dry-run mode.", fg=typer.colors.YELLOW)
        typer.echo("Dry run payload:")
        typer.echo(json.dumps(payload, indent=2))
        raise typer.Exit(code=0)

    try:
        if order_type_valid == "MARKET":
            response = place_market_order(symbol_valid, side_valid, quantity_valid)
        else:
            response = place_limit_order(symbol_valid, side_valid, quantity_valid, price_valid)
        typer.secho("Order submitted successfully.", fg=typer.colors.GREEN)
        _print_order_result(response)
    except BinanceClientError as exc:
        typer.secho(f"API error: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
