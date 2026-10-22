# Validation

- Live collection completed at 2026-10-22T18:45:14.521330+00:00.
- 23 championship rounds exported from the 2026 calendar; this is the count returned by the source, not a hardcoded season size.
- JSON and CSV have matching row counts; event IDs are unique.
- Date ranges are valid and collection timestamps match.
- Six unit tests passed: same-month dates, cross-month dates, cross-year dates, invalid span rejection, duplicate card handling, changed markup rejection.
- Python syntax compilation passed.
- Exact session times, future daily refreshes, other seasons and commercial use rights were not validated.
- Data is a snapshot and can change. Verify against the official source before use.

## Version 2 — automatic API

- All 10 tests passed: the original 6 parser tests plus 4 API/cache tests.
- Verified background startup collection without a website request triggering it.
- Verified a due refresh changes the API response without manual file replacement.
- Verified repeated visitor requests do not cause extra source requests.
- Verified CORS permits the configured origin and omits permission for another origin.
- Verified failed refresh retains prior data, marks it stale, and survives cache restart.
- Verified an empty cache returns HTTP 503, not fabricated or stale bundled data.
- A real local Uvicorn process fetched the official source and returned HTTP 200 with 23 rounds and stale=false.
- Syntax compilation passed.
- The Docker image, external deployment, domain/TLS setup and connection to the user's website have NOT been executed.
- Refresh interval behavior is covered using an advanced test clock; no six-hour wall-clock soak test was performed.
