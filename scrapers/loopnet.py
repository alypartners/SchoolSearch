"""
Scraper: LoopNet — Commercial Real Estate listings in Austin
Searches for listings matching known school addresses.

NOTE: LoopNet is heavily JS-rendered and may require rotating user-agents or
a paid API. This scraper uses their search page with address-based queries.
If blocked, it returns the last known state (no false alert).
"""

import hashlib
import json
import time
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

SOURCE_NAME = "LoopNet"
BASE_SEARCH_URL = "https://www.loopnet.com/search/commercial-real-estate/austin-tx/for-sale/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def scrape(schools: List[Dict]) -> Tuple[str, List[Dict]]:
    """
    For each school, run a LoopNet search for its street address and check
    if any listing title/address matches.

    Returns:
        (content_hash, changes_list)
    """
    all_results = []
    changes = []

    for school in schools:
        results, matched = _search_school(school)
        all_results.extend(results)
        changes.extend(matched)
        # Be polite to avoid rate-limiting
        time.sleep(2)

    content = json.dumps(all_results, sort_keys=True)
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    return (content_hash, changes)


def _search_school(school: Dict) -> Tuple[List[Dict], List[Dict]]:
    """Search LoopNet for a specific school's street address."""
    # Use just the street portion (e.g., "906 W Milton St")
    street = school["address"].split(",")[0].strip()
    search_url = f"{BASE_SEARCH_URL}?sk={street.replace(' ', '+')}&t=4"

    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=30)
        if resp.status_code == 403:
            print(f"[{SOURCE_NAME}] Blocked (403) for {school['name']} — skipping")
            return ([], [])
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[{SOURCE_NAME}] Error searching {school['name']}: {e}")
        return ([], [])

    soup = BeautifulSoup(resp.text, "html.parser")
    listings = _extract_listings(soup, resp.url)
    matched = _match_to_school(listings, school)
    return (listings, matched)


def _extract_listings(soup: BeautifulSoup, page_url: str) -> List[Dict]:
    listings = []
    # LoopNet listing cards use various selectors depending on version
    for selector in [".placard", ".listing-card", "article.property", "[data-testid='listing-card']"]:
        cards = soup.select(selector)
        if cards:
            for card in cards:
                title = card.get_text(separator=" ", strip=True)[:200]
                link_tag = card.find("a", href=True)
                link = ""
                if link_tag:
                    href = link_tag["href"]
                    link = href if href.startswith("http") else f"https://www.loopnet.com{href}"
                listings.append({"title": title, "link": link or page_url})
            break
    return listings


def _match_to_school(listings: List[Dict], school: Dict) -> List[Dict]:
    changes = []
    street = school["address"].split(",")[0].lower().strip()
    street_number = street.split()[0] if street else ""
    street_name = " ".join(street.split()[1:3]) if street else ""

    for listing in listings:
        text = listing["title"].lower()
        # Match on street number + street name fragment
        if street_number and street_name and street_number in text and street_name in text:
            changes.append({
                "source": SOURCE_NAME,
                "source_url": listing["link"],
                "school": f"{school['name']} ({school['address']})",
                "summary": f"LoopNet listing may match school address: {listing['title'][:100]}",
                "details": f"Address searched: {school['address']}",
            })
    return changes
