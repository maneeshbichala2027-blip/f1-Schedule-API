// Add this module to your existing website; no CSV/JSON uploads required.
// Replace the public GitHub data URL once, or use your hosted HTTPS API URL.
const DATA_URL = "https://raw.githubusercontent.com/maneeshbichala2027-blip/f1-Schedule-API/main/f1-schedule-starter/data/schedule-2026.json";
// For a hosted Python API instead, use its https://.../api/schedule URL.

export async function loadRaceSchedule() {
  const response = await fetch(DATA_URL, {
    cache: "no-store",
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error(`Schedule unavailable (${response.status})`);
  return response.json();
}

// Optional minimal integration: pass a container already in your website.
export function mountRaceSchedule(container) {
  let stopped = false;
  let timer;

  async function update() {
    try {
      const data = await loadRaceSchedule();
      if (stopped) return;
      const note = document.createElement("p");
      const updated = new Date(data.fetched_at).toLocaleString();
      const stale = data.stale ?? (Date.now() - Date.parse(data.fetched_at) > 12 * 3600 * 1000);
      note.textContent = `Last successful update: ${updated}${stale ? " — refresh delayed; showing saved schedule" : ""}`;
      const list = document.createElement("ul");
      for (const race of data.races) {
        const li = document.createElement("li");
        li.textContent = `Round ${race.round}: ${race.country_label} · ${race.weekend_start} to ${race.weekend_end}`;
        if (race.sessions?.length) {
          const sessions = document.createElement("ul");
          for (const session of race.sessions) {
            const row = document.createElement("li");
            const time = session.start_time_utc
              ? new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "short" }).format(new Date(session.start_time_utc)) + " IST"
              : "Time not published";
            row.textContent = `${session.name}: ${time}`;
            sessions.append(row);
          }
          li.append(sessions);
        }
        list.append(li);
      }
      container.replaceChildren(note, list);
    } catch (error) {
      if (!stopped) {
        // Keep already-rendered races visible after a temporary API failure.
        let errorNote = container.querySelector("[data-schedule-error]");
        if (!errorNote) {
          errorNote = document.createElement("p");
          errorNote.dataset.scheduleError = "true";
          container.prepend(errorNote);
        }
        errorNote.textContent = "Unable to refresh the schedule. Trying again shortly.";
        console.error(error);
      }
    } finally {
      if (!stopped) timer = setTimeout(update, 60000);
    }
  }

  update();
  return () => { stopped = true; clearTimeout(timer); };
}
