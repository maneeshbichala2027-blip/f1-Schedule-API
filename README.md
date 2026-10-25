# Official race schedule scraper

Collects race weekends and published practice, qualifying, sprint and race start times in UTC, track-local time and IST.

- [Scraper setup and field documentation](f1-schedule-starter/README.md)
- [Automatic refresh workflow](.github/workflows/update-schedule.yml)
- [Website integration helper](f1-schedule-starter/website-integration.js)
- [Public JSON data](https://raw.githubusercontent.com/maneeshbichala2027-blip/f1-Schedule-API/main/f1-schedule-starter/data/schedule-2026.json)

GitHub Actions requests a refresh every six hours and on scraper code updates. It runs tests, collects the data and commits a successful update. No paid backend is required for this public-repository route. GitHub scheduling delays and source availability can affect freshness.

In your website, fetch the public JSON URL above or import the configured helper. The website itself has not been modified by this scraper update.

Source-use rights are separate from hosting; see the detailed README before commercial reuse.
