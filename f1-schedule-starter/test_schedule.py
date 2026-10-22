import base64
import json
import unittest
from scrape_schedule import parse_dates, parse_schedule


class CalendarTests(unittest.TestCase):
    def test_same_month(self):
        self.assertEqual(parse_dates("06 - 08 Mar", 2026), ("2026-03-06", "2026-03-08"))

    def test_cross_month(self):
        self.assertEqual(parse_dates("30 OCT - 01 NOV", 2026), ("2026-10-30", "2026-11-01"))

    def test_invalid_span(self):
        with self.assertRaises(ValueError):
            parse_dates("08 - 06 Mar", 2026)

    def test_cross_year(self):
        self.assertEqual(parse_dates("31 DEC - 02 JAN", 2026), ("2026-12-31", "2027-01-02"))

    def test_main_card_and_hero_duplicate(self):
        context = base64.b64encode(json.dumps({"raceName": "FORMULA 1 EXAMPLE", "trackCountry": "Example", "trackName": "Venue"}).encode()).decode()
        card = f'<a class="group" href="/en/racing/2026/example" data-f1rd-a7s-context="{context}"><span>ROUND 1</span><span>06 - 08 Mar</span></a>'
        page = '<html><a class="group/schedule-card" href="/en/racing/2026/example">ROUND 1</a>' + card + card + '</html>'
        races = parse_schedule(page, 2026, None)
        self.assertEqual(len(races), 1)
        self.assertEqual(races[0]["venue_label"], "Venue")

    def test_changed_markup_fails(self):
        with self.assertRaises(ValueError):
            parse_schedule('<html><h1>No calendar</h1></html>', 2026, None)


if __name__ == "__main__":
    unittest.main()
