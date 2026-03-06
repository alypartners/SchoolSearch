"""
Email alert system for Austin ISD School Property Monitor.
Sends HTML emails via Gmail SMTP when property changes are detected.
"""

import smtplib
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import List, Dict, Any


def send_alert(config: Dict, changes: List[Dict]) -> bool:
    """
    Send a consolidated HTML email alert for all detected changes.

    Args:
        config: dict with gmail_address, gmail_app_password, alert_email
        changes: list of change dicts from scrapers, each with keys:
                 source, source_url, school (or None), summary, details

    Returns:
        True if sent successfully, False otherwise.
    """
    if not changes:
        return False

    subject = _build_subject(changes)
    html_body = _build_html_body(changes)
    text_body = _build_text_body(changes)

    recipients = config["alert_email"]
    if isinstance(recipients, str):
        recipients = [recipients]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["gmail_address"]
    msg["To"] = ", ".join(recipients)

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(config["gmail_address"], config["gmail_app_password"])
            server.sendmail(
                config["gmail_address"],
                recipients,
                msg.as_string()
            )
        print(f"[alert] Email sent to {', '.join(recipients)} — {len(changes)} change(s)")
        return True
    except smtplib.SMTPAuthenticationError:
        print("[alert] ERROR: Gmail authentication failed. Check gmail_app_password in config.json.")
        return False
    except Exception as e:
        print(f"[alert] ERROR sending email: {e}")
        return False


def send_test_alert(config: Dict) -> bool:
    """Send a test email to verify credentials and config are working."""
    test_change = {
        "source": "Test",
        "source_url": "https://example.com",
        "school": "Test School (1234 Example St)",
        "summary": "This is a test alert — your monitoring system is configured correctly.",
        "details": "No real changes detected. This email confirms alerts are working."
    }
    return send_alert(config, [test_change])


def _build_subject(changes: List[Dict]) -> str:
    n = len(changes)
    sources = sorted(set(c["source"] for c in changes))
    school_names = sorted(set(c["school"] for c in changes if c.get("school")))

    if school_names:
        schools_str = ", ".join(school_names[:2])
        if len(school_names) > 2:
            schools_str += f" +{len(school_names) - 2} more"
        return f"[AISD Alert] Activity detected — {schools_str} ({', '.join(sources)})"
    else:
        return f"[AISD Alert] {n} change(s) detected — {', '.join(sources)}"


def _build_html_body(changes: List[Dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = ""
    for c in changes:
        school = c.get("school") or "—"
        source = c.get("source", "Unknown")
        url = c.get("source_url", "#")
        summary = c.get("summary", "")
        details = c.get("details", "")
        rows += f"""
        <tr>
          <td style="padding:8px;border:1px solid #ddd;font-weight:bold;">{school}</td>
          <td style="padding:8px;border:1px solid #ddd;">
            <a href="{url}" style="color:#1a73e8;">{source}</a>
          </td>
          <td style="padding:8px;border:1px solid #ddd;">{summary}</td>
          <td style="padding:8px;border:1px solid #ddd;font-size:12px;color:#555;">{details}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:900px;margin:auto;padding:20px;">
  <div style="background:#d32f2f;color:white;padding:16px 20px;border-radius:6px 6px 0 0;">
    <h2 style="margin:0;">Austin ISD Property Alert</h2>
    <p style="margin:4px 0 0;">Detected {len(changes)} change(s) — {now}</p>
  </div>
  <div style="border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 6px 6px;">
    <table style="width:100%;border-collapse:collapse;">
      <thead>
        <tr style="background:#f5f5f5;">
          <th style="padding:8px;border:1px solid #ddd;text-align:left;">School</th>
          <th style="padding:8px;border:1px solid #ddd;text-align:left;">Source</th>
          <th style="padding:8px;border:1px solid #ddd;text-align:left;">Summary</th>
          <th style="padding:8px;border:1px solid #ddd;text-align:left;">Details</th>
        </tr>
      </thead>
      <tbody>{rows}
      </tbody>
    </table>
    <hr style="margin:24px 0;border:none;border-top:1px solid #eee;">
    <p style="color:#888;font-size:12px;">
      Austin ISD School Property Monitor — running automatically via GitHub Actions.<br>
      To unsubscribe or adjust settings, edit <code>config.json</code>.
    </p>
  </div>
</body>
</html>"""


def _build_text_body(changes: List[Dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"Austin ISD Property Alert — {now}",
        f"{len(changes)} change(s) detected",
        "=" * 60,
    ]
    for c in changes:
        lines.append(f"\nSchool:  {c.get('school') or '—'}")
        lines.append(f"Source:  {c.get('source', 'Unknown')} — {c.get('source_url', '')}")
        lines.append(f"Summary: {c.get('summary', '')}")
        if c.get("details"):
            lines.append(f"Details: {c['details']}")
        lines.append("-" * 40)
    return "\n".join(lines)


if __name__ == "__main__":
    # Quick test: python -m alerts.email_alert
    import sys
    import os
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    if not os.path.exists(config_path):
        print("config.json not found. Copy config.example.json and fill in your credentials.")
        sys.exit(1)
    with open(config_path) as f:
        cfg = json.load(f)
    print("Sending test email...")
    ok = send_test_alert(cfg)
    sys.exit(0 if ok else 1)
