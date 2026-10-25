# Version 3 validation

- Live full-season collection succeeded: 23 rounds and 115 sessions.
- Snapshot calendar fetched at 2026-10-24T21:16:07.086177+00:00; individual session retrieval timestamps are stored on each race and session.
- All 19 unit/integration tests passed, covering calendar parsing, API cache behavior, timezone conversion, IST date rollover, daylight saving, sprint labels, unpublished start times and changed markup.
- Every collected race has a source-published race start time.
- All UTC/IST timestamp pairs represent the same instant.
- Session CSV row count matches the nested JSON session count. Session IDs are unique within each weekend.
- Website JavaScript syntax check and Python syntax checks passed.
- GitHub workflow YAML structure validated locally.
- GitHub workflow execution, cloud deployment, Docker image and connection to the user's website have NOT been performed.
- Schedule changes and provider layout changes can require maintenance. Data licensing was not granted by creating this package.
