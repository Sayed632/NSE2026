"""
weekly_self_analysis.py
Compiles system-wide historical accuracy metrics every Monday morning
and transmits performance diagnostics via Telegram.
"""

import os
import json
import logging
import pandas as pd
from datetime import datetime
import pytz

# Evolutionary engine component linkages
from pattern_memory import harvest_winning_patterns
from gemini_self_rewriter import execute_meta_cognitive_rewriter
from report_generator import send_telegram

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

PREDICTIONS_FILE    = "reports/predictions.csv"
RULES_OVERRIDE_FILE = "reports/scoring_rules_override.json"


def run_weekly_pipeline(force: bool = False) -> bool:
    """Executes closed-loop historical performance audits and broadcasts diagnostics."""
    now = datetime.now(IST)
    
    # Restrict execution solely to Mondays unless explicitly overridden via force flag
    if now.weekday() != 0 and not force:
        logger.info("Weekly performance audit bypassed. Scheduling window targets Mondays.")
        return False

    if not os.path.exists(PREDICTIONS_FILE):
        logger.info("No prediction entries logged. Weekly analysis loop suspended.")
        return False

    try:
        df = pd.read_csv(PREDICTIONS_FILE)
    except Exception as e:
        logger.error(f"Failed to read predictions dataset during weekly audit: {e}")
        return False

    if df.empty or "correct" not in df.columns:
        logger.warning("Predictions database contains insufficient records to audit.")
        return False

    # 1. Trigger Underlying Evolutionary Engines
    logger.info("Harvesting recurring profitable signal patterns...")
    harvest_winning_patterns()
    
    logger.info("Running meta-cognitive prompt rewriting loop...")
    execute_meta_cognitive_rewriter()

    # 2. Extract Mathematical Hit-Ratios
    evaluated = df[df["correct"].notna()]
    total_calls = len(evaluated)
    
    if total_calls == 0:
        logger.info("Zero positions have hit their maturity target dates yet. Skipping report broadcast.")
        return False

    correct_calls = int(evaluated["correct"].sum())
    win_rate = round((correct_calls / total_calls) * 100, 1)

    # Segregate performance across timelines
    list_a_runs = evaluated[evaluated["list_type"] == "LIST_A"]
    list_b_runs = evaluated[evaluated["list_type"] == "LIST_B"]

    win_rate_a = round((list_a_runs["correct"].sum() / len(list_a_runs) * 100), 1) if not list_a_runs.empty else 0.0
    win_rate_b = round((list_b_runs["correct"].sum() / len(list_b_runs) * 100), 1) if not list_b_runs.empty else 0.0

    # 3. Ingest Current Prompt Override Insights for the Telegram card
    active_constraint = "No negative overrides compiled. Relying on baseline rules."
    if os.path.exists(RULES_OVERRIDE_FILE):
        try:
            with open(RULES_OVERRIDE_FILE, "r") as f:
                active_constraint = json.load(f).get("identified_fault_pattern", active_constraint)
        except Exception:
            pass

    # 4. Assemble the Diagnostic Performance Card
    diagnostic_card = [
        "🔄 *AGENT SELF-EVOLUTION SYSTEM AUDIT*",
        f"📅 Date: {now.strftime('%d %b %Y')}",
        "---",
        f"📊 *Lifetime Verified Stocks:* {total_calls} assets",
        f"🎯 *System Accuracy Rate:* `{win_rate}%`",
        f"  • List A (Short-Term Win Rate): `{win_rate_a}%`",
        f"  • List B (Long-Term Win Rate): `{win_rate_b}%`",
        "---",
        "🧠 *Self-Evolved Constraint Update:*",
        f"_{active_constraint}_",
        "---",
        "⚙️ _Dynamic channel trust weights re-calibrated. Future extraction passes modified successfully._"
    ]

    payload_text = "\n".join(diagnostic_card)
    
    # 5. Broadcast to Telegram Channel using the shared reporting pipeline array format
    try:
        send_telegram([payload_text])
        logger.info("Weekly system diagnostic performance card pushed to Telegram.")
        return True
    except Exception as e:
        logger.error(f"Failed broadcasting system performance summary card: {e}")
        return False


if __name__ == "__main__":
    run_weekly_pipeline(force=True)
