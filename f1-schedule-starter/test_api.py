import json
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from api import ScheduleStore, create_app

PAGE = '''<html><a class="group" href="/en/racing/2026/example"><span>ROUND 1</span><p class="display-xl">Example</p><span>FORMULA 1 EXAMPLE</span><span>06 - 08 Mar</span></a></html>'''


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now = [1800000000.0]
        self.calls = []
        self.page = PAGE
        def fetch(year):
            self.calls.append(year)
            return self.page
        self.store = ScheduleStore(self.directory.name, 2026, 3600, fetch=fetch, clock=lambda: self.now[0], enricher=lambda races: races)

    def test_due_refresh_changes_data_and_get_does_not_scrape(self):
        self.assertTrue(self.store.tick())
        self.assertFalse(self.store.tick())
        self.page = PAGE.replace("06 - 08 Mar", "13 - 15 Mar")
        self.now[0] += 3601
        self.assertTrue(self.store.tick())
        with TestClient(create_app(self.store, ["https://example.com"])) as client:
            for _ in range(3):
                response = client.get("/api/schedule", headers={"Origin": "https://example.com"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["races"][0]["weekend_start"], "2026-03-13")
            self.assertEqual(response.headers["access-control-allow-origin"], "https://example.com")
            blocked = client.get("/api/schedule", headers={"Origin": "https://other.example"})
            self.assertNotIn("access-control-allow-origin", blocked.headers)
        self.assertEqual(len(self.calls), 2)

    def test_failure_preserves_cache_and_reports_stale(self):
        self.store.tick()
        original = self.store.response()["races"]
        self.page = "<html>broken</html>"
        self.now[0] += 3601
        with self.assertLogs("schedule", level="ERROR"):
            self.assertFalse(self.store.tick())
        result = self.store.response()
        self.assertEqual(result["races"], original)
        self.assertTrue(result["stale"])
        self.assertTrue(result["last_refresh_failed"])
        # Restart preserves last good data and last attempted refresh.
        restarted = ScheduleStore(self.directory.name, 2026, 3600, fetch=lambda _: self.fail("Unexpected fetch"), clock=lambda: self.now[0], enricher=lambda races: races)
        self.assertFalse(restarted.tick())
        self.assertEqual(restarted.response()["races"], original)

    def test_unavailable_is_503(self):
        # No lifespan context here: deliberately inspect an empty cache.
        client = TestClient(create_app(self.store, []))
        self.assertEqual(client.get("/api/schedule").status_code, 503)
        self.assertEqual(client.get("/ready").status_code, 503)

    def test_background_startup_collects_without_visitor(self):
        with TestClient(create_app(self.store, [])) as client:
            deadline = time.monotonic() + 3
            while self.store.response() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(len(self.calls), 1)
            self.assertEqual(client.get("/ready").status_code, 200)


if __name__ == "__main__":
    unittest.main()
