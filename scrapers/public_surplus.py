"""
Scraper: PublicSurplus.com — Austin ISD auction listings
URL: https://www.publicsurplus.com/sms/austinisd,tx/browse/home
"""

import hashlib
import json
import re
import time
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

SOURCE_NAME = "PublicSurplus"
SOURCE_URL = "https://www.publicsurplus.com/sms/austinisd,tx/browse/home"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def scrape(schools: List[Dict]) -> Tuple[str, List[Dict]]:
    """
    Fetch PublicSurplus Austin ISD listings page and check for auctions
    matching known school names or addresses.

    Returns:
        (content_hash, changes_list)
        changes_list is empty if nothing new, otherwise contains dicts for email_alert.
    """
    try:
        resp = requests.get(SOURCE_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[{SOURCE_NAME}] Request error: {e}")
        return ("ERROR", [])

    soup = BeautifulSoup(resp.text, "html.parser")

    # Collect all listing text — titles, descriptions, links
    listings = _extract_listings(soup)
    content = json.dumps(listings, sort_keys=True)
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    # Match listings against known schools
    changes = _match_schools(listings, schools)

    return (content_hash, changes)


def _extract_listings(soup: BeautifulSoup) -> List[Dict]:
    listings = []

    # PublicSurplus uses table rows for auction items
    rows = soup.select("table.table tbody tr")
    if not rows:
        # Fallback: grab all anchor text that looks like auction items
        rows = soup.select("tr")

    for row in rows:
        cells = row.find_all("td")
        if not cells:
            continue
        title_cell = cells[0] if cells else None
        if not title_cell:
            continue
        title = title_cell.get_text(strip=True)
        link_tag = title_cell.find("a")
        link = ""
        if link_tag and link_tag.get("href"):
            href = link_tag["href"]
            link = href if href.startswith("http") else f"https://www.publicsurplus.com{href}"

        # Also grab any extra text from remaining cells (end date, price, etc.)
        extra = " | ".join(c.get_text(strip=True) for c in cells[1:] if c.get_text(strip=True))

        if title:
            listings.append({"title": title, "link": link, "extra": extra})

    return listings


def _match_schools(listings: List[Dict], schools: List[Dict]) -> List[Dict]:
    changes = []
    for listing in listings:
        text = (listing["title"] + " " + listing["extra"]).lower()
        matched_school = _find_matching_school(text, schools)
        if matched_school:
            changes.append({
                "source": SOURCE_NAME,
                "source_url": listing["link"] or SOURCE_URL,
                "school": f"{matched_school['name']} ({matched_school['address']})",
                "summary": f"New auction listing: {listing['title']}",
                "details": listing["extra"],
            })
        elif _is_school_property(text):
            # Generic AISD property match without specific school
            changes.append({
                "source": SOURCE_NAME,
                "source_url": listing["link"] or SOURCE_URL,
                "school": None,
                "summary": f"Possible AISD property listing: {listing['title']}",
                "details": listing["extra"],
            })
    return changes


def _find_matching_school(text: str, schools: List[Dict]) -> Optional[Dict]:
    for school in schools:
        # Match on school name keywords
        name_words = school["name"].lower().replace("elementary", "").replace("middle", "").replace("school", "").split()
        name_words = [w for w in name_words if len(w) > 3]
        if any(w in text for w in name_words):
            return school
        # Match on street address
        addr_parts = school["address"].lower().split(",")[0].split()
        addr_keywords = [p for p in addr_parts if len(p) > 3 and not p.isdigit()]
        if addr_keywords and all(k in text for k in addr_keywords[:2]):
            return school
    return None


def _is_school_property(text: str) -> bool:
    keywords = ["aisd", "austin isd", "school", "campus", "elementary", "middle school"]
    return any(k in text for k in keywords)
