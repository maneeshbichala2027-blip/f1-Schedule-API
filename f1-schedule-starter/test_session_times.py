import json
import unittest
from session_times import parse_sessions, aware_time


def page(sessions):
    stream = 'a:' + json.dumps({'race': {'meetingSessions': sessions}}) + '\n'
    return '<html><script>self.__next_f.push(' + json.dumps([1, stream]) + ')</script></html>'


def session(**changes):
    result = {'session': 'r', 'description': 'Race', 'sessionType': 'Race', 'startTime': '2026-10-25T15:00:00', 'endTime': '2026-10-25T17:00:00', 'gmtOffset': '-05:00', 'timezone': 'US/Central', 'state': 'upcoming'}
    result.update(changes)
    return result


class SessionTests(unittest.TestCase):
    def test_utc_ist_and_next_day(self):
        row = parse_sessions(page([session()]), 'https://example.com', None)[0]
        self.assertEqual(row['start_time_utc'], '2026-10-25T20:00:00+00:00')
        self.assertEqual(row['start_time_ist'], '2026-10-26T01:30:00+05:30')
        self.assertEqual(row['start_time_track'], '2026-10-25T15:00:00-05:00')

    def test_seasonal_dst_offset(self):
        self.assertEqual(aware_time('2026-11-21T20:00:00', '-08:00', 'America/Los_Angeles').astimezone(__import__('datetime').timezone.utc).isoformat(), '2026-11-22T04:00:00+00:00')

    def test_offset_mismatch_fails(self):
        with self.assertRaises(ValueError):
            parse_sessions(page([session(gmtOffset='-06:00')]), '', None)

    def test_missing_start_is_not_invented(self):
        row = parse_sessions(page([session(startTime=None, endTime=None)]), '', None)[0]
        self.assertIsNone(row['start_time_utc'])
        self.assertEqual(row['timing_status'], 'not_published')

    def test_no_offset_fails(self):
        with self.assertRaises(ValueError):
            aware_time('2026-10-25T15:00:00', None, 'US/Central')

    def test_already_utc_time_preserved(self):
        self.assertEqual(aware_time('2026-10-25T20:00:00Z', None, 'US/Central').isoformat(), '2026-10-25T20:00:00+00:00')

    def test_sprint_labels_preserved(self):
        rows = parse_sessions(page([session(session='s', description='Sprint', sessionType='Sprint')]), '', None)
        self.assertEqual(rows[0]['name'], 'Sprint')

    def test_empty_schedule_explicit(self):
        self.assertEqual(parse_sessions(page([]), '', None), [])

    def test_changed_markup_fails(self):
        with self.assertRaises(ValueError):
            parse_sessions('<html>No session data</html>', '', None)


if __name__ == '__main__':
    unittest.main()
