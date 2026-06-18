"""
pattern_memory.py
Extracts recurring keyword strings from winning historical entries
to identify high-probability catalytic patterns.
"""

import os
import json
import logging
import pandas as pd

logger = logging.getLogger(__name__)

PREDICTIONS_FILE = "reports/predictions.csv"
PATTERN_FILE     = "reports/pattern_memory.json"

# High-signal financial catalysts to prioritize for keyword memory extractions
SIGNATURE_KEYWORDS = [
    "order", "contract", "capacity", "expansion", "dividend", "demerger", 
    "acquisition", "merger", "fii", "dii", "bulk", "block", "earnings", 
    "profit", "revenue", "breakout", "turnaround", "allocation", "sme"
]


def harvest_winning_patterns():
    """Scans historical logs to index high-conviction keyword patterns."""
    if not os.path.exists(PREDICTIONS_FILE):
        logger.info("Predictions registry matrix absent. Skipping pattern harvesting.")
        return

    try:
        df = pd.read_csv(PREDICTIONS_FILE)
    except Exception as e:
        logger.error(f"Failed to read predictions database for pattern engine: {e}")
        return

    if df.empty or "correct" not in df.columns:
        return

    # Filter for successful calls that generated positive returns
    winning_runs = df[(df["correct"] == True) & (df["pct_change"] > 0)]
    if winning_runs.empty:
        logger.info("Insufficient successful historical data points to extract patterns.")
        return

    pattern_registry = {}

    for _, row in winning_runs.iterrows():
        ticker = str(row["symbol"])
        news_text = str(row.get("trigger_news", "")).lower()
        gain = float(row.get("pct_change", 0))
        
        # Isolate text catalysts that match our signature keyword matrix
        matched_tokens = [token for token in SIGNATURE_KEYWORDS if token in news_text]
        
        if not matched_tokens:
            continue

        if ticker not in pattern_registry:
            pattern_registry[ticker] = {
                "symbol": ticker,
                "keywords": matched_tokens,
                "occurrences": 1,
                "avg_gain_pct": gain,
                "confidence": "low"
            }
        else:
            entry = pattern_registry[ticker]
            # Recalculate rolling mathematical averages for target assets
            total_gain = (entry["avg_gain_pct"] * entry["occurrences"]) + gain
            entry["occurrences"] += 1
            entry["avg_gain_pct"] = round(total_gain / entry["occurrences"], 2)
            
            # Update matching tokens safely without duplicating list indexes
            entry["keywords"] = list(set(entry["keywords"] + matched_tokens))
            
            # Grade pattern reliability based on recurring frequencies
            if entry["occurrences"] >= 3:
                entry["confidence"] = "high"
            elif entry["occurrences"] == 2:
                entry["confidence"] = "medium"

    try:
        with open(PATTERN_FILE, "w", encoding="utf-8") as f:
            json.dump(pattern_registry, f, indent=2)
        logger.info(f"Pattern memory snapshot updated successfully with {len(pattern_registry)} active asset profiles.")
    except Exception as e:
        logger.error(f"Failed committing pattern memories back to repository directory: {e}")


if __name__ == "__main__":
    harvest_winning_patterns()
