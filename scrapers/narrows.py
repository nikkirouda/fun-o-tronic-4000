"""Narrows Center for the Arts (Fall River) — accesso ShoWare performance list JSON, with prices and availability."""
from __future__ import annotations

import re
from datetime import datetime

from .common import TZ, clean, get_json, log, make_event, summarize, to_dt

SOURCE = {"name": "Narrows Center for the Arts", "url": "https://narrowscenter.showare.com/", "venue": "Narrows Center for the Arts",
          "city": "Fall River", "address": "16 Anawan St, Fall River, MA", "lat": 41.7027, "lon": -71.1612}
API = "https://narrowscenter.showare.com/include/widgets/events/performancelist.asp"
SKIP_RX = re.compile(r"gift card|raffle|donation|membership|commitment to community|parking|yoga|class\b|workshop|camp\b", re.I)


def fetch() -> list[dict]:
    out = []
    for page in range(1, 8):
        try:
            data = get_json(API, params={"action": "perf", "page": page}, headers={"Accept": "application/json,*/*"}, timeout=40)
        except Exception as e:  # noqa: BLE001
            log.info("narrows page %s: %s", page, e)
            break
        perfs = data.get("performance") or []
        if not perfs:
            break
        for p in perfs:
            title = clean(p.get("Event") or p.get("PerformanceName") or "")
            if SKIP_RX.search(title) or p.get("ItemType") not in (None, "P"):
                continue
            start = to_dt(p.get("PerformanceDateTime"))
            end = to_dt(p.get("PerformanceEndDateTime"))
            if not start or (end and (end - start).days > 2):  # multi-month "performances" are campaigns, not shows
                continue
            if start < datetime.now(TZ):
                continue
            pmin = float(p.get("PerformanceMinPrice") or 0) or None
            pmax = float(p.get("PerformanceMaxPrice") or 0) or None
            on_sale = to_dt(p.get("SalesStart")) if p.get("IsSalesPeriodStarted") == "0" else None
            avail = int(p.get("AvailableTickets") or 0)
            img = p.get("PerformanceImage") or p.get("Image1") or ""
            e = make_event(
                source="narrows", title=title, start=start, end=end if end and end != start else None,
                url=f"https://narrowscenter.showare.com/eventperformances.asp?evt={p.get('EventID')}",
                venue=SOURCE["venue"], address=SOURCE["address"], city=SOURCE["city"], lat=SOURCE["lat"], lon=SOURCE["lon"],
                category=None, description=clean(p.get("Description", "")), summary=summarize(clean(p.get("Description", ""))),
                image=f"https://narrowscenter.showare.com/uplimage/{img}" if img and img != "Blank.gif" else "",
                ticket_url=f"https://narrowscenter.showare.com/eventperformances.asp?evt={p.get('EventID')}",
                price_min=pmin, price_max=pmax, on_sale=on_sale, sold_out=avail == 0 and p.get("IsSalesPeriodStarted") == "1",
                tags=[clean(p.get("SEO_EventType", ""))] if p.get("SEO_EventType") else [],
                extra={"available": avail},
            )
            if e:
                e["kids"] = False
                if e["category"] in ("other", "talk", "community"):
                    e["category"] = "music"  # the Narrows is a concert hall first
                out.append(e)
        if len(perfs) < 15:
            break
    return out
