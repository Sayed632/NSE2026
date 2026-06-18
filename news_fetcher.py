"""
news_fetcher.py
Alpha-Driven Multi-Stream Ingestion Pipeline.
Targets Macro Policy Streams, Exchange Announcements, and Corporate Registries.
"""

import os
import logging
import requests
import feedparser
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STEALTH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8"
}

# Targeted Indian Capital Markets & Macro Policy Ingestion Matrix
INTELLIGENCE_FEEDS = {
    "PIB_Govt_Policy": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1",
    "Moneycontrol_Corporate": "https://www.moneycontrol.com/rss/company_news.xml",
    "Moneycontrol_Business": "https://www.moneycontrol.com/rss/business.xml",
    "SEBI_Circulars_Orders": "https://www.sebi.gov.in/sebiweb/home/rss.jsp?sid=1",
    "NSE_Corporate_Announcements": "https://www.nseindia.com/static/rss-feed" # Tracks live filings
}

CHANNELS = {
    "SME_Emerging": "https://insights.dsij.in/products/sme-emerging",
    "Flash_News": "https://insights.dsij.in/products/flash-news",
    "Low_Priced_Scrips": "https://insights.dsij.in/products/low-priced-scrips"
}

def process_page_to_unified_text(html_content: str) -> str:
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "lxml")
    for script in soup(["script", "style", "header", "footer", "nav"]):
        script.extract()
    return " ".join(soup.get_text().split())

def fetch_dsij_stream() -> list[dict]:
    """Attempts stealth ingestion of premium metrics, falling back safely on blocks."""
    payloads = []
    username, password = os.environ.get("DSJ_USER_ID"), os.environ.get("DSJ_PASSWORD")
    if not username or not password:
        return []
        
    session = requests.Session()
    try:
        get_res = session.get("https://insights.dsij.in/login", headers=STEALTH_HEADERS, timeout=10)
        soup = BeautifulSoup(get_res.text, "html.parser")
        token_input = soup.find("input", {"name": "_token"})
        token = token_input["value"] if token_input else ""
        
        login_data = {"_token": token, "email": username, "password": password}
        post_res = session.post("https://insights.dsij.in/login", data=login_data, headers=STEALTH_HEADERS, timeout=12)
        
        if "login" not in post_res.url.lower():
            for name, url in CHANNELS.items():
                res = session.get(url, headers=STEALTH_HEADERS, timeout=8)
                if res.status_code == 200:
                    clean_text = process_page_to_unified_text(res.text)
                    if "upgrade your plan" not in clean_text.lower():
                        payloads.append({"channel": name, "raw_data_dump": clean_text})
    except Exception as e:
        logger.warning(f"DSIJ pipeline bypassed: {e}")
    return payloads

def ingest_market_intelligence() -> list[dict]:
    """Compiles macro-policy, corporate actions, and premium signals into one context payload."""
    data_matrix = fetch_dsij_stream()
    
    logger.info("Ingesting institutional macro policy and corporate announcements feeds...")
    for feed_name, feed_url in INTELLIGENCE_FEEDS.items():
        try:
            feed = feedparser.parse(feed_url)
            compiled_items = []
            for entry in feed.entries[:25]: # Deep historical context capture window
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                description = entry.get("description", "")
                compiled_items.append(f"Source: {feed_name}\nHeadline: {title}\nSummary: {summary}\nContext: {description}\n---")
            
            if compiled_items:
                data_matrix.append({
                    "channel": feed_name,
                    "raw_data_dump": "\n".join(compiled_items)
                })
        except Exception as e:
            logger.error(f"Failed aggregating data points from source node {feed_name}: {e}")
            
    return data_matrix
