"""Sidearm Sports ICS feeds: Brown, Providence College, URI, Bryant. Home games only.

Behind Imperva; retries with backoff help.
"""
from __future__ import annotations

import re
import time

import requests

from .common import UA, clean, log, make_event, to_dt

SOURCE = {"name": "College athletics (Sidearm)", "url": "https://brownbears.com", "city": "Providence"}

SCHOOLS = {
    "brown": {"ics": "https://brownbears.com/calendar.ashx/calendar.ics", "team": "Brown", "city": "Providence",
              "home_rx": r"Providence, R\.I\.", "lat": 41.8305, "lon": -71.3985, "web": "https://brownbears.com"},
    "pc": {"ics": "https://friars.com/calendar.ashx/calendar.ics", "team": "Providence College", "city": "Providence",
           "home_rx": r"Providence, R\.I\.", "lat": 41.8440, "lon": -71.4376, "web": "https://friars.com"},
    "uri": {"ics": "https://gorhody.com/calendar.ashx/calendar.ics", "team": "URI", "city": "Kingston",
            "home_rx": r"Kingston, R\.I\.|Providence, R\.I\.|Pawtucket, R\.I\.", "lat": 41.4853, "lon": -71.5302, "web": "https://gorhody.com"},
    "bryant": {"ics": "https://bryantbulldogs.com/calendar.ashx/calendar.ics", "team": "Bryant", "city": "Smithfield",
               "home_rx": r"Smithfield, R\.I\.", "lat": 41.9214, "lon": -71.5389, "web": "https://bryantbulldogs.com"},
}
# low-interest sports for a spectator, dropped unless it's a championship
MINOR = re.compile(r"\b(golf|sailing|squash|fencing|cross country|equestrian|rowing|crew|tennis|track|"
                   r"swimming|diving|skiing|rugby|water polo)\b", re.I)


def _get(url: str) -> str:
    last = None
    for i in range(4):
        try:
            r = requests.get(url, timeout=40, headers={"User-Agent": UA, "Accept": "text/calendar,*/*"},
                             allow_redirects=False)
            if r.status_code == 200 and "BEGIN:VCALENDAR" in r.text:
                return r.text
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:  # noqa: PERF203
            last = str(e)
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"{url}: {last}")


def fetch() -> list[dict]:
    from icalendar import Calendar
    out = []
    for key, s in SCHOOLS.items():
        try:
            cal = Calendar.from_ical(_get(s["ics"]))
        except Exception as e:  # noqa: BLE001
            log.warning("sidearm %s: %s", key, e)
            continue
        n = 0
        for c in cal.walk("VEVENT"):
            summ = clean(str(c.get("SUMMARY", "")))
            loc = clean(str(c.get("LOCATION", "")))
            # "[N] Brown University Men's Basketball vs Yale" → sport + opponent; "at X" is an away game
            m = re.match(r"(?:\[[A-Z]\]\s*)?(.*?)\s+(vs\.?|at)\s+(.*)", summ)
            if not m:
                continue
            team_sport, vs_at, opp = m.groups()
            if vs_at.lower() == "at" or not re.search(s["home_rx"], loc):
                continue  # away game
            sport = re.sub(r"^(Brown University|Providence College|University of Rhode Island|Rhode Island|Bryant University|Bryant)\s*", "", team_sport).strip()
            if MINOR.search(sport) and not re.search(r"champ|ivy|tournament", summ + loc, re.I):
                continue
            parts = [x.strip() for x in loc.split(",")]
            venue = parts[-1] if len(parts) >= 3 else s["team"]
            if re.fullmatch(r"R\.?I\.?|Rhode Island", venue, re.I):
                venue = parts[0] if len(parts) == 2 else s["team"]
            dtstart = c.decoded("DTSTART")
            all_day = not hasattr(dtstart, "hour")
            title = f"{s['team']} {sport} vs {clean(opp)}"
            desc = clean(str(c.get("DESCRIPTION", "")))
            desc = re.sub(r"\s*(TV|Radio|Streaming Video|Live Stats|Live Video|Audio|Tickets|Video):.*$", "", desc).strip()
            desc = re.sub(rf"^{re.escape(summ)}\s*", "", desc).strip()
            ev = make_event(
                source="college_sports", title=title, start=to_dt(dtstart), url=str(c.get("URL", "")) or s["web"],
                venue=venue, city=s["city"], lat=s["lat"], lon=s["lon"], category="sports", all_day=all_day,
                tags=[sport.lower(), s["team"].lower(), "home game"], description=desc, performer=clean(opp),
                extra={"sport": sport, "school": s["team"]},
            )
            if ev:
                ev["kids"] = False
                out.append(ev)
                n += 1
        log.info("sidearm %s: %d home games", key, n)
    return out
