"""PatronManager (Salesforce) public event lists: Trinity Rep, The Gamm. One row per performance."""
from __future__ import annotations

import re

from .common import clean, get_json, log, make_event, summarize

SOURCE = {"name": "Trinity Rep / The Gamm (PatronManager)", "url": ""}

ORGS = [
    {"key": "trinity", "api": "https://trinityrep.my.salesforce-sites.com/ticket/PatronTicket__PublicApiEventList",
     "venue": "Trinity Repertory Company", "city": "Providence", "address": "201 Washington St", "lat": 41.8232, "lon": -71.4128,
     "web": "https://www.trinityrep.com/shows/", "category": "theater"},
    {"key": "gamm", "api": "https://gammtheatre.my.salesforce-sites.com/ticket/PatronTicket__PublicApiEventList",
     "venue": "The Gamm Theatre", "city": "Warwick", "address": "1245 Jefferson Blvd", "lat": 41.7249, "lon": -71.4459,
     "web": "https://www.gammtheatre.org/", "category": "theater"},
]
SKIP_TYPES = {"Subscription", "Package", "Membership", "Donation", "Gift Card"}
SKIP_RX = re.compile(r"subscription|flex pass|gift certificate|membership|donation|class|camp|workshop|parking", re.I)


def fetch() -> list[dict]:
    out: list[dict] = []
    for o in ORGS:
        try:
            data = get_json(o["api"], timeout=90)
        except Exception as e:  # noqa: BLE001
            log.warning("patronmanager %s: %s", o["key"], e)
            continue
        vraw = data.get("venues") or {}
        venues = vraw if isinstance(vraw, dict) else {v.get("id"): v for v in vraw if isinstance(v, dict)}
        n = 0
        for ev in data.get("events", []):
            if ev.get("type") in SKIP_TYPES or SKIP_RX.search(ev.get("name", "")):
                continue
            desc = clean(ev.get("detail") or ev.get("description") or "")
            img = ev.get("largeImagePath") or ev.get("smallImagePath") or ""
            for inst in ev.get("instances", []):
                if inst.get("nonTimed"):
                    continue
                iso = (inst.get("formattedDates") or {}).get("ISO8601")
                if not iso:
                    continue
                v = venues.get(inst.get("venueId")) or {}
                vname = clean(v.get("name", "")) or o["venue"]
                pmin = pmax = None
                try:
                    prices = [lvl["price"] for a in inst.get("allocations", []) for lvl in a.get("levels", []) if lvl.get("price") is not None]
                    if prices:
                        pmin, pmax = min(prices), max(prices)
                except (TypeError, KeyError):
                    pass
                e = make_event(
                    source=f"pm:{o['key']}", title=ev.get("name", ""), start=iso, url=o["web"], venue=vname,
                    address=o["address"] if vname == o["venue"] else "", city=o["city"],
                    lat=o["lat"] if vname == o["venue"] else None, lon=o["lon"] if vname == o["venue"] else None,
                    category=o["category"], description=desc, summary=summarize(desc), image=img,
                    ticket_url=inst.get("purchaseUrl") or ev.get("purchaseUrl") or "", price_min=pmin, price_max=pmax,
                    sold_out=bool(inst.get("soldOut")) or (inst.get("saleStatus") or "").lower() == "sold out",
                    tags=[ev.get("category")] if ev.get("category") else [],
                    extra={"sale_status": inst.get("saleStatus"), "instance": inst.get("name")},
                )
                if e:
                    if (inst.get("saleStatus") or "").lower() not in ("on sale", "sold out", ""):
                        e["tags"] = sorted(set(e["tags"] + [inst["saleStatus"].lower()]))
                    e["source_name"] = o["venue"]
                    e["source_url"] = o["web"]
                    out.append(e)
                    n += 1
        log.info("patronmanager %s: %d performances", o["key"], n)
    return out
