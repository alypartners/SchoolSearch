"""
Scraper: BoardDocs — Austin ISD Board Meeting Agendas
URL: https://go.boarddocs.com/tx/austinisd/Board.nsf/Public
Monitors agendas for property-related items (sale, surplus, RFP, disposition).
"""

import hashlib
import json
import re
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

SOURCE_NAME = "BoardDocs (AISD Board)"
SOURCE_URL = "https://go.boarddocs.com/tx/austinisd/Board.nsf/Public"
# BoardDocs API endpoint for recent meetings
MEETINGS_API = "https://go.boarddocs.com/tx/austinisd/Board.nsf/BD-GetMeetings?open&pk=AUSTINISD"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Referer": "https://go.boarddocs.com/",
}

PROPERTY_KEYWORDS = [
    "sale", "sell", "property", "surplus", "bid", "rfp", "real estate",
    "disposition", "convey", "auction", "lease", "facility closure",
    "school closure", "closed campus", "request for proposal",
]


def scrape(schools: List[Dict]) -> Tuple[str, List[Dict]]:
    """
    Fetch recent BoardDocs meetings and agenda items.
    Look for property-related agenda items mentioning school names.

    Returns:
        (content_hash, changes_list)
    """
    meetings = _fetch_meetings()
    if not meetings:
        print(f"[{SOURCE_NAME}] Could not fetch meetings list.")
        return ("ERROR", [])

    # Check only the most recent 3 meetings to avoid over-fetching
    recent = meetings[:3]
    all_agenda_items = []
    for meeting in recent:
        items = _fetch_agenda(meeting.get("unique", ""), meeting.get("numberDate", ""))
        all_agenda_items.extend(items)

    content = json.dumps(all_agenda_items, sort_keys=True)
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    changes = _match_items(all_agenda_items, schools)
    return (content_hash, changes)


def _fetch_meetings() -> List[Dict]:
    try:
        resp = requests.get(MEETINGS_API, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        # BoardDocs returns a list of meeting objects
        if isinstance(data, list):
            return sorted(data, key=lambda m: m.get("numberDate", ""), reverse=True)
        return []
    except Exception as e:
        print(f"[{SOURCE_NAME}] Meetings fetch error: {e}")
        # Fallback: parse the HTML page for meeting links
        return _fetch_meetings_html()


def _fetch_meetings_html() -> List[Dict]:
    try:
        resp = requests.get(SOURCE_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        meetings = []
        for a in soup.select("a[href*='Meeting']"):
            text = a.get_text(strip=True)
            href = a.get("href", "")
            if text:
                meetings.append({"unique": href, "numberDate": text, "label": text})
        return meetings[:5]
    except Exception as e:
        print(f"[{SOURCE_NAME}] HTML fallback error: {e}")
        return []


def _fetch_agenda(meeting_id: str, meeting_date: str) -> List[Dict]:
    if not meeting_id:
        return []
    try:
        agenda_url = (
            f"https://go.boarddocs.com/tx/austinisd/Board.nsf/"
            f"BD-GetAgendaForPublic?open&meeting={meeting_id}"
        )
        resp = requests.get(agenda_url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        items = []
        if isinstance(data, list):
            for item in data:
                title = item.get("name", item.get("title", ""))
                uid = item.get("unique", "")
                link = (
                    f"https://go.boarddocs.com/tx/austinisd/Board.nsf/goto?open&id={uid}"
                    if uid else SOURCE_URL
                )
                items.append({"title": title, "link": link, "meeting_date": meeting_date})
        return items
    except Exception as e:
        print(f"[{SOURCE_NAME}] Agenda fetch error for meeting {meeting_id}: {e}")
        return []


def _match_items(items: List[Dict], schools: List[Dict]) -> List[Dict]:
    changes = []
    for item in items:
        text = item["title"].lower()
        has_property_kw = any(kw in text for kw in PROPERTY_KEYWORDS)
        matched_school = _find_matching_school(text, schools)

        if has_property_kw or matched_school:
            school_label = (
                f"{matched_school['name']} ({matched_school['address']})"
                if matched_school else None
            )
            changes.append({
                "source": SOURCE_NAME,
                "source_url": item["link"],
                "school": school_label,
                "summary": f"Board agenda item: {item['title']}",
                "details": f"Meeting date: {item.get('meeting_date', 'unknown')}",
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
