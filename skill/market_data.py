"""
skill/market_data.py
Fetches OHLCV candles from public APIs (no auth needed).
Compresses 100+ candles into structured context the LLM can actually use.
"""

import math
import time
import logging
from typing import List, Dict, Optional, Tuple
import requests

logger = logging.getLogger("market_data")

# ── Public API endpoints (no key needed) ──────────────────────
KRAKEN_OHLCV  = "https://api.kraken.com/0/public/OHLC"
COINBASE_SPOT = "https://api.coinbase.com/v2/prices/{}/spot"
COINGECKO_IDS = {"BTC-USD": "bitcoin", "ETH-USD": "ethereum", "SOL-USD": "solana"}

KRAKEN_PAIRS = {
    "BTC-USD": "XBTUSD",
    "ETH-USD": "ETHUSD",
    "SOL-USD": "SOLUSD",
}
KRAKEN_INTERVALS = {"1h": 60, "4h": 240, "1d": 1440}


def fetch_kraken_ohlcv(symbol: str, timeframe: str = "1h", limit: int = 100) -> List[Dict]:
    pair     = KRAKEN_PAIRS.get(symbol, symbol.replace("-", ""))
    interval = KRAKEN_INTERVALS.get(timeframe, 60)
    try:
        r = requests.get(KRAKEN_OHLCV, params={"pair": pair, "interval": interval},
                         timeout=12)
        data = r.json()
        if data.get("error"):
            logger.warning(f"Kraken error: {data['error']}")
            return []
        result_key = list(data["result"].keys())[0]
        raw = data["result"][result_key]
        candles = []
        for c in raw[-limit:]:
            candles.append({
                "timestamp": int(c[0]),
                "open":   float(c[1]),
                "high":   float(c[2]),
                "low":    float(c[3]),
                "close":  float(c[4]),
                "volume": float(c[6]),
            })
        return candles
    except Exception as e:
        logger.error(f"Kraken fetch failed ({symbol}): {e}")
        return []


def fetch_coingecko_ohlcv(symbol: str, days: int = 7) -> List[Dict]:
    cg_id = COINGECKO_IDS.get(symbol)
    if not cg_id:
        return []
    try:
        r = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{cg_id}/ohlc",
            params={"vs_currency": "usd", "days": str(days)},
            timeout=12
        )
        raw = r.json()
        return [{"timestamp": c[0]//1000, "open": c[1], "high": c[2],
                 "low": c[3], "close": c[4], "volume": 0} for c in raw]
    except Exception as e:
        logger.error(f"CoinGecko fetch failed: {e}")
        return []


def get_current_price(symbol: str) -> Optional[float]:
    try:
        r = requests.get(COINBASE_SPOT.format(symbol), timeout=8)
        return float(r.json()["data"]["amount"])
    except Exception:
        pass
    try:
        cg_id = COINGECKO_IDS.get(symbol)
        if cg_id:
            r = requests.get(
                f"https://api.coingecko.com/api/v3/simple/price",
                params={"ids": cg_id, "vs_currencies": "usd"}, timeout=8
            )
            return float(r.json()[cg_id]["usd"])
    except Exception:
        pass
    return None


def fetch_candles(symbol: str, timeframe: str = "1h", limit: int = 100) -> List[Dict]:
    """Try Kraken first, fall back to CoinGecko."""
    candles = fetch_kraken_ohlcv(symbol, timeframe, limit)
    if not candles:
        logger.info(f"  Falling back to CoinGecko for {symbol}")
        candles = fetch_coingecko_ohlcv(symbol)
    return candles


# ── Technical Indicators (pure Python) ───────────────────────
def _ema(values: List[float], period: int) -> List[Optional[float]]:
    out = [None] * len(values)
    if len(values) < period:
        return out
    k = 2 / (period + 1)
    out[period-1] = sum(values[:period]) / period
    for i in range(period, len(values)):
        out[i] = values[i] * k + out[i-1] * (1 - k)
    return out


