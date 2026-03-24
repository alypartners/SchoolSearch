#!/usr/bin/env python3
"""
Austin ISD School Property Monitor
Main orchestrator — runs all scrapers, detects changes, sends alerts,
updates state.json, and regenerates the dashboard.

Usage:
    python monitor.py              # Normal run
    python monitor.py --test-email # Send a test alert email
    python monitor.py --force      # Force alert even if no changes
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SCHOOLS_PATH = os.path.join(DATA_DIR, "schools.json")
STATE_PATH = os.path.join(DATA_DIR, "state.json")
DASHBOARD_PATH = os.path.join(BASE_DIR, "dashboard", "index.html")


def load_config() -> Dict:
    if not os.path.exists(CONFIG_PATH):
        print(
            "ERROR: config.json not found.\n"
            "Copy config.example.json to config.json and fill in your credentials."
        )
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_schools() -> List[Dict]:
    with open(SCHOOLS_PATH) as f:
        data = json.load(f)
    return data["schools"]


def load_state() -> Dict:
    if not os.path.exists(STATE_PATH):
        return {"last_run": None, "scrapers": {}}
    with open(STATE_PATH) as f:
        return json.load(f)


def save_state(state: Dict):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)
    print(f"[monitor] State saved to {STATE_PATH}")


def run_scraper(name: str, module, schools: List[Dict], prev_state: Dict, force: bool):
    """Run a single scraper and return (new_hash, changes)."""
    print(f"[monitor] Running scraper: {name}")
    try:
        content_hash, changes = module.scrape(schools)
    except Exception as e:
        print(f"[monitor] ERROR in {name}: {e}")
        return (prev_state.get(name, {}).get("hash", "ERROR"), [])

    prev_hash = prev_state.get(name, {}).get("hash")
    is_new = content_hash != prev_hash and content_hash != "ERROR"

    if is_new or force:
        if is_new:
            print(f"[monitor] CHANGE DETECTED in {name} ({len(changes)} change(s))")
        elif force:
            print(f"[monitor] Force mode — treating {name} as changed")
        return (content_hash, changes)
    else:
        print(f"[monitor] No change in {name}")
        return (content_hash, [])


def generate_dashboard(schools: List[Dict], state: Dict, all_changes: List[Dict]):
    """Generate an HTML dashboard summarizing current status."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_run = state.get("last_run", "Never")

    # Build per-school alert status
    alerted_school_ids = set()
    for change in all_changes:
        school_label = change.get("school", "")
        for school in schools:
            if school["name"] in (school_label or ""):
                alerted_school_ids.add(school["id"])

    rows = ""
    for school in schools:
        status_color = (
            "#d32f2f" if school["id"] in alerted_school_ids
            else "#f57c00" if school["status"] == "proposed_closing"
            else "#388e3c"
        )
        status_label = (
            "ALERT" if school["id"] in alerted_school_ids
            else "Proposed Closing" if school["status"] == "proposed_closing"
            else "Confirmed Closing"
        )
        rows += f"""
        <tr>
          <td style="padding:8px;border:1px solid #ddd;">{school['name']}</td>
          <td style="padding:8px;border:1px solid #ddd;">{school['address']}</td>
          <td style="padding:8px;border:1px solid #ddd;">{school['type'].title()}</td>
          <td style="padding:8px;border:1px solid #ddd;">
            <span style="background:{status_color};color:white;padding:2px 8px;border-radius:4px;font-size:12px;">
              {status_label}
            </span>
          </td>
        </tr>"""

    change_rows = ""
    for c in all_changes:
        change_rows += f"""
        <tr>
          <td style="padding:8px;border:1px solid #ddd;">{c.get('source','')}</td>
          <td style="padding:8px;border:1px solid #ddd;">{c.get('school') or '—'}</td>
          <td style="padding:8px;border:1px solid #ddd;">
            <a href="{c.get('source_url','#')}">{c.get('summary','')}</a>
          </td>
        </tr>"""

    changes_section = ""
    if all_changes:
        changes_section = f"""
    <h2 style="color:#d32f2f;">Recent Alerts ({len(all_changes)})</h2>
    <table style="width:100%;border-collapse:collapse;margin-bottom:24px;">
      <thead>
        <tr style="background:#fce4e4;">
          <th style="padding:8px;border:1px solid #ddd;text-align:left;">Source</th>
          <th style="padding:8px;border:1px solid #ddd;text-align:left;">School</th>
          <th style="padding:8px;border:1px solid #ddd;text-align:left;">Summary</th>
        </tr>
      </thead>
      <tbody>{change_rows}</tbody>
    </table>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Austin ISD Property Monitor — Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 1000px; margin: auto; padding: 20px; }}
    h1 {{ color: #333; }}
    .meta {{ color: #777; font-size: 13px; margin-bottom: 24px; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; }}
    th {{ background: #f5f5f5; text-align: left; }}
  </style>
</head>
<body>
  <h1>Austin ISD Closing School Property Monitor</h1>
  <p class="meta">Last run: {last_run} &nbsp;|&nbsp; Dashboard generated: {now}</p>
  {changes_section}
  <h2>Monitored Schools ({len(schools)})</h2>
  <table>
    <thead>
      <tr style="background:#f5f5f5;">
        <th style="padding:8px;border:1px solid #ddd;">School</th>
        <th style="padding:8px;border:1px solid #ddd;">Address</th>
        <th style="padding:8px;border:1px solid #ddd;">Type</th>
        <th style="padding:8px;border:1px solid #ddd;">Status</th>
      </tr>
    </thead>
    <tbody>{rows}
    </tbody>
  </table>
  <h2>Sources Monitored</h2>
  <ul>
    <li><a href="https://www.publicsurplus.com/sms/austinisd,tx/browse/home">PublicSurplus — AISD Auctions</a></li>
    <li><a href="https://www.austinisd.org/press-releases">AISD Press Releases</a></li>
    <li><a href="https://www.austinisd.org/facilities">AISD Facilities / Surplus Property Pages</a></li>
    <li><a href="https://go.boarddocs.com/tx/austinisd/Board.nsf/Public">BoardDocs — Board Meeting Agendas</a></li>
    <li><a href="https://www.loopnet.com/search/commercial-real-estate/austin-tx/for-sale/">LoopNet — Commercial Listings</a></li>
    <li><a href="https://www.crexi.com/properties">Crexi — Commercial Listings</a></li>
    <li><a href="https://www.traviscad.org/property-search/">TCAD — Travis County Appraisal District</a></li>
  </ul>
  <p style="color:#aaa;font-size:11px;margin-top:40px;">
    Auto-generated by SchoolSearch monitor.py — runs daily via GitHub Actions.
  </p>
</body>
</html>"""

    os.makedirs(os.path.dirname(DASHBOARD_PATH), exist_ok=True)
    with open(DASHBOARD_PATH, "w") as f:
        f.write(html)
    print(f"[monitor] Dashboard written to {DASHBOARD_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Austin ISD Property Monitor")
    parser.add_argument("--test-email", action="store_true", help="Send a test alert email and exit")
    parser.add_argument("--force", action="store_true", help="Force alert even if no changes detected")
    args = parser.parse_args()

    config = load_config()
    schools = load_schools()
    state = load_state()

    # Handle test email
    if args.test_email:
        from alerts.email_alert import send_test_alert
        ok = send_test_alert(config)
        sys.exit(0 if ok else 1)

    # Import all scrapers
    from scrapers import public_surplus, aisd_press, aisd_facilities, aisd_community, boarddocs, loopnet, crexi, tcad

    scraper_modules = [
        ("public_surplus", public_surplus),
        ("aisd_press", aisd_press),
        ("aisd_facilities", aisd_facilities),
        ("aisd_community", aisd_community),
        ("boarddocs", boarddocs),
        ("loopnet", loopnet),
        ("crexi", crexi),
        ("tcad", tcad),
    ]

    all_changes = []
    new_hashes = {}

    for name, module in scraper_modules:
        prev = state.get("scrapers", {})
        new_hash, changes = run_scraper(name, module, schools, prev, args.force)
        new_hashes[name] = {
            "hash": new_hash,
            "last_checked": datetime.now(timezone.utc).isoformat(),
            "changes_found": len(changes),
        }
        all_changes.extend(changes)

    # Update and save state
    now_iso = datetime.now(timezone.utc).isoformat()
    state["last_run"] = now_iso
    state["scrapers"] = new_hashes
    save_state(state)

    # Send alert if changes found
    if all_changes:
        print(f"[monitor] Sending alert for {len(all_changes)} change(s)...")
        from alerts.email_alert import send_alert
        send_alert(config, all_changes)
    else:
        print("[monitor] No changes detected — no alert sent.")

    # Generate dashboard
    generate_dashboard(schools, state, all_changes)

    print(f"[monitor] Done. {len(all_changes)} change(s) found across {len(scraper_modules)} source(s).")


if __name__ == "__main__":
    main()
