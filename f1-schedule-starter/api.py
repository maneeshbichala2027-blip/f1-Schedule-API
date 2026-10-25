"""Schedule API with automatic, persistent background refresh.

Run one process/worker with a persistent STATE_DIR. No visitors trigger scraping.
"""
import asyncio
import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from scrape_schedule import collect_online, parse_schedule
from session_times import enrich_races

log = logging.getLogger("schedule")


class ScheduleStore:
    def __init__(self, directory, year, interval=21600, fetch=collect_online, clock=time.time, enricher=enrich_races):
        self.path = Path(directory) / "schedule.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.year, self.interval, self.fetch, self.clock = year, interval, fetch, clock
        self.enricher = enricher
        self.lock = threading.Lock()
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS cache (year INTEGER PRIMARY KEY, payload TEXT, attempted REAL, succeeded REAL, failed INTEGER NOT NULL DEFAULT 0)")
            db.execute("INSERT OR IGNORE INTO cache(year) VALUES (?)", (year,))

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def read(self):
        with self.connect() as db:
            row = db.execute("SELECT payload, attempted, succeeded, failed FROM cache WHERE year=?", (self.year,)).fetchone()
        return {"payload": json.loads(row[0]) if row[0] else None, "attempted": row[1], "succeeded": row[2], "failed": bool(row[3])}

    def tick(self):
        """Refresh if due. Keep last good data after any fetch/parse failure."""
        with self.lock:
            current = self.read()
            now = self.clock()
            if current["attempted"] is not None and now - current["attempted"] < self.interval:
                return False
            # Persist the attempt so restarting a failing service doesn't hammer F1.
            with self.connect() as db:
                db.execute("UPDATE cache SET attempted=? WHERE year=?", (now, self.year))
            try:
                content = self.fetch(self.year)
                fetched_at = datetime.fromtimestamp(self.clock(), timezone.utc).isoformat()
                races = parse_schedule(content, self.year, fetched_at)
                old = current["payload"]
                if old and len(races) < len(old["races"]):
                    raise ValueError("Round count fell; review the source before accepting a smaller calendar")
                races = self.enricher(races)
                payload = {"schema_version": 2, "season": self.year, "source_url": f"https://www.formula1.com/en/racing/{self.year}", "fetched_at": fetched_at, "date_semantics": "Weekend dates are date-only; session timestamps have UTC offsets. End times are scheduled, not actual finishes.", "races": races}
                with self.connect() as db:
                    db.execute("UPDATE cache SET payload=?, succeeded=?, failed=0 WHERE year=?", (json.dumps(payload, ensure_ascii=False), self.clock(), self.year))
                log.info("Refreshed %s schedule: %s rounds", self.year, len(races))
                return True
            except Exception:
                log.exception("Schedule refresh failed; preserving the previous successful schedule")
                with self.connect() as db:
                    db.execute("UPDATE cache SET failed=1 WHERE year=?", (self.year,))
                return False

    def response(self):
        current = self.read()
        if current["payload"] is None:
            return None
        stale = current["failed"] or self.clock() - current["succeeded"] > self.interval + 300
        return {**current["payload"], "stale": stale, "last_refresh_failed": current["failed"], "refresh_interval_seconds": self.interval}


def create_app(store=None, origins=None):
    if store is None:
        year = int(os.environ.get("F1_SEASON", datetime.now(timezone.utc).year))
        interval = int(os.environ.get("REFRESH_SECONDS", "21600"))
        if not 1950 <= year <= 2100 or interval < 3600:
            raise ValueError("F1_SEASON must be 1950–2100; REFRESH_SECONDS must be at least 3600")
        store = ScheduleStore(os.environ.get("STATE_DIR", "state"), year, interval)
    if origins is None:
        origins = [v.strip() for v in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",") if v.strip()]
    if "*" in origins:
        raise ValueError("Set specific ALLOWED_ORIGINS, not *")

    async def refresh_loop():
        while True:
            try:
                await asyncio.to_thread(store.tick)
            except Exception:
                log.exception("Collector task failed; will retry its scheduling check")
            await asyncio.sleep(min(60, store.interval))

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(refresh_loop())
        yield
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    app = FastAPI(title="Race Schedule API", version="2.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET"], allow_headers=["Accept"], expose_headers=["Retry-After"])

    @app.get("/health")
    def health():
        return {"status": "running", "season": store.year, "schedule_available": store.read()["payload"] is not None}

    @app.get("/api/schedule")
    def schedule():
        result = store.response()
        if result is None:
            return JSONResponse({"detail": "Schedule not ready. Initial collection may be running or may have failed."}, status_code=503, headers={"Retry-After": "60", "Cache-Control": "no-store"})
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    @app.get("/ready")
    def ready():
        result = store.response()
        available = result is not None and not result["stale"]
        return JSONResponse({"ready": available}, status_code=200 if available else 503)

    return app
