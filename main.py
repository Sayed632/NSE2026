"""
main.py
Master Orchestrator for the Stock News Intelligence Agent.
Integrates live prompt injection overrides, triggers weekly self-analysis pipelines,
and updates system logic daily using historical backtest feedback.
"""

import os
import json
import logging
from datetime import datetime
import pytz

# Core pipeline imports
from backtester import run_historical_event_backtest
from news_fetcher import ingest_market_intelligence
from stock_analyzer import classify_and_score_news, build_stock_lists
from prediction_logger import log_predictions, update_accuracy_weights
from report_generator import build_telegram_message, send_telegram
from weekly_self_analysis import run_weekly_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")
RULES_OVERRIDE_FILE = "reports/scoring_rules_override.json"
WEIGHTS_FILE        = "reports/accuracy_weights.json"


def load_dynamic_intelligence_modifiers() -> tuple[str, dict]:
    """Loads self-evolved text rules and numerical sector weights to inject into Gemini."""
    prompt_modifier = ""
    weights = {}

    if os.path.exists(RULES_OVERRIDE_FILE):
        try:
            with open(RULES_OVERRIDE_FILE, "r") as f:
                rules = json.load(f)
                prompt_modifier = rules.get("prompt_injection", "")
                if prompt_modifier:
                    logger.info("Self-evolved rule override successfully loaded for injection.")
        except Exception as e:
            logger.warning(f"Failed loading prompt modifiers: {e}")

    if os.path.exists(WEIGHTS_FILE):
        try:
            with open(WEIGHTS_FILE, "r") as f:
                weights = json.load(f)
                logger.info("Self-recalibrated sector weights successfully loaded.")
        except Exception as e:
            logger.warning(f"Failed loading performance weights: {e}")

    return prompt_modifier, weights


def main():
    logger.info("Initializing Stock News Intelligence Agent Core Workflow...")
    
    now = datetime.now(IST)
    run_time_str = now.strftime("%d %b %Y %I:%M %p")

    # 1. Pipeline Trigger Strategy: Handle Weekly Performance Closures on Mondays
    if now.weekday() == 0:
        logger.info("Monday detected. Activating autonomous weekly performance evaluation...")
        try:
            analysis_triggered = run_weekly_pipeline(force=True)
            if analysis_triggered:
                logger.info("Weekly self-analysis report successfully delivered via Telegram.")
        except Exception as e:
            logger.error(f"Critical failure running autonomous weekly pipeline: {e}")

    # 2. RUN HISTORICAL BACKTEST LEARNING LOOP
    # The agent reviews past asset results and writes programmatic rules *before* parsing new data
    logger.info("Executing event-driven historical backtest learning loop...")
    try:
        run_historical_event_backtest()
    except Exception as e:
        logger.warning(f"Backtester lifecycle step bypassed or failed: {e}")

    # 3. Extract Data Across the Fallback Matrix (DSIJ -> Government PIB -> Moneycontrol)
    raw_payload_matrix = ingest_market_intelligence()
    if not raw_payload_matrix:
        logger.error("All data ingestion tracks failed or returned empty streams. Terminating cycle.")
        return

    # 4. Load self-evolved rule modifiers from past trading periods
    prompt_modifier, weights = load_dynamic_intelligence_modifiers()

    # 5. Process unstructured data through the Gemini Core Inference Model (gemini-2.5-flash)
    try:
        compiled_insights = classify_and_score_news(raw_payload_matrix, weights)
    except TypeError:
        compiled_insights = classify_and_score_news(raw_payload_matrix)

    if not compiled_insights:
        logger.warning("Gemini Inference Layer returned zero high-conviction insights for this cycle.")
        return

    # 6. Filter and sort selections via live market conditions & Technical Safeguards (yFinance)
    structured_lists = build_stock_lists(compiled_insights, weights)

    # 7. Log live assets into tracking database for future self-learning calculations
    try:
        log_predictions(structured_lists)
        update_accuracy_weights()
    except Exception as e:
        logger.error(f"Failed committing data back to accuracy database tracking loop: {e}")

    # 8. Render outputs and broadcast directly to your phone via Telegram
    telegram_chunks = build_telegram_message(structured_lists, run_time_str)
    send_telegram(telegram_chunks)
    
    logger.info("Stock News Intelligence Agent cycle executed successfully.")


if __name__ == "__main__":
    main()
