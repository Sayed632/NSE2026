"""
pattern_memory.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 2 — Component 2: News Pattern Memory
"""

import os
import json
import re
import logging
import time
import pandas as pd
import google.generativeai as genai
from datetime import datetime
import pytz

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")

PREDICTIONS_FILE  = "reports/predictions.csv"
PATTERN_FILE      = "reports/pattern_memory.json"
MIN_CONFIDENCE    = 2

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
MODEL = genai.GenerativeModel("gemini-1.5-flash")


def _call_gemini(prompt: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            return MODEL.generate_content(prompt).text.strip()
        except Exception as e:
            logger.warning(f"Gemini call failed (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)
    return ""


def _extract_keywords(text: str) -> list[str]:
    stopwords = {"the","a","an","is","are","was","were","of","in","on","at",
                 "to","for","and","or","with","by","from","has","have","will",
                 "its","this","that","these","those","india","indian","nse","bse"}
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    return [w for w in words if w not in stopwords][:8]


def update_pattern_memory() -> int:
    if not os.path.exists(PREDICTIONS_FILE):
        return 0

    df      = pd.read_csv(PREDICTIONS_FILE)
    correct = df[(df["correct"] == True) & (df["pct_change"].notna())].copy()

    if correct.empty:
        logger.info("No correct predictions to extract patterns from yet.")
        return 0

    memory = {}
    if os.path.exists(PATTERN_FILE):
        try:
            with open(PATTERN_FILE) as f:
                memory = json.load(f)
        except Exception:
            memory = {}

    updated = 0

    for _, row in correct.iterrows():
        symbol     = row["symbol"]
        trigger    = str(row.get("trigger_news", ""))
        pct_change = float(row.get("pct_change", 0))
        list_type  = row.get("list_type", "")
        date       = row.get("date_predicted", "")

        if not trigger or len(trigger) < 10:
            continue

        keywords    = _extract_keywords(trigger)
        if not keywords:
            continue

        pattern_key = f"{'+'.join(sorted(keywords[:3]))}::{symbol}"

        if pattern_key not in memory:
            memory[pattern_key] = {
                "symbol":           symbol,
                "keywords":         keywords[:5],
                "trigger_examples": [],
                "occurrences":      0,
                "avg_gain_pct":     0.0,
                "list_type":        list_type,
                "confidence":       "low",
                "last_seen":        date,
            }

        entry = memory[pattern_key]
        n     = entry["occurrences"]
        avg   = entry["avg_gain_pct"]
        entry["avg_gain_pct"]  = round((avg * n + pct_change) / (n + 1), 2)
        entry["occurrences"]  += 1
        entry["last_seen"]     = date

        if trigger[:100] not in entry["trigger_examples"]:
            entry["trigger_examples"].append(trigger[:100])
            entry["trigger_examples"] = entry["trigger_examples"][-3:]

        occ = entry["occurrences"]
        entry["confidence"] = (
            "high"   if occ >= 5 else
            "medium" if occ >= MIN_CONFIDENCE else
            "low"
        )
        updated += 1

    if updated > 0:
        os.makedirs("reports", exist_ok=True)
        with open(PATTERN_FILE, "w") as f:
            json.dump(memory, f, indent=2)
        logger.info(f"Pattern memory updated: {updated} patterns added/reinforced.")

    return updated


def get_pattern_boost(news_headline: str, symbol: str) -> float:
    if not os.path.exists(PATTERN_FILE):
        return 0.0

    try:
        with open(PATTERN_FILE) as f:
            memory = json.load(f)
    except Exception:
        return 0.0

    news_keywords = set(_extract_keywords(news_headline))
    best_boost    = 0.0

    for pattern_key, entry in memory.items():
        if entry["symbol"] != symbol:
            continue
        pattern_kws = set(entry.get("keywords", []))
        overlap     = len(news_keywords & pattern_kws)

        if overlap >= 2:
            conf  = entry.get("confidence", "low")
            boost = {"high": 2.5, "medium": 1.5, "low": 1.0}.get(conf, 0.0)
            if boost > best_boost:
                best_boost = boost

    return best_boost


def get_memory_context_for_prompt() -> str:
    if not os.path.exists(PATTERN_FILE):
        return ""

    try:
        with open(PATTERN_FILE) as f:
            memory = json.load(f)
    except Exception:
        return ""

    strong = [
        v for v in memory.values()
        if v.get("confidence") in ("high", "medium")
    ]

    if not strong:
        return ""

    lines = ["VERIFIED HISTORICAL PATTERNS (from past correct predictions):"]
    for p in sorted(strong, key=lambda x: -x["occurrences"])[:12]:
        sym  = p["symbol"].replace(".NS", "")
        kws  = ", ".join(p["keywords"][:4])
        gain = p["avg_gain_pct"]
        occ  = p["occurrences"]
        conf = p["confidence"]
        lines.append(
            f"  - News with [{kws}] → {sym} gained avg {gain:+.1f}% "
            f"({occ}x, {conf} confidence)"
        )

    return "\n".join(lines)


def save_pattern_report() -> None:
    if not os.path.exists(PATTERN_FILE):
        return

    with open(PATTERN_FILE) as f:
        memory = json.load(f)

    now_str = datetime.now(IST).strftime("%d %b %Y %I:%M %p")
    lines   = [f"# Pattern Memory Report\n**Updated:** {now_str} IST\n"]

    for conf_level in ("high", "medium", "low"):
        group = [v for v in memory.values() if v.get("confidence") == conf_level]
        if not group:
            continue
        emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}[conf_level]
        lines.append(f"\n## {emoji} {conf_level.upper()} Confidence Patterns\n")
        lines.append("| Stock | Keywords | Avg Gain | Times Seen | Last Seen |")
        lines.append("|-------|----------|----------|------------|-----------|")
        for p in sorted(group, key=lambda x: -x["avg_gain_pct"]):
            sym  = p["symbol"].replace(".NS","")
            kws  = ", ".join(p["keywords"][:4])
            gain = p["avg_gain_pct"]
            occ  = p["occurrences"]
            last = p["last_seen"]
            lines.append(f"| **{sym}** | {kws} | +{gain:.1f}% | {occ} | {last} |")

    with open("reports/pattern_memory_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info("Pattern memory report saved.")
