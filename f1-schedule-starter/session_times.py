"""Read session schedules embedded in public official race pages (no JS execution)."""
import json
import re
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from lxml import html
from urllib.robotparser import RobotFileParser

from scrape_schedule import AGENT, ORIGIN, download


def structured_sessions(content):
    document = html.fromstring(content)
    chunks = []
    for script in document.xpath('//script'):
        text = (script.text or '').strip()
        prefix = 'self.__next_f.push('
        if not text.startswith(prefix):
            continue
        try:
            payload = json.loads(text[len(prefix):].rstrip(';')[:-1])
        except (ValueError, TypeError):
            continue
        if isinstance(payload, list) and len(payload) > 1 and payload[0] == 1 and isinstance(payload[1], str):
            chunks.append(payload[1])
    stream = ''.join(chunks)
    candidates = []
    for match in re.finditer(r'"meetingSessions"\s*:', stream):
        try:
            value, _ = json.JSONDecoder().raw_decode(stream[match.end():].lstrip())
        except ValueError:
            continue
        if isinstance(value, list) and all(isinstance(s, dict) for s in value):
            candidates.append(value)
    if not candidates:
        raise ValueError('Session schedule structure not found; review race page parser')
    if any(c != candidates[0] for c in candidates):
        raise ValueError('Conflicting session schedules in race page')
    return candidates[0]


def aware_time(value, offset, zone_name):
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    was_naive = dt.tzinfo is None
    if was_naive:
        if offset and re.fullmatch(r'[+-]\d{2}:\d{2}', offset):
            sign = 1 if offset[0] == '+' else -1
            hours, minutes = map(int, offset[1:].split(':'))
            if hours > 23 or minutes > 59:
                raise ValueError('Invalid source UTC offset')
            dt = dt.replace(tzinfo=timezone(sign * timedelta(hours=hours, minutes=minutes)))
        else:
            # Never silently interpret a timezone-less start as UTC.
            raise ValueError('Published session time has no explicit UTC offset')
    if zone_name:
        local = dt.astimezone(ZoneInfo(zone_name))
        if was_naive and local.utcoffset() != dt.utcoffset():
            raise ValueError(f'Source UTC offset disagrees with timezone {zone_name}')
    return dt


def parse_sessions(content, source_url, fetched_at):
    result = []
    seen = set()
    for raw in structured_sessions(content):
        key = raw.get('session') or raw.get('shortName')
        if not key or key in seen:
            raise ValueError('Missing or duplicate session identifier')
        seen.add(key)
        zone = raw.get('timezone')
        start = aware_time(raw.get('startTime'), raw.get('gmtOffset'), zone)
        end = aware_time(raw.get('endTime'), raw.get('gmtOffset'), zone)
        if start and end and end < start:
            raise ValueError('Session end precedes start')
        def fmt(value, target=None):
            if value is None:
                return None
            return (value.astimezone(target) if target else value).isoformat()
        result.append({
            'session_id': key, 'name': raw.get('description') or raw.get('shortName'),
            'session_type': raw.get('sessionType'), 'source_state': raw.get('state'),
            'timing_status': 'published' if start else 'not_published',
            'track_timezone': zone, 'source_utc_offset': raw.get('gmtOffset'),
            'start_time_utc': fmt(start, timezone.utc),
            'start_time_track': fmt(start, ZoneInfo(zone)) if zone else fmt(start),
            'start_time_ist': fmt(start, ZoneInfo('Asia/Kolkata')),
            'scheduled_end_time_utc': fmt(end, timezone.utc),
            'source_url': source_url, 'fetched_at': fetched_at,
        })
    return sorted(result, key=lambda s: s['start_time_utc'] or '9999')


def enrich_races(races, fetch=download, pause=2):
    robots = RobotFileParser()
    robots.parse(fetch(f'{ORIGIN}/robots.txt').decode('utf-8').splitlines())
    for race in races:
        if not robots.can_fetch(AGENT, race['source_url']):
            raise ValueError('Race page collection is disallowed by robots.txt')
        if pause:
            time.sleep(pause)
        content = fetch(race['source_url'])
        fetched = datetime.now(timezone.utc).isoformat()
        sessions = parse_sessions(content, race['source_url'], fetched)
        race['sessions'] = sessions
        race['sessions_status'] = 'published' if sessions else 'not_published'
        race['sessions_fetched_at'] = fetched
        main_race = next((s for s in sessions if (s['session_type'] or '').lower() == 'race' or s['session_id'] == 'r'), None)
        for suffix in ['utc', 'track', 'ist']:
            race[f'race_start_time_{suffix}'] = main_race.get(f'start_time_{suffix}') if main_race else None
        race['track_timezone'] = main_race.get('track_timezone') if main_race else None
        print(f"Collected sessions: {race['event_id']} ({len(sessions)})", flush=True)
    return races
