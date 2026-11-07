"""Plain iCalendar feeds (public Google calendars, LiveWhale ICS, Tribe ?ical=1 where REST is off)."""
from __future__ import annotations

from .common import get, log, parse_ics

SOURCE = {"name": "Calendar feeds", "url": ""}

FEEDS = [
    {"key": "waterfire", "url": "https://calendar.google.com/calendar/ical/c_abac7353049370d1120804a7ed43360381966cf3cdad78c649175cd6a1d24afd%40group.calendar.google.com/public/basic.ics",
     "venue": "WaterFire Providence", "city": "Providence", "address": "Waterplace Park", "lat": 41.8275, "lon": -71.4136,
     "category": "festival", "url_base": "https://www.waterfire.org/schedule/", "name": "WaterFire Providence"},
    {"key": "jwu", "url": "https://events.jwu.edu/live/ical/events", "venue": "", "city": "Providence", "category": None,
     "url_base": "https://events.jwu.edu", "name": "Events@JWU", "public_only": True},
    {"key": "rihs_ics", "url": "https://www.rihs.org/events/list/?ical=1", "venue": "", "city": "Providence", "category": "talk",
     "url_base": "https://www.rihs.org/events/", "name": "RI Historical Society"},
]


def fetch() -> list[dict]:
    out: list[dict] = []
    for f in FEEDS:
        try:
            text = get(f["url"], timeout=60).text
        except Exception as e:  # noqa: BLE001
            log.info("ics %s: %s", f["key"], str(e)[:100])
            continue
        evs = parse_ics(text, source=f"ics:{f['key']}", venue=f.get("venue", ""), city=f.get("city", ""),
                        address=f.get("address", ""), url_base=f.get("url_base", ""), category=f.get("category"))
        if f.get("public_only"):
            evs = [e for e in evs if any("public" in t for t in e.get("tags", []))]
        for e in evs:
            if f.get("lat") is not None:
                e["lat"], e["lon"] = f["lat"], f["lon"]
            e["source_name"] = f["name"]
            e["source_url"] = f.get("url_base", "")
            if f["key"] == "waterfire":
                e["is_free"] = True
                e["kids"] = False
        log.info("ics %s: %d", f["key"], len(evs))
        out.extend(evs)
    return out
