"""
stock_analyzer.py
Uses Gemini AI to:
  1. Classify and score each news item
  2. Map news → sectors → NSE stocks
  3. Produce List A (surge), List B (long-term), List C (negative)
Also handles Phase 2 self-learning weight loading.
"""

import os
import json
import logging
import time
import pandas as pd
import yfinance as yf
import google.generativeai as genai
from datetime import datetime
import pytz

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")

# ── Gemini setup ──────────────────────────────────────────────────────────────
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
MODEL = genai.GenerativeModel("gemini-1.5-flash")

# ── Sector → representative NSE symbols map ───────────────────────────────────
# This is a seed map; Gemini will expand it dynamically based on news
SECTOR_SEED_STOCKS = {
    "Defence":          ["HAL.NS","BEL.NS","BDL.NS","ZENTEC.NS","ASTRAZEN.NS",
                         "DATAPATTNS.NS","MTAR.NS","GRSE.NS","COCHINSHIP.NS",
                         "PARAS.NS","AXISCADES.NS"],
    "Banking":          ["HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","KOTAKBANK.NS",
                         "AXISBANK.NS","BANKBARODA.NS","FEDERALBNK.NS","IDFCFIRSTB.NS"],
    "NBFC":             ["BAJFINANCE.NS","CHOLAFIN.NS","MUTHOOTFIN.NS","MANAPPURAM.NS",
                         "LTFH.NS","PNBHOUSING.NS"],
    "IT":               ["TCS.NS","INFY.NS","WIPRO.NS","HCLTECH.NS","TECHM.NS",
                         "PERSISTENT.NS","COFORGE.NS","MPHASIS.NS","LTIM.NS"],
    "Pharma":           ["SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS","DIVISLAB.NS",
                         "AUROPHARMA.NS","IPCA.NS","ALKEM.NS","GRANULES.NS"],
    "Infrastructure":   ["LT.NS","NBCC.NS","IRCON.NS","KEC.NS","KALPATPOWR.NS",
                         "PNCINFRA.NS","HG.NS","AHLUCONT.NS"],
    "Steel & Metals":   ["TATASTEEL.NS","JSWSTEEL.NS","SAIL.NS","HINDALCO.NS",
                         "NATIONALUM.NS","NMDC.NS","MOIL.NS"],
    "Cement":           ["ULTRACEMCO.NS","SHREECEM.NS","AMBUJACEM.NS","ACC.NS",
                         "DALBHARAT.NS","JKCEMENT.NS","RAMCOCEM.NS"],
    "Energy & Power":   ["NTPC.NS","POWERGRID.NS","TATAPOWER.NS","ADANIGREEN.NS",
                         "TORNTPOWER.NS","CESC.NS","SJVN.NS","NHPC.NS"],
    "Oil & Gas":        ["RELIANCE.NS","ONGC.NS","IOC.NS","BPCL.NS","HINDPETRO.NS",
                         "GAIL.NS","IGL.NS","MGL.NS"],
    "Auto":             ["MARUTI.NS","TATAMOTORS.NS","M&M.NS","BAJAJ-AUTO.NS",
                         "HEROMOTOCO.NS","EICHERMOT.NS","ASHOKLEY.NS","TVSMOTOR.NS"],
    "EV & New Energy":  ["TATAPOWER.NS","ADANIGREEN.NS","WAAREEENER.NS","PREMIER.NS",
                         "GREENPANEL.NS","EXIDEIND.NS","AMARA-RAJA.NS"],
    "Telecom":          ["BHARTIARTL.NS","IDEA.NS","TATACOMM.NS","STLTECH.NS",
                         "HFCL.NS","TEJAS.NS","RAILTEL.NS"],
    "Real Estate":      ["DLF.NS","GODREJPROP.NS","OBEROIRLTY.NS","PRESTIGE.NS",
                         "PHOENIXLTD.NS","SOBHA.NS","MAHLIFE.NS"],
    "FMCG":             ["HINDUNILVR.NS","ITC.NS","NESTLEIND.NS","BRITANNIA.NS",
                         "DABUR.NS","MARICO.NS","COLPAL.NS","EMAMILTD.NS"],
    "Agri & Fertilizer":["COROMANDEL.NS","CHAMBAL.NS","DEEPAKFERT.NS","NFL.NS",
                         "RALLIS.NS","PI.NS","KAVERI.NS","ESCORTS.NS"],
    "Railways":         ["IRFC.NS","RVNL.NS","RAILVIKAS.NS","IRCTC.NS",
                         "TITAGARH.NS","TEXRAIL.NS","KERNEX.NS"],
    "Aviation":         ["INDIGO.NS","SPICEJET.NS","BLUEDART.NS"],
    "Chemicals":        ["PIDILITIND.NS","DEEPAKNTR.NS","AAVAS.NS","CLEAN.NS",
                         "FINEORG.NS","NAVINFLUOR.NS","FLUOROCHEM.NS"],
    "Semiconductor":    ["DIXON.NS","KAYNES.NS","SYRMA.NS","AVALON.NS",
                         "CGPOWER.NS","HITACHIENER.NS","VEDL.NS"],
}


