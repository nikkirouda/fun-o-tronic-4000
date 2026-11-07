"""Rhode Island Comedy Connection — ICS for the list, JSON-LD on event pages for price + on-sale."""
from __future__ import annotations

from .common import event_from_jsonld, get, get_soup, jsonld_events, log, parse_ics

SOURCE = {"name": "RI Comedy Connection", "url": "https://www.ricomedyconnection.com/events", "venue": "Comedy Connection",
          "city": "East Providence", "address": "39 Warren Ave", "lat": 41.8143, "lon": -71.3703}
ICS = "https://www.ricomedyconnection.com/api/calendar/events.ics"
MAX_DETAIL = 60


def fetch() -> list[dict]:
    evs = parse_ics(get(ICS, timeout=40).text, source="comedy_connection", venue=SOURCE["venue"], city=SOURCE["city"],
                    address=SOURCE["address"], url_base=SOURCE["url"], category="comedy")
    for e in evs:
        e["lat"], e["lon"] = SOURCE["lat"], SOURCE["lon"]
        e["kids"] = False
    # enrich the soonest N with price/on-sale/ticket link from the page's JSON-LD
    by_url: dict[str, list[dict]] = {}
    for e in evs:
        if e.get("url", "").startswith("http"):
            by_url.setdefault(e["url"], []).append(e)
    for i, (url, group) in enumerate(sorted(by_url.items(), key=lambda kv: kv[1][0]["start"])):
        if i >= MAX_DETAIL:
            break
        try:
            objs = jsonld_events(get_soup(url, timeout=30))
        except Exception as ex:  # noqa: BLE001
            log.debug("comedy detail %s: %s", url, ex)
            continue
        for obj in objs:
            d = event_from_jsonld(obj, source="comedy_connection", default_venue=SOURCE["venue"], default_city=SOURCE["city"], category="comedy")
            if not d:
                continue
            for e in group:
                if e["start"][:13] == d["start"][:13] or len(group) == 1:
                    for k in ("ticket_url", "price_min", "price_max", "on_sale", "image", "description", "sold_out", "performer"):
                        if d.get(k) not in (None, "", False) and e.get(k) in (None, "", False):
                            e[k] = d[k]
                    if e.get("price_min") is not None and not e.get("price_text"):
                        e["price_text"] = f"${e['price_min']:.2f}".replace(".00", "")
                    if not e.get("summary") and e.get("description"):
                        from .common import summarize
                        e["summary"] = summarize(e["description"])
    return evs