def _rsi(closes: List[float], period: int = 14) -> List[Optional[float]]:
    out = [None] * len(closes)
    if len(closes) < period + 1:
        return out
    gains = [max(0, closes[i]-closes[i-1]) for i in range(1, len(closes))]
    losses = [max(0, closes[i-1]-closes[i]) for i in range(1, len(closes))]
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    for i in range(period, len(closes)):
        out[i] = 100 if al == 0 else 100 - 100/(1 + ag/al)
        idx = i - period
        ag = (ag*(period-1) + gains[idx]) / period
        al = (al*(period-1) + losses[idx]) / period
    return out


def _bollinger(closes: List[float], period=20, std_dev=2.0) -> Tuple:
    if len(closes) < period:
        return None, None, None
    w = closes[-period:]
    mid = sum(w) / period
    var = sum((x-mid)**2 for x in w) / period
    std = math.sqrt(var)
    return round(mid + std_dev*std, 2), round(mid, 2), round(mid - std_dev*std, 2)


def _macd(closes: List[float]):
    e12 = _ema(closes, 12)
    e26 = _ema(closes, 26)
    macd_line = [
        (a - b) if (a is not None and b is not None) else None
        for a, b in zip(e12, e26)
    ]
    valid = [(i, v) for i, v in enumerate(macd_line) if v is not None]
    if len(valid) < 9:
        return None, None, None
    vals = [v for _, v in valid]
    sig_vals = _ema(vals, 9)
    sig = sig_vals[-1] if sig_vals[-1] is not None else None
    ml  = macd_line[-1]
    hist = (ml - sig) if (ml and sig) else None
    prev_ml = next((v for v in reversed(macd_line[:-1]) if v is not None), None)
    prev_sig = sig_vals[-2] if len(sig_vals) >= 2 and sig_vals[-2] is not None else None
    cross = None
    if ml and sig and prev_ml and prev_sig:
        if prev_ml <= prev_sig and ml > sig:
            cross = "BULLISH_CROSS"
        elif prev_ml >= prev_sig and ml < sig:
            cross = "BEARISH_CROSS"
    return round(ml, 6) if ml else None, round(sig, 6) if sig else None, cross


def detect_support_resistance(candles: List[Dict], window: int = 5) -> Tuple[float, float]:
    """Simple pivot-based S/R detection."""
    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]
    pivots_high, pivots_low = [], []
    for i in range(window, len(highs) - window):
        if highs[i] == max(highs[i-window:i+window+1]):
            pivots_high.append(highs[i])
        if lows[i] == min(lows[i-window:i+window+1]):
            pivots_low.append(lows[i])
    resistance = round(sum(sorted(pivots_high)[-3:]) / 3, 2) if pivots_high else candles[-1]["high"]
    support    = round(sum(sorted(pivots_low)[:3]) / 3, 2)  if pivots_low  else candles[-1]["low"]
    return support, resistance


