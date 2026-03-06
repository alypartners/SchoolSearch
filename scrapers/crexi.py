"""
Scraper: Crexi.com — Commercial Real Estate listings in Austin
Searches for listings matching known school addresses.

NOTE: Crexi is JS-rendered. This scraper tries their search API endpoint.
If unavailable, falls back to HTML scraping of search results.
"""

import hashlib
import json
import time
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

SOURCE_NAME = "Crexi"
BASE_URL = "https://www.crexi.com"
SEARCH_URL = "https://www.crexi.com/properties"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}


def scrape(schools: List[Dict]) -> Tuple[str, List[Dict]]:
    """
    Search Crexi for each school's address.

    Returns:
        (content_hash, changes_list)
    """
    all_results = []
    changes = []

    for school in schools:
        results, matched = _search_school(school)
        all_results.extend(results)
        changes.extend(matched)
        time.sleep(2)

    content = json.dumps(all_results, sort_keys=True)
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    return (content_hash, changes)


def _search_school(school: Dict) -> Tuple[List[Dict], List[Dict]]:
    street = school["address"].split(",")[0].strip()
    # Crexi search: address query
    params = {
        "address": street + " Austin TX",
        "propertyTypes": "5",  # Special Purpose (schools fall here)
        "transactionType": "sale",
    }
    try:
        resp = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=30)
        if resp.status_code in (403, 429):
            print(f"[{SOURCE_NAME}] Rate-limited for {school['name']} — skipping")
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
    for selector in [
        ".property-card",
        ".listing-card",
        "[data-testid='property-card']",
        "article",
        ".card",
    ]:
        cards = soup.select(selector)
        if cards:
            for card in cards:
                title = card.get_text(separator=" ", strip=True)[:250]
                link_tag = card.find("a", href=True)
                link = ""
                if link_tag:
                    href = link_tag["href"]
                    link = href if href.startswith("http") else f"{BASE_URL}{href}"
                if title:
                    listings.append({"title": title, "link": link or page_url})
            break
    return listings


def _match_to_school(listings: List[Dict], school: Dict) -> List[Dict]:
    changes = []
    street = school["address"].split(",")[0].lower().strip()
    parts = street.split()
    street_number = parts[0] if parts else ""
    street_name = " ".join(parts[1:3]) if len(parts) > 1 else ""

    for listing in listings:
        text = listing["title"].lower()
        if street_number and street_name and street_number in text and street_name in text:
            changes.append({
                "source": SOURCE_NAME,
                "source_url": listing["link"],
                "school": f"{school['name']} ({school['address']})",
                "summary": f"Crexi listing may match school address: {listing['title'][:100]}",
                "details": f"Address searched: {school['address']}",
            })
    return changes
