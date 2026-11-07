"""Newport Classical — WP REST lists the concerts; each page carries schema.org Event JSON-LD."""
from __future__ import annotations

import re

from .common import clean, event_from_jsonld, get_json, get_soup, jsonld_events, log

VENUE_RX = re.compile(r"(Rosecliff|The Breakers|Marble House|The Elms|Chateau-sur-Mer|Emmanuel Church|Newport Classical Recital Hall|"
                      r"St\.? [A-Z][a-z]+'?s? Church|Trinity Church|Kay Chapel|Belcourt|Rough Point|Redwood Library|Jane Pickens)", re.I)


def _venue_from_title(*texts: str) -> str:
    for t in texts:
        m = VENUE_RX.search(clean(t))
        if m:
            return m.group(1)
    if any("mansion" in clean(t).lower() for t in texts):
        return "Rosecliff"
    return "Newport Classical"

SOURCE = {"name": "Newport Classical", "url": "https://newportclassical.org/concerts/", "city": "Newport"}
MAX = 60


def fetch() -> list[dict]:
    rows = get_json("https://newportclassical.org/wp-json/wp/v2/event", params={"per_page": 100}, timeout=40)
    out = []
    for r in rows[:MAX]:
        link = r.get("link")
        if not link:
            continue
        try:
            objs = jsonld_events(get_soup(link, timeout=30))
        except Exception as e:  # noqa: BLE001
            log.debug("newport classical %s: %s", link, e)
            continue
        for obj in objs:
            # their JSON-LD stamps local times with a Z and uses "Address of <title>" as the place name
            for k in ("startDate", "endDate"):
                if isinstance(obj.get(k), str):
                    obj[k] = re.sub(r"(Z|[+-]\d{2}:\d{2})$", "", obj[k])
            loc = obj.get("location")
            if isinstance(loc, dict) and str(loc.get("name", "")).lower().startswith("address of"):
                addr = loc.get("address")
                loc["name"] = clean(addr.get("name", "") if isinstance(addr, dict) else "") or _venue_from_title(obj.get("name", ""), r.get("title", {}).get("rendered", ""))
            e = event_from_jsonld(obj, source="newport_classical", default_city="Newport", category="classical", url=link)
            if e:
                e["kids"] = False
                if not e["ticket_url"]:
                    e["ticket_url"] = link
                out.append(e)
    return out
