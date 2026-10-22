# Race schedule collector + automatic API — version 2

Collects championship race-weekend dates from the official Formula1.com calendar.
This is an independent technical starter, not an official or endorsed F1 product.

## Start the automatic API (Python 3.10+)

Unzip this project and open Terminal in its folder.

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn api:create_app --factory --host 0.0.0.0 --port 8000 --workers 1
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn api:create_app --factory --host 0.0.0.0 --port 8000 --workers 1
```

Open http://localhost:8000/api/schedule after initial collection completes.
Interactive endpoint documentation: http://localhost:8000/docs.

The service automatically collects the current season on first startup and checks
for refreshes every six hours. It stores the last successful schedule in SQLite.
Visitors read the cached data; they do not trigger new scrapes. On a source failure,
the API keeps the saved schedule and marks it stale. If no good schedule exists,
it returns HTTP 503 rather than inventing data. Initial retrieval may take a minute.
The collector makes no immediate retry after failure; its next attempt is at the
normal refresh interval, including across restarts using the same persistent disk.

Configure environment variables before starting:

| Variable | Default | Purpose |
| --- | --- | --- |
| F1_SEASON | Current UTC year | Season to collect; pin this if needed |
| REFRESH_SECONDS | 21600 | Refresh interval; minimum 3600 seconds |
| STATE_DIR | state | Writable persistent SQLite directory |
| ALLOWED_ORIGINS | http://localhost:3000,http://localhost:5173 | Comma-separated website origins |

Production example (replace example.com with your actual website origin):

```bash
export F1_SEASON=2026
export STATE_DIR=/absolute/persistent/directory
export ALLOWED_ORIGINS=https://example.com,https://www.example.com
python -m uvicorn api:create_app --factory --host 0.0.0.0 --port 8000 --workers 1
```

Use exactly one worker and one service replica. This starter embeds its collector
inside the API process. Multiple workers or replicas would each run a collector.
For horizontal scaling, move collection to one dedicated scheduled worker and use
a shared database. CORS governs browser access; it is not API authentication.
The read API is public, has no public refresh endpoint and is not a paid API gateway.

## Connect your website once

Use `website-integration.js`: replace API_BASE with the hosted HTTPS API URL and
import `mountRaceSchedule` into your existing website:

```javascript
import { mountRaceSchedule } from './website-integration.js';
const unmount = mountRaceSchedule(document.querySelector('#race-schedule'));
// Call unmount() when navigating away in a single-page app.
```

Your existing page needs a container: `<div id="race-schedule"></div>`.
Or use `loadRaceSchedule()` and render the data with your own UI components.
The helper refreshes the displayed data every minute while mounted, retains its
last rendered races on a temporary API failure, and displays stale-data status.
Only the backend contacts Formula1.com, at its configured interval.

No recurring JSON/CSV upload is required. Fetching an API still transfers JSON
automatically, which is different from manually replacing a file.

## Deploy the backend

Run this on an always-on Python/container host with outbound HTTPS, persistent
storage and an HTTPS endpoint. A static-only host cannot run this Python service.
A sleeping process cannot run the refresh loop while asleep. Use an always-on
instance for the stated schedule. This project has NOT been deployed for you.

Build/run the included Dockerfile if your host supports Docker:

```bash
docker build -t race-schedule-api .
docker run -d --name race-schedule-api --restart unless-stopped \
  -p 8000:8000 \
  -e F1_SEASON=2026 \
  -e ALLOWED_ORIGINS=https://example.com \
  -v race-schedule-data:/data \
  race-schedule-api
```

The container listens on port 8000; configure your host or HTTPS reverse proxy to
route to it. Docker alone does not configure a domain or TLS certificate. If the
host requires its own port, override the launch command accordingly.
Mount persistent storage at /data (or your STATE_DIR); back up the SQLite database.
For custom bind mounts, the directory must be writable by container UID 10001.

After deployment:

1. Check `/health` for process health and `/ready` for a fresh usable schedule.
2. Check `/api/schedule` for races and fetched_at.
3. Configure ALLOWED_ORIGINS to your exact website origin, including https://.
4. Set API_BASE to your backend's HTTPS address.
5. Deploy your website once. The data then refreshes without file uploads.

Monitor logs for failures and /ready for stale data. Changes appear after a successful
backend refresh and the website's next API poll, not instantly when F1 edits a page.
The count-drop guard blocks automatic acceptance of a smaller season. If rounds are
legitimately removed, review the source, stop the service, back up state, then reset
the season's cache row before restarting. Layout changes require parser maintenance.

## Optional one-time JSON / CSV export

The original command remains available for debugging or downloads:

```bash
python scrape_schedule.py --year 2026
```

Outputs: `data/schedule-2026.json` and `data/schedule-2026.csv`.
These files are NOT the API's database and do not need to be uploaded to your site.
The bundled data folder is a previously collected snapshot, not a live API response.

## Data fields

- season, round, event_id (the source page slug)
- country_label: the source's event label, not a verified geographic country
- race_name: official event title as shown by the source
- venue_label: the source's trackName metadata, often a city; nullable and NOT guaranteed to be the circuit's full name
- weekend_start and weekend_end: ISO calendar dates, not UTC timestamps
- source_url and fetched_at (UTC retrieval timestamp)

Top-level JSON contains source, schema version, collection mode and timestamps.
Testing events are excluded. Duplicate featured cards are excluded.
No race count, venue or date is hardcoded.

## Using JSON in a website

Copy the generated JSON to your site's public data directory. For example:

```javascript
const response = await fetch('/data/schedule-2026.json');
if (!response.ok) throw new Error('Schedule unavailable');
const { races, fetched_at } = await response.json();
console.table(races.map(r => ({
  round: r.round,
  name: r.country_label,
  start: r.weekend_start,
  end: r.weekend_end
})));
```

Render titles as text, not raw HTML. Display source and last successful refresh.
Keep date-only values as calendar dates; avoid treating midnight UTC as a race time.
The API is included; hosting and connecting your existing website are separate deployment steps.

## Standalone export reliability

The standalone collector honors robots.txt and validates date ranges and fields.
It preserves existing export files when collection fails. Each export file is
replaced atomically; the CSV/JSON pair is not a single transaction.

Offline parsing of HTML you already possess:

```bash
python scrape_schedule.py --year 2026 --html calendar.html --out offline-data
```

Offline exports have null fetched_at, since retrieval time is unknown.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m unittest -v
```

## Scope and next step

This version covers race-weekend date ranges. Exact practice, sprint, qualifying and
race start times are NOT included. The next module should read each weekend's
schedule, retain timezone-aware source times and convert them for display,
including Asia/Kolkata. Dates alone cannot support an accurate race-start countdown.

No images, logos, news, video or results are collected.

## Content-use terms

Public accessibility and robots allowance do not grant commercial reuse rights.
Formula1.com's published legal notices restrict extraction and commercial reuse.
Obtain permission covering your intended collection, storage and website use before
commercial deployment. This prototype and source attribution do not supply a licence.

Official calendar: https://www.formula1.com/en/racing/2026
Legal notices: https://www.formula1.com/en/information/legal-notices.7egvZU48hzrypubGBNcQKt

See VALIDATION.md for the checks performed on this delivered version.
