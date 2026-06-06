"""
report_generator.py
Builds two outputs:
  1. Telegram message (concise, mobile-friendly)
  2. Full markdown report saved to reports/report_YYYY-MM-DD.md
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

MAX_TELEGRAM_MSG = 4000  # Telegram limit is 4096 chars per message


def _fmt_inr(crore_val) -> str:
    """Format market cap in crore with readable suffix."""
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
    """
    Build Telegram-friendly message(s).
    Splits into multiple messages if content exceeds 4000 chars.
    Returns list of message strings.
    """
    list_a   = results.get("list_a", [])
    list_b   = results.get("list_b", [])
    list_c   = results.get("list_c", [])
    top_news = results.get("top_news", [])

    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🗞 *MARKET INTELLIGENCE REPORT*")
    lines.append(f"📅 {run_time} IST")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━\n")

    # Top news triggers
    if top_news:
        lines.append("📰 *TOP NEWS TRIGGERS:*")
        for i, n in enumerate(top_news[:4], 1):
            score = n.get("score", 0)
            emoji = "🔴" if score >= 8 else "🟡" if score >= 6 else "🟢"
            title = n.get("title", "")[:90]
            lines.append(f"{emoji} {i}\\. {title}")
            lines.append(f"    _Score: {score}/10 | {n.get('reason','')[:80]}_")
        lines.append("")

    # List A — Surge candidates
    if list_a:
        lines.append("🚀 *SURGE CANDIDATES \\(Short\\-Term\\):*")
        for s in list_a:
            sym   = s['symbol'].replace('.NS','')
            price = s['price']
            vol   = s['vol_ratio']
            tgt   = s.get('target_zone','')
            reason = s.get('reason','')[:70]
            lines.append(
                f"• *{sym}* @ ₹{price} | Vol: {vol}x | Target: ₹{tgt}"
            )
            lines.append(f"  _{reason}_")
        lines.append("")
    else:
        lines.append("🚀 *SURGE CANDIDATES:* No high-conviction picks today\n")

    # List B — Long-term buys
    if list_b:
        lines.append("📈 *LONG\\-TERM BUY LIST:*")
        for s in list_b:
            sym    = s['symbol'].replace('.NS','')
            price  = s['price']
            mktcap = _fmt_inr(s.get('market_cap', 0))
            revg   = s.get('rev_growth', 'N/A')
            thesis = s.get('thesis','')[:70]
            lines.append(f"• *{sym}* @ ₹{price} | Mkt Cap: {mktcap} | Rev Growth: {revg}%")
            lines.append(f"  _{thesis}_")
        lines.append("")
    else:
        lines.append("📈 *LONG\\-TERM BUY LIST:* No qualifying picks today\n")

    # List C — Negative
    if list_c:
        lines.append("🔴 *AVOID / NEGATIVE IMPACT:*")
        for s in list_c:
            sym    = s['symbol'].replace('.NS','')
            reason = s.get('reason','')[:70]
            lines.append(f"• *{sym}* — _{reason}_")
        lines.append("")

    lines.append("⚠️ _AI research only\\. Not SEBI registered advice\\._")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    # Split into chunks if too long
    full_text  = "\n".join(lines)
    chunks     = []
    current    = ""
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
    """Build a full markdown report for GitHub Actions artifact."""
    list_a   = results.get("list_a", [])
    list_b   = results.get("list_b", [])
    list_c   = results.get("list_c", [])
    top_news = results.get("top_news", [])

    lines = []
    lines.append(f"# 📊 Market Intelligence Report — {date_str}\n")
    lines.append(f"**Generated:** {run_time} IST  \n")
    lines.append(f"**Stock Universe:** All NSE-listed stocks  \n")
    lines.append(f"**Sources:** NSE/BSE, PIB, MoF, Economic Times, Moneycontrol\n")
    lines.append("---\n")

    # News section
    lines.append("## 📰 Top News Triggers\n")
    if top_news:
        lines.append("| # | Source | Headline | Score | Sectors Positive | Sectors Negative |")
        lines.append("|---|--------|----------|-------|-----------------|-----------------|")
        for i, n in enumerate(top_news, 1):
            src   = n.get("source","")[:20]
            title = n.get("title","")[:80]
            score = n.get("score", 0)
            sp    = ", ".join(n.get("sectors_positive",[]))[:40]
            sn    = ", ".join(n.get("sectors_negative",[]))[:40]
            lines.append(f"| {i} | {src} | {title} | {score}/10 | {sp} | {sn} |")
    else:
        lines.append("_No high-impact news found today._")
    lines.append("")

    # List A
    lines.append("## 🚀 List A — Short-Term Surge Candidates\n")
    lines.append("> Criteria: Near 52-week high, volume buildup > 1.3x, above 200 DMA\n")
    if list_a:
        lines.append("| Symbol | Price (₹) | Market Cap | Vol Ratio | % from 52W High | Target Zone | Trigger News |")
        lines.append("|--------|-----------|-----------|-----------|-----------------|-------------|--------------|")
        for s in list_a:
            sym    = s['symbol'].replace('.NS','')
            price  = s['price']
            mktcap = _fmt_inr(s.get('market_cap',0))
            vol    = s['vol_ratio']
            p52    = s['pct_from_52h']
            tgt    = s.get('target_zone','')
            news   = s.get('trigger_news','')[:60]
            lines.append(f"| **{sym}** | ₹{price} | {mktcap} | {vol}x | -{p52}% | ₹{tgt} | {news} |")
        lines.append("")
        lines.append("### Individual Analysis\n")
        for s in list_a:
            sym = s['symbol'].replace('.NS','')
            lines.append(f"#### {sym}")
            lines.append(f"- **Price:** ₹{s['price']} | **Target Zone:** ₹{s.get('target_zone','')}")
            lines.append(f"- **Volume Ratio:** {s['vol_ratio']}x (20-day avg)")
            lines.append(f"- **Distance from 52W High:** -{s['pct_from_52h']}%")
            lines.append(f"- **Reason:** {s.get('reason','')}")
            lines.append(f"- **Trigger News:** {s.get('trigger_news','')}")
            lines.append(f"- **Risk:** {s.get('risk','')}\n")
    else:
        lines.append("_No surge candidates identified today._\n")

    # List B
    lines.append("## 📈 List B — Long-Term Buy Candidates\n")
    lines.append("> Criteria: Revenue growth >15% YoY, D/E <1, Market Cap <₹20,000 Cr, structural sector tailwind\n")
    if list_b:
        lines.append("| Symbol | Price (₹) | Market Cap | Rev Growth | D/E | Horizon | Thesis |")
        lines.append("|--------|-----------|-----------|-----------|-----|---------|--------|")
        for s in list_b:
            sym    = s['symbol'].replace('.NS','')
            price  = s['price']
            mktcap = _fmt_inr(s.get('market_cap',0))
            revg   = s.get('rev_growth','N/A')
            de     = s.get('de_ratio','N/A')
            thesis = s.get('thesis','')[:60]
            lines.append(f"| **{sym}** | ₹{price} | {mktcap} | {revg}% | {de} | {s.get('horizon','')} | {thesis} |")
        lines.append("")
        lines.append("### Individual Analysis\n")
        for s in list_b:
            sym = s['symbol'].replace('.NS','')
            lines.append(f"#### {sym}")
            lines.append(f"- **Price:** ₹{s['price']} | **Market Cap:** {_fmt_inr(s.get('market_cap',0))}")
            lines.append(f"- **Revenue Growth:** {s.get('rev_growth','N/A')}% YoY")
            lines.append(f"- **Debt/Equity:** {s.get('de_ratio','N/A')}")
            lines.append(f"- **Investment Thesis:** {s.get('thesis','')}")
            lines.append(f"- **Catalysts:** {s.get('catalysts','')}")
            lines.append(f"- **Time Horizon:** {s.get('horizon','')}")
            lines.append(f"- **Risk Factors:** {s.get('risk','')}\n")
    else:
        lines.append("_No long-term candidates identified today._\n")

    # List C
    lines.append("## 🔴 List C — Negative Impact / Avoid\n")
    if list_c:
        lines.append("| Symbol | Price (₹) | Reason | News | Duration |")
        lines.append("|--------|-----------|--------|------|----------|")
        for s in list_c:
            sym    = s['symbol'].replace('.NS','')
            reason = s.get('reason','')[:60]
            news   = s.get('news','')[:60]
            dur    = s.get('duration','')
            lines.append(f"| {sym} | ₹{s['price']} | {reason} | {news} | {dur} |")
    else:
        lines.append("_No negative impact stocks identified today._\n")

    lines.append("\n---")
    lines.append("## ⚙️ Agent Metadata\n")
    lines.append(f"- **Run time:** {run_time} IST")
    lines.append(f"- **List A picks:** {len(list_a)}")
    lines.append(f"- **List B picks:** {len(list_b)}")
    lines.append(f"- **List C stocks:** {len(list_c)}")
    lines.append(f"- **Top news items evaluated:** {len(top_news)}")
    lines.append("\n> ⚠️ **Disclaimer:** This report is generated by an AI agent for research purposes only.")
    lines.append("> It is NOT SEBI-registered investment advice. Always do your own due diligence.\n")

    return "\n".join(lines)


def save_markdown_report(content: str, date_str: str) -> str:
    """Save markdown report to reports/ folder."""
    os.makedirs("reports", exist_ok=True)
    filename = f"reports/report_{date_str}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Markdown report saved: {filename}")
    return filename


async def _send_telegram_async(messages: list[str]) -> bool:
    """Send messages to Telegram asynchronously."""
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.warning("Telegram credentials not set — skipping Telegram delivery.")
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
        # Try plain text fallback
        try:
            plain = messages[0].replace("*","").replace("_","").replace("\\","")
            await bot.send_message(chat_id=chat_id, text=plain[:4000])
            logger.info("Sent Telegram fallback plain text.")
            return True
        except Exception as e2:
            logger.error(f"Telegram fallback also failed: {e2}")
            return False


def send_telegram(messages: list[str]) -> bool:
    """Sync wrapper for async Telegram send."""
    return asyncio.run(_send_telegram_async(messages))
          
