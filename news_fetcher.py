"""
news_fetcher.py
Fetches news from NSE/BSE announcements, PIB, MoF, MHA,
Economic Times and Moneycontrol via RSS and HTTP scraping.
"""

import requests
import feedparser
from bs4 import BeautifulSoup
import time
import logging
from datetime import datetime, timedelta
import pytz

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── RSS feeds (reliable, no scraping needed) ─────────────────────────────────
RSS_FEEDS = {
    "Economic Times Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "Economic Times Economy":  "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms",
    "Moneycontrol Markets":    "https://www.moneycontrol.com/rss/MCtopnews.xml",
    "PIB":                     "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",
    "Google News India Market":"https://news.google.com/rss/search?q=india+stock+market+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en",
    "Google News Policy":      "https://news.google.com/rss/search?q=india+government+policy+economy+budget&hl=en-IN&gl=IN&ceid=IN:en",
    "Google News Defence":     "https://news.google.com/rss/search?q=india+defence+ministry+contract+order&hl=en-IN&gl=IN&ceid=IN:en",
}

# ── BSE announcements (XML feed) ─────────────────────────────────────────────
BSE_ANN_URL = (
    "https://api.bseindia.com/BseIndiaAPI/api/AnnGetAnnouncementXML/w"
    "?strCat=-1&strPrevDate={}&strScrip=&strSearch=P&strToDate={}&strType=C&subcategory=-1"
)

# ── NSE corporate filings RSS ─────────────────────────────────────────────────
NSE_CORP_RSS = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"


def _parse_rss(name: str, url: str, max_items: int = 15) -> list[dict]:
    """Parse an RSS/Atom feed and return a list of news dicts."""
    items = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:max_items]:
            pub = entry.get("published", entry.get("updated", ""))
            items.append({
                "source": name,
                "title":  entry.get("title", "").strip(),
                "summary": entry.get("summary", entry.get("description", "")).strip()[:500],
                "url":    entry.get("link", ""),
                "published": pub,
            })
    except Exception as e:
        logger.warning(f"RSS fetch failed [{name}]: {e}")
    return items


def fetch_rss_news() -> list[dict]:
    """Fetch all RSS feeds and return combined list."""
    all_news = []
    for name, url in RSS_FEEDS.items():
        logger.info(f"Fetching RSS: {name}")
        items = _parse_rss(name, url)
        all_news.extend(items)
        time.sleep(0.5)
    logger.info(f"Total RSS items fetched: {len(all_news)}")
    return all_news


def fetch_bse_announcements() -> list[dict]:
    """Fetch today's BSE corporate announcements via API."""
    items = []
    try:
        today = datetime.now(IST).strftime("%Y%m%d")
        yesterday = (datetime.now(IST) - timedelta(days=1)).strftime("%Y%m%d")
        url = BSE_ANN_URL.format(yesterday, today)
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml-xml")
            for row in soup.find_all("row")[:30]:
                title   = row.find("NEWSSUB")
                company = row.find("SLONGNAME")
                scrip   = row.find("SCRIP_CD")
                items.append({
                    "source":    "BSE Announcement",
                    "title":     (title.text if title else "").strip(),
                    "summary":   f"Company: {company.text if company else ''} | Scrip: {scrip.text if scrip else ''}",
                    "url":       "https://www.bseindia.com/corporates/ann.html",
                    "published": datetime.now(IST).isoformat(),
                })
        logger.info(f"BSE announcements fetched: {len(items)}")
    except Exception as e:
        logger.warning(f"BSE fetch failed: {e}")
    return items


def fetch_pib_policy_news() -> list[dict]:
    """Fetch PIB press releases via scraping as fallback."""
    items = []
    try:
        resp = requests.get(
            "https://pib.gov.in/allRel.aspx",
            headers=HEADERS, timeout=15
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        for link in soup.select("ul.rel-list li a")[:20]:
            items.append({
                "source":    "PIB Government",
                "title":     link.get_text(strip=True),
                "summary":   "",
                "url":       "https://pib.gov.in" + link.get("href", ""),
                "published": datetime.now(IST).isoformat(),
            })
        logger.info(f"PIB items fetched: {len(items)}")
    except Exception as e:
        logger.warning(f"PIB scrape failed: {e}")
    return items


def fetch_all_news() -> list[dict]:
    """
    Master function — fetches from all sources and
    returns a deduplicated, combined list of news items.
    """
    all_news = []
    all_news.extend(fetch_rss_news())
    all_news.extend(fetch_bse_announcements())
    all_news.extend(fetch_pib_policy_news())

    # Deduplicate by title
    seen = set()
    unique_news = []
    for item in all_news:
        key = item["title"].lower()[:80]
        if key and key not in seen:
            seen.add(key)
            unique_news.append(item)

    logger.info(f"Total unique news items: {len(unique_news)}")
    return unique_news