def detect_trend(closes: List[float], period: int = 20) -> str:
    if len(closes) < period:
        return "UNKNOWN"
    recent = closes[-period:]
    first_half  = sum(recent[:period//2]) / (period//2)
    second_half = sum(recent[period//2:]) / (period//2)
    diff = (second_half - first_half) / first_half * 100
    if diff > 3:   return "BULLISH"
    if diff < -3:  return "BEARISH"
    return "SIDEWAYS"


def detect_volatility(candles: List[Dict], period: int = 20) -> str:
    if len(candles) < period:
        return "UNKNOWN"
    ranges = [(c["high"] - c["low"]) / c["close"] * 100 for c in candles[-period:]]
    avg = sum(ranges) / len(ranges)
    if avg > 4:   return "HIGH"
    if avg > 2:   return "MEDIUM"
    return "LOW"


def detect_pattern(candles: List[Dict]) -> str:
    """Basic pattern detection — enough for LLM context."""
    closes = [c["close"] for c in candles[-20:]]
    highs  = [c["high"]  for c in candles[-20:]]
    lows   = [c["low"]   for c in candles[-20:]]
    if not closes:
        return "No pattern detected"
    patterns = []
    # Higher highs + higher lows = uptrend structure
    if highs[-1] > highs[-5] and lows[-1] > lows[-5]:
        patterns.append("Higher highs and higher lows (uptrend structure)")
    if highs[-1] < highs[-5] and lows[-1] < lows[-5]:
        patterns.append("Lower highs and lower lows (downtrend structure)")
    # Consolidation
    price_range = (max(closes) - min(closes)) / closes[0] * 100
    if price_range < 5:
        patterns.append("Tight consolidation / range-bound")
    elif price_range > 20:
        patterns.append("High volatility expansion")
    # Recent candle
    last = candles[-1]
    body = abs(last["close"] - last["open"])
    wick = last["high"] - last["low"]
    if wick > 0 and body / wick < 0.2:
        patterns.append("Doji / indecision candle on last bar")
    return " | ".join(patterns) if patterns else "No clear pattern"


# ── Main compression function ─────────────────────────────────
def build_market_context(symbol: str, candles: List[Dict]) -> Dict:
    """
    Compresses 100 candles into a structured dict the LLM can analyze.
    This is the KEY step — LLMs work better on compressed structure than raw numbers.
    """
    if len(candles) < 20:
        return {"error": f"Only {len(candles)} candles available"}

    closes  = [c["close"]  for c in candles]
    volumes = [c["volume"] for c in candles]
    price   = closes[-1]

    # Indicators
    rsi_vals   = _rsi(closes)
    rsi_now    = next((v for v in reversed(rsi_vals) if v is not None), None)
    macd_v, sig_v, cross = _macd(closes)
    bbu, bbm, bbl = _bollinger(closes)
    support, resistance = detect_support_resistance(candles)
    trend      = detect_trend(closes)
    volatility = detect_volatility(candles)
    pattern    = detect_pattern(candles)

    # Volume profile
    avg_vol = sum(volumes[-20:]) / 20 if volumes else 0
    vol_ratio = round(volumes[-1] / avg_vol, 2) if avg_vol else 1

    # Price changes
    chg_1d  = round((closes[-1]/closes[-24]  - 1)*100, 2) if len(closes) >= 24  else 0
    chg_7d  = round((closes[-1]/closes[-168] - 1)*100, 2) if len(closes) >= 168 else 0
    chg_1h  = round((closes[-1]/closes[-2]   - 1)*100, 2) if len(closes) >= 2   else 0

    # RSI label
    rsi_label = ("OVERSOLD ⚠️"   if rsi_now and rsi_now < 30  else
                 "OVERBOUGHT ⚠️" if rsi_now and rsi_now > 70  else
                 "neutral")

    # MACD label
    macd_label = (cross if cross else
                  ("MACD bullish" if macd_v and sig_v and macd_v > sig_v else "MACD bearish"))

    return {
        "symbol":     symbol,
        "price":      round(price, 4),
        "trend":      trend,
        "volatility": volatility,
        "pattern":    pattern,
        "support":    support,
        "resistance": resistance,
        "rsi":        round(rsi_now, 1) if rsi_now else None,
        "rsi_label":  rsi_label,
        "macd":       macd_v,
        "macd_signal": sig_v,
        "macd_label": macd_label,
        "bb_upper":   bbu,
        "bb_mid":     bbm,
        "bb_lower":   bbl,
        "bb_position": (
            "Above upper band" if bbu and price > bbu else
            "Below lower band" if bbl and price < bbl else
            f"{round((price-bbl)/(bbu-bbl)*100) if bbu and bbl else 50}% through band"
        ),
        "volume_ratio": vol_ratio,
        "volume_label": ("HIGH VOLUME" if vol_ratio > 1.5 else
                         "low volume"  if vol_ratio < 0.6 else "normal volume"),
        "chg_1h":  chg_1h,
        "chg_1d":  chg_1d,
        "chg_7d":  chg_7d,
        "candle_count": len(candles),
    }
