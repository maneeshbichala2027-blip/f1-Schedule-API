"""Collect race-weekend dates from the public Formula1.com calendar."""
import argparse
import base64
import csv
import io
import json
import re
import sys
import tempfile
import os
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from lxml import html

ORIGIN = "https://www.formula1.com"
AGENT = "RaceCalendarCollector/0.1"
MONTHS = dict(zip("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), range(1, 13)))
DATE_RANGE = re.compile(r"^(\d{1,2})\s*([A-Z]{3})?\s*[-–—]\s*(\d{1,2})\s*([A-Z]{3})$", re.I)
FIELDS = ["season", "round", "event_id", "country_label", "race_name", "venue_label", "weekend_start", "weekend_end", "source_url", "fetched_at"]


def parse_dates(value, year):
    match = DATE_RANGE.fullmatch(" ".join(value.split()))
    if not match:
        raise ValueError(f"Unrecognized weekend date: {value!r}")
    first, first_month, last, last_month = match.groups()
    end_month = MONTHS[last_month.upper()]
    start_month = MONTHS[(first_month or last_month).upper()]
    end_year = year + (end_month < start_month)
    start = date(year, start_month, int(first))
    end = date(end_year, end_month, int(last))
    if not 0 <= (end - start).days <= 7:
        raise ValueError(f"Unexpected weekend span: {value!r}")
    return start.isoformat(), end.isoformat()


def metadata(anchor):
    value = anchor.get("data-f1rd-a7s-context", "")
    try:
        result = json.loads(base64.b64decode(value, validate=True))
        return result if isinstance(result, dict) else {}
    except (ValueError, UnicodeDecodeError):
        return {}


def parse_schedule(content, year, fetched_at):
    document = html.fromstring(content)
    races = {}
    # Exact class token selects the main calendar, excluding duplicate hero cards.
    anchors = document.xpath('//a[contains(concat(" ", normalize-space(@class), " "), " group ")]')
    for anchor in anchors:
        href = anchor.get("href", "")
        match = re.fullmatch(rf"/en/racing/{year}/([a-z0-9-]+)/?", href)
        if not match:
            continue
        tokens = [" ".join(t.split()) for t in anchor.xpath('.//text()[not(ancestor::svg)]') if t.strip()]
        rounds = [re.fullmatch(r"ROUND\s+(\d+)", t, re.I) for t in tokens]
        rounds = [int(m.group(1)) for m in rounds if m]
        if not rounds:
            continue  # Pre-season testing is not a championship round.
        dates = [t for t in tokens if DATE_RANGE.fullmatch(t)]
        info = metadata(anchor)
        race_name = info.get("raceName") or next((t for t in tokens if t.startswith("FORMULA 1 ")), None)
        country = info.get("trackCountry")
        if not country:
            labels = anchor.xpath('.//p[contains(@class,"display-xl")]/text()')
            country = labels[0].strip() if labels else None
        if len(dates) != 1 or not country or not race_name:
            raise ValueError(f"Calendar structure changed near {href}; no output replaced")
        start, end = parse_dates(dates[0], year)
        item = dict(zip(FIELDS, [year, rounds[0], match.group(1), country, race_name, info.get("trackName"), start, end, urljoin(ORIGIN, href), fetched_at]))
        if href in races and races[href] != item:
            raise ValueError(f"Conflicting duplicate event: {href}")
        races[href] = item
    result = sorted(races.values(), key=lambda r: r["round"])
    if not result:
        raise ValueError("No championship rounds found; source may have changed")
    if len({r["round"] for r in result}) != len(result):
        raise ValueError("Multiple events use the same round number")
    return result


def download(url):
    request = Request(url, headers={"User-Agent": AGENT, "Accept": "text/html,text/plain"})
    with urlopen(request, timeout=45) as response:
        if response.status != 200:
            raise ValueError(f"Unexpected HTTP status: {response.status}")
        return response.read()


def collect_online(year):
    url = f"{ORIGIN}/en/racing/{year}"
    # Fail closed if robots cannot be retrieved; no block bypass or retries.
    robots = RobotFileParser()
    robots.parse(download(f"{ORIGIN}/robots.txt").decode("utf-8").splitlines())
    if not robots.can_fetch(AGENT, url):
        raise ValueError("Collection disallowed by robots.txt")
    return download(url)


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=datetime.now(timezone.utc).year)
    parser.add_argument("--html", type=Path, help="Parse an existing calendar HTML file offline")
    parser.add_argument("--out", type=Path, default=Path("data"))
    parser.add_argument("--weekends-only", action="store_true", help="Skip exact session-time collection")
    args = parser.parse_args()
    if not 1950 <= args.year <= 2100:
        parser.error("year must be between 1950 and 2100")
    try:
        content = args.html.read_bytes() if args.html else collect_online(args.year)
        fetched_at = datetime.now(timezone.utc).isoformat() if not args.html else None
        races = parse_schedule(content, args.year, fetched_at)
        if not args.weekends_only:
            if args.html:
                raise ValueError("Use --weekends-only with offline calendar HTML; session pages are separate")
            from session_times import enrich_races
            races = enrich_races(races)
        target = args.out / f"schedule-{args.year}"
        # Preserve a good existing schedule if a later scrape loses records.
        previous_path = target.with_suffix(".json")
        if previous_path.exists():
            previous = json.loads(previous_path.read_text(encoding="utf-8"))
            if len(races) < len(previous.get("races", [])):
                raise ValueError("Round count fell; review source before replacing existing output")
        payload = {"schema_version": 2, "season": args.year, "source_url": f"{ORIGIN}/en/racing/{args.year}", "fetched_at": fetched_at, "parsed_at": datetime.now(timezone.utc).isoformat(), "collection_mode": "offline" if args.html else "online", "date_semantics": "Weekend dates are date-only; session timestamps include UTC offsets. End times are scheduled, not actual finishes.", "races": races}
        output = io.StringIO(newline="")
        csv_fields = FIELDS + ['race_start_time_utc', 'race_start_time_track', 'race_start_time_ist', 'track_timezone']
        writer = csv.DictWriter(output, fieldnames=csv_fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(races)
        atomic_write(target.with_suffix(".csv"), output.getvalue())
        session_rows = [{"season": args.year, "round": r['round'], "event_id": r['event_id'], **s} for r in races for s in r.get('sessions', [])]
        session_csv = io.StringIO(newline='')
        session_fields = ['season', 'round', 'event_id', 'session_id', 'name', 'session_type', 'source_state', 'timing_status', 'track_timezone', 'source_utc_offset', 'start_time_utc', 'start_time_track', 'start_time_ist', 'scheduled_end_time_utc', 'source_url', 'fetched_at']
        sw = csv.DictWriter(session_csv, fieldnames=session_fields)
        sw.writeheader()
        sw.writerows(session_rows)
        atomic_write(args.out / f'sessions-{args.year}.csv', session_csv.getvalue())
        atomic_write(previous_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        print(f"Exported {len(races)} rounds and {len(session_rows)} sessions to {args.out}")
    except Exception as exc:
        print(f"Collection failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
