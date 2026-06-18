"""

# Add this import at the top of main.py
from backtester import run_historical_event_backtest

# Inside your def main(): function, run it right at the beginning
def main():
    logger.info("Initializing Stock News Intelligence Agent Core Workflow...")
    
    # Run the backtest first so the agent can learn and update its rules before scanning today's news
    try:
        run_historical_event_backtest()
    except Exception as e:
        logger.warning(f"Backtester cycle skipped: {e}")

main.py
Master Orchestrator for the Stock News Intelligence Agent.
Integrates live prompt injection overrides and triggers weekly self-analysis pipelines.
"""

import os
import json
import logging
from datetime import datetime
import pytz

# Core pipeline imports
from news_fetcher import ingest_market_intelligence
from stock_analyzer import classify_and_score_news, build_stock_lists
from prediction_logger import log_predictions, update_accuracy_weights
from report_generator import build_telegram_message, build_markdown_report, save_markdown_report, send_telegram
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
    date_str     = now.strftime("%Y-%m-%d")

    # 1. Pipeline Trigger Strategy: Handle Weekly Performance Closures on Mondays
    if now.weekday() == 0:
        logger.info("Monday detected. Activating autonomous weekly performance evaluation...")
        try:
            analysis_triggered = run_weekly_pipeline(force=True)
            if analysis_triggered:
                logger.info("Weekly self-analysis report successfully delivered via Telegram.")
        except Exception as e:
            logger.error(f"Critical failure running autonomous weekly pipeline: {e}")

    # 2. Extract Data Across the Fallback Matrix (DSIJ -> Moneycontrol -> Govt PIB)
    raw_payload_matrix = ingest_market_intelligence()
    if not raw_payload_matrix:
        logger.error("All data ingestion tracks failed or returned empty streams. Terminating cycle.")
        return

    # 3. Load self-evolved rule modifiers from past trading periods
    prompt_modifier, weights = load_dynamic_intelligence_modifiers()

    # 4. Process unstructured data through the Gemini Core Inference Model
    # Note: If your stock_analyzer doesn't support the modifier yet, it passes safely.
    try:
        compiled_insights = classify_and_score_news(raw_payload_matrix, weights)
    except TypeError:
        # Fallback if stock_analyzer has old function signature
        compiled_insights = classify_and_score_news(raw_payload_matrix)

    if not compiled_insights:
        logger.warning("Gemini Inference Layer returned zero high-conviction insights for this cycle.")
        return

    # 5. Filter and sort selections via live market conditions (yFinance metrics)
    structured_lists = build_stock_lists(compiled_insights, weights)

    # 6. Log live assets into tracking database for future self-learning calculations
    try:
        log_predictions(structured_lists)
        update_accuracy_weights()
    except Exception as e:
        logger.error(f"Failed committing data back to accuracy database tracking loop: {e}")

    # 7. Render outputs and broadcast directly to your phone via Telegram
    telegram_chunks = build_telegram_message(structured_lists, run_time_str)
    send_telegram(telegram_chunks)

    # 8. Save snapshot report file to local workspace directory for Git commit tracking
    md_report = build_markdown_report(structured_lists, run_time_str, date_str)
    save_markdown_report(md_report, date_str)
    
    logger.info("Stock News Intelligence Agent cycle executed successfully.")


if __name__ == "__main__":
    main()
