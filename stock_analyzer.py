import json
import time
import logging

logger = logging.getLogger(__name__)

def classify_and_score_news(raw_ingestion_payload: list[dict], weights: dict) -> list[dict]:
    """
    Sends consolidated unstructured text tables directly to Gemini
    instructing it to run multi-horizon recommendation matrix mappings.
    """
    if not raw_ingestion_payload:
        return []
        
    compiled_recommendations = []
    
    # Process each complex data channel stream layout-agnostically
    for stream in raw_ingestion_payload:
        prompt = f"""You are a senior hedge fund systems analyst running deep telemetry checks on Indian stock updates.
Analyze this raw data dump extracted from the DSIJ portal channel: [{stream['channel']}].

Data Payload:
\"\"\"
{stream['raw_data_dump'][:6000]}
\"\"\"

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
- Do not output any markdown code blocks, backticks (```), or conversational preambles.
"""
        try:
            # Call your configured Gemini Model instance (Ensure MODEL is defined globally in stock_analyzer.py)
            response = MODEL.generate_content(prompt)
            
            # Clean up potential markdown wrapper wrappers cleanly on a single line
            clean_text = response.text.strip()
            clean_text = clean_text.replace("```json", "").replace("
```JSON", "").replace("```", "").strip()
            
            if not clean_text or clean_text == "[]":
                continue
                
            parsed_insights = json.loads(clean_text)
            for insight in parsed_insights:
                # Append origin tracker metadata parameters so downstream filters know the source
                insight["channel"] = stream["channel"]
                compiled_recommendations.append(insight)
        except Exception as e:
            logger.warning(f"Failed decoding stream payload tracking data for {stream['channel']}: {e}")
            
        time.sleep(1) # Controlled API loop pacing to avoid rate limiting
        
    return compiled_recommendations
