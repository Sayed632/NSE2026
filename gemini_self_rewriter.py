"""
gemini_self_rewriter.py
Autonomous Prompt Engineering Layer.
Reviews system errors and writes strict heuristic constraint overrides.
"""

import os
import json
import logging
import pandas as pd
import google.generativeai as genai

logger = logging.getLogger(__name__)

PREDICTIONS_FILE    = "reports/predictions.csv"
RULES_OVERRIDE_FILE = "reports/scoring_rules_override.json"

if "GEMINI_API_KEY" in os.environ:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
MODEL = genai.GenerativeModel("gemini-1.5-flash")


def execute_meta_cognitive_rewriter():
    """Analyzes system failure rows and generates programmatic prompt behavioral adjustments."""
    if not os.path.exists(PREDICTIONS_FILE):
        logger.info("No prediction database metrics logged yet. Rewriter suspended.")
        return

    try:
        df = pd.read_csv(PREDICTIONS_FILE)
    except Exception as e:
        logger.error(f"Failed loading predictions tracking registry matrix: {e}")
        return

    if df.empty or "correct" not in df.columns:
        return

    # Isolate failures where the model assigned high conviction but the trade lost money
    system_failures = df[df["correct"] == False].tail(10)
    if system_failures.empty:
        logger.info("Zero recent system selection failures detected. Retaining current prompts.")
        return

    # Isolate confirmed multi-horizon wins to prevent over-correcting successful patterns
    system_successes = df[df["correct"] == True].tail(10)

    # Format historical failures into a clean data summary for Gemini's review
    failure_payload = []
    for _, row in system_failures.iterrows():
        failure_payload.append({
            "ticker": row["symbol"],
            "list_context": row["list_type"],
            "loss_incurred": f"{row.get('pct_change', 0)}%",
            "news_catalyst": row.get("trigger_news", "N/A")[:200]
        })

    prompt = f"""You are the core optimization compiler for an autonomous Indian stock trading agent.
Your job is to look at your own recent bad calls, analyze why your text analysis failed, and write a strict rule to prevent making that mistake again.

YOUR RECENT UNPROFITABLE SELECTIONS (FAILURES):
{json.dumps(failure_payload, indent=2)}

RECENT CONFIRMED PROFITABLE SELECTIONS (SUCCESSES TO PROTECT):
{json.dumps(system_successes[['symbol', 'list_type', 'pct_change']].to_dict('records'), indent=2)}

Task:
Identify the common theme across your recent failures (e.g., falling for speculative penny stock pumps, misinterpreting flat quarterly results, over-scoring short-term news, etc.).
Write a concise, commanding logical constraint instruction (Max 3 sentences). 
This instruction will be directly injected into your analysis engine to subtract points or skip matching assets that display these risk traits.

Expected Output Format (Strict JSON Object):
{{
  "identified_fault_pattern": "Clear explanation of the error pattern you found in your data",
  "prompt_injection": "CRITICAL NEGATIVE FILTERING RULE: If an asset displays [identified flaw], you MUST subtract 3 points from its score and label its strategy as SPECULATIVE."
}}

Rules:
- Do not use markdown code blocks, backticks, or conversational preamble.
- Output ONLY the raw JSON object.
"""

    try:
        response = MODEL.generate_content(prompt)
        
        # --- DESERIALIZER CLEANUP LAYER ---
        raw_lines = response.text.splitlines()
        clean_lines = []
        for line in raw_lines:
            strip_line = line.strip()
            if "`" in strip_line:
                continue
            if strip_line.lower() == "json":
                continue
            clean_lines.append(strip_line)
            
        clean_text = "".join(clean_lines).strip()
        
        # Validate JSON integrity before updating rules
        parsed_rules = json.loads(clean_text)
        
        os.makedirs("reports", exist_ok=True)
        with open(RULES_OVERRIDE_FILE, "w", encoding="utf-8") as f:
            json.dump(parsed_rules, f, indent=2)
            
        logger.info("Autonomous scoring prompt override file compiled and successfully saved.")
    except Exception as e:
        logger.error(f"Meta-cognitive rewriter execution lifecycle failed: {e}")


if __name__ == "__main__":
    execute_meta_cognitive_rewriter()
