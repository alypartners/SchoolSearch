"""
Scraper: AISD Community Engagement & Meetings Pages
Monitors AISD pages that publish community meeting notices, presentations,
and property repurposing updates — often posted before formal press releases.

Key pages:
- https://www.austinisd.org/community-engagement
- https://www.austinisd.org/right-sizing
- https://www.austinisd.org/news
- https://www.austinisd.org/facilities/surplus-property
- https://www.austinisd.org/bond/community-meetings
"""

import hashlib
import json
import re
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

SOURCE_NAME = "AISD Community Engagement"
URLS_TO_MONITOR = [
    "https://www.austinisd.org/community-engagement",
    "https://www.austinisd.org/right-sizing",
    "https://www.austinisd.org/news",
    "https://www.austinisd.org/facilities/surplus-property",
    "https://www.austinisd.org/bond/community-meetings",
    "https://www.austinisd.org/future-ready-aisd",
]
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

PROPERTY_KEYWORDS = [
    "surplus", "repurpose", "repurposing", "sale", "sell", "lease",
    "disposition", "rfp", "bid", "community input", "market analysis",
    "entitlement", "facility evaluation", "surplus property repurposing",
    "community meeting", "presentation", "campus", "property",
    "closing", "closed", "consolidat",
]


def scrape(schools: List[Dict]) -> Tuple[str, List[Dict]]:
    """
    Fetch AISD community engagement pages and detect mentions of
    school names alongside property/repurposing activity.

    Returns:
        (content_hash, changes_list)
    """
    all_content = []
    all_changes = []

    for url in URLS_TO_MONITOR:
        page_text, changes = _scrape_url(url, schools)
        all_content.append({"url": url, "text": page_text[:300]})
        all_changes.extend(changes)

    content_hash = hashlib.sha256(
        json.dumps(all_content, sort_keys=True).encode()
    ).hexdigest()

    return (content_hash, all_changes)


def _scrape_url(url: str, schools: List[Dict]) -> Tuple[str, List[Dict]]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 404:
            return ("", [])
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[{SOURCE_NAME}] Error fetching {url}: {e}")
        return ("ERROR", [])

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove nav/header/footer noise
    for tag in soup.select("nav, header, footer, .menu, .navigation"):
        tag.decompose()

    main = soup.find("main") or soup.find("article") or soup.body
    text = main.get_text(separator=" ", strip=True) if main else soup.get_text()
    text_lower = text.lower()

    changes = []

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
        school_mentioned = any(w in text_lower for w in name_words)
        has_property_kw = any(kw in text_lower for kw in PROPERTY_KEYWORDS)

        if school_mentioned and has_property_kw:
            snippet = _find_snippet(text, name_words + PROPERTY_KEYWORDS)
            changes.append({
                "source": SOURCE_NAME,
                "source_url": url,
                "school": f"{school['name']} ({school['address']})",
                "summary": (
                    f"AISD community page mentions {school['name']} "
                    f"with property/repurposing activity"
                ),
                "details": snippet,
            })

    return (text[:300], changes)


def _find_snippet(text: str, keywords: List[str]) -> str:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for sentence in sentences:
        s_lower = sentence.lower()
        if any(kw in s_lower for kw in keywords):
            return sentence[:250]
    return text[:250]