def _call_gemini(prompt: str, retries: int = 3) -> str:
    """Call Gemini with retry logic."""
    for attempt in range(retries):
        try:
            response = MODEL.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.warning(f"Gemini call failed (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)
    return ""


def load_self_learning_weights() -> dict:
    """
    Load accuracy weights from Phase 2 self-learning log if it exists.
    Falls back to equal weights on first run.
    """
    weights_file = "reports/accuracy_weights.json"
    default_weights = {sector: 1.0 for sector in SECTOR_SEED_STOCKS}
    if os.path.exists(weights_file):
        try:
            with open(weights_file) as f:
                saved = json.load(f)
            logger.info("Loaded self-learning weights from previous runs.")
            return saved
        except Exception:
            pass
    return default_weights


def classify_and_score_news(news_items: list[dict], weights: dict) -> list[dict]:
    """
    Send batches of news to Gemini for classification + impact scoring.
    Returns enriched news list with: type, sectors, score, summary.
    """
    if not news_items:
        return []

    # Prepare compact news batch for Gemini (max 30 items per call)
    batches = [news_items[i:i+30] for i in range(0, len(news_items), 30)]
    scored_items = []

    for batch_num, batch in enumerate(batches):
        news_text = "\n".join(
            f"{i+1}. [{item['source']}] {item['title']} | {item['summary'][:200]}"
            for i, item in enumerate(batch)
        )

        # Sector weight context for Gemini
        weight_context = ", ".join(
            f"{s}:{w:.1f}" for s, w in weights.items() if w != 1.0
        )
        weight_hint = f"\nHistorical accuracy weights (higher = more reliable signal): {weight_context}" if weight_context else ""

        prompt = f"""You are an expert Indian stock market analyst.
Analyze these {len(batch)} news items and return a JSON array.
{weight_hint}

For each news item return:
{{
  "index": <1-based index>,
  "type": <one of: Government_Policy | Corporate_Event | Regulatory | Macro | Sector_Trigger | Other>,
  "sectors_positive": [<list of sectors that benefit, from: {list(SECTOR_SEED_STOCKS.keys())}>],
  "sectors_negative": [<list of sectors hurt>],
  "score": <integer 0-10, impact score>,
  "reason": <one sentence why this matters to Indian stocks>,
  "key_companies": [<up to 5 specific NSE-listed company names most directly impacted>]
}}

Rules:
- Score >= 7 only for high-certainty, high-magnitude news
- Score < 5 for vague, minor, or routine news
- Be specific about Indian market impact
- Only include sectors from the provided list
- Return ONLY valid JSON array, no markdown, no preamble

NEWS ITEMS:
{news_text}
"""
        logger.info(f"Scoring batch {batch_num+1}/{len(batches)} with Gemini...")
        raw = _call_gemini(prompt)

        try:
            # Strip any accidental markdown fences
            clean = raw.replace("```json", "").replace("```", "").strip()
            scored = json.loads(clean)
            for item in scored:
                idx = item.get("index", 1) - 1
                if 0 <= idx < len(batch):
                    batch[idx].update({
                        "news_type":        item.get("type", "Other"),
                        "sectors_positive": item.get("sectors_positive", []),
                        "sectors_negative": item.get("sectors_negative", []),
                        "score":            int(item.get("score", 0)),
                        "reason":           item.get("reason", ""),
                        "key_companies":    item.get("key_companies", []),
                    })
            scored_items.extend(batch)
        except Exception as e:
            logger.warning(f"Gemini JSON parse failed for batch {batch_num+1}: {e}")
            # Still add unscored batch items so we don't lose data
            for item in batch:
                item.setdefault("score", 0)
                item.setdefault("sectors_positive", [])
                item.setdefault("sectors_negative", [])
                item.setdefault("key_companies", [])
            scored_items.extend(batch)

        time.sleep(1)

    # Filter only meaningful news (score >= 5)
    impactful = [n for n in scored_items if n.get("score", 0) >= 5]
    logger.info(f"Impactful news items (score>=5): {len(impactful)}")
    return impactful


def _get_stock_data(symbol: str) -> dict | None:
    """Fetch price, volume, and basic fundamentals for a stock."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="3mo")
        if hist.empty:
            return None
        info = ticker.info

        current_price   = round(hist["Close"].iloc[-1], 2)
        avg_volume_20d  = hist["Volume"].tail(20).mean()
        last_volume     = hist["Volume"].iloc[-1]
        vol_ratio       = round(last_volume / avg_volume_20d, 2) if avg_volume_20d > 0 else 0
        week52_high     = info.get("fiftyTwoWeekHigh", current_price)
        ma200           = hist["Close"].tail(200).mean() if len(hist) >= 200 else hist["Close"].mean()
        pct_from_52h    = round((week52_high - current_price) / week52_high * 100, 1)
        above_200ma     = current_price > ma200

        return {
            "symbol":         symbol,
            "price":          current_price,
            "vol_ratio":      vol_ratio,
            "pct_from_52h":   pct_from_52h,
            "above_200ma":    above_200ma,
            "market_cap_cr":  round(info.get("marketCap", 0) / 1e7, 0),
            "pe_ratio":       info.get("trailingPE", None),
            "revenue_growth": info.get("revenueGrowth", None),
            "debt_equity":    info.get("debtToEquity", None),
            "promoter_hold":  info.get("heldPercentInsiders", None),
            "52w_high":       week52_high,
        }
    except Exception as e:
        logger.debug(f"yfinance error for {symbol}: {e}")
        return None


def build_stock_lists(impactful_news: list[dict], weights: dict) -> dict:
    """
    Main stock classification engine.
    Returns dict with keys: list_a (surge), list_b (long-term), list_c (negative),
    top_news (for report header).
    """
    if not impactful_news:
        return {"list_a": [], "list_b": [], "list_c": [], "top_news": []}

    # Aggregate positive / negative sectors across all impactful news
    sector_pos_score = {}
    sector_neg_score = {}
    top_news = sorted(impactful_news, key=lambda x: x.get("score", 0), reverse=True)[:5]

    for news in impactful_news:
        score   = news.get("score", 0)
        w_boost = 1.0
        for sector in news.get("sectors_positive", []):
            w       = weights.get(sector, 1.0)
            sector_pos_score[sector] = sector_pos_score.get(sector, 0) + score * w * w_boost
        for sector in news.get("sectors_negative", []):
            w = weights.get(sector, 1.0)
            sector_neg_score[sector] = sector_neg_score.get(sector, 0) + score * w

    # Collect candidate stocks
    positive_symbols = set()
    negative_symbols = set()
    stock_news_map   = {}  # symbol → triggering news item

    for sector, agg_score in sector_pos_score.items():
        if agg_score >= 5:
            for sym in SECTOR_SEED_STOCKS.get(sector, []):
                positive_symbols.add(sym)
                if sym not in stock_news_map:
                    # Find the top news for this sector
                    for n in top_news:
                        if sector in n.get("sectors_positive", []):
                            stock_news_map[sym] = n
                            break

    for sector, agg_score in sector_neg_score.items():
        if agg_score >= 5:
            for sym in SECTOR_SEED_STOCKS.get(sector, []):
                negative_symbols.add(sym)

    # Ask Gemini to add any extra stocks mentioned directly in news
    direct_companies = []
    for n in impactful_news:
        direct_companies.extend(n.get("key_companies", []))
    direct_companies = list(set(direct_companies))

    if direct_companies:
        prompt = f"""Convert these Indian company names to NSE ticker symbols (add .NS suffix).
Return ONLY a JSON array of strings like ["SYMBOL.NS", ...].
Companies: {direct_companies}
Rules: Only include if actually listed on NSE. Return empty array if unsure."""
        raw = _call_gemini(prompt)
        try:
            clean    = raw.replace("```json","").replace("```","").strip()
            extra    = json.loads(clean)
            positive_symbols.update(extra)
        except Exception:
            pass

    # Fetch stock data and classify
    list_a = []  # Surge candidates
    list_b = []  # Long-term buys
    list_c = []  # Negative / avoid

    logger.info(f"Fetching data for {len(positive_symbols)} positive candidates...")
    for sym in list(positive_symbols)[:60]:  # Cap at 60 to avoid rate limits
        data = _get_stock_data(sym)
        if not data:
            continue

        triggering_news = stock_news_map.get(sym, top_news[0] if top_news else {})
        news_title      = triggering_news.get("title", "")[:80]
        news_reason     = triggering_news.get("reason", "")[:100]

        # ── LIST A: Short-term surge criteria ────────────────────────────────
        is_near_high    = data["pct_from_52h"] <= 5
        has_vol_buildup = data["vol_ratio"] >= 1.3
        above_200       = data["above_200ma"]
        surge_score     = sum([is_near_high, has_vol_buildup, above_200])

        if surge_score >= 2:
            target_zone = round(data["price"] * 1.10, 1)
            list_a.append({
                "symbol":       sym,
                "price":        data["price"],
                "market_cap":   data["market_cap_cr"],
                "vol_ratio":    data["vol_ratio"],
                "pct_from_52h": data["pct_from_52h"],
                "trigger_news": news_title,
                "reason":       news_reason,
                "target_zone":  target_zone,
                "risk":         "High momentum — use trailing stop loss",
            })

        # ── LIST B: Long-term buy criteria ────────────────────────────────────
        rev_growth   = data.get("revenue_growth") or 0
        de_ratio     = data.get("debt_equity") or 999
        mktcap       = data.get("market_cap_cr") or 9999999
        good_growth  = rev_growth > 0.15
        low_debt     = de_ratio < 100          # yfinance returns as %, so 100 = 1x
        smallmid_cap = mktcap < 20000
        long_score   = sum([good_growth, low_debt, smallmid_cap])

        if long_score >= 2:
            list_b.append({
                "symbol":       sym,
                "price":        data["price"],
                "market_cap":   data["market_cap_cr"],
                "rev_growth":   round(rev_growth * 100, 1),
                "de_ratio":     round(de_ratio, 1),
                "thesis":       news_reason,
                "catalysts":    news_title,
                "horizon":      "6 months – 3 years",
                "risk":         "Policy reversal or sector slowdown",
            })

        time.sleep(0.3)

    # Negative list (only fetch price for context)
    logger.info(f"Fetching data for {len(negative_symbols)} negative candidates...")
    for sym in list(negative_symbols - positive_symbols)[:30]:
        data = _get_stock_data(sym)
        if not data:
            continue
        triggering_news = {}
        for n in impactful_news:
            for sector, stocks in SECTOR_SEED_STOCKS.items():
                if sym in stocks and sector in n.get("sectors_negative", []):
                    triggering_news = n
                    break
        list_c.append({
            "symbol":  sym,
            "price":   data["price"],
            "reason":  triggering_news.get("reason", "Sector headwind from news"),
            "news":    triggering_news.get("title", "")[:80],
            "duration":"Short to medium term",
        })
        time.sleep(0.3)

    # Sort by quality
    list_a.sort(key=lambda x: x["vol_ratio"], reverse=True)
    list_b.sort(key=lambda x: x.get("rev_growth", 0), reverse=True)

    logger.info(f"List A: {len(list_a)} | List B: {len(list_b)} | List C: {len(list_c)}")
    return {
        "list_a":   list_a[:10],
        "list_b":   list_b[:10],
        "list_c":   list_c[:8],
        "top_news": top_news,
      }
  
