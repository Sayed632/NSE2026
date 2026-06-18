"""
prediction_logger.py
Stores open positions and calculates mathematical sector track weights
based on historical performance realizations.
"""

import os
import json
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

PREDICTIONS_FILE = "reports/predictions.csv"
WEIGHTS_FILE     = "reports/accuracy_weights.json"


def log_predictions(structured_lists: dict):
    """Logs newly identified assets with prospective forward verification timestamps."""
    os.makedirs("reports", exist_ok=True)
    
    new_records = []
    today = datetime.now(IST).date()
    
    # Process Short-Term assets (List A) -> 7-Day Verification Target
    for stock in structured_lists.get("list_a", []):
        new_records.append({
            "date_predicted": today,
            "symbol": stock["symbol"],
            "entry_price": stock["price"],
            "list_type": "LIST_A",
            "trigger_news": stock.get("reason", "No reason mapped"),
            "channel": stock.get("origin_channel", "Unknown"),
            "eval_date": today + timedelta(days=7),
            "correct": None,
            "pct_change": None
        })

    # Process Long-Term assets (List B) -> 30-Day Verification Target
    for stock in structured_lists.get("list_b", []):
        new_records.append({
            "date_predicted": today,
            "symbol": stock["symbol"],
            "entry_price": stock["price"],
            "list_type": "LIST_B",
            "trigger_news": stock.get("reason", "No reason mapped"),
            "channel": stock.get("origin_channel", "Unknown"),
            "eval_date": today + timedelta(days=30),
            "correct": None,
            "pct_change": None
        })

    if not new_records:
        logger.info("No active selections present to append to tracking files.")
        return

    new_df = pd.DataFrame(new_records)

    if os.path.exists(PREDICTIONS_FILE):
        try:
            old_df = pd.read_csv(PREDICTIONS_FILE)
            # Prevent duplicate logging for identical tickers flagged on the same date
            combined_df = pd.concat([old_df, new_df]).drop_duplicates(
                subset=["date_predicted", "symbol", "list_type"], keep="first"
            )
            combined_df.to_csv(PREDICTIONS_FILE, index=False)
        except Exception as e:
            logger.error(f"Error appending back into prediction matrix storage node: {e}")
    else:
        new_df.to_csv(PREDICTIONS_FILE, index=False)
    logger.info(f"Successfully tracked {len(new_df)} prospective allocations in master logs.")


def update_accuracy_weights():
    """
    Evaluates matured targets via historical market quotes (yfinance)
    and adjusts baseline tracking modifiers proportionally.
    """
    if not os.path.exists(PREDICTIONS_FILE):
        return

    try:
        df = pd.read_csv(PREDICTIONS_FILE)
    except Exception as e:
        logger.error(f"Failed loading metrics registry matrix: {e}")
        return

    today = datetime.now(IST).date()
    df["eval_date"] = pd.to_datetime(df["eval_date"]).dt.date
    df["date_predicted"] = pd.to_datetime(df["date_predicted"]).dt.date

    has_updates = False

    # Pull un-evaluated rows whose milestone date has come due
    matured_mask = (df["correct"].isna()) & (df["eval_date"] <= today)
    matured_indices = df[matured_mask].index

    for idx in matured_indices:
        ticker = df.at[idx, "symbol"]
        entry = float(df.at[idx, "entry_price"])
        list_type = df.at[idx, "list_type"]
        pred_date = df.at[idx, "date_predicted"]
        ev_date = df.at[idx, "eval_date"]

        try:
            tk = yf.Ticker(ticker)
            # Request historical boundaries surrounding target execution date window
            hist = tk.history(start=pred_date, end=ev_date + timedelta(days=4))
            if hist.empty:
                continue

            # Identify maximum achieved boundary close to track peak performance
            highest_close = float(hist["Close"].max())
            pct_gain = ((highest_close - entry) / entry) * 100
            df.at[idx, "pct_change"] = round(pct_gain, 2)

            # Benchmark performance expectations depending on system setup type
            if list_type == "LIST_A":
                df.at[idx, "correct"] = bool(pct_gain >= 6.0)  # Short-term target
            else:
                df.at[idx, "correct"] = bool(pct_gain >= 15.0) # Long-term multiplier

            has_updates = True
            logger.info(f"Evaluated performance milestone for {ticker}: Gain = {pct_gain:.1f}%")
        except Exception as e:
            logger.warning(f"Failed processing market evaluation for asset {ticker}: {e}")

    if has_updates:
        try:
            df.to_csv(PREDICTIONS_FILE, index=False)
        except Exception as e:
            logger.error(f"Failed flashing metrics changes to disk: {e}")

    # --- RECALCULATE DYNAMIC CHANNEL / SECTOR WEIGHTS ---
    evaluated = df[df["correct"].notna()]
    if len(evaluated) < 5:
        return  # Require stable data foundations before adapting model heuristics

    # Establish baseline index weight mapping matrix
    weights = {}
    all_channels = df["channel"].dropna().unique()
    for ch in all_channels:
        weights[ch] = 1.0

    for ch in all_channels:
        ch_history = evaluated[evaluated["channel"] == ch]
        if ch_history.empty:
            continue

        total = len(ch_history)
        correct_runs = int(ch_history["correct"].sum())
        success_ratio = correct_runs / total

        # Shift weights dynamically based on historical performance ratios
        if success_ratio >= 0.70:
            weights[ch] = 1.35  # High-conviction bump
        elif success_ratio >= 0.50:
            weights[ch] = 1.10  # Moderate confidence bump
        elif success_ratio <= 0.30:
            weights[ch] = 0.65  # Penalize high-risk/underperforming channels

    try:
        with open(WEIGHTS_FILE, "w") as f:
            json.dump(weights, f, indent=2)
        logger.info("Dynamic tracking confidence index successfully flushed to operational matrix.")
    except Exception as e:
        logger.error(f"Failed writing dynamic weight matrices back to filesystem: {e}")
