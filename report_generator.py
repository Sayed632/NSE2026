"""
report_generator.py
Polished Telegram Card Compiler for the NSE 2026 Scanner Pipeline.
"""

import os
import logging
import requests

logger = logging.getLogger(__name__)

def build_telegram_message(structured_lists: dict, run_time_str: str) -> list[str]:
    chunks = []
    
    header = [
        "🤖 *[NSE 2026 SCANNER]*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "📡 *EARLY-STAGE CATALYST RADAR*",
        f"📅 `{run_time_str}`",
        "━━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    
    # 1. Actionable Short-Term Policy Breakouts
    list_a_section = ["🚀 *LIST A: POLICY & MOMENTUM BREAKOUTS*"]
    list_a = structured_lists.get("list_a", [])
    if not list_a:
        list_a_section.append("  • _No high-conviction momentum setups qualified in this cycle._\n")
    else:
        for stock in list_a:
            clean_reason = stock["reason"].replace("_", "\\_").replace("*", "\\*")
            list_a_section.append(f"🔥 *{stock['symbol']}* | Price: `₹{stock['price']}` (Score: `{stock['score']}/10`)")
            list_a_section.append(f"   🎯 Breakout Target: `₹{stock['target_zone']}`")
            list_a_section.append(f"   💡 Structural Driver: _{clean_reason}_\n")

    # 2. Medium-Term Trend Compounders
    list_b_section = ["📈 *LIST B: STRUCTURAL INDUSTRIAL TRENDS*"]
    list_b = structured_lists.get("list_b", [])
    if not list_b:
        list_b_section.append("  • _No long-term macro trend shifts detected._\n")
    else:
        for stock in list_b:
            clean_reason = stock["reason"].replace("_", "\\_").replace("*", "\\*")
            list_b_section.append(f"💎 *{stock['symbol']}* | Price: `₹{stock['price']}` (Score: `{stock['score']}/10`)")
            list_b_section.append(f"   ⏳ Horizon Strategy: `{stock['horizon']}`")
            list_b_section.append(f"   💡 Investment Thesis: _{clean_reason}_\n")

    footer = [
        "━━━━━━━━━━━━━━━━━━━━━━",
        "⚠️ _Autonomous multi-factor asset matrix tracking. Not registered financial advice._",
        "⚙️ _Feeds checked: PIB Policy, SEBI Circulars, Corporate Filings & Registry Nodes_"
    ]

    full_body = "\n".join(header + list_a_section + ["---"] + list_b_section + footer)
    
    if len(full_body) <= 4000:
        chunks.append(full_body)
    else:
        chunks.append("\n".join(header + list_a_section))
        chunks.append("\n".join(list_b_section + footer))
        
    return chunks

def send_telegram(message_chunks: list[str]):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in message_chunks:
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Telegram transport error: {e}")

def build_markdown_report(structured_lists: dict, run_time_str: str, date_str: str) -> str:
    return f"# Market Intelligence Analysis Report - {date_str}\nTimestamp: {run_time_str}"

def save_markdown_report(report_content: str, date_str: str):
    pass
