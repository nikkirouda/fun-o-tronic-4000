"""Ticketmaster Discovery API — everything they sell within ~60 miles of Providence.

Needs TICKETMASTER_KEY in the environment (free key from developer.ticketmaster.com, stored as a
GitHub Actions secret). Without it this module returns nothing and reports itself as skipped.
Events farther than FAR_MILES from the house are tagged "worth the drive" and get `far: true`.
"""
from __future__ import annotations

import math
import os
import time

from .common import log, make_event

SOURCE = {"name": "Ticketmaster", "url": "https://www.ticketmaster.com"}
API = "https://app.ticketmaster.com/discovery/v2/events.json"
HOME = (41.8268, -71.4025)  # College Hill
RADIUS_MILES = 60
FAR_MILES = 35
SEG_TO_CAT = {"Music": "music", "Sports": "sports", "Arts & Theatre": "theater", "Film": "film", "Miscellaneous": "other"}
GENRE_TO_CAT = {"Comedy": "comedy", "Classical": "classical", "Opera": "classical", "Dance": "dance", "Children's Theatre": "family",
                "Circus & Specialty Acts": "festival", "Fairs & Festivals": "festival"}


def _miles(lat: float, lon: float) -> float:
    r = 3958.8
    p1, p2 = math.radians(HOME[0]), math.radians(lat)
    dp, dl = math.radians(lat - HOME[0]), math.radians(lon - HOME[1])
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fetch() -> list[dict]:
    key = os.environ.get("TICKETMASTER_KEY", "").strip()
    if not key:
        log.info("ticketmaster: no TICKETMASTER_KEY set; skipping")
        return []
    from .common import get_json
    out: list[dict] = []
    page = 0
    while page < 5:  # 5 × 200 = 1000, the API's deep-paging cap
        try:
            data = get_json(API, params={"apikey": key, "latlong": f"{HOME[0]},{HOME[1]}", "radius": RADIUS_MILES, "unit": "miles",
                                         "size": 200, "page": page, "sort": "date,asc", "locale": "*"}, timeout=40)
        except Exception as e:  # noqa: BLE001
            log.warning("ticketmaster page %s: %s", page, e)
            break
        events = (data.get("_embedded") or {}).get("events") or []
        for ev in events:
            try:
                e = convert(ev)
                if e:
                    out.append(e)
            except Exception as ex:  # noqa: BLE001
                log.debug("ticketmaster skip %s: %s", ev.get("id"), ex)
        pg = data.get("page") or {}
        if page + 1 >= int(pg.get("totalPages") or 0):
            break
        page += 1
        time.sleep(0.25)  # 5 req/s limit
    log.info("ticketmaster: %d events", len(out))
    return out


def convert(ev: dict) -> dict | None:
    dates = ev.get("dates") or {}
    start = (dates.get("start") or {})
    if start.get("timeTBA") or start.get("dateTBD") or start.get("dateTBA"):
        when = start.get("localDate")
        all_day = True
    else:
        when = start.get("dateTime") or start.get("localDate")
        all_day = not start.get("dateTime")
    if not when:
        return None
    status = (dates.get("status") or {}).get("code", "")
    if status in ("cancelled", "postponed"):
        return None
    venues = (ev.get("_embedded") or {}).get("venues") or [{}]
    v = venues[0]
    loc = v.get("location") or {}
    lat = float(loc["latitude"]) if loc.get("latitude") else None
    lon = float(loc["longitude"]) if loc.get("longitude") else None
    city = (v.get("city") or {}).get("name", "")
    state = (v.get("state") or {}).get("stateCode", "")
    addr = (v.get("address") or {}).get("line1", "")
    far = bool(lat and lon and _miles(lat, lon) > FAR_MILES)
    cls = (ev.get("classifications") or [{}])[0]
    seg = (cls.get("segment") or {}).get("name", "")
    genre = (cls.get("genre") or {}).get("name", "")
    sub = (cls.get("subGenre") or {}).get("name", "")
    cat = GENRE_TO_CAT.get(genre) or SEG_TO_CAT.get(seg)
    if seg == "Arts & Theatre" and "Comedy" in (genre + sub):
        cat = "comedy"
    pr = (ev.get("priceRanges") or [{}])[0]
    sales = (ev.get("sales") or {}).get("public") or {}
    on_sale = sales.get("startDateTime")
    imgs = sorted([i for i in ev.get("images") or [] if i.get("ratio") == "16_9" and not i.get("fallback")],
                  key=lambda i: -(i.get("width") or 0))
    attractions = [a.get("name", "") for a in (ev.get("_embedded") or {}).get("attractions") or []]
    info = " ".join(x for x in (ev.get("info"), ev.get("pleaseNote")) if x)
    e = make_event(
        source="ticketmaster", title=ev.get("name", ""), start=when, url=ev.get("url", ""), venue=v.get("name", ""),
        address=f"{addr}, {city}, {state}".strip(", "), city=city if state == "RI" else f"{city}, {state}", lat=lat, lon=lon,
        category=cat, tags=[t for t in (seg, genre, sub) if t and t != "Undefined"] + (["worth the drive"] if far else []),
        description=info, image=imgs[0]["url"] if imgs else "", ticket_url=ev.get("url", ""),
        price_min=pr.get("min"), price_max=pr.get("max"), on_sale=on_sale,
        sold_out=status == "offsale" and False, all_day=all_day, performer=", ".join(attractions),
        extra={"tm_id": ev.get("id"), "status": status, "far": far},
    )
    if e:
        e["far"] = far
        if e["on_sale"]:
            from .common import to_dt
            from datetime import datetime
            if to_dt(e["on_sale"]) and to_dt(e["on_sale"]) <= datetime.now(to_dt(e["on_sale"]).tzinfo):
                e["on_sale"] = None
    return e
