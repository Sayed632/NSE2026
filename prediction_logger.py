"""
prediction_logger.py
Phase 2 Self-Learning Foundation.

Every run logs predictions to reports/predictions.csv.
After 7 days, the outcome_tracker checks actual price movements.
After 20+ data points, accuracy_weights.json is updated so the
agent scores future news with calibrated sector confidence.

Phase 1: Logs predictions only.
Phase 2: Full feedback loop (auto-activated once 20 rows exist).
"""

import os
import json
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import pytz

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IST          = pytz.timezone("Asia/Kolkata")
PREDICTIONS_FILE = "reports/predictions.csv"
WEIGHTS_FILE     = "reports/accuracy_weights.json"
MIN_ROWS_FOR_LEARNING = 20


def log_predictions(results: dict) -> None:
    """
    Append today's List A and List B picks to predictions.csv
    so outcomes can be tracked 7 days later.
    """
    os.makedirs("reports", exist_ok=True)
    today    = datetime.now(IST).strftime("%Y-%m-%d")
    rows     = []

    for stock in results.get("list_a", []):
        rows.append({
            "date_predicted": today,
            "symbol":         stock["symbol"],
            "list_type":      "A_SURGE",
            "price_at_pred":  stock["price"],
            "target":         stock.get("target_zone", ""),
            "trigger_news":   stock.get("trigger_news", "")[:100],
            "outcome_date":   (datetime.now(IST) + timedelta(days=7)).strftime("%Y-%m-%d"),
            "price_at_outcome": None,
            "pct_change":       None,
            "correct":          None,
        })

    for stock in results.get("list_b", []):
        rows.append({
            "date_predicted": today,
            "symbol":         stock["symbol"],
            "list_type":      "B_LONGTERM",
            "price_at_pred":  stock["price"],
            "target":         "",
            "trigger_news":   stock.get("catalysts", "")[:100],
            "outcome_date":   (datetime.now(IST) + timedelta(days=30)).strftime("%Y-%m-%d"),
            "price_at_outcome": None,
            "pct_change":       None,
            "correct":          None,
        })

    if not rows:
        logger.info("No predictions to log today.")
        return

    new_df = pd.DataFrame(rows)

    if os.path.exists(PREDICTIONS_FILE):
        existing = pd.read_csv(PREDICTIONS_FILE)
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    combined.to_csv(PREDICTIONS_FILE, index=False)
    logger.info(f"Logged {len(rows)} predictions to {PREDICTIONS_FILE}")


def run_outcome_tracker() -> int:
    """
    Check predictions whose outcome_date has passed.
    Fetch actual prices, compute % change, mark correct/incorrect.
    Returns number of rows updated.
    """
    if not os.path.exists(PREDICTIONS_FILE):
        return 0

    df      = pd.read_csv(PREDICTIONS_FILE)
    today   = datetime.now(IST).strftime("%Y-%m-%d")
    updated = 0

    for idx, row in df.iterrows():
        if pd.notna(row.get("correct")):
            continue  # Already evaluated
        if str(row.get("outcome_date", "")) > today:
            continue  # Not due yet

        symbol = row["symbol"]
        try:
            ticker  = yf.Ticker(symbol)
            hist    = ticker.history(period="5d")
            if hist.empty:
                continue
            current_price = round(hist["Close"].iloc[-1], 2)
            pred_price    = float(row["price_at_pred"])
            pct_change    = round((current_price - pred_price) / pred_price * 100, 2)

            # Correct = surged > 3% for List A, > 5% for List B within timeframe
            threshold = 3.0 if row["list_type"] == "A_SURGE" else 5.0
            correct   = pct_change >= threshold

            df.at[idx, "price_at_outcome"] = current_price
            df.at[idx, "pct_change"]       = pct_change
            df.at[idx, "correct"]          = correct
            updated += 1
            logger.info(f"Outcome: {symbol} {pct_change:+.1f}% → {'✓' if correct else '✗'}")
        except Exception as e:
            logger.debug(f"Outcome fetch failed for {symbol}: {e}")

    if updated > 0:
        df.to_csv(PREDICTIONS_FILE, index=False)
        logger.info(f"Updated {updated} prediction outcomes.")

    return updated


def update_accuracy_weights(sector_seed_stocks: dict) -> dict:
    """
    Phase 2 core: rebuild accuracy_weights.json from prediction outcomes.
    Only runs once MIN_ROWS_FOR_LEARNING evaluated rows exist.
    Returns updated weights dict.
    """
    if not os.path.exists(PREDICTIONS_FILE):
        return {}

    df = pd.read_csv(PREDICTIONS_FILE)
    evaluated = df[df["correct"].notna()]

    if len(evaluated) < MIN_ROWS_FOR_LEARNING:
        logger.info(
            f"Only {len(evaluated)} evaluated predictions — need {MIN_ROWS_FOR_LEARNING} for weight update."
        )
        return {}

    # Build reverse map: symbol → sectors
    symbol_to_sectors = {}
    for sector, symbols in sector_seed_stocks.items():
        for sym in symbols:
            symbol_to_sectors.setdefault(sym, []).append(sector)

    # Compute per-sector accuracy
    sector_stats = {}
    for _, row in evaluated.iterrows():
        sectors = symbol_to_sectors.get(row["symbol"], ["Other"])
        for sector in sectors:
            if sector not in sector_stats:
                sector_stats[sector] = {"correct": 0, "total": 0}
            sector_stats[sector]["total"] += 1
            if row["correct"]:
                sector_stats[sector]["correct"] += 1

    weights = {}
    for sector, stats in sector_stats.items():
        accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0.5
        # Weight scale: 0.5 (poor) to 1.5 (excellent)
        weights[sector] = round(0.5 + accuracy, 2)

    # Fill missing sectors with 1.0
    for sector in sector_seed_stocks:
        weights.setdefault(sector, 1.0)

    os.makedirs("reports", exist_ok=True)
    with open(WEIGHTS_FILE, "w") as f:
        json.dump(weights, f, indent=2)

    logger.info(f"✅ Accuracy weights updated: {weights}")

    # Print learning summary
    summary_lines = ["## Self-Learning Summary\n"]
    summary_lines.append(f"Total evaluated predictions: {len(evaluated)}\n")
    summary_lines.append("| Sector | Correct | Total | Accuracy | Weight |\n")
    summary_lines.append("|--------|---------|-------|----------|--------|\n")
    for sector, stats in sorted(sector_stats.items(), key=lambda x: -x[1].get("correct",0)/max(x[1].get("total",1),1)):
        acc = stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0
        w   = weights.get(sector, 1.0)
        summary_lines.append(
            f"| {sector} | {stats['correct']} | {stats['total']} | {acc:.0f}% | {w} |\n"
        )

    with open("reports/learning_summary.md", "w") as f:
        f.writelines(summary_lines)

    return weights
          
