"""
report_generator.py
Builds Telegram message and markdown GitHub report.
"""

import os
import logging
import asyncio
from datetime import datetime
import pytz
from telegram import Bot
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")
MAX_TELEGRAM_MSG = 4000


def _fmt_inr(crore_val) -> str:
    try:
        val = float(crore_val)
        if val >= 100000:
            return f"₹{val/100000:.1f}L Cr"
        elif val >= 1000:
            return f"₹{val/1000:.1f}K Cr"
        return f"₹{val:.0f} Cr"
    except Exception:
        return "N/A"


def build_telegram_message(results: dict, run_time: str) -> list[str]:
    list_a   = results.get("list_a", [])
    list_b   = results.get("list_b", [])
    list_c   = results.get("list_c", [])
    top_news = results.get("top_news", [])

    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🗞 *MARKET INTELLIGENCE REPORT*")
    lines.append(f"📅 {run_time} IST")
    lines.append("🤖 NSE2026 Stock News Agent")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━\n")

    if top_news:
        lines.append("📰 *TOP NEWS TRIGGERS:*")
        for i, n in enumerate(top_news[:4], 1):
            score = n.get("score", 0)
            emoji = "🔴" if score >= 8 else "🟡" if score >= 6 else "🟢"
            title = n.get("title", "")[:90]
            lines.append(f"{emoji} {i}\\. {title}")
            lines.append(f"    _Score: {score}/10_")
        lines.append("")

    if list_a:
        lines.append("🚀 *SURGE CANDIDATES \\(Short\\-Term\\):*")
        for s in list_a:
            sym    = s['symbol'].replace('.NS','')
            price  = s['price']
            vol    = s['vol_ratio']
            tgt    = s.get('target_zone','')
            reason = s.get('reason','')[:70]
            lines.append(f"• *{sym}* @ ₹{price} | Vol: {vol}x | Target: ₹{tgt}")
            lines.append(f"  _{reason}_")
        lines.append("")
    else:
        lines.append("🚀 *SURGE CANDIDATES:* No high\\-conviction picks today\n")

    if list_b:
        lines.append("📈 *LONG\\-TERM BUY LIST:*")
        for s in list_b:
            sym    = s['symbol'].replace('.NS','')
            price  = s['price']
            mktcap = _fmt_inr(s.get('market_cap', 0))
            revg   = s.get('rev_growth', 'N/A')
            thesis = s.get('thesis','')[:70]
            lines.append(f"• *{sym}* @ ₹{price} | Cap: {mktcap} | Growth: {revg}%")
            lines.append(f"  _{thesis}_")
        lines.append("")
    else:
        lines.append("📈 *LONG\\-TERM BUY LIST:* No qualifying picks today\n")

    if list_c:
        lines.append("🔴 *AVOID / NEGATIVE IMPACT:*")
        for s in list_c:
            sym    = s['symbol'].replace('.NS','')
            reason = s.get('reason','')[:70]
            lines.append(f"• *{sym}* — _{reason}_")
        lines.append("")

    lines.append("⚠️ _AI research only\\. Not SEBI registered advice\\._")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    full_text = "\n".join(lines)
    chunks    = []
    current   = ""
    for line in lines:
        if len(current) + len(line) + 1 > MAX_TELEGRAM_MSG:
            chunks.append(current)
            current = line
        else:
            current += "\n" + line
    if current:
        chunks.append(current)

    return chunks if chunks else [full_text]


def build_markdown_report(results: dict, run_time: str, date_str: str) -> str:
    list_a   = results.get("list_a", [])
    list_b   = results.get("list_b", [])
    list_c   = results.get("list_c", [])
    top_news = results.get("top_news", [])

    lines = []
    lines.append(f"# Market Intelligence Report — {date_str}\n")
    lines.append(f"**Generated:** {run_time} IST\n")
    lines.append("---\n")

    lines.append("## Top News Triggers\n")
    if top_news:
        lines.append("| # | Source | Headline | Score |")
        lines.append("|---|--------|----------|-------|")
        for i, n in enumerate(top_news, 1):
            src   = n.get("source","")[:20]
            title = n.get("title","")[:80]
            score = n.get("score", 0)
            lines.append(f"| {i} | {src} | {title} | {score}/10 |")
    lines.append("")

    lines.append("## List A — Surge Candidates\n")
    if list_a:
        lines.append("| Symbol | Price | Vol Ratio | Target | Reason |")
        lines.append("|--------|-------|-----------|--------|--------|")
        for s in list_a:
            sym    = s['symbol'].replace('.NS','')
            lines.append(
                f"| **{sym}** | ₹{s['price']} | {s['vol_ratio']}x "
                f"| ₹{s.get('target_zone','')} | {s.get('reason','')[:60]} |"
            )
    else:
        lines.append("_No surge candidates today._\n")

    lines.append("\n## List B — Long-Term Buys\n")
    if list_b:
        lines.append("| Symbol | Price | Market Cap | Rev Growth | Thesis |")
        lines.append("|--------|-------|-----------|-----------|--------|")
        for s in list_b:
            sym = s['symbol'].replace('.NS','')
            lines.append(
                f"| **{sym}** | ₹{s['price']} | {_fmt_inr(s.get('market_cap',0))} "
                f"| {s.get('rev_growth','N/A')}% | {s.get('thesis','')[:60]} |"
            )
    else:
        lines.append("_No long-term candidates today._\n")

    lines.append("\n## List C — Avoid\n")
    if list_c:
        lines.append("| Symbol | Reason |")
        lines.append("|--------|--------|")
        for s in list_c:
            sym = s['symbol'].replace('.NS','')
            lines.append(f"| {sym} | {s.get('reason','')[:80]} |")
    else:
        lines.append("_No negative impact stocks today._\n")

    lines.append("\n---")
    lines.append("> AI research only. Not SEBI registered advice.")

    return "\n".join(lines)


def save_markdown_report(content: str, date_str: str) -> str:
    os.makedirs("reports", exist_ok=True)
    filename = f"reports/report_{date_str}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Markdown report saved: {filename}")
    return filename


async def _send_telegram_async(messages: list[str]) -> bool:
    token   = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.warning("Telegram credentials not set.")
        return False

    bot = Bot(token=token)
    try:
        for msg in messages:
            await bot.send_message(
                chat_id=chat_id,
                text=msg,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            await asyncio.sleep(1)
        logger.info(f"Sent {len(messages)} Telegram message(s).")
        return True
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        try:
            plain = messages[0].replace("*","").replace("_","").replace("\\","")
            await bot.send_message(chat_id=chat_id, text=plain[:4000])
            return True
        except Exception as e2:
            logger.error(f"Telegram fallback failed: {e2}")
            return False


def send_telegram(messages: list[str]) -> bool:
    return asyncio.run(_send_telegram_async(messages))
