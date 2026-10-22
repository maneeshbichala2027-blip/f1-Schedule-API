// Add this module to your existing website; no CSV/JSON uploads required.
// Use the hosted HTTPS API URL in production. Do not use localhost there.
const API_BASE = "http://localhost:8000";

export async function loadRaceSchedule() {
  const response = await fetch(`${API_BASE}/api/schedule`, {
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
      note.textContent = `Last successful update: ${updated}${data.stale ? " — refresh delayed; showing saved schedule" : ""}`;
      const list = document.createElement("ul");
      for (const race of data.races) {
        const li = document.createElement("li");
        li.textContent = `Round ${race.round}: ${race.country_label} · ${race.weekend_start} to ${race.weekend_end}`;
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
