import json
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional

from .ai_engine import CopilotReport
from .store import load_trade_records


DEFAULT_DASHBOARD_PATH = Path(__file__).resolve().parent.parent / "trading_copilot_dashboard.html"


def _html_template() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TradeMind AI Copilot &mdash; Hackathon Dashboard</title>
  <meta name="description" content="AI-powered Binance Trading Copilot with explainable AI, sentiment analysis, risk intelligence and live market signals." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet" />
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {
      --bg: #030712;
      --bg2: #0a0f1e;
      --panel: rgba(10, 15, 40, 0.72);
      --panel-border: rgba(99, 179, 237, 0.14);
      --text: #e8f4fd;
      --muted: #7a9bbf;
      --accent: #38bdf8;
      --accent2: #818cf8;
      --accent3: #34d399;
      --warn: #fbbf24;
      --danger: #f87171;
      --good: #34d399;
      --glow-blue: rgba(56,189,248,0.22);
      --glow-purple: rgba(129,140,248,0.18);
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html { scroll-behavior: smooth; }
    body {
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      overflow-x: hidden;
      background-image:
        radial-gradient(ellipse 80% 50% at 10% -10%, rgba(56,189,248,0.12) 0%, transparent 60%),
        radial-gradient(ellipse 60% 40% at 90% 5%, rgba(129,140,248,0.10) 0%, transparent 50%),
        radial-gradient(ellipse 50% 60% at 50% 100%, rgba(52,211,153,0.06) 0%, transparent 60%);
    }

    /* ── Grid ── */
    .wrap { max-width: 1500px; margin: 0 auto; padding: 24px 28px 48px; }

    /* ── Header ── */
    .header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 18px 28px; margin-bottom: 28px;
      background: var(--panel);
      border: 1px solid var(--panel-border);
      border-radius: 20px;
      backdrop-filter: blur(24px);
      box-shadow: 0 0 60px rgba(56,189,248,0.06);
    }
    .logo { display: flex; align-items: center; gap: 14px; }
    .logo-dot {
      width: 38px; height: 38px; border-radius: 12px;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      display: grid; place-items: center; font-size: 18px;
      box-shadow: 0 0 20px var(--glow-blue);
      animation: pulse-logo 3s ease-in-out infinite;
    }
    @keyframes pulse-logo {
      0%,100% { box-shadow: 0 0 20px var(--glow-blue); }
      50%      { box-shadow: 0 0 36px rgba(56,189,248,0.5); }
    }
    .logo-text h1 { font-size: 22px; font-weight: 800; letter-spacing: -0.5px; }
    .logo-text h1 span { color: var(--accent); }
    .logo-text p  { font-size: 12px; color: var(--muted); margin-top: 2px; letter-spacing: 0.06em; }
    .header-right { display: flex; align-items: center; gap: 14px; }
    .live-badge {
      display: flex; align-items: center; gap: 7px;
      padding: 7px 14px; border-radius: 999px;
      background: rgba(52,211,153,0.1); border: 1px solid rgba(52,211,153,0.3);
      font-size: 12px; font-weight: 600; color: var(--good);
    }
    .live-dot {
      width: 7px; height: 7px; border-radius: 50%; background: var(--good);
      animation: blink 1.4s ease-in-out infinite;
    }
    @keyframes blink { 0%,100%{opacity:1;} 50%{opacity:0.2;} }
    .ts { font-size: 12px; color: var(--muted); font-family: 'JetBrains Mono', monospace; }

    /* ── Cards / Panels ── */
    .card, .panel {
      background: var(--panel);
      border: 1px solid var(--panel-border);
      border-radius: 20px;
      backdrop-filter: blur(20px);
    }
    .card { padding: 22px 24px; }
    .panel { padding: 22px 24px; }
    .card:hover, .panel:hover {
      border-color: rgba(99,179,237,0.28);
      box-shadow: 0 0 40px rgba(56,189,248,0.06);
      transition: border-color .3s, box-shadow .3s;
    }
    .section-label {
      font-size: 11px; font-weight: 700; letter-spacing: 0.14em;
      text-transform: uppercase; color: var(--accent); margin-bottom: 6px;
    }
    .panel-title {
      font-size: 16px; font-weight: 700; margin-bottom: 16px;
      display: flex; align-items: center; gap: 10px;
    }
    .panel-title .icon {
      width: 30px; height: 30px; border-radius: 9px;
      display: grid; place-items: center; font-size: 15px;
    }

    /* ── Hero Metrics Row ── */
    .hero-grid {
      display: grid;
      grid-template-columns: 2.4fr repeat(3, 1fr);
      gap: 16px;
      margin-bottom: 16px;
    }
    .price-card { grid-column: 1; }
    .price-card .eyebrow { font-size: 12px; color: var(--muted); letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 8px; }
    .price-card .price   { font-size: clamp(32px, 4vw, 52px); font-weight: 900; letter-spacing: -2px; font-family: 'JetBrains Mono', monospace; }
    .price-card .symbol  { color: var(--accent); }
    .price-card .change  { font-size: 16px; font-weight: 600; margin-top: 6px; }
    .change.up   { color: var(--good); }
    .change.down { color: var(--danger); }
    .change.flat { color: var(--muted); }

    .metric-card { display: flex; flex-direction: column; justify-content: space-between; }
    .metric-card .m-label { font-size: 11px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }
    .metric-card .m-val   { font-size: 30px; font-weight: 800; letter-spacing: -1px; line-height: 1; }
    .metric-card .m-sub   { font-size: 12px; color: var(--muted); margin-top: 8px; }
    .clr-green  { color: var(--good); }
    .clr-yellow { color: var(--warn); }
    .clr-red    { color: var(--danger); }
    .clr-blue   { color: var(--accent); }
    .clr-purple { color: var(--accent2); }
    .clr-white  { color: var(--text); }

    /* ── Recommendation Banner ── */
    .rec-banner {
      padding: 16px 24px;
      border-radius: 16px;
      margin-bottom: 16px;
      border: 1px solid;
      display: flex; align-items: center; justify-content: space-between;
      animation: fade-in 0.6s ease;
    }
    .rec-banner.buy    { background: rgba(52,211,153,0.08); border-color: rgba(52,211,153,0.35); }
    .rec-banner.sell   { background: rgba(248,113,113,0.08); border-color: rgba(248,113,113,0.35); }
    .rec-banner.hold   { background: rgba(251,191,36,0.07);  border-color: rgba(251,191,36,0.30); }
    .rec-banner .rec-label { font-size: 13px; color: var(--muted); }
    .rec-banner .rec-val   { font-size: 28px; font-weight: 900; letter-spacing: -0.5px; }
    .rec-banner .rec-conf  { font-size: 13px; color: var(--muted); text-align: right; }
    .rec-banner .rec-conf b { font-size: 22px; display: block; font-weight: 800; }

    /* ── Main Grid ── */
    .main-grid {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 16px;
      margin-bottom: 16px;
    }
    .left-col  { display: flex; flex-direction: column; gap: 16px; }
    .right-col { display: flex; flex-direction: column; gap: 16px; }

    /* ── Charts ── */
    .chart-wrap { position: relative; height: 240px; }
    .chart-wrap canvas { border-radius: 12px; }

    /* ── Sentiment Bar ── */
    .sent-row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
    .sent-row .sent-lbl { width: 64px; font-size: 13px; font-weight: 600; }
    .sent-row .sent-pct { width: 38px; font-size: 13px; font-family: 'JetBrains Mono', monospace; text-align: right; }
    .bar-track { flex: 1; height: 9px; border-radius: 999px; background: rgba(148,163,184,0.12); overflow: hidden; }
    .bar-fill   { height: 100%; border-radius: 999px; transition: width 1.2s cubic-bezier(.22,1,.36,1); }
    .bar-fill.bull { background: linear-gradient(90deg, var(--good), #6ee7b7); }
    .bar-fill.neu  { background: linear-gradient(90deg, var(--warn), #fde68a); }
    .bar-fill.bear { background: linear-gradient(90deg, var(--danger), #fca5a5); }

    /* ── Risk Gauge ── */
    .gauge-wrap { position: relative; height: 160px; display: flex; align-items: center; justify-content: center; }
    .gauge-wrap canvas { max-height: 160px; }
    .gauge-center {
      position: absolute; bottom: 12px; left: 50%; transform: translateX(-50%);
      text-align: center; pointer-events: none;
    }
    .gauge-center .g-val { font-size: 26px; font-weight: 800; font-family: 'JetBrains Mono', monospace; }
    .gauge-center .g-lbl { font-size: 11px; color: var(--muted); margin-top: 2px; }

    /* ── Explanation List ── */
    .exp-list { display: flex; flex-direction: column; gap: 10px; }
    .exp-item {
      padding: 12px 14px; border-radius: 13px;
      background: rgba(56,189,248,0.06); border: 1px solid rgba(56,189,248,0.12);
      font-size: 13px; line-height: 1.55; color: var(--text);
      display: flex; gap: 10px; align-items: flex-start;
    }
    .exp-item .exp-icon { font-size: 15px; flex-shrink: 0; margin-top: 1px; }

    /* ── Trade History Table ── */
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th { text-align: left; padding: 10px 12px; color: var(--muted); font-weight: 600; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; border-bottom: 1px solid rgba(148,163,184,0.1); }
    td { padding: 11px 12px; border-bottom: 1px solid rgba(148,163,184,0.07); }
    tr:last-child td { border-bottom: none; }
    .badge { display: inline-block; padding: 3px 9px; border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: 0.04em; }
    .badge.buy  { background: rgba(52,211,153,0.15); color: #6ee7b7; }
    .badge.sell { background: rgba(248,113,113,0.15); color: #fca5a5; }

    /* ── Chips / Tags ── */
    .chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
    .chip {
      padding: 6px 13px; border-radius: 999px; font-size: 12px; font-weight: 600;
      background: rgba(148,163,184,0.1); border: 1px solid rgba(148,163,184,0.15); color: var(--muted);
    }
    .chip.good { background: rgba(52,211,153,0.1); border-color: rgba(52,211,153,0.25); color: #6ee7b7; }
    .chip.warn { background: rgba(251,191,36,0.1);  border-color: rgba(251,191,36,0.25);  color: #fde68a; }
    .chip.bad  { background: rgba(248,113,113,0.1); border-color: rgba(248,113,113,0.25); color: #fca5a5; }
    .chip.info { background: rgba(56,189,248,0.1);  border-color: rgba(56,189,248,0.25);  color: #7dd3fc; }

    /* ── Technical Signals Grid ── */
    .sig-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .sig-item { padding: 14px; border-radius: 14px; background: rgba(148,163,184,0.05); border: 1px solid rgba(148,163,184,0.08); }
    .sig-item .si-label { font-size: 11px; color: var(--muted); font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 6px; }
    .sig-item .si-val   { font-size: 20px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
    .sig-item .si-sub   { font-size: 11px; color: var(--muted); margin-top: 4px; }

    /* ── Bottom Grid ── */
    .bottom-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

    /* ── Animations ── */
    @keyframes fade-in { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:none; } }
    .card, .panel { animation: fade-in .5s ease both; }

    /* ── Responsive ── */
    @media (max-width: 1100px) {
      .hero-grid { grid-template-columns: 1fr 1fr; }
      .price-card { grid-column: 1 / -1; }
      .main-grid  { grid-template-columns: 1fr; }
      .bottom-grid{ grid-template-columns: 1fr; }
    }
    @media (max-width: 600px) {
      .hero-grid  { grid-template-columns: 1fr 1fr; }
      .sig-grid   { grid-template-columns: 1fr; }
      .wrap { padding: 12px 14px 32px; }
    }
  </style>
</head>
<body>
<div class="wrap">

  <!-- ── Header ── -->
  <div class="header">
    <div class="logo">
      <div class="logo-dot">&#9670;</div>
      <div class="logo-text">
        <h1>TradeMind <span>AI</span></h1>
        <p>Explainable Trading Copilot &bull; Hackathon Edition</p>
      </div>
    </div>
    <div class="header-right">
      <div class="live-badge"><div class="live-dot"></div> LIVE DATA</div>
      <div class="ts">Generated: {{timestamp}}</div>
    </div>
  </div>

  <!-- ── Hero Metrics ── -->
  <div class="hero-grid">
    <div class="card price-card">
      <div class="eyebrow">Current Price &bull; {{symbol}}</div>
      <div class="price"><span class="symbol">{{symbol}}</span> &nbsp;${{price}}</div>
      <div class="change {{change_class}}">{{change}}% &nbsp;(24h)</div>
      <div class="chips">
        <span class="chip {{strategy_class}}">Strategy: {{strategy}}</span>
        <span class="chip {{regime_class}}">Regime: {{regime}}</span>
        <span class="chip info">Stop-loss {{stop_loss}}%</span>
        <span class="chip info">Take-profit {{take_profit}}%</span>
        <span class="chip">Position {{position_size}} USDT</span>
      </div>
    </div>
    <div class="card metric-card">
      <div class="m-label">Confidence Score</div>
      <div class="m-val clr-blue">{{prediction_conf}}%</div>
      <div class="m-sub">Short-term: {{direction}}</div>
    </div>
    <div class="card metric-card">
      <div class="m-label">AI Sentiment</div>
      <div class="m-val {{sent_color}}">{{sentiment}}</div>
      <div class="m-sub">Confidence {{sentiment_conf}}%</div>
    </div>
    <div class="card metric-card">
      <div class="m-label">Risk Score</div>
      <div class="m-val {{risk_color}}">{{risk_score}}<span style="font-size:14px;font-weight:400;color:var(--muted)">/100</span></div>
      <div class="m-sub">Daily guard: {{daily_guard}}</div>
    </div>
  </div>

  <!-- ── Recommendation Banner ── -->
  <div class="rec-banner {{rec_class}}">
    <div>
      <div class="rec-label">AI Recommendation</div>
      <div class="rec-val {{rec_color}}">{{recommendation}}</div>
    </div>
    <div style="flex:1; padding: 0 32px;">
      <div style="font-size:13px;color:var(--muted);margin-bottom:6px;">Why this recommendation?</div>
      <div style="font-size:13px;line-height:1.6;">{{rec_reason}}</div>
    </div>
    <div class="rec-conf">
      <div>Prediction Confidence</div>
      <b class="clr-blue">{{prediction_conf}}%</b>
    </div>
  </div>

  <!-- ── Main Grid ── -->
  <div class="main-grid">
    <div class="left-col">

      <!-- Price Chart -->
      <div class="panel">
        <div class="panel-title">
          <div class="icon" style="background:rgba(56,189,248,0.12);">&#128200;</div>
          Price Trend &mdash; {{symbol}}
        </div>
        <div class="chart-wrap"><canvas id="priceChart"></canvas></div>
      </div>

      <!-- Technical Signals -->
      <div class="panel">
        <div class="panel-title">
          <div class="icon" style="background:rgba(129,140,248,0.12);">&#9889;</div>
          Technical Signals
        </div>
        <div class="sig-grid">
          <div class="sig-item">
            <div class="si-label">RSI (14)</div>
            <div class="si-val {{rsi_color}}">{{rsi}}</div>
            <div class="si-sub">{{rsi_state}}</div>
          </div>
          <div class="sig-item">
            <div class="si-label">MACD Histogram</div>
            <div class="si-val {{macd_color}}">{{macd_hist}}</div>
            <div class="si-sub">{{macd_state}}</div>
          </div>
          <div class="sig-item">
            <div class="si-label">Volume Change</div>
            <div class="si-val {{vol_color}}">{{vol_change}}%</div>
            <div class="si-sub">vs prior 3 candles</div>
          </div>
          <div class="sig-item">
            <div class="si-label">Trend Strength</div>
            <div class="si-val {{trend_color}}">{{trend_strength}}%</div>
            <div class="si-sub">15-candle momentum</div>
          </div>
          <div class="sig-item">
            <div class="si-label">ATR (14)</div>
            <div class="si-val clr-white">{{atr}}%</div>
            <div class="si-sub">Volatility measure</div>
          </div>
          <div class="sig-item">
            <div class="si-label">Volatility</div>
            <div class="si-val clr-white">{{volatility}}%</div>
            <div class="si-sub">20-candle std dev</div>
          </div>
        </div>
      </div>

      <!-- Trade History -->
      <div class="panel">
        <div class="panel-title">
          <div class="icon" style="background:rgba(52,211,153,0.12);">&#128203;</div>
          Trade History
        </div>
        {{history_table}}
      </div>

    </div>
    <div class="right-col">

      <!-- Risk Gauge -->
      <div class="panel">
        <div class="panel-title">
          <div class="icon" style="background:rgba(248,113,113,0.12);">&#128737;</div>
          Risk Intelligence
        </div>
        <div class="gauge-wrap">
          <canvas id="riskGauge"></canvas>
          <div class="gauge-center">
            <div class="g-val {{risk_color}}">{{risk_score}}</div>
            <div class="g-lbl">Risk Score</div>
          </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:8px;">
          <div class="sig-item"><div class="si-label">Risk Level</div><div class="si-val {{risk_color}}">{{risk_level}}</div></div>
          <div class="sig-item"><div class="si-label">Position</div><div class="si-val clr-white" style="font-size:14px;">{{position_qty}} {{base}}</div></div>
        </div>
      </div>

      <!-- Sentiment Breakdown -->
      <div class="panel">
        <div class="panel-title">
          <div class="icon" style="background:rgba(251,191,36,0.12);">&#127757;</div>
          AI Sentiment Breakdown
        </div>
        <div class="sent-row">
          <div class="sent-lbl clr-green">Bullish</div>
          <div class="sent-pct">{{bullish}}%</div>
          <div class="bar-track"><div class="bar-fill bull" style="width:{{bullish}}%"></div></div>
        </div>
        <div class="sent-row">
          <div class="sent-lbl clr-yellow">Neutral</div>
          <div class="sent-pct">{{neutral}}%</div>
          <div class="bar-track"><div class="bar-fill neu" style="width:{{neutral}}%"></div></div>
        </div>
        <div class="sent-row">
          <div class="sent-lbl clr-red">Bearish</div>
          <div class="sent-pct">{{bearish}}%</div>
          <div class="bar-track"><div class="bar-fill bear" style="width:{{bearish}}%"></div></div>
        </div>
        <div style="margin-top:14px;padding:12px;border-radius:12px;background:rgba(148,163,184,0.06);font-size:12px;color:var(--muted);line-height:1.6;">
          {{sentiment_evidence}}
        </div>
      </div>

      <!-- Prediction Mix -->
      <div class="panel">
        <div class="panel-title">
          <div class="icon" style="background:rgba(56,189,248,0.12);">&#127919;</div>
          AI Prediction Mix
        </div>
        <div class="chart-wrap" style="height:180px;">
          <canvas id="predictionChart"></canvas>
        </div>
      </div>

    </div>
  </div>

  <!-- ── Bottom Grid ── -->
  <div class="bottom-grid">
    <!-- Trade Explanation -->
    <div class="panel">
      <div class="panel-title">
        <div class="icon" style="background:rgba(52,211,153,0.12);">&#129504;</div>
        Explainable AI &mdash; Trade Reasoning
      </div>
      <div class="exp-list">
        {{explanation_items}}
      </div>
    </div>

    <!-- Probability Bars -->
    <div class="panel">
      <div class="panel-title">
        <div class="icon" style="background:rgba(129,140,248,0.12);">&#128202;</div>
        Direction Probabilities
      </div>
      <div style="display:flex;flex-direction:column;gap:18px;margin-top:4px;">
        <div>
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;font-size:13px;">
            <span class="clr-green" style="font-weight:600;">UP</span>
            <span class="clr-green" style="font-family:'JetBrains Mono',monospace;font-weight:700;">{{prob_up}}%</span>
          </div>
          <div class="bar-track" style="height:13px;border-radius:8px;">
            <div class="bar-fill bull" style="width:{{prob_up}}%;height:100%;"></div>
          </div>
        </div>
        <div>
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;font-size:13px;">
            <span class="clr-yellow" style="font-weight:600;">SIDEWAYS</span>
            <span class="clr-yellow" style="font-family:'JetBrains Mono',monospace;font-weight:700;">{{prob_sideways}}%</span>
          </div>
          <div class="bar-track" style="height:13px;border-radius:8px;">
            <div class="bar-fill neu" style="width:{{prob_sideways}}%;height:100%;"></div>
          </div>
        </div>
        <div>
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;font-size:13px;">
            <span class="clr-red" style="font-weight:600;">DOWN</span>
            <span class="clr-red" style="font-family:'JetBrains Mono',monospace;font-weight:700;">{{prob_down}}%</span>
          </div>
          <div class="bar-track" style="height:13px;border-radius:8px;">
            <div class="bar-fill bear" style="width:{{prob_down}}%;height:100%;"></div>
          </div>
        </div>
        <div style="margin-top:8px;padding:16px;border-radius:14px;background:rgba(56,189,248,0.06);border:1px solid rgba(56,189,248,0.12);">
          <div style="font-size:11px;color:var(--muted);font-weight:700;letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px;">Summary</div>
          <div style="font-size:13px;line-height:1.6;">{{summary}}</div>
        </div>
      </div>
    </div>
  </div>

</div><!-- /wrap -->

<script>
  const priceData      = {{price_data}};
  const predData       = {{prediction_data}};
  const riskScore      = {{risk_score_raw}};

  /* ── Price Line Chart ── */
  new Chart(document.getElementById('priceChart'), {
    type: 'line',
    data: {
      labels: priceData.labels,
      datasets: [{
        label: '{{symbol}} Price',
        data: priceData.values,
        borderColor: '#38bdf8',
        backgroundColor: (ctx) => {
          const g = ctx.chart.ctx.createLinearGradient(0,0,0,220);
          g.addColorStop(0,'rgba(56,189,248,0.22)');
          g.addColorStop(1,'rgba(56,189,248,0.01)');
          return g;
        },
        tension: 0.38, fill: true, pointRadius: 0,
        borderWidth: 2.5,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 1000 },
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#5a7a9f', font:{size:10} }, grid: { color: 'rgba(148,163,184,0.06)' } },
        y: { ticks: { color: '#5a7a9f', font:{size:10} }, grid: { color: 'rgba(148,163,184,0.06)' } }
      }
    }
  });

  /* ── Prediction Doughnut ── */
  new Chart(document.getElementById('predictionChart'), {
    type: 'doughnut',
    data: {
      labels: ['Up', 'Sideways', 'Down'],
      datasets: [{
        data: [predData.up, predData.sideways, predData.down],
        backgroundColor: ['rgba(52,211,153,0.85)','rgba(251,191,36,0.75)','rgba(248,113,113,0.85)'],
        borderWidth: 0, hoverOffset: 8,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '68%',
      plugins: { legend: { position: 'bottom', labels: { color:'#7a9bbf', padding:14, font:{size:12} } } }
    }
  });

  /* ── Risk Gauge (custom arc) ── */
  const riskCanvas = document.getElementById('riskGauge');
  const riskCtx    = riskCanvas.getContext('2d');
  riskCanvas.width  = 220;
  riskCanvas.height = 140;

  function drawGauge(score) {
    riskCtx.clearRect(0,0,220,140);
    const cx=110, cy=130, r=88, lw=18;
    const startA = Math.PI, endA = 2*Math.PI;
    const norm = Math.max(0,Math.min(1, score/100));

    // Track
    riskCtx.beginPath();
    riskCtx.arc(cx,cy,r,startA,endA);
    riskCtx.strokeStyle='rgba(148,163,184,0.1)';
    riskCtx.lineWidth=lw; riskCtx.lineCap='round';
    riskCtx.stroke();

    // Fill gradient
    const fillEnd = startA + norm*Math.PI;
    const grd = riskCtx.createLinearGradient(cx-r,cy,cx+r,cy);
    grd.addColorStop(0,'#34d399');
    grd.addColorStop(0.45,'#fbbf24');
    grd.addColorStop(1,'#f87171');
    riskCtx.beginPath();
    riskCtx.arc(cx,cy,r,startA,fillEnd);
    riskCtx.strokeStyle=grd;
    riskCtx.lineWidth=lw; riskCtx.lineCap='round';
    riskCtx.stroke();
  }
  // Animate gauge fill
  let current=0;
  const step=() => { if(current<riskScore){current+=2;drawGauge(current);requestAnimationFrame(step);} else drawGauge(riskScore); };
  step();
</script>
</body>
</html>
"""


def _risk_label(score: int) -> str:
    if score <= 30:
        return "Low"
    if score <= 60:
        return "Medium"
    return "High"


def _trend_from_report(report: CopilotReport) -> str:
    ts = report.technical.trend_strength
    if ts > 0.5:
        return "Bullish"
    if ts < -0.5:
        return "Bearish"
    return "Neutral"


def _recommendation(report: CopilotReport) -> str:
    pred = report.prediction.direction
    sentiment = report.sentiment.label
    if pred == "UP" and sentiment in ("Bullish", "Neutral"):
        return "BUY"
    if pred == "DOWN" and sentiment in ("Bearish", "Neutral"):
        return "SELL"
    if report.risk.max_daily_loss_blocked:
        return "HOLD"
    return "HOLD"


def _format_explanation_items(explanations: List[str]) -> str:
    if not explanations:
        return '<div class="exp-item"><span class="exp-icon">&#8212;</span>No explanation available.</div>'
    icons = ["&#9654;", "&#9654;", "&#9654;", "&#9654;", "&#9654;", "&#9654;"]
    return "".join(
        f'<div class="exp-item"><span class="exp-icon">{icons[i % len(icons)]}</span>{item}</div>'
        for i, item in enumerate(explanations)
    )


def _format_history_table(records: List[Dict[str, object]]) -> str:
    if not records:
        return '<div style="color:var(--muted);font-size:13px;padding:12px 0;">No trade history recorded yet.</div>'
    rows = []
    for record in reversed(records[-8:]):
        side = str(record.get("side", record.get("decision", "N/A"))).upper()
        badge_class = "buy" if side == "BUY" else "sell"
        rows.append(
            f'<tr>'
            f'<td><strong>{record.get("symbol", "N/A")}</strong></td>'
            f'<td><span class="badge {badge_class}">{side}</span></td>'
            f'<td style="font-family:\'JetBrains Mono\',monospace;">'
            f'{record.get("quantity", record.get("position_size_qty", "N/A"))}</td>'
            f'<td style="color:var(--muted);font-size:12px;">{str(record.get("timestamp", ""))[:19]}</td>'
            f'</tr>'
        )
    return (
        '<table><thead><tr>'
        '<th>Symbol</th><th>Side</th><th>Qty</th><th>Time</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>'
    )


def report_to_price_points(report: CopilotReport) -> Dict[str, List[float]]:
    """Return real Binance close prices for the chart, falling back to a simulated curve."""
    if report.price_history and len(report.price_history) >= 5:
        # Use real candle close prices fetched from Binance
        return {"labels": report.price_labels, "values": report.price_history}
    # Fallback (should not normally be reached)
    base = report.current_price
    labels = [str(i + 1) for i in range(50)]
    values = [round(base * (1 + (i - 25) * 0.0018), 2) for i in range(50)]
    return {"labels": labels, "values": values}


def render_dashboard(
    report: CopilotReport,
    output_path: Optional[str] = None,
    recent_records: Optional[List[Dict[str, object]]] = None,
    open_browser: bool = False,
) -> Path:
    from datetime import datetime, timezone

    records = recent_records if recent_records is not None else load_trade_records(limit=50)
    html = _html_template()

    # ── Derived values ──
    tech = report.technical
    sent = report.sentiment
    risk = report.risk
    pred = report.prediction
    rec  = _recommendation(report)
    risk_label = _risk_label(risk.portfolio_risk_score)
    trend = _trend_from_report(report)

    rsi_state = "Oversold" if tech.rsi < 30 else "Overbought" if tech.rsi > 70 else "Neutral"
    macd_state = "Bullish momentum" if tech.macd_histogram > 0 else "Bearish momentum"
    change_class = "up" if report.change_24h_pct > 0 else "down" if report.change_24h_pct < 0 else "flat"

    rec_class = "buy" if rec == "BUY" else "sell" if rec == "SELL" else "hold"
    rec_color = "clr-green" if rec == "BUY" else "clr-red" if rec == "SELL" else "clr-yellow"
    sent_color = "clr-green" if sent.label == "Bullish" else "clr-red" if sent.label == "Bearish" else "clr-yellow"
    risk_color = "clr-green" if risk.portfolio_risk_score <= 30 else "clr-yellow" if risk.portfolio_risk_score <= 60 else "clr-red"
    rsi_color  = "clr-red" if tech.rsi < 30 else "clr-red" if tech.rsi > 70 else "clr-white"
    macd_color = "clr-green" if tech.macd_histogram > 0 else "clr-red"
    vol_color  = "clr-green" if tech.volume_change_pct > 0 else "clr-red"
    trend_color = "clr-green" if tech.trend_strength > 0 else "clr-red"

    strategy_class = "good" if report.strategy == "trend_following" else "warn" if report.strategy == "defensive" else ""
    regime_class = "good" if report.market_regime == "trending" else "warn" if report.market_regime == "high volatility" else ""

    rec_reason = "; ".join(report.explanation[:3]) if report.explanation else report.summary
    base_currency = report.symbol.replace("USDT", "")
    ts_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── Apply substitutions ──
    subs = {
        "{{symbol}}":           report.symbol,
        "{{price}}":            f"{report.current_price:,.4f}",
        "{{change}}":           f"{report.change_24h_pct:+.2f}",
        "{{change_class}}":     change_class,
        "{{timestamp}}":        ts_str,
        "{{sentiment}}":        sent.label,
        "{{sentiment_conf}}":   str(sent.confidence_pct),
        "{{sent_color}}":       sent_color,
        "{{risk_score}}":       str(risk.portfolio_risk_score),
        "{{risk_score_raw}}":   str(risk.portfolio_risk_score),
        "{{risk_color}}":       risk_color,
        "{{risk_level}}":       risk_label,
        "{{daily_guard}}":      "BLOCKED" if risk.max_daily_loss_blocked else "ACTIVE",
        "{{direction}}":        pred.direction,
        "{{prediction_conf}}":  str(pred.confidence_pct),
        "{{strategy}}":         report.strategy.replace("_", " ").title(),
        "{{strategy_class}}":   strategy_class,
        "{{regime}}":           report.market_regime.title(),
        "{{regime_class}}":     regime_class,
        "{{stop_loss}}":        f"{risk.stop_loss_pct:.2f}",
        "{{take_profit}}":      f"{risk.take_profit_pct:.2f}",
        "{{position_size}}":    f"{risk.position_size_usdt:.2f}",
        "{{position_qty}}":     f"{risk.position_size_qty:.6f}",
        "{{base}}":             base_currency,
        "{{recommendation}}":   rec,
        "{{rec_class}}":        rec_class,
        "{{rec_color}}":        rec_color,
        "{{rec_reason}}":       rec_reason,
        "{{rsi}}":              f"{tech.rsi:.1f}",
        "{{rsi_state}}":        rsi_state,
        "{{rsi_color}}":        rsi_color,
        "{{macd_hist}}":        f"{tech.macd_histogram:+.4f}",
        "{{macd_state}}":       macd_state,
        "{{macd_color}}":       macd_color,
        "{{vol_change}}":       f"{tech.volume_change_pct:+.1f}",
        "{{vol_color}}":        vol_color,
        "{{trend_strength}}":   f"{tech.trend_strength:+.2f}",
        "{{trend_color}}":      trend_color,
        "{{atr}}":              f"{tech.atr_pct:.2f}",
        "{{volatility}}":       f"{tech.volatility_pct:.2f}",
        "{{bullish}}":          str(sent.bullish_pct),
        "{{neutral}}":          str(sent.neutral_pct),
        "{{bearish}}":          str(sent.bearish_pct),
        "{{sentiment_evidence}}": " &bull; ".join(sent.evidence[:4]),
        "{{prob_up}}":          str(pred.probabilities.get("up", 0)),
        "{{prob_down}}":        str(pred.probabilities.get("down", 0)),
        "{{prob_sideways}}":    str(pred.probabilities.get("sideways", 0)),
        "{{summary}}":          report.summary,
        "{{explanation_items}}":_format_explanation_items(report.explanation[:6]),
        "{{history_table}}":    _format_history_table(records),
        "{{price_data}}":       json.dumps(report_to_price_points(report)),
        "{{prediction_data}}":  json.dumps(pred.probabilities),
    }

    for placeholder, value in subs.items():
        html = html.replace(placeholder, str(value))

    path = Path(output_path) if output_path else DEFAULT_DASHBOARD_PATH
    path.write_text(html, encoding="utf-8")

    if open_browser:
        webbrowser.open(path.resolve().as_uri())

    return path