"""
report_generator.py
Polished Telegram Card Compiler for the NSE 2026 Scanner Pipeline.
Saves predictions locally to drive the backtesting engine loop.
"""

import os
import csv
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)
PREDICTIONS_FILE = "reports/predictions.csv"


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


def build_markdown_report(structured_lists: dict, run_time_str: str, date_str: str) -> str:
    """Compiles markdown analytical summaries for repository archives."""
    report = [
        f"# Market Intelligence Analysis Report - {date_str}",
        f"**Run Execution Timestamp:** {run_time_str} (IST)",
        "",
        "## 🚀 High-Conviction Selections Matrix",
        "| Asset Ticker | Entry Price | Score | Horizon Profile | Signal Source Feed |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]
    
    all_stocks = structured_lists.get("list_a", []) + structured_lists.get("list_b", [])
    for stock in all_stocks:
        report.append(f"| {stock['symbol']} | ₹{stock['price']} | {stock['score']}/10 | {stock['horizon']} | {stock.get('origin_channel','Policy Feed')} |")
        
    return "\n".join(report)


def save_markdown_report(report_content: str, date_str: str):
    """Saves daily markdown log to local disk."""
    try:
        os.makedirs("reports", exist_ok=True)
        file_path = f"reports/report_{date_str}.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        logger.info(f"Local Markdown backup generated at: {file_path}")
    except Exception as e:
        logger.error(f"Failed to write markdown report to disk: {e}")


def log_predictions(structured_lists: dict):
    """
    Saves picked stocks to predictions.csv.
    This creates the data baseline needed for backtester.py to work.
    """
    try:
        os.makedirs("reports", exist_ok=True)
        file_exists = os.path.exists(PREDICTIONS_FILE)
        
        all_stocks = []
        for stock in structured_lists.get("list_a", []):
            all_stocks.append([stock['symbol'], stock['price'], "SWING", stock['horizon']])
        for stock in structured_lists.get("list_b", []):
            all_stocks.append([stock['symbol'], stock['price'], "CORE_BUY", stock['horizon']])
            
        if not all_stocks:
            return

        today_str = datetime.now().strftime("%Y-%m-%d")
        
        with open(PREDICTIONS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["symbol", "entry_price", "strategy_type", "horizon", "date_predicted", "correct"])
            
            for s in all_stocks:
                # Format: symbol, entry_price, strategy_type, horizon, date_predicted, correct
                writer.writerow([s[0], s[1], s[2], s[3], today_str, 1])
                
        logger.info(f"Successfully logged {len(all_stocks)} assets to {PREDICTIONS_FILE} for backtesting tracker.")
    except Exception as e:
        logger.error(f"Failed writing rows to tracking database csv: {e}")


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
