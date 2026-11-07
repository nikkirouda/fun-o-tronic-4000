"""RISD public events via the CampusLabs Engage discovery API (student orgs, Staff Council, BAI partners)."""
from __future__ import annotations

import re
from datetime import date

from .common import clean, get_json, make_event

SOURCE = {"name": "RISD (Engage)", "url": "https://involved.risd.edu/events", "city": "Providence", "lat": 41.8262, "lon": -71.4069}
API = "https://involved.risd.edu/api/discovery/event/search"
IMG = "https://se-images.campuslabs.com/clink/images/"


def fetch() -> list[dict]:
    data = get_json(API, params={"endsAfter": f"{date.today().isoformat()}T00:00:00", "orderByField": "endsOn",
                                 "orderByDirection": "ascending", "status": "Approved", "take": 200}, timeout=40)
    out = []
    for r in data.get("value", []):
        if r.get("visibility") != "Public":
            continue
        if re.search(r"advising|office hours|drop-in|meeting|training|orientation|info session|registration", r.get("name", ""), re.I):
            continue
        if (r.get("theme") or "") not in ("Arts", "Cultural", "Social", "Learning", "Thoughtfulness", "Spirituality", ""):
            continue
        cats = r.get("categoryNames") or []
        theme = r.get("theme") or ""
        desc = clean(r.get("description", ""))
        venue = clean(r.get("location", "")) or "RISD"
        e = make_event(
            source="risd_engage", title=r.get("name", ""), start=r.get("startsOn"), end=r.get("endsOn"),
            url=f"https://involved.risd.edu/event/{r.get('id')}", venue=venue if "risd" in venue.lower() else f"RISD — {venue}",
            city="Providence", lat=float(r["latitude"]) if r.get("latitude") else SOURCE["lat"],
            lon=float(r["longitude"]) if r.get("longitude") else SOURCE["lon"],
            category=None, tags=cats + [theme, "risd"], description=desc,
            image=IMG + r["imagePath"] if r.get("imagePath") else "", is_free=True if "Free Food" in (r.get("benefitNames") or []) else None,
            extra={"org": r.get("organizationName")},
        )
        if e:
            if e["category"] == "other":
                e["category"] = "art" if theme in ("Arts", "Cultural") else "talk" if theme in ("Learning", "Thoughtfulness") else "other"
            out.append(e)
    return out
