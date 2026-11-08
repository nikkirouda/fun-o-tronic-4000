"""Events@Brown (LiveWhale) — the university-wide public calendar, incl. TAPS, BAI, lectures.

JSON endpoint caps at 1000 rows, so we page by date window. Keep only things an outsider
would attend: tagged 'Open to the Public' or a performance/exhibition, drop internal
groups (HR, career center, study sessions) and canceled items.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from .common import clean, get_json, log, make_event

SOURCE = {"name": "Events@Brown", "url": "https://events.brown.edu", "city": "Providence",
          "lat": 41.8268, "lon": -71.4025}
BASE = "https://events.brown.edu/live/json/events"
SKIP_GROUPS = re.compile(r"human resources|tisch career|academic calendar|study abroad|bwell|counseling|"
                         r"public safety|curricular resource|master.s programs|professional studies|"
                         r"registrar|dining|residential|student activities office|graduate school|"
                         r"computation and visualization|library instruction|writing center|financial aid", re.I)
SKIP_TYPES = {"Study and Review Sessions", "Auditions and Rehearsals"}
KEEP_TYPES = {"Performances, Concerts and Exhibitions", "Lectures, Seminars and Workshops",
              "Conferences and Colloquia"}
TYPE_TO_CAT = {"Performances, Concerts and Exhibitions": None, "Lectures, Seminars and Workshops": "talk",
               "Conferences and Colloquia": "talk"}
WINDOW_DAYS = 21
HORIZON_DAYS = 240


def fetch() -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    start = date.today()
    while (start - date.today()).days < HORIZON_DAYS:
        end = start + timedelta(days=WINDOW_DAYS)
        url = f"{BASE}/start_date/{start.isoformat()}/end_date/{end.isoformat()}/max/3000/"
        try:
            rows = get_json(url, timeout=90)
        except Exception as e:  # noqa: BLE001
            log.warning("brown window %s failed: %s", start, e)
            rows = []
        if len(rows) >= 1000:
            log.warning("brown window %s hit the 1000 cap; narrow WINDOW_DAYS", start)
        for r in rows:
            try:
                ev = convert(r)
            except Exception as e:  # noqa: BLE001
                log.debug("brown skip %s: %s", r.get("id"), e)
                continue
            if ev and ev["id"] not in seen:
                seen.add(ev["id"])
                out.append(ev)
        start = end + timedelta(days=1)
    return out


def convert(r: dict) -> dict | None:
    if r.get("is_canceled"):
        return None
    types = set(r.get("event_types") or [])
    types_clean = {t.strip() for t in types}
    group = r.get("group") or ""
    if types_clean & SKIP_TYPES or SKIP_GROUPS.search(group):
        return None
    public = "Open to the Public" in types_clean
    is_athletics = group == "Athletics"
    if not (public or types_clean & KEEP_TYPES or is_athletics):
        return None
    if r.get("is_online") and not r.get("location"):
        return None
    title = r.get("title") or ""
    if is_athletics:
        if re.search(r"\bat\b", title) and not re.search(r"\bvs\.?\b", title):
            return None  # away game
        loc_txt = clean(r.get("location") or r.get("location_title") or "")
        if loc_txt and not re.search(r"R\.I\.|Rhode Island|Providence|Pawtucket|Kingston|Bristol|Newport", loc_txt):
            return None  # neutral site out of state (e.g. "Charlottesville, Va.")
        cat = "sports"
    else:
        cat = None
        for t in types_clean:
            if t in TYPE_TO_CAT and TYPE_TO_CAT[t]:
                cat = TYPE_TO_CAT[t]
        # performances get guessed from text (music vs theater vs dance vs art)
    loc = clean(r.get("location") or r.get("location_title") or "")
    venue, address = (loc.split(" - ", 1) + [""])[:2] if " - " in loc else (loc, "")
    if re.search(r"R\.I\.,", venue):  # athletics style: "Providence, R.I., Meehan Auditorium"
        venue = venue.split(",")[-1].strip()
    room = clean(r.get("custom_room_number") or "")
    tags = [clean(t) for t in (r.get("tags") or [])] + sorted(types_clean)
    if r.get("custom_event_sponsor"):
        tags.append(clean(r["custom_event_sponsor"]))
    end = r.get("date2_iso") if r.get("date2_iso") and str(r["date2_iso"])[:10] == str(r["date_iso"])[:10] else None
    ev = make_event(
        source="brown_events", title=title, start=r["date_iso"], end=end, url=r.get("url", ""),
        venue=venue or "Brown University", address=address or (room and f"{room}, Brown University"),
        city="Providence",
        lat=float(r["location_latitude"]) if r.get("location_latitude") else None,
        lon=float(r["location_longitude"]) if r.get("location_longitude") else None,
        category=cat, tags=tags, description=r.get("description") or "", image=r.get("image") or "",
        price_text=r.get("cost") or "", all_day=bool(r.get("is_all_day")),
        extra={"group": group, "sponsor": r.get("custom_event_sponsor")},
    )
    if ev and ev["category"] == "other" and "Performances, Concerts and Exhibitions" in types_clean:
        ev["category"] = "art" if re.search(r"exhibit|gallery|opening|art at watson|installation|on view", title + (r.get("description") or "") + group, re.I) else "music"
    if ev and ev["category"] == "other" and (public or group):
        ev["category"] = "talk"
    if ev and not ev["is_free"] and not ev["price_text"] and not is_athletics:
        ev["is_free"] = None  # unknown, not claimed
    return ev
