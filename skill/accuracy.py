"""
skill/accuracy.py
Checks yesterday's forecasts against actual price movement.
This is what makes the forecaster accountable and improvable over time.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict
from skill.database import get_conn, record_outcome
from skill.market_data import get_current_price, fetch_candles

logger = logging.getLogger("accuracy")


def check_yesterdays_forecasts() -> List[Dict]:
    """
    For every forecast made yesterday, check if it was correct.
    Returns list of outcome dicts.
    """
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    outcomes  = []

    with get_conn() as conn:
        pending = conn.execute("""
            SELECT f.id, f.symbol, f.direction, f.confidence, f.date
            FROM forecasts f
            LEFT JOIN outcomes o ON o.forecast_id = f.id
            WHERE f.date = ? AND o.id IS NULL
        """, (yesterday,)).fetchall()

    if not pending:
        logger.info("No pending forecasts to check")
        return []

    logger.info(f"Checking {len(pending)} forecasts from {yesterday}...")

    for row in pending:
        symbol  = row["symbol"]
        fid     = row["id"]
        pred    = row["direction"]

        try:
            # Get yesterday's open (first candle of the day)
            candles = fetch_candles(symbol, "1h", 48)
            if not candles or len(candles) < 24:
                logger.warning(f"  Not enough candles to check {symbol}")
                continue

            # Open = 24h ago close, Close = current price
            price_open  = candles[-25]["close"] if len(candles) >= 25 else candles[0]["close"]
            price_close = candles[-1]["close"]

            correct, actual, pct = record_outcome(fid, symbol, price_open, price_close)

            result = {
                "symbol":      symbol,
                "predicted":   pred,
                "actual":      actual,
                "pct_change":  pct,
                "correct":     bool(correct),
                "confidence":  row["confidence"],
                "date":        yesterday,
            }
            outcomes.append(result)

            icon = "✅" if correct else "❌"
            logger.info(
                f"  {icon} {symbol}: predicted {pred} | actual {actual} | "
                f"{pct:+.2f}% | conf was {row['confidence']}%"
            )

        except Exception as e:
            logger.error(f"  Failed to check {symbol}: {e}")

    return outcomes


def get_accuracy_summary() -> str:
    """Generate a plain-English accuracy summary for the dashboard."""
    from skill.database import get_accuracy_stats
    stats = get_accuracy_stats(days=30)
    total = stats["total"]
    if total == 0:
        return "No forecasts recorded yet. Run daily analysis to start tracking accuracy."

    acc = stats["accuracy"]
    correct = stats["correct"]

    # Per-symbol breakdown
    symbol_stats = {}
    for row in stats["rows"]:
        sym = row["symbol"]
        if sym not in symbol_stats:
            symbol_stats[sym] = {"total": 0, "correct": 0}
        symbol_stats[sym]["total"] += 1
        if row["was_correct"]:
            symbol_stats[sym]["correct"] += 1

    sym_lines = []
    for sym, s in symbol_stats.items():
        sym_acc = round(s["correct"] / s["total"] * 100, 1) if s["total"] else 0
        sym_lines.append(f"  {sym}: {sym_acc}% ({s['correct']}/{s['total']})")

    return (
        f"30-Day Accuracy: {acc}% ({correct}/{total} forecasts correct)\n" +
        "\n".join(sym_lines)
    )
