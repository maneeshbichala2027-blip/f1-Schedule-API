# F1 schedule scraper with session times — version 3

This independent starter collects race-weekend dates and exact scheduled session
start times from public Formula1.com calendar and race pages. It is not an official
or endorsed Formula 1 product. Commercial data-use permission is separate.

## Free automatic updates using GitHub

1. This repository is already public: maneeshbichala2027-blip/f1-Schedule-API.
2. Keep scraper files in f1-schedule-starter/. The workflow is at the repository
   root under .github/workflows/update-schedule.yml and runs from that subfolder.
3. Open the repository Actions tab to view automatic refresh runs.
4. The workflow must be on your default branch. The instructions below assume main.
5. In repository Settings → Secrets and variables → Actions → Variables, add
   F1_SEASON with value 2026 to pin the season. The workflow defaults to 2026 so the configured website URL stays consistent.
6. Open Actions → Update official race schedule → Run workflow. Allow several minutes
   because the scraper retrieves every race's session schedule with request delays.
7. On success the workflow commits `f1-schedule-starter/data/schedule-2026.json`, `f1-schedule-starter/data/schedule-2026.csv`
   and `f1-schedule-starter/data/sessions-2026.csv`. Repository rules must allow this workflow to push.
   The file declares contents: write; organization policy can override that setting.
8. website-integration.js already points at this repository's public schedule URL.
9. Import mountRaceSchedule into your existing website and pass your schedule element:

```javascript
import { mountRaceSchedule } from './website-integration.js';
const unmount = mountRaceSchedule(document.querySelector('#race-schedule'));
```

Your page needs a container: `<div id="race-schedule"></div>`. Call unmount when
leaving the view in a single-page app. You can instead call loadRaceSchedule and
render the returned data in your own existing design.

The configured public data URL looks like this:

https://raw.githubusercontent.com/maneeshbichala2027-blip/f1-Schedule-API/main/f1-schedule-starter/data/schedule-2026.json

Open the resulting real URL in your browser to verify it returns JSON. No secret or
GitHub token belongs in your website code. This direct URL requires a public repo.
Only publish data and code you have the rights to publish. Your main website repo
can remain private. Serve the website over HTTP(S), not by double-clicking a file.

The workflow requests updates every six hours, at minute 17 UTC. The website helper
reads data every minute while mounted, but GitHub caching can add a delay. This is
scheduled data collection, NOT a live timing service. No Render subscription or
always-on Python server is needed for this route. Standard GitHub-hosted runners
are free for public repos, subject to GitHub terms and limits. Scheduled runs may
be delayed or skipped. Public repo scheduled workflows can be disabled after 60 days
of inactivity. Check the Actions tab and last successful update occasionally.

The workflow is configured in this repository. Check Actions for its latest result.
Your separate website still needs to import the helper or fetch the data URL.

## Data available to your website

Top-level JSON: schema_version=2, season, source_url, fetched_at, parsed_at,
collection_mode, date_semantics, races. The standalone exporter adds parsed_at and
collection_mode; the optional API provides stale and refresh status instead.

Each race includes:

- season, round, event_id, country_label, race_name, venue_label
- weekend_start and weekend_end: date-only values
- race_start_time_utc, race_start_time_track, race_start_time_ist
- track_timezone: source timezone, such as US/Central
- sessions_status, sessions_fetched_at, sessions
- source_url and fetched_at

The country_label is the source's event label, not verified geography. venue_label
may be a city; it is not guaranteed to be the circuit's full name.

Each session includes:

- session_id, name, session_type, source_state, timing_status
- start_time_utc, start_time_track, start_time_ist
- scheduled_end_time_utc, track_timezone, source_utc_offset
- source_url, fetched_at

