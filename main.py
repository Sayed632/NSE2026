"""
main.py
Master orchestrator for the Indian Stock News Intelligence Agent.
Includes secure checks for Dalal Street Journal (DSJ) premium session credentials.
"""

import os
import sys
import logging
from datetime import datetime
import pytz

from news_fetcher      import fetch_all_news
from stock_analyzer    import (
    classify_and_score_news,
    build_stock_lists,
    load_self_learning_weights,
    SECTOR_SEED_STOCKS,
)
from prediction_logger import (
    log_predictions,
    run_outcome_tracker,
    update_accuracy_weights,
)
from report_generator  import (
    build_telegram_message,
    build_markdown_report,
    save_markdown_report,
    send_telegram,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)
IST    = pytz.timezone("Asia/Kolkata")


def check_env_vars() -> bool:
    """Verifies all core integrations and credential vaults are present before running execution blocks."""
    required = [
        "GEMINI_API_KEY", 
        "TELEGRAM_TOKEN", 
        "TELEGRAM_CHAT_ID",
        "DSJ_USER_ID",      
        "DSJ_PASSWORD"      
    ]
    missing  = [v for v in required if not os.environ.get(v)]
    if missing:
        logger.error(f"Missing environment variables or repository secrets: {missing}")
        logger.error("Please add them under Settings -> Secrets and variables -> Actions in your GitHub repository.")
        return False
    return True


def main():
    now_ist  = datetime.now(IST)
    run_time = now_ist.strftime("%d %b %Y %I:%M %p")
    date_str = now_ist.strftime("%Y-%m-%d")

    logger.info("=" * 60)
    logger.info(f"  STOCK NEWS INTELLIGENCE AGENT — {run_time} IST")
    logger.info("=" * 60)

    if not check_env_vars():
        sys.exit(1)

    os.makedirs("reports", exist_ok=True)

    logger.info("\n[STEP 1] Fetching news from all sources (including authenticated premium feeds)...")
    all_news = fetch_all_news()
    if not all_news:
        logger.warning("No news fetched — all sources may be down. Exiting.")
        sys.exit(0)

    logger.info("\n[STEP 2] Loading self-learning accuracy weights...")
    weights = load_self_learning_weights()

    logger.info(f"\n[STEP 3] Scoring {len(all_news)} news items with Gemini AI...")
    impactful_news = classify_and_score_news(all_news, weights)

    if not impactful_news:
        logger.info("No high-impact news found today.")
        results = {"list_a": [], "list_b": [], "list_c": [], "top_news": []}
    else:
        logger.info(f"\n[STEP 4] Building stock lists...")
        results = build_stock_lists(impactful_news, weights)

    logger.info("\n[STEP 5] Logging predictions for self-learning...")
    log_predictions(results)

    logger.info("\n[STEP 6] Checking outcomes for past predictions...")
    updated = run_outcome_tracker()
    logger.info(f"  Outcomes updated: {updated}")

    logger.info("\n[STEP 7] Checking if weight update is warranted...")
    new_weights = update_accuracy_weights(SECTOR_SEED_STOCKS)
    if new_weights:
        logger.info("  Self-learning weights updated.")
    else:
        logger.info("  Not enough data yet for weight update.")

    logger.info("\n[STEP 8] Building reports...")
    tg_messages = build_telegram_message(results, run_time)
    md_content  = build_markdown_report(results, run_time, date_str)

    logger.info("\n[STEP 9] Saving report and sending Telegram...")
    report_path = save_markdown_report(md_content, date_str)
    logger.info(f"  Report saved: {report_path}")

    tg_ok = send_telegram(tg_messages)
    if tg_ok:
        logger.info("  Telegram sent successfully.")
    else:
        logger.warning("  Telegram delivery failed.")

    logger.info("\n" + "=" * 60)
    logger.info("  AGENT RUN COMPLETE")
    logger.info(f"  List A (Surge):     {len(results['list_a'])} stocks")
    logger.info(f"  List B (Long-term): {len(results['list_b'])} stocks")
    logger.info(f"  List C (Negative):  {len(results['list_c'])} stocks")
    logger.info(f"  Report:             {report_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
