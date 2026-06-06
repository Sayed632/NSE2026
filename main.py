"""
main.py
Master orchestrator for the Indian Stock News Intelligence Agent.

Pipeline:
  1. Fetch news from all sources
  2. Load self-learning weights (Phase 2 foundation)
  3. Score and classify news with Gemini AI
  4. Build stock lists A / B / C
  5. Log predictions for future outcome tracking
  6. Run outcome tracker on past predictions
  7. Update accuracy weights if enough data exists
  8. Generate Telegram message + markdown report
  9. Send Telegram + save report to /reports/

Run locally:
  python main.py

Run via GitHub Actions:
  See .github/workflows/scanner.yml
"""

import os
import sys
import logging
from datetime import datetime
import pytz

# ── local modules ─────────────────────────────────────────────────────────────
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
    """Validate required environment variables are set."""
    required = ["GEMINI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    missing  = [v for v in required if not os.environ.get(v)]
    if missing:
        logger.error(f"Missing environment variables: {missing}")
        logger.error("Set them in GitHub Secrets or your local .env file.")
        return False
    return True


def main():
    now_ist  = datetime.now(IST)
    run_time = now_ist.strftime("%d %b %Y %I:%M %p")
    date_str = now_ist.strftime("%Y-%m-%d")

    logger.info("=" * 60)
    logger.info(f"  STOCK NEWS INTELLIGENCE AGENT — {run_time} IST")
    logger.info("=" * 60)

    # ── Validate secrets ──────────────────────────────────────────────────────
    if not check_env_vars():
        sys.exit(1)

    os.makedirs("reports", exist_ok=True)

    # ── STEP 1: Fetch all news ────────────────────────────────────────────────
    logger.info("\n[STEP 1] Fetching news from all sources...")
    all_news = fetch_all_news()
    if not all_news:
        logger.warning("No news fetched — all sources may be down. Exiting.")
        sys.exit(0)

    # ── STEP 2: Load self-learning weights ────────────────────────────────────
    logger.info("\n[STEP 2] Loading self-learning accuracy weights...")
    weights = load_self_learning_weights()

    # ── STEP 3: Score news with Gemini ────────────────────────────────────────
    logger.info(f"\n[STEP 3] Scoring {len(all_news)} news items with Gemini AI...")
    impactful_news = classify_and_score_news(all_news, weights)

    if not impactful_news:
        logger.info("No high-impact news found today (score >= 5). Sending quiet report.")
        results = {"list_a": [], "list_b": [], "list_c": [], "top_news": []}
    else:
        # ── STEP 4: Build stock lists ─────────────────────────────────────────
        logger.info(f"\n[STEP 4] Building stock lists from {len(impactful_news)} impactful items...")
        results = build_stock_lists(impactful_news, weights)

    # ── STEP 5: Log predictions (Phase 2 seed) ────────────────────────────────
    logger.info("\n[STEP 5] Logging predictions for self-learning...")
    log_predictions(results)

    # ── STEP 6: Run outcome tracker on past predictions ───────────────────────
    logger.info("\n[STEP 6] Checking outcomes for past predictions...")
    updated = run_outcome_tracker()
    logger.info(f"  Outcomes updated: {updated}")

    # ── STEP 7: Update accuracy weights if enough data ────────────────────────
    logger.info("\n[STEP 7] Checking if weight update is warranted...")
    new_weights = update_accuracy_weights(SECTOR_SEED_STOCKS)
    if new_weights:
        logger.info("  ✅ Self-learning weights updated from prediction history.")
    else:
        logger.info("  ⏳ Not enough evaluated predictions yet for weight update.")

    # ── STEP 8: Build reports ─────────────────────────────────────────────────
    logger.info("\n[STEP 8] Building Telegram message and markdown report...")
    tg_messages = build_telegram_message(results, run_time)
    md_content  = build_markdown_report(results, run_time, date_str)

    # ── STEP 9: Save markdown and send Telegram ───────────────────────────────
    logger.info("\n[STEP 9] Saving report and sending Telegram alert...")
    report_path = save_markdown_report(md_content, date_str)
    logger.info(f"  Report saved: {report_path}")

    tg_ok = send_telegram(tg_messages)
    if tg_ok:
        logger.info("  ✅ Telegram message(s) sent successfully.")
    else:
        logger.warning("  ⚠️ Telegram delivery failed — report still saved to GitHub.")

    # ── Summary ───────────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("  AGENT RUN COMPLETE")
    logger.info(f"  List A (Surge):     {len(results['list_a'])} stocks")
    logger.info(f"  List B (Long-term): {len(results['list_b'])} stocks")
    logger.info(f"  List C (Negative):  {len(results['list_c'])} stocks")
    logger.info(f"  Top news scored:    {len(results['top_news'])}")
    logger.info(f"  Report:             {report_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
  
