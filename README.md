# Austin ISD School Property Monitor

Monitors multiple online sources daily and sends an email alert when any closing Austin ISD school property goes up for sale, auction, or is transferred.

## Monitored Schools

16 schools confirmed or proposed to close for 2026-27:

**Confirmed:** Barrington ES, Becker ES, Dawson ES, Oak Springs ES, Ridgetop ES, Sunset Valley ES, Widén ES, Winn Montessori ES, Bedichek MS, Martin MS, International High School

**Proposed (spring 2026 decision pending):** Bryker Woods ES, Maplewood ES, Palm ES, Odom ES, Reilly ES

## Sources Monitored

| Source | What it watches |
|--------|----------------|
| [PublicSurplus](https://www.publicsurplus.com/sms/austinisd,tx/browse/home) | AISD auction/surplus property listings |
| [AISD Press Releases](https://www.austinisd.org/press-releases) | Official announcements mentioning sale/surplus/RFP |
| [BoardDocs](https://go.boarddocs.com/tx/austinisd/Board.nsf/Public) | Board meeting agendas with property items |
| [LoopNet](https://www.loopnet.com/) | Commercial real estate listings by address |
| [Crexi](https://www.crexi.com/) | Commercial real estate listings by address |
| [TCAD](https://www.traviscad.org/) | Travis County ownership/appraisal records |

## Setup

### 1. Clone and install

```bash
git clone <your-repo-url>
cd SchoolSearch
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp config.example.json config.json
```

Edit `config.json`:
```json
{
  "gmail_address": "your.gmail@gmail.com",
  "gmail_app_password": "xxxx xxxx xxxx xxxx",
  "alert_email": "recipient@example.com"
}
```

**Gmail App Password:** Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) — requires 2FA enabled.

### 3. Test email

```bash
python monitor.py --test-email
```

### 4. Run manually

```bash
python monitor.py
```

Open `dashboard/index.html` in your browser to see current status.

## GitHub Actions (automated daily runs)

1. Push this repo to GitHub
2. Go to **Settings → Secrets and variables → Actions** and add:
   - `GMAIL_ADDRESS` — your Gmail address
   - `GMAIL_APP_PASSWORD` — your Gmail app password
   - `ALERT_EMAIL` — where to send alerts
3. The workflow runs daily at 9 AM Central and on manual trigger
4. Enable GitHub Pages on the `dashboard/` folder to view the dashboard online

## File Structure

```
SchoolSearch/
├── monitor.py              # Main orchestrator
├── config.json             # Credentials (gitignored)
├── config.example.json     # Template
├── requirements.txt
├── data/
│   ├── schools.json        # School list with addresses
│   └── state.json          # Last-known state (auto-updated)
├── scrapers/
│   ├── public_surplus.py
│   ├── aisd_press.py
│   ├── boarddocs.py
│   ├── loopnet.py
│   ├── crexi.py
│   └── tcad.py
├── alerts/
│   └── email_alert.py
└── dashboard/
    └── index.html          # Auto-generated status page
```

## How it works

1. Each scraper fetches its source and returns a SHA-256 hash of the content
2. The hash is compared to the previous run stored in `state.json`
3. If changed, the scraper also returns the specific matching items (school name/address matches)
4. All changes are consolidated into a single HTML email alert
5. `state.json` and `dashboard/index.html` are updated and committed back to the repo

## Updating the school list

Edit `data/schools.json` to add TCAD account numbers once confirmed, or to add/remove schools.
