"""
stock_analyzer.py
Processes layout-agnostic raw streams through Gemini with dynamic rule injection,
and applies secondary structural filters via yfinance.
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

# Configured to use the updated, highly stable model version
MODEL = genai.GenerativeModel("gemini-2.5-flash")


def classify_and_score_news(raw_ingestion_payload: list[dict], weights: dict = None) -> list[dict]:
    """
    Sends consolidated unstructured text tables directly to Gemini
    instructing it to run multi-horizon recommendation matrix mappings.
    Injects self-evolved heuristic rules dynamically.
    """
    if not raw_ingestion_payload:
        return []
        
    weights = weights or {}
    compiled_recommendations = []
    
    # Extract prompt injection rules from the scoring_rules_override system if available
    rules_override_prompt = ""
    if os.path.exists("reports/scoring_rules_override.json"):
        try:
            with open("reports/scoring_rules_override.json", "r") as f:
                rules_override_prompt = json.load(f).get("prompt_injection", "")
        except Exception:
            pass

    for stream in raw_ingestion_payload:
        channel_weight = weights.get(stream['channel'], 1.0)
        
        prompt = f"""You are a senior hedge fund systems analyst running deep telemetry checks on Indian stock updates.
Analyze this raw data dump extracted from the market intelligence feed channel: [{stream['channel']}].
Current channel confidence weight adjustment: {channel_weight}

Data Payload:
\"\"\"
{stream['raw_data_dump'][:6000]}
\"\"\"

CRITICAL EVOLUTIONARY SCORING RULES TO APPLY:
{rules_override_prompt if rules_override_prompt else "No override constraints active for this cycle. Rely on standard baseline financial filters."}

Task:
Extract and output a raw JSON array of objects representing high-conviction insights.
If the channel contains institutional numbers (FII/DII) or multi-investor portfolios, aggregate that context to identify target tickers.

Expected Output Format (Strict JSON Array):
[
  {{
    "ticker": "NSE_SYMBOL.NS",
    "company_name": "Name of firm",
    "strategy_type": "SWING" | "CORE_BUY" | "SPECULATIVE_PENNY" | "SME_MOMENTUM" | "MACRO_SHORT",
    "horizon": "Short-term (2-15 Days)" | "Medium-term (1-6 Months)" | "Long-term (1-3 Years)",
    "score": 7,
    "catalyst_reasoning": "Clear statement combining bulk data, broker views, or price volume actions"
  }}
]

Rules:
- Append .NS to every ticker symbol.
- If no actionable stock can be confirmed from the payload text dump, return an empty JSON array: [].
- Do not output any markdown code blocks, backticks, or conversational preambles.
"""
        try:
            response = MODEL.generate_content(prompt)
            
            # --- SMARTPHONE SAFE CLEANUP DESERIALIZER ---
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
            
            if not clean_text or clean_text == "[]":
                continue
                
            parsed_insights = json.loads(clean_text)
            for insight in parsed_insights:
                insight["channel"] = stream["channel"]
                # Apply channel weight modifiers to the internal conviction matrix score
                base_score = insight.get("score", 5)
                insight["score"] = min(10, max(1, round(base_score * channel_weight)))
                compiled_recommendations.append(insight)
        except Exception as e:
            logger.warning(f"Failed decoding stream payload tracking data for {stream['channel']}: {e}")
            
        time.sleep(1)
        
    return compiled_recommendations


def build_stock_lists(compiled_recommendations: list[dict], weights: dict = None) -> dict:
    """Processes asset selections across standard market cap and volatility filters."""
    list_a = []  # Short-Term / Swing / SME Momentum
    list_b = []  # Core Structural Compounders / Multibaggers
    list_c = []  # Negative / Headwinds / Shorts

    seen_tickers = set()

    for item in compiled_recommendations:
        ticker = item.get("ticker")
        if not ticker or ticker in seen_tickers:
            continue
            
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(period="6mo")
            if hist.empty:
                continue
                
            info = tk.info
            curr_price = round(hist["Close"].iloc[-1], 2)
            mkt_cap = round(info.get("marketCap", 0) / 1e7, 2) if info.get("marketCap") else 0
            
            # Skip extreme micro-caps unless matching specific risk streams
            if mkt_cap < 1000 and item["strategy_type"] not in ["SPECULATIVE_PENNY", "SME_MOMENTUM"]:
                continue
                
            processed_stock = {
                "symbol": ticker,
                "price": curr_price,
                "market_cap": mkt_cap,
                "reason": item["catalyst_reasoning"],
                "horizon": item["horizon"],
                "origin_channel": item["channel"]
            }
            
            if item["strategy_type"] in ["SWING", "SME_MOMENTUM"]:
                processed_stock["target_zone"] = round(curr_price * 1.08, 1)
                list_a.append(processed_stock)
            elif item["strategy_type"] in ["CORE_BUY", "SPECULATIVE_PENNY"]:
                processed_stock["horizon_target"] = "12 - 36 Months"
                list_b.append(processed_stock)
            elif item["strategy_type"] == "MACRO_SHORT":
                list_c.append(processed_stock)
                
            seen_tickers.add(ticker)
            time.sleep(0.1)
        except Exception:
            continue

    return {
        "list_a": list_a[:10],
        "list_b": list_b[:10],
        "list_c": list_c[:5],
        "top_news": compiled_recommendations[:5]
    }
