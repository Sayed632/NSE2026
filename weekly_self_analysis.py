"""
weekly_self_analysis.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 2 — Component 3: Weekly Gemini Self-Analysis Report
"""

import os
import json
import logging
import time
import pandas as pd
import google.generativeai as genai
from datetime import datetime, timedelta
import pytz
import asyncio
from telegram import Bot
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")

PREDICTIONS_FILE    = "reports/predictions.csv"
WEIGHTS_FILE        = "reports/accuracy_weights.json"
PATTERN_FILE        = "reports/pattern_memory.json"
RULES_OVERRIDE_FILE = "reports/scoring_rules_override.json"

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
MODEL = genai.GenerativeModel("gemini-1.5-flash")


def _call_gemini(prompt: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            return MODEL.generate_content(prompt).text.strip()
        except Exception as e:
            logger.warning(f"Gemini attempt {attempt+1} failed: {e}")
            time.sleep(2 ** attempt)
    return ""


def _load_file(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def _get_week_label() -> str:
    return datetime.now(IST).strftime("%Y-W%W")


def _is_monday() -> bool:
    return datetime.now(IST).weekday() == 0


def generate_weekly_report(force: bool = False) -> str | None:
    if not force and not _is_monday():
        logger.info("Weekly analysis runs on Mondays only. Skipping.")
        return None

    if not os.path.exists(PREDICTIONS_FILE):
        logger.info("No predictions data yet for weekly analysis.")
        return None

    df = pd.read_csv(PREDICTIONS_FILE)
    if df.empty:
        return None

    evaluated = df[df["correct"].notna()].copy()
    pending   = df[df["correct"].isna()].copy()

    today    = datetime.now(IST).date()
    week_ago = today - timedelta(days=7)
    df["date_predicted"] = pd.to_datetime(df["date_predicted"])
    this_week = evaluated[
        evaluated["date_predicted"].dt.date >= week_ago
    ]

    total_all    = len(evaluated)
    correct_all  = int(evaluated["correct"].sum())
    acc_all      = round(correct_all / total_all * 100, 1) if total_all > 0 else 0

    total_week   = len(this_week)
    correct_week = int(this_week["correct"].sum()) if total_week > 0 else 0
    acc_week     = round(correct_week / total_week * 100, 1) if total_week > 0 else 0

    weights  = _load_file(WEIGHTS_FILE, {})
    patterns = _load_file(PATTERN_FILE, {})
    rules    = _load_file(RULES_OVERRIDE_FILE, {})

    wrong_week = this_week[this_week["correct"] == False][
        ["symbol","trigger_news","pct_change","list_type"]
    ].head(8).to_dict("records")

    right_week = this_week[this_week["correct"] == True].sort_values(
        "pct_change", ascending=False
    )[["symbol","trigger_news","pct_change","list_type"]].head(5).to_dict("records")

    strong_patterns = sorted(
        [v for v in patterns.values() if v.get("confidence") in ("high","medium")],
        key=lambda x: (-x["occurrences"], -x["avg_gain_pct"])
    )[:6]

    weights_table = "\n".join(
        f"  {s}: {w}" for s, w in sorted(weights.items(), key=lambda x: -x[1])
    ) if weights else "  (not yet generated)"

    prompt = f"""You are an AI stock analyst reviewing your own weekly performance
for Indian NSE stocks.

PERFORMANCE:
All-time accuracy : {acc_all}% ({correct_all}/{total_all})
This week accuracy: {acc_week}% ({correct_week}/{total_week})
Pending predictions: {len(pending)}

THIS WEEK WRONG CALLS:
{json.dumps(wrong_week, indent=2)}

THIS WEEK CORRECT CALLS:
{json.dumps(right_week, indent=2)}

SECTOR WEIGHTS:
{weights_table}

TOP PATTERNS:
{json.dumps(strong_patterns[:4], indent=2)}

CURRENT RULE:
{rules.get("prompt_injection", "None yet")}

Write weekly self-analysis with these sections:

## This Week in Numbers
## What Worked This Week
## What Failed This Week
## Emerging Pattern Discoveries
## What I'm Changing Next Week
## Sectors to Watch Next Week

Be specific, honest, data-driven. Max 500 words. First person as AI agent.
"""

    logger.info("Generating weekly self-analysis...")
    analysis = _call_gemini(prompt)

    if not analysis:
        return None

    week_label = _get_week_label()
    now_str    = datetime.now(IST).strftime("%d %b %Y %I:%M %p")

    sector_lines = ["| Sector | Weight | Trust |", "|--------|--------|-------|"]
    for sector, w in sorted(weights.items(), key=lambda x: -x[1])[:10]:
        trust = "🟢 High" if w >= 1.3 else "🟡 Medium" if w >= 0.9 else "🔴 Low"
        sector_lines.append(f"| {sector} | {w} | {trust} |")

    md = f"""# Weekly Self-Analysis — {week_label}
**Generated:** {now_str} IST
**All-time accuracy:** {acc_all}% | **This week:** {acc_week}%

---

{analysis}

---

## Sector Trust Levels

{chr(10).join(sector_lines)}

---

## Pattern Memory Snapshot

| Stock | Keywords | Avg Gain | Confidence | Seen |
|-------|----------|----------|------------|------|
"""
    for p in strong_patterns[:8]:
        sym  = p["symbol"].replace(".NS","")
        kws  = ", ".join(p["keywords"][:3])
        gain = p["avg_gain_pct"]
        conf = p["confidence"]
        occ  = p["occurrences"]
        md  += f"| **{sym}** | {kws} | +{gain:.1f}% | {conf} | {occ}x |\n"

    md += "\n> AI self-analysis only. Not SEBI investment advice.\n"

    os.makedirs("reports", exist_ok=True)
    filename = f"reports/weekly_analysis_{week_label}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(md)
    logger.info(f"Weekly analysis saved: {filename}")

    return md


async def _send_telegram_async(message: str) -> bool:
    token   = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False
    try:
        bot = Bot(token=token)
        await bot.send_message(
            chat_id=chat_id,
            text=message[:4000],
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return True
    except Exception as e:
        logger.error(f"Weekly Telegram send failed: {e}")
        try:
            plain = message.replace("*","").replace("_","").replace("\\","")
            await bot.send_message(chat_id=chat_id, text=plain[:4000])
            return True
        except Exception:
            return False


def send_weekly_telegram(md_content: str, force: bool = False) -> bool:
    if not force and not _is_monday():
        return False
    if not md_content:
        return False
    return asyncio.run(_send_telegram_async(md_content[:4000]))


def run_weekly_pipeline(force: bool = False) -> bool:
    md = generate_weekly_report(force=force)
    if md:
        send_weekly_telegram(md, force=force)
        return True
    return False
