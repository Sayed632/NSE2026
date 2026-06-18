"""
stock_analyzer.py
Advanced Multi-Factor Policy Analyzer & Supply Chain Engine.
"""

import os
import json
import time
import logging
import yfinance as yf
import google.generativeai as genai

logger = logging.getLogger(__name__)

if "GEMINI_API_KEY" in os.environ:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
MODEL = genai.GenerativeModel("gemini-2.5-flash")

def classify_and_score_news(raw_ingestion_payload: list[dict], weights: dict = None) -> list[dict]:
    if not raw_ingestion_payload:
        return []
    weights = weights or {}
    compiled_insights = []

    rules_override = ""
    if os.path.exists("reports/scoring_rules_override.json"):
        try:
            with open("reports/scoring_rules_override.json", "r") as f:
                rules_override = json.load(f).get("prompt_injection", "")
        except Exception:
            pass

    for stream in raw_ingestion_payload:
        channel_weight = weights.get(stream['channel'], 1.0)
        
        prompt = f"""You are an institutional alpha research model tracking Indian equities.
Your objective is to identify asymmetric stock opportunities driven by structural catalysts BEFORE price realization occurs.

ANALYZE THIS RAW DATA STREAM FROM CURRENT MARKET NODES:
\"\"\"
{stream['raw_data_dump'][:7500]}
\"\"\"

CRITICAL STRATEGIC MATRIX FOR CONVICTION MATCHING:
1. Government Capital Expenditure (CapEx / PLI / Policy Frameworks):
   If a policy highlights infrastructure, border defense, aerospace, renewable grids, or manufacturing setups, automatically trace the listed contractors.
2. Proxy & Supply Chain Mapping:
   Government text rarely names tickers. If you identify themes like "Smart Borders", "Anti-Drone", "Unmanned Surveillance", "Shipbuilding", or "Radar Arrays", you MUST map them directly to relevant Indian listed players (e.g., ZENTEC.NS, IDEAFORGE.NS, DATAPATTERNS.NS, BEL.NS, BDL.NS, BEML.NS, COCHINSHIP.NS, PARAS.NS, BHARATFORG.NS, CYIENTDLM.NS).
3. Core Corporate Triggers: Mergers, Demergers, Massive Order Wins (>100 Cr), and Multi-Year Institutional Contracts.

DYNAMIC SYSTEM POLICIES:
{rules_override if rules_override else "No runtime constraints active. Focus on identifying early catalytic policy movements."}

Output an explicit JSON array of objects. Do not use markdown tags, backticks, or text commentary.
Format:
[
  {{
    "ticker": "SYMBOL.NS",
    "company_name": "Full legal name of company",
    "strategy_type": "SWING" | "CORE_BUY" | "SME_MOMENTUM",
    "horizon": "Short-term (2-15 Days)" | "Medium-term (1-6 Months)",
    "score": 1 to 10,
    "catalyst_reasoning": "Detailed breakdown explaining the direct line of sight between the policy/news event and the company's financial catalyst."
  }}
]
"""
        try:
            response = MODEL.generate_content(prompt)
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            if not clean_text or clean_text == "[]":
                continue
                
            parsed = json.loads(clean_text)
            for insight in parsed:
                insight["channel"] = stream["channel"]
                base_score = insight.get("score", 5)
                insight["score"] = min(10, max(1, round(base_score * channel_weight)))
                compiled_insights.append(insight)
        except Exception as e:
            logger.warning(f"Error compiling stream data context for {stream['channel']}: {e}")
        time.sleep(0.5)
        
    return compiled_insights

def build_stock_lists(compiled_insights: list[dict], weights: dict = None) -> dict:
    """Filters identified assets, adapting market cap filters dynamically for policy breakout groups."""
    list_a, list_b, top_news = [], [], []
    seen = set()

    for item in compiled_insights:
        ticker = item.get("ticker", "").upper()
        if not ticker or ticker in seen:
            continue
            
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(period="5d") # Ultra-tight window to identify current baseline reference points
            if hist.empty:
                continue
                
            curr_price = round(hist["Close"].iloc[-1], 2)
            info = tk.info
            mkt_cap = round(info.get("marketCap", 0) / 1e7, 2) if info.get("marketCap") else 0
            
            # RE-ENGINEERED VOLATILITY OVERRIDE: Allow specialized small-caps to pass if backed by an institutional score >= 7
            if mkt_cap < 500 and item.get("score", 5) < 7:
                continue
                
            stock_record = {
                "symbol": ticker,
                "price": curr_price,
                "market_cap": mkt_cap,
                "reason": item["catalyst_reasoning"],
                "horizon": item["horizon"],
                "origin_channel": item["channel"],
                "score": item["score"]
            }
            
            if item["strategy_type"] in ["SWING", "SME_MOMENTUM"]:
                stock_record["target_zone"] = round(curr_price * 1.08, 1) # Propose clean 8% target breakout expectations
                list_a.append(stock_record)
            else:
                list_b.append(stock_record)
                
            top_news.append(item)
            seen.add(ticker)
        except Exception:
            continue

    # Sort choices by score to highlight the highest conviction ideas first
    list_a.sort(key=lambda x: x.get("score", 0), reverse=True)
    list_b.sort(key=lambda x: x.get("score", 0), reverse=True)

    return {"list_a": list_a[:10], "list_b": list_b[:10], "top_news": top_news[:5]}
