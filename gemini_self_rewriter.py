"""
gemini_self_rewriter.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 2 — Component 1: Gemini Self-Rewrite of Scoring Rules

What it does:
  - Reads predictions.csv (all evaluated outcomes)
  - Reads accuracy_weights.json (current sector weights)
  - Feeds both to Gemini and asks: "What did you get wrong and why?"
  - Gemini produces:
      a) A written diagnosis of failure patterns
      b) An updated sector-scoring prompt injection
         (stored in reports/scoring_rules_override.json)
  - Next time classify_and_score_news() runs, it loads this
    override and injects it into the Gemini scoring prompt
    so the model literally uses its own lessons

Activation: auto-runs when >= 20 evaluated predictions exist
            AND it's Monday (weekly rewrite cadence)
            OR forced via --force flag
"""

import os
import json
import logging
import time
import pandas as pd
import google.generativeai as genai
from datetime import datetime
import pytz

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")

PREDICTIONS_FILE    = "reports/predictions.csv"
WEIGHTS_FILE        = "reports/accuracy_weights.json"
RULES_OVERRIDE_FILE = "reports/scoring_rules_override.json"
SELF_ANALYSIS_FILE  = "reports/gemini_self_analysis.md"
MIN_EVALUATED       = 20

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
MODEL = genai.GenerativeModel("gemini-1.5-flash")


def _call_gemini(prompt: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            response = MODEL.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.warning(f"Gemini call failed (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)
    return ""


def _load_evaluated_predictions() -> pd.DataFrame | None:
    if not os.path.exists(PREDICTIONS_FILE):
        logger.info("No predictions file found yet.")
        return None
    df = pd.read_csv(PREDICTIONS_FILE)
    evaluated = df[df["correct"].notna()].copy()
    if len(evaluated) < MIN_EVALUATED:
        logger.info(
            f"Only {len(evaluated)} evaluated rows — need {MIN_EVALUATED} to run self-rewrite."
        )
        return None
    return evaluated


def _load_current_weights() -> dict:
    if os.path.exists(WEIGHTS_FILE):
        with open(WEIGHTS_FILE) as f:
            return json.load(f)
    return {}


def _is_monday() -> bool:
    return datetime.now(IST).weekday() == 0


def run_gemini_self_rewrite(force: bool = False) -> bool:
    if not force and not _is_monday():
        logger.info("Self-rewrite runs on Mondays only. Skipping today.")
        return False

    evaluated = _load_evaluated_predictions()
    if evaluated is None:
        return False

    weights = _load_current_weights()

    correct_df   = evaluated[evaluated["correct"] == True]
    incorrect_df = evaluated[evaluated["correct"] == False]

    wrong_samples = incorrect_df[["symbol", "list_type", "trigger_news",
                                   "pct_change", "date_predicted"]].head(15).to_dict("records")
    right_samples = correct_df[["symbol", "list_type", "trigger_news",
                                  "pct_change", "date_predicted"]].head(10).to_dict("records")

    total     = len(evaluated)
    n_correct = int(evaluated["correct"].sum())
    accuracy  = round(n_correct / total * 100, 1)

    weights_str = json.dumps(weights, indent=2)
    wrong_str   = json.dumps(wrong_samples, indent=2)
    right_str   = json.dumps(right_samples, indent=2)

    diagnosis_prompt = f"""You are an AI stock analyst reviewing your own prediction record for Indian NSE stocks.

OVERALL ACCURACY: {accuracy}% ({n_correct}/{total} correct)

CURRENT SECTOR WEIGHTS (higher = more trusted signal):
{weights_str}

WRONG PREDICTIONS (these stocks did NOT move as expected):
{wrong_str}

CORRECT PREDICTIONS (these worked well):
{right_str}

Your task:
1. Identify 3-5 specific PATTERNS in the wrong predictions
2. Identify 2-3 patterns in the CORRECT predictions that should be reinforced
3. Write a concise diagnosis (max 300 words)

Format your response as:

### FAILURE PATTERNS
[list patterns]

### SUCCESS PATTERNS
[list patterns]

### DIAGNOSIS
[paragraph]

### RECOMMENDED SCORING ADJUSTMENTS
[specific rules]
"""

    logger.info("Running Gemini self-diagnosis on prediction history...")
    diagnosis = _call_gemini(diagnosis_prompt)
    time.sleep(2)

    rules_prompt = f"""Based on this diagnosis of Indian stock prediction accuracy:

{diagnosis}

Generate a JSON object of scoring rule OVERRIDES.
Return ONLY valid JSON in this exact structure:
{{
  "generated_at": "{datetime.now(IST).strftime('%Y-%m-%d')}",
  "overall_accuracy": {accuracy},
  "sector_score_adjustments": {{
    "SectorName": <integer -3 to +3>
  }},
  "conditional_rules": [
    "<rule as plain English, max 80 chars>"
  ],
  "boost_news_types": [
    "<news type that gave correct signals>"
  ],
  "penalise_news_types": [
    "<news type that gave wrong signals>"
  ],
  "prompt_injection": "<2-3 sentence instruction to inject into scoring prompt>"
}}
Return ONLY the JSON object, no markdown, no preamble.
"""

    logger.info("Generating scoring rules override JSON...")
    raw_rules = _call_gemini(rules_prompt)
    time.sleep(1)

    try:
        clean = raw_rules.replace("```json", "").replace("```", "").strip()
        rules = json.loads(clean)
        os.makedirs("reports", exist_ok=True)
        with open(RULES_OVERRIDE_FILE, "w") as f:
            json.dump(rules, f, indent=2)
        logger.info(f"Scoring rules override saved: {RULES_OVERRIDE_FILE}")
    except Exception as e:
        logger.error(f"Failed to parse rules JSON: {e}")
        rules = {}

    now_str = datetime.now(IST).strftime("%d %b %Y %I:%M %p")
    md = f"""# Gemini Self-Analysis Report
**Generated:** {now_str} IST
**Evaluated Predictions:** {total}
**Overall Accuracy:** {accuracy}%

---

## Diagnosis

{diagnosis}

---

## Scoring Rules Override

```json
{json.dumps(rules, indent=2)}
