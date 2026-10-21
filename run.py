"""
run.py — Market Forecaster main entry point
Scheduler + dashboard + OpenClaw skill interface
"""

import asyncio
import logging
import os
import sys
import threading
import time
from datetime import datetime, timedelta

import yaml

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, "analyst.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger("main")

# ── Init everything ───────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from skill.database   import init_db, save_forecast, save_report, get_todays_forecast
from skill.market_data import fetch_candles, build_market_context
from skill.llm_analyst import LLMAnalyst, detect_gpu_and_model
from skill.accuracy    import check_yesterdays_forecasts


def load_config() -> dict:
    path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


def run_full_analysis(config: dict, llm: LLMAnalyst, state: dict) -> list:
    """
    Full analysis cycle:
    1. Check yesterday's forecasts for accuracy
    2. Fetch market data for all symbols
    3. Ask LLM to forecast each symbol
    4. Generate combined daily report
    5. Save everything to DB
    """
    date = datetime.now().strftime("%Y-%m-%d")
    state["status_msg"] = "⟳ Checking yesterday's forecasts..."
    logger.info("=" * 55)
    logger.info(f"  FORECAST CYCLE — {date}")
    logger.info("=" * 55)

    # Step 1: accuracy check
    outcomes = check_yesterdays_forecasts()
    if outcomes:
        correct = sum(1 for o in outcomes if o["correct"])
        logger.info(f"Accuracy check: {correct}/{len(outcomes)} correct yesterday")

    # Step 2 + 3: fetch + forecast
    forecasts = []
    for symbol in config.get("symbols", ["BTC-USD", "ETH-USD", "SOL-USD"]):
        state["status_msg"] = f"⟳ Fetching {symbol}..."

        # Skip if already done today
        existing = get_todays_forecast(symbol)
        if existing:
            logger.info(f"  {symbol}: already forecasted today, skipping")
            forecasts.append(existing)
            continue

        candles = fetch_candles(symbol, "1h", config.get("candles_lookback", 100))
        if not candles:
            logger.warning(f"  {symbol}: no candle data — skipping")
            continue

        context = build_market_context(symbol, candles)
        if "error" in context:
            logger.warning(f"  {symbol}: {context['error']}")
            continue

        state["status_msg"] = f"⟳ LLM analyzing {symbol}..."
        fc = llm.forecast(context)
        if not fc:
            logger.warning(f"  {symbol}: LLM returned nothing")
            continue

        # Save to DB
        fc_id = save_forecast(
            date        = date,
            symbol      = symbol,
            direction   = fc.get("direction", "NEUTRAL"),
            confidence  = fc.get("confidence", 50),
            reasoning   = fc.get("reasoning", ""),
            key_levels  = fc.get("key_levels", {}),
            risk_level  = fc.get("risk_level", "MEDIUM"),
            summary     = fc.get("summary", ""),
            model       = llm.model,
        )
        fc["db_id"] = fc_id
        forecasts.append(fc)
        logger.info(f"  ✓ {symbol}: {fc['direction']} {fc['confidence']}% — saved")

    # Step 4: daily report
    if forecasts:
        state["status_msg"] = "⟳ Generating daily report..."
        report = llm.generate_daily_report(forecasts)
        save_report(date, report, llm.model)
        logger.info("  ✓ Daily report saved")
    else:
        report = "No forecasts generated today."

    state["last_run"]   = datetime.now().strftime("%Y-%m-%d %H:%M")
    state["status_msg"] = f"✅ Analysis complete — {len(forecasts)} forecasts generated"
    logger.info(f"Cycle complete: {len(forecasts)} forecasts")
    return forecasts


def scheduler_loop(config: dict, llm: LLMAnalyst, state: dict):
    """Runs daily at the configured hour. Also listens for run_now signals."""
    target_hour = config.get("analysis_hour", 8)
    logger.info(f"Scheduler active — daily analysis at {target_hour:02d}:00")

    while state.get("scheduler_running"):
        now = datetime.now()

        # Check for manual trigger
        if state.get("run_now_signal"):
            state["run_now_signal"] = False
            run_full_analysis(config, llm, state)

        # Scheduled daily run
        next_run = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        state["next_run"] = next_run.strftime("%Y-%m-%d %H:%M")

        if now.hour == target_hour and now.minute == 0 and now.second < 30:
            run_full_analysis(config, llm, state)
            time.sleep(60)   # Don't re-trigger in same minute

        time.sleep(10)


def start_dashboard(state: dict, config: dict):
    from dashboard.app import create_app
    app = create_app(state)
    app.run(
        host=config.get("host", "0.0.0.0"),
        port=config.get("port", 5050),
        debug=False, use_reloader=False
    )


def main():
    config = load_config()
    init_db()

    logger.info("=" * 55)
    logger.info("  MARKET FORECASTER — Market Forecasting Agent")
    logger.info("  No trading. Offline LLM. Daily reports.")
    logger.info(f"  Dashboard: http://localhost:{config.get('port', 5050)}")
    logger.info("=" * 55)

    llm = LLMAnalyst(config)
    llm_online = llm.is_online()

    state = {
        "scheduler_running": False,
        "run_now_signal":    False,
        "start_scheduler_signal": False,
        "llm_status":  "online" if llm_online else "offline",
        "llm_model":   llm.model,
        "running":     False,
        "last_run":    "Never",
        "next_run":    "—",
        "status_msg":  "Ready" if llm_online else "⚠️ Ollama not running — start with: ollama serve",
        "uptime_start": time.time(),
    }

    if not llm_online:
        logger.warning("⚠️  Ollama not reachable. Start it with: ollama serve")
        logger.warning("   Then pull a model: ollama pull qwen2.5:7b")

    # Dashboard in background
    t = threading.Thread(target=start_dashboard, args=(state, config), daemon=True)
    t.start()
    logger.info("Dashboard started ✓")

    # Signal handling loop
    logger.info("Waiting for commands (use dashboard or press Ctrl+C)")
    sched_thread = None

    while True:
        # Re-check LLM status
        state["llm_status"] = "online" if llm.is_online() else "offline"

        if state.get("start_scheduler_signal"):
            state["start_scheduler_signal"] = False
            if not state["scheduler_running"]:
                state["scheduler_running"] = True
                state["running"] = True
                sched_thread = threading.Thread(
                    target=scheduler_loop, args=(config, llm, state), daemon=True
                )
                sched_thread.start()
                logger.info("Scheduler started")
                state["status_msg"] = f"▶ Running — daily analysis at {config.get('analysis_hour',8):02d}:00"

        if state.get("run_now_signal") and not state["scheduler_running"]:
            state["run_now_signal"] = False
            threading.Thread(
                target=run_full_analysis, args=(config, llm, state), daemon=True
            ).start()

        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Market Forecaster shutting down.")
