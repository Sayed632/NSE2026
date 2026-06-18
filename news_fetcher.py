"""
news_fetcher.py
Multi-source ingestion engine capable of standard HTML parsing,
macro statistic scraping, and fallback generic structural text dumps.
"""

import os
import logging
import requests
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

# Highly diversified asset endpoints provided by the user
DSIJ_STREAM_CHANNELS = {
    "Swing_Trading":       "https://insights.dsij.in/insight/trending-news/swing-trading",
    "Penny_Stocks":        "https://insights.dsij.in/insight/trending-news/penny-stocks",
    "Multibagger_News":    "https://insights.dsij.in/insight/trending-news/multibagger",
    "SME_Emerging":        "https://insights.dsij.in/insight/trending-news/sme",
    "Quarterly_Results":   "https://insights.dsij.in/insight/trending-news/quarterly-results",
    "FII_DII_Flows":       "https://insights.dsij.in/markets/market-statistics/fii-dii",
    "Broker_Research":     "https://insights.dsij.in/markets/reports/broker-reports",
    "Guru_Investors":      "https://insights.dsij.in/markets/reports/guru-investors",
    "Sprinting_Unicorns":  "https://insights.dsij.in/screener_details/operationtype/sprintingunicorns",
    "Mindshare_Intel":     "https://insights.dsij.in/insight/trending-news/mindshare",
    "Top_Gainers":         "https://insights.dsij.in/markets/market-statistics/top-gainers",
    "Personal_Finance":    "https://insights.dsij.in/insight/trending-news/personal-finance",
    "Experts_Speak":       "https://insights.dsij.in/insight/knowledge/experts-speak",
    "Multibagger_Screen":  "https://insights.dsij.in/screener_details/operationtype/multibaggers",
    "Corporate_Actions":   "https://insights.dsij.in/insight/trending-news/bonus-stock-split"
}

def get_authenticated_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
    })
    
    username = os.environ.get("DSJ_USER_ID")
    password = os.environ.get("DSJ_PASSWORD")
    login_url = "https://www.dsij.in/LoginPage"
    
    payload = {"txtUser": username, "txtPassword": password, "btnLogin": "Login"}
    try:
        session.get("https://www.dsij.in/", timeout=10)
        session.post(login_url, data=payload, timeout=12)
        return session
    except Exception as e:
        logger.error(f"Authentication failure: {e}")
    return session

def process_page_to_unified_text(html_content: str) -> str:
    """
    Layout-Agnostic text extractor. Removes script/style clutter, leaving
    clean semantic text tables and paragraphs intact for Gemini context analysis.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Prune non-analytical components immediately
    for element in soup(["script", "style", "nav", "footer", "header"]):
        element.extract()
        
    # Grab structural tables (e.g., FII/DII data rows or Guru tables)
    table_strings = []
    for table in soup.find_all("table"):
        rows = []
        for row in table.find_all("tr"):
            cells = [cell.text.strip().replace("\n", " ") for cell in row.find_all(["td", "th"])]
            rows.append(" | ".join(cells))
        table_strings.append("\n".join(rows))
        table.extract() # Remove to prevent duplicating text down below
        
    # Harvest remaining paragraph blocks and structural items
    text_content = soup.get_text(separator="\n")
    lines = [line.strip() for line in text_content.splitlines() if len(line.strip()) > 20]
    
    # Return structured consolidation
    return "\n--- TABLE DATA ---\n".join(table_strings) + "\n--- BODY TEXT ---\n" + "\n".join(lines[:120])

def fetch_all_news() -> list[dict]:
    """Loops through all structural web configurations and packs them as an raw data package."""
    session = get_authenticated_session()
    raw_ingestion_payload = []
    
    for channel, url in DSIJ_STREAM_CHANNELS.items():
        logger.info(f"Ingesting channel data pipeline: [{channel}]")
        try:
            response = session.get(url, timeout=15)
            if response.status_code == 200:
                # Layout-agnostic consolidation
                extracted_data = process_page_to_unified_text(response.text)
                raw_ingestion_payload.append({
                    "channel": channel,
                    "url": url,
                    "raw_data_dump": extracted_data
                })
        except Exception as e:
            logger.error(f"Error harvesting data from stream {channel}: {e}")
            
    return raw_ingestion_payload
