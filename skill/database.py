"""
skill/database.py
Stores all forecasts, outcomes, and accuracy data in SQLite.
Lives in data/forecasts.db — persists across restarts.
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import List, Optional, Dict

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "forecasts.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS forecasts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            symbol      TEXT NOT NULL,
            timeframe   TEXT NOT NULL DEFAULT '24h',
            direction   TEXT NOT NULL,   -- BULLISH / BEARISH / NEUTRAL
            confidence  INTEGER NOT NULL, -- 0-100
            reasoning   TEXT,
            key_levels  TEXT,            -- JSON: {support: x, resistance: y}
            risk_level  TEXT,            -- LOW / MEDIUM / HIGH
            summary     TEXT,            -- plain English paragraph
            model_used  TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS outcomes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            forecast_id  INTEGER REFERENCES forecasts(id),
            date         TEXT NOT NULL,
            symbol       TEXT NOT NULL,
            price_open   REAL,
            price_close  REAL,
            pct_change   REAL,
            actual_dir   TEXT,           -- BULLISH / BEARISH / NEUTRAL
            was_correct  INTEGER,        -- 1 = yes, 0 = no
            checked_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS daily_reports (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT NOT NULL,
            report     TEXT NOT NULL,    -- full plain-English report
            model_used TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS market_snapshots (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            date      TEXT NOT NULL,
            symbol    TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            snapshot  TEXT NOT NULL,     -- JSON compressed market context
            saved_at  TEXT DEFAULT (datetime('now'))
        );
        """)
    print("[DB] Database initialized ✓")


def save_forecast(date: str, symbol: str, direction: str, confidence: int,
                  reasoning: str, key_levels: dict, risk_level: str,
                  summary: str, model: str, timeframe: str = "24h") -> int:
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO forecasts
                (date, symbol, timeframe, direction, confidence, reasoning,
                 key_levels, risk_level, summary, model_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (date, symbol, timeframe, direction, confidence, reasoning,
              json.dumps(key_levels), risk_level, summary, model))
        return cur.lastrowid


def save_report(date: str, report: str, model: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO daily_reports (date, report, model_used) VALUES (?,?,?)",
            (date, report, model)
        )


def save_snapshot(date: str, symbol: str, timeframe: str, snapshot: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO market_snapshots (date, symbol, timeframe, snapshot)
            VALUES (?,?,?,?)
        """, (date, symbol, timeframe, json.dumps(snapshot)))


def record_outcome(forecast_id: int, symbol: str, price_open: float,
                   price_close: float):
    pct = ((price_close - price_open) / price_open) * 100
    if pct > 1.0:
        actual = "BULLISH"
    elif pct < -1.0:
        actual = "BEARISH"
    else:
        actual = "NEUTRAL"

    with get_conn() as conn:
        row = conn.execute(
            "SELECT direction FROM forecasts WHERE id=?", (forecast_id,)
        ).fetchone()
        correct = 1 if (row and row["direction"] == actual) else 0
        date = datetime.now().strftime("%Y-%m-%d")
        conn.execute("""
            INSERT INTO outcomes
                (forecast_id, date, symbol, price_open, price_close,
                 pct_change, actual_dir, was_correct)
            VALUES (?,?,?,?,?,?,?,?)
        """, (forecast_id, date, symbol, price_open, price_close,
              round(pct, 4), actual, correct))
        return correct, actual, round(pct, 4)


def get_accuracy_stats(symbol: str = None, days: int = 30) -> Dict:
    with get_conn() as conn:
        if symbol:
            rows = conn.execute("""
                SELECT o.was_correct, o.symbol, o.pct_change, o.actual_dir,
                       f.direction, f.confidence, o.date
                FROM outcomes o JOIN forecasts f ON o.forecast_id = f.id
                WHERE o.symbol=? AND o.date >= date('now', ?)
                ORDER BY o.date DESC
            """, (symbol, f"-{days} days")).fetchall()
        else:
            rows = conn.execute("""
                SELECT o.was_correct, o.symbol, o.pct_change, o.actual_dir,
                       f.direction, f.confidence, o.date
                FROM outcomes o JOIN forecasts f ON o.forecast_id = f.id
                WHERE o.date >= date('now', ?)
                ORDER BY o.date DESC
            """, (f"-{days} days",)).fetchall()

        total  = len(rows)
        correct = sum(1 for r in rows if r["was_correct"] == 1)
        return {
            "total":    total,
            "correct":  correct,
            "wrong":    total - correct,
            "accuracy": round(correct / total * 100, 1) if total else 0,
            "rows":     [dict(r) for r in rows[:20]]
        }


def get_recent_forecasts(n: int = 10) -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT f.*, o.was_correct, o.actual_dir, o.pct_change
            FROM forecasts f
            LEFT JOIN outcomes o ON o.forecast_id = f.id
            ORDER BY f.created_at DESC LIMIT ?
        """, (n,)).fetchall()
        return [dict(r) for r in rows]


def get_recent_reports(n: int = 7) -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_reports ORDER BY created_at DESC LIMIT ?", (n,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_todays_forecast(symbol: str) -> Optional[Dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM forecasts WHERE date=? AND symbol=? ORDER BY id DESC LIMIT 1",
            (today, symbol)
        ).fetchone()
        return dict(row) if row else None
