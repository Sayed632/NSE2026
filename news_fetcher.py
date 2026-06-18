"""
news_fetcher.py
Multi-tier Ingestion Engine with Resilient Fallbacks.
DSIJ Stealth -> Moneycontrol Public Feed -> Govt Policy Stream (PIB).
"""

import os
import logging
import requests
import feedparser
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User-Agent Mimicry Matrix to bypass structural bot checks
STEALTH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
}

# 15 Hardcoded DSIJ Intelligence Feed Mappings
CHANNELS = {
    "SME_Emerging": "https://insights.dsij.in/products/sme-emerging",
    "Flash_News": "https://insights.dsij.in/products/flash-news",
    "Low_Priced_Scrips": "https://insights.dsij.in/products/low-priced-scrips",
    "Value_Scrips": "https://insights.dsij.in/products/value-scrips",
    "Growth_Scrips": "https://insights.dsij.in/products/growth-scrips",
    "Stock_Kirana": "https://insights.dsij.in/products/stock-kirana",
    "Technical_Traders": "https://insights.dsij.in/products/technical-traders",
    "Derivatives_Whiz": "https://insights.dsij.in/products/derivatives-whiz",
    "Options_Traders": "https://insights.dsij.in/products/options-traders",
    "Trading_Call": "https://insights.dsij.in/products/trading-call",
    "Delivery_Call": "https://insights.dsij.in/products/delivery-call",
    "Intraday_Call": "https://insights.dsij.in/products/intraday-call",
    "Micro_Cap_Gems": "https://insights.dsij.in/products/micro-cap-gems",
    "Hidden_Gems": "https://insights.dsij.in/products/hidden-gems",
    "Mid_Cap_Marvels": "https://insights.dsij.in/products/mid-cap-marvels"
}

PUBLIC_FEEDS = {
    "Moneycontrol_Market": "https://www.moneycontrol.com/rss/marketnews.xml",
    "Moneycontrol_Business": "https://www.moneycontrol.com/rss/business.xml",
    "PIB_Govt_Policy": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1"
}


def process_page_to_unified_text(html_content: str) -> str:
    """Strips formatting structures to minimize API consumption footprints."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "lxml")
    
    # Prune non-contextual artifacts
    for script in soup(["script", "style", "header", "footer", "nav"]):
        script.extract()
        
    lines = (line.strip() for line in soup.get_text().splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    return "\n".join(chunk for chunk in chunks if chunk)


def fetch_dsij_stream() -> list[dict]:
    """Authenticates and iterates through core DSIJ intelligence channels."""
    payloads = []
    username = os.environ.get("DSJ_USER_ID")
    password = os.environ.get("DSJ_PASSWORD")
    
    if not username or not password:
        logger.warning("DSIJ Credentials absent. Skipping primary tier.")
        return []
        
    session = requests.Session()
    login_url = "https://insights.dsij.in/login"
    
    try:
        # Initial handshake to establish baseline cookies
        get_res = session.get(login_url, headers=STEALTH_HEADERS, timeout=10)
        soup = BeautifulSoup(get_res.text, "html.parser")
        token_input = soup.find("input", {"name": "_token"})
        token = token_input["value"] if token_input else ""
        
        login_data = {
            "_token": token,
            "email": username,
            "password": password
        }
        
        # Fire authentication challenge
        post_res = session.post(login_url, data=login_data, headers=STEALTH_HEADERS, timeout=12)
        if "login" in post_res.url.lower() and post_res.status_code == 200:
            logger.error("DSIJ gateway rejected credentials or flagged session as bot.")
            return []
            
        # Ingest raw text data from the 15 targeted stream paths
        for name, url in CHANNELS.items():
            res = session.get(url, headers=STEALTH_HEADERS, timeout=8)
            if res.status_code == 200:
                clean_text = process_page_to_unified_text(res.text)
                # Verify that we got content instead of paywall blockades
                if "upgrade your plan" not in clean_text.lower() and len(clean_text) > 200:
                    payloads.append({
                        "channel": name,
                        "raw_data_dump": clean_text
                    })
            logger.info(f"DSIJ stream extraction step evaluated for channel: {name}")
            
    except Exception as e:
        logger.warning(f"Primary DSIJ data connection pipeline dropped: {e}")
        
    return payloads


def fetch_public_fallbacks() -> list[dict]:
    """Extracts unstructured text telemetry out of institutional RSS feeds."""
    payloads = []
    logger.info("Initializing public-facing institutional fallback tracks...")
    
    for name, url in PUBLIC_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            compiled_items = []
            
            for entry in feed.entries[:20]:  # Capture the latest 20 breaking updates
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                description = entry.get("description", "")
                compiled_items.append(f"Heading: {title}\nSummary: {summary}\nContext: {description}\n---")
                
            if compiled_items:
                payloads.append({
                    "channel": name,
                    "raw_data_dump": "\n".join(compiled_items)
                })
                logger.info(f"Successfully processed public fallback track: {name}")
        except Exception as e:
            logger.error(f"Failed pulling public RSS feed payload for {name}: {e}")
            
    return payloads


def ingest_market_intelligence() -> list[dict]:
    """Main execution engine balancing active streams with standard fallbacks."""
    # Step 1: Execute primary DSIJ capture matrix
    data_matrix = fetch_dsij_stream()
    
    # Step 2: If DSIJ is empty, blocked, or paywalled, activate Tier-2 Public Networks
    if not data_matrix:
        logger.warning("Primary stream dataset empty. Activating public networks.")
        data_matrix = fetch_public_fallbacks()
    else:
        # Step 3: Always append Government PIB policy signals alongside DSIJ data
        try:
            pib_feed = feedparser.parse(PUBLIC_FEEDS["PIB_Govt_Policy"])
            pib_items = []
            for entry in pib_feed.entries[:15]:
                pib_items.append(f"Govt Notification: {entry.get('title','')}\n{entry.get('summary','')}\n---")
            if pib_items:
                data_matrix.append({
                    "channel": "PIB_Govt_Policy",
                    "raw_data_dump": "\n".join(pib_items)
                })
                logger.info("Government Policy Stream appended to active data payload matrix.")
        except Exception as e:
            logger.error(f"Isolated policy stream attachment skipped: {e}")
            
    return data_matrix