Practice, qualifying, sprint qualifying, sprint and race sessions are collected
when present in the official race page's meetingSessions data. The scraper does
not assume every weekend has the same format or fabricate missing sessions.
Unpublished start times are null. An explicitly empty source schedule has an empty
sessions array and sessions_status=not_published. Unrecognized markup is a failure,
not a reason to invent times. No countdown should be shown for null start times.

Times include dates and UTC offsets. IST is Asia/Kolkata (+05:30); a race can fall
on the following calendar day in India. The parser checks the supplied offset
against the supplied timezone, so daylight-saving mismatches fail validation.
Scheduled end times are NOT actual race finishes. A completed session's start
is the schedule published by the source, not necessarily its actual start.

Use race_start_time_utc for an exact race-start countdown. Never turn a weekend
calendar date into an assumed race start time.

## Run the collector locally (Python 3.10+)

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-scraper.txt
python scrape_schedule.py --year 2026
```

Windows PowerShell: use `py -m venv .venv`, then `.venv\Scripts\Activate.ps1`.
The command now includes session times by default. It fetches all race pages with
two-second pauses. Use --weekends-only to skip sessions. Offline calendar parsing
requires --weekends-only because session details are on separate race pages:

```bash
python scrape_schedule.py --year 2026 --html calendar.html --weekends-only --out offline-data
```

Outputs include the main JSON, one race-summary CSV, and a separate session CSV.
JSON is the recommended input for websites because it preserves nested sessions.
Any download or parser failure aborts collection before output replacement. A
lower round count than an existing saved schedule also requires manual review.
Each file is replaced atomically; the three files are not one atomic transaction.
The GitHub job commits only if the whole collector command succeeds.

## Optional hosted API

The previously provided Python API also includes session times automatically.
Use this only if you prefer a hosted backend instead of free GitHub updates.

```bash
python -m pip install -r requirements.txt
python -m uvicorn api:create_app --factory --host 0.0.0.0 --port 8000 --workers 1
```

Endpoints: /api/schedule, /health and /ready. The API starts background collection
on startup and checks its six-hour refresh interval once a minute. Initial full
collection can take several minutes. Visitors never trigger collection. It keeps
the last successful snapshot and marks it stale if a later refresh fails. With no
successful snapshot it returns HTTP 503. A schedule is committed to SQLite only
after all calendar and session collection succeeds.

Settings: F1_SEASON (current UTC year by default), REFRESH_SECONDS (21600; minimum
3600), STATE_DIR (state), ALLOWED_ORIGINS (comma-separated exact website origins).
Use one worker and one replica with persistent storage. The in-process scheduler
cannot refresh while its host is asleep. The Dockerfile listens on port 8000 and
stores state under /data; attach a writable persistent volume. Configure HTTPS
through your hosting provider. This project does not configure a domain or TLS.

For a hosted API, replace DATA_URL in website-integration.js with its HTTPS
/api/schedule address. CORS is a browser control, not authentication. The API is
public and does not expose a visitor-triggered scrape endpoint. Monitor logs and
/ready. Deployments, Docker and GitHub execution are not validated by local tests.

## Tests and maintenance

```bash
python -m pip install -r requirements-dev.txt
python -m unittest -v
```

See VALIDATION.md for performed checks. The parser reads JSON embedded in public
page scripts without executing JavaScript. Changes to that source structure may
require maintenance. It honors robots.txt and does not bypass logins, CAPTCHAs or
blocks. It makes a finite sequential pass over the calendar and linked races.

## Content-use terms

Public access and robots allowance do not grant commercial rights. Formula1.com's
legal notices restrict extraction and commercial reuse. Obtain permission covering
collection, storage and website use before commercial deployment. The included
workflow, attribution and hosting plan do not supply a data licence.

Official calendar: https://www.formula1.com/en/racing/2026
Legal notices: https://www.formula1.com/en/information/legal-notices.7egvZU48hzrypubGBNcQKt
GitHub billing: https://docs.github.com/en/actions/concepts/billing-and-usage
GitHub schedules: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
