"""
Scraper: Travis Central Appraisal District (TCAD)
URL: https://www.traviscad.org/

Queries TCAD property search for known school addresses to detect
ownership changes, new listings, or status changes.

TCAD has a public property search at:
  https://www.traviscad.org/property-search/
Their underlying API endpoint accepts address lookups.
"""

import hashlib
import json
import re
import time
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

SOURCE_NAME = "TCAD (Travis CAD)"
TCAD_SEARCH_URL = "https://www.traviscad.org/property-search/"
# TCAD uses an iframed search tool; the underlying search API:
TCAD_API_URL = "https://propaccess.traviscad.org/clientdb/Property.aspx"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Referer": "https://propaccess.traviscad.org/",
}

# AISD as owner — variations to detect
AISD_OWNER_PATTERNS = [
    "austin independent school",
    "austin i.s.d",
    "aisd",
    "austin isd",
]


def scrape(schools: List[Dict]) -> Tuple[str, List[Dict]]:
    """
    For each school with a known address, query TCAD property records.
    Detect if ownership has changed away from AISD (indicating a sale).

    Returns:
        (content_hash, changes_list)
    """
    all_records = []
    changes = []

    for school in schools:
        record = _lookup_property(school)
        if record:
            all_records.append(record)
            change = _check_for_changes(record, school)
            if change:
                changes.append(change)
        time.sleep(1.5)

    content = json.dumps(all_records, sort_keys=True)
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    return (content_hash, changes)


def _lookup_property(school: Dict) -> Optional[Dict]:
    """Look up a property by address on TCAD."""
    # If we have a TCAD account number, use it directly
    if school.get("tcad_account"):
        return _lookup_by_account(school["tcad_account"], school)

    # Otherwise search by address
    return _lookup_by_address(school)


def _lookup_by_address(school: Dict) -> Optional[Dict]:
    street = school["address"].split(",")[0].strip()
    # Parse street number and name
    parts = street.split()
    if not parts:
        return None
    street_num = parts[0]
    street_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    # TCAD propaccess address search
    search_url = "https://propaccess.traviscad.org/clientdb/Property.aspx"
    params = {
        "cid": "1",
        "type": "address",
        "value": street,
    }

    try:
        resp = requests.get(search_url, params=params, headers=HEADERS, timeout=30)
        if resp.status_code in (403, 429):
            print(f"[{SOURCE_NAME}] Rate-limited for {school['name']}")
            return None
        resp.raise_for_status()
        return _parse_property_page(resp.text, school)
    except requests.RequestException as e:
        print(f"[{SOURCE_NAME}] Error for {school['name']}: {e}")
        return None


def _lookup_by_account(account_num: str, school: Dict) -> Optional[Dict]:
    search_url = "https://propaccess.traviscad.org/clientdb/Property.aspx"
    params = {"cid": "1", "type": "acct", "value": account_num}
    try:
        resp = requests.get(search_url, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return _parse_property_page(resp.text, school)
    except requests.RequestException as e:
        print(f"[{SOURCE_NAME}] Error for account {account_num}: {e}")
        return None


def _parse_property_page(html: str, school: Dict) -> Optional[Dict]:
    soup = BeautifulSoup(html, "html.parser")

    # Look for owner name in the property details table
    owner = ""
    address_found = ""

    # TCAD propaccess has a results table
    for row in soup.select("table tr"):
        cells = row.find_all(["td", "th"])
        cell_texts = [c.get_text(strip=True).lower() for c in cells]
        full_texts = [c.get_text(strip=True) for c in cells]

        for i, ct in enumerate(cell_texts):
            if "owner" in ct and i + 1 < len(full_texts):
                owner = full_texts[i + 1]
            if "situs" in ct or "property address" in ct:
                if i + 1 < len(full_texts):
                    address_found = full_texts[i + 1]

    # Try to find owner from labeled divs/spans too
    if not owner:
        for label in soup.find_all(string=re.compile(r"owner", re.I)):
            parent = label.parent
            if parent:
                sibling = parent.find_next_sibling()
                if sibling:
                    owner = sibling.get_text(strip=True)
                    break

    if not owner and not address_found:
        return None

    return {
        "school_id": school["id"],
        "school_name": school["name"],
        "address_searched": school["address"],
        "tcad_owner": owner,
        "tcad_address": address_found,
        "url": f"https://propaccess.traviscad.org/clientdb/Property.aspx?cid=1&type=address&value={school['address'].split(',')[0]}",
    }


def _check_for_changes(record: Dict, school: Dict) -> Optional[Dict]:
    """Return a change dict if owner is no longer AISD."""
    owner = record.get("tcad_owner", "").lower()
    if not owner:
        return None

    is_aisd = any(pattern in owner for pattern in AISD_OWNER_PATTERNS)

    if not is_aisd and owner:
        # Owner changed — possible sale!
        return {
            "source": SOURCE_NAME,
            "source_url": record["url"],
            "school": f"{school['name']} ({school['address']})",
            "summary": f"TCAD ownership change detected — owner is now: {record['tcad_owner']}",
            "details": (
                f"Expected AISD ownership. TCAD shows: '{record['tcad_owner']}'. "
                f"This may indicate a completed property sale or transfer. "
                f"Verify at: {record['url']}"
            ),
        }
    return None
