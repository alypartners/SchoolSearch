"""
Scraper: Austin ISD Press Releases
URL: https://www.austinisd.org/press-releases
Monitors for keywords: sale, property, surplus, bid, RFP, school names
"""

import hashlib
import json
import re
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

SOURCE_NAME = "AISD Press Releases"
SOURCE_URL = "https://www.austinisd.org/press-releases"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

PROPERTY_KEYWORDS = [
    "sale", "sell", "sold", "property", "surplus", "bid", "rfp",
    "request for proposal", "real estate", "disposition", "convey",
    "auction", "lease", "facility", "campus closure", "closed campus",
]


def scrape(schools: List[Dict]) -> Tuple[str, List[Dict]]:
    """
    Fetch AISD press releases page and look for property-related posts
    mentioning school names or property keywords.

    Returns:
        (content_hash, changes_list)
    """
    try:
        resp = requests.get(SOURCE_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[{SOURCE_NAME}] Request error: {e}")
        return ("ERROR", [])

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = _extract_articles(soup)
    content = json.dumps(articles, sort_keys=True)
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    changes = _match_articles(articles, schools)
    return (content_hash, changes)


def _extract_articles(soup: BeautifulSoup) -> List[Dict]:
    articles = []

    # Try common CMS patterns for press release lists
    for selector in [
        "article",
        ".press-release",
        ".views-row",
        ".news-item",
        "li.node",
        ".view-content .node",
    ]:
        items = soup.select(selector)
        if items:
            for item in items:
                title_tag = item.find(["h2", "h3", "h4", "a"])
                title = title_tag.get_text(strip=True) if title_tag else ""
                link_tag = item.find("a", href=True)
                link = ""
                if link_tag:
                    href = link_tag["href"]
                    link = href if href.startswith("http") else f"https://www.austinisd.org{href}"
                date_tag = item.find(class_=re.compile(r"date|time|posted", re.I))
                date = date_tag.get_text(strip=True) if date_tag else ""
                blurb_tag = item.find(["p", "div"], class_=re.compile(r"body|summary|text|desc", re.I))
                blurb = blurb_tag.get_text(strip=True)[:200] if blurb_tag else ""

                if title:
                    articles.append({"title": title, "link": link, "date": date, "blurb": blurb})
            break

    # Fallback: grab all links with text
    if not articles:
        for a in soup.select("a[href]"):
            text = a.get_text(strip=True)
            if len(text) > 15:
                href = a["href"]
                link = href if href.startswith("http") else f"https://www.austinisd.org{href}"
                articles.append({"title": text, "link": link, "date": "", "blurb": ""})

    return articles


def _match_articles(articles: List[Dict], schools: List[Dict]) -> List[Dict]:
    changes = []
    for article in articles:
        full_text = (article["title"] + " " + article["blurb"]).lower()

        has_property_keyword = any(kw in full_text for kw in PROPERTY_KEYWORDS)
        matched_school = _find_matching_school(full_text, schools)

        if matched_school and has_property_keyword:
            changes.append({
                "source": SOURCE_NAME,
                "source_url": article["link"] or SOURCE_URL,
                "school": f"{matched_school['name']} ({matched_school['address']})",
                "summary": article["title"],
                "details": f"{article['date']} — {article['blurb']}".strip(" —"),
            })
        elif has_property_keyword and _is_aisd_property_context(full_text):
            changes.append({
                "source": SOURCE_NAME,
                "source_url": article["link"] or SOURCE_URL,
                "school": None,
                "summary": f"AISD property press release: {article['title']}",
                "details": f"{article['date']} — {article['blurb']}".strip(" —"),
            })

    return changes


def _find_matching_school(text: str, schools: List[Dict]) -> Optional[Dict]:
    for school in schools:
        name_words = (
            school["name"]
            .lower()
            .replace("elementary", "")
            .replace("middle", "")
            .replace("school", "")
            .split()
        )
        name_words = [w for w in name_words if len(w) > 3]
        if any(w in text for w in name_words):
            return school
    return None


def _is_aisd_property_context(text: str) -> bool:
    return any(w in text for w in ["austin isd", "aisd", "district property", "school property"])
