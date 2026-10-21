# SKILL: market_analyst
# OpenClaw Market Analysis & Forecasting Skill
# Version: 1.0
# Author: Mathew Eng

## Purpose
Fetches real market data, compresses it into structured context,
feeds it to a local offline LLM, generates daily forecast reports,
and tracks accuracy over time. No trading. No API keys needed.

## Trigger phrases
- "analyze the market"
- "what does the market look like"
- "run market analysis"
- "generate market report"
- "forecast BTC/ETH/SOL"
- "what did the LLM learn today"
- "show forecast accuracy"

## Inputs
- symbols: list of trading pairs (default: BTC-USD, ETH-USD, SOL-USD)
- timeframes: 1h, 4h, 1d
- lookback_candles: 100 (default)

## Outputs
- Daily report: plain English market summary
- Forecast: Bullish/Bearish/Neutral + confidence %
- Accuracy log: yesterday's forecast vs actual outcome
- SQLite database: all forecasts and outcomes stored locally

## Data sources (all public, no auth required)
- Kraken public REST API (primary)
- Coinbase public REST API (fallback)
- CoinGecko public API (secondary fallback)

## LLM
- Provider: Ollama (local, offline)
- Auto-detect GPU: RTX 3090 → qwen2.5:14b | RTX 3060 → qwen2.5:7b
- Fallback: any model found in Ollama
- Internet: NOT required after model download

## Files
- skill/market_data.py     — fetches + compresses OHLCV
- skill/llm_analyst.py     — LLM interface + prompt builder
- skill/accuracy.py        — tracks forecast vs reality
- skill/database.py        — SQLite storage
- dashboard/app.py         — Flask status page
- run.py                   — main entry point
- install.sh / install.bat — one-click setup
