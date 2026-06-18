"""
report_generator.py
Formats market intelligence outputs into structural markdown/text cards
and broadcasts payloads securely via the Telegram Bot API.
"""

import os
import logging
import requests

logger = logging.getLogger(__name__)


def build_telegram_message(structured_lists: dict, run_time_str: str) -> list[str]:
    """
    Transforms structured dataset metrics into cleanly segmented text alerts.
    Explicitly branded for distinct repository identification in busy feeds.
    """
    chunks = []
    
    # Header Segment with Unique Repository Identifier Tags
    header = [
        "🤖 *[NSE 2026 SCANNER]*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "🗞 *MARKET INTELLIGENCE REPORT*",
        f"📅 `{run_time_str}`",
        "━━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    
    # Processing Top Macro News Signals
    news_section = ["📰 *TOP ANNOUNCEMENTS / POLICIES:*"]
    top_news = structured_lists.get("top_news", [])
    if not top_news:
        news_section.append("  • _No structural macro signals captured in this cycle._")
    else:
        for idx, item in enumerate(top_news, 1):
            clean_reason = item.get("catalyst_reasoning", "Context unassigned").replace("_", "\\_").replace("*", "\\*")
            news_section.append(f"*{idx}. {item.get('ticker','UNKNOWN')}* (Score: `{item.get('score', 5)}/10`)")
            news_section.append(f"   📢 _{clean_reason}_\n")
            
    # Processing Short-Term Swing Candidates (List A)
    list_a_section = ["🚀 *LIST A: SHORT-TERM SWING / MOMENTUM*"]
    list_a = structured_lists.get("list_a", [])
    if not list_a:
        list_a_section.append("  • _No high-conviction breakout setups qualified today._\n")
    else:
        for stock in list_a:
            clean_reason = stock.get("reason", "No reason").replace("_", "\\_").replace("*", "\\*")
            list_a_section.append(f"🔹 *{stock['symbol']}* | Price: `₹{stock['price']}`")
            list_a_section.append(f"   🎯 Target Zone: `₹{stock.get('target_zone', 'N/A')}`")
            list_a_section.append(f"   ⚡ Catalyst: _{clean_reason}_\n")

    # Processing Structural Compounders (List B)
    list_b_section = ["📈 *LIST B: LONG-TERM INVESTMENT / WEALTH*"]
    list_b = structured_lists.get("list_b", [])
    if not list_b:
        list_b_section.append("  • _No structural long-term trend catalysts detected._\n")
    else:
        for stock in list_b:
            clean_reason = stock.get("reason", "No reason").replace("_", "\\_").replace("*", "\\*")
            list_b_section.append(f"🔸 *{stock['symbol']}* | Price: `₹{stock['price']}`")
            list_b_section.append(f"   ⏳ Horizon: `{stock.get('horizon_target', '12-36 Months')}`")
            list_b_section.append(f"   💡 Investment Thesis: _{clean_reason}_\n")

    # Footer Disclaimer and Repository Closing Signature
    footer = [
        "━━━━━━━━━━━━━━━━━━━━━━",
        "⚠️ _AI structural data analytics only. Not official SEBI registered investment advice._",
        "📡 *[Source Node: NSE2026/Main Engine]*"
    ]

    # Combine data components into a clean string array
    full_body = "\n".join(header + news_section + ["---"] + list_a_section + ["---"] + list_b_section + footer)
    
    # Telegram messages have a hard 4096-character limit. Chunk if exceeded.
    if len(full_body) <= 4000:
        chunks.append(full_body)
    else:
        # Fallback segmentation split logic if data runs extremely long
        chunks.append("\n".join(header + news_section))
        chunks.append("\n".join(list_a_section + ["---"] + list_b_section + footer))
        
    return chunks


def build_markdown_report(structured_lists: dict, run_time_str: str, date_str: str) -> str:
    """Compiles deep Markdown files for structural logging within GitHub workspaces."""
    report = [
        f"# Market Intelligence Analysis Report - {date_str}",
        f"**Run Execution Timestamp:** {run_time_str} (IST)",
        "",
        "## 🚀 High-Conviction Selections Matrix",
        "| Asset Ticker | Entry Price | Market Cap (Cr) | Horizon Profile | Signal Source Feed |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]
    
    for stock in structured_lists.get("list_a", []) + structured_lists.get("list_b", []):
        report.append(f"| {stock['symbol']} | ₹{stock['price']} | {stock['market_cap']} | {stock['horizon']} | {stock.get('origin_channel','Fallback Stream')} |")
        
    return "\n".join(report)


def save_markdown_report(report_content: str, date_str: str):
    """Flashes local analytical reports onto the git runner's workspace disk."""
    try:
        os.makedirs("reports", exist_ok=True)
        file_path = f"reports/Report_{date_str}.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        logger.info(f"Local Markdown backup generated successfully at: {file_path}")
    except Exception as e:
        logger.error(f"Failed to flash Markdown tracking report to git environment: {e}")


def send_telegram(message_chunks: list[str]):
    """Transmits formatted reporting chunks to the targeted Telegram chat node."""
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        logger.warning("Telegram credentials absent from environments. Broadcast skipped.")
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
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code != 200:
                logger.error(f"Telegram endpoint rejected broadcast message: {res.text}")
        except Exception as e:
            logger.error(f"Network transport error trying to hit Telegram gateway: {e}")
