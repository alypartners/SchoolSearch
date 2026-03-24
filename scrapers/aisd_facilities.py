"""
Scraper: AISD Facilities / Surplus Property Pages
Monitors AISD's facilities and surplus property repurposing pages directly,
which are updated before press releases and board meetings.

Key pages:
- https://www.austinisd.org/facilities
- https://www.austinisd.org/surplus-property (if it exists)
- https://www.austinisd.org/bond (bond/facilities updates)
"""

import hashlib
import json
import re
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

SOURCE_NAME = "AISD Facilities Page"
URLS_TO_MONITOR = [
    "https://www.austinisd.org/facilities",
    "https://www.austinisd.org/bond",
    "https://www.austinisd.org/right-sizing",
    "https://www.austinisd.org/surplus-property",
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
    "entitlement", "facility evaluation", "surplus property repurposing process",
    "closing", "closed campus",
]


def scrape(schools: List[Dict]) -> Tuple[str, List[Dict]]:
    """
    Fetch AISD facilities pages and check for property-related content
    mentioning school names or surplus property keywords.

    Returns:
        (content_hash, changes_list)
    """
    all_content = []
    all_changes = []

    for url in URLS_TO_MONITOR:
        content, changes = _scrape_url(url, schools)
        all_content.append({"url": url, "content": content})
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
    # Get main page text (strip nav/footer noise)
    main = soup.find("main") or soup.find("article") or soup.body
    text = main.get_text(separator=" ", strip=True) if main else soup.get_text()
    text_lower = text.lower()

    changes = []

    # Check each school against page text
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
            # Find the most relevant sentence
            snippet = _find_snippet(text, name_words)
            changes.append({
                "source": SOURCE_NAME,
                "source_url": url,
                "school": f"{school['name']} ({school['address']})",
                "summary": f"AISD facilities page mentions {school['name']} with property activity",
                "details": snippet,
            })

    return (text[:500], changes)


def _find_snippet(text: str, keywords: List[str]) -> str:
    """Find a relevant sentence containing one of the keywords."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for sentence in sentences:
        if any(kw in sentence.lower() for kw in keywords):
            return sentence[:200]
    return text[:200]
