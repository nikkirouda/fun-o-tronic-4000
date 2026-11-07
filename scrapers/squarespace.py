"""Squarespace event collections: `<page>?format=json-pretty` → upcoming[] with epoch-ms dates."""
from __future__ import annotations

import re

from .common import clean, get_json, log, make_event, parse_price

SOURCE = {"name": "Squarespace venues", "url": ""}

SITES = [
    {"key": "fete", "base": "https://www.fetemusic.com", "pages": ["/all-shows", "/special-events"], "venue": "Fete Music Hall",
     "city": "Providence", "address": "103 Dike St", "lat": 41.8155, "lon": -71.4323, "category": "music"},
    {"key": "as220", "base": "https://as220.org", "pages": ["/calendar"], "venue": "AS220", "city": "Providence",
     "address": "115 Empire St", "lat": 41.8232, "lon": -71.4119, "category": None},
    {"key": "newportlive", "base": "https://www.newportlive.org", "pages": ["/concerts"], "venue": "Newport Live", "city": "Newport",
     "category": "music"},
    {"key": "pumphouse", "base": "https://www.pumphousemusicworks.com", "pages": ["/event-calendar"], "venue": "Pump House Music Works",
     "city": "Peace Dale", "address": "1464 Kingstown Rd", "lat": 41.4479, "lon": -71.5006, "category": "music"},
]
TICKET_RX = re.compile(r"https?://[^\s\"'<>]*(ticketweb|eventbrite|etix|dice\.fm|opendate|ticketmaster|tixr|seetickets|showclix|ovationtix)[^\s\"'<>]*", re.I)


def fetch() -> list[dict]:
    out: list[dict] = []
    for s in SITES:
        for page in s["pages"]:
            try:
                data = get_json(f"{s['base']}{page}?format=json-pretty", timeout=40)
            except Exception as e:  # noqa: BLE001
                log.info("sqs %s%s: %s", s["key"], page, str(e)[:100])
                continue
            n = 0
            for it in data.get("upcoming", []):
                body = it.get("body", "") or ""
                text = clean(body)
                m = TICKET_RX.search(body)
                pmin, pmax, free = parse_price(text[:600])
                loc = it.get("location") or {}
                venue = clean(loc.get("addressTitle", "")) or s["venue"]
                ev = make_event(
                    source=f"sqs:{s['key']}", title=it.get("title", ""), start=int(it["startDate"]) if it.get("startDate") else None,
                    end=int(it["endDate"]) if it.get("endDate") else None, url=s["base"] + it.get("fullUrl", ""),
                    venue=venue if venue.lower().startswith(s["venue"].lower()[:5]) else s["venue"],
                    address=clean(loc.get("addressLine1", "")) or s.get("address", ""), city=s["city"],
                    lat=s.get("lat"), lon=s.get("lon"), category=s["category"],
                    tags=list(it.get("categories", [])) + list(it.get("tags", [])),
                    summary=clean(it.get("excerpt", "")), description=text, image=it.get("assetUrl", ""),
                    ticket_url=m.group(0) if m else "", price_min=pmin, price_max=pmax, is_free=free,
                    price_text=(re.search(r"\$\s?\d[\d.]*(?:\s*(?:/|-|–|to)\s*\$?\d[\d.]*)?[^.<]{0,30}", text) or [None])[0] if "$" in text else "",
                )
                if ev:
                    ev["source_name"] = s["venue"]
                    ev["source_url"] = s["base"]
                    out.append(ev)
                    n += 1
            log.info("sqs %s%s: %d", s["key"], page, n)
    return out
