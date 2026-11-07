"""Carbonhouse RSS (ev: namespace) for The VETS, Amica Mutual Pavilion, RI Convention Center.
Start times are UTC. Ticket links are only on the detail page; we fetch those for the soonest shows."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .common import clean, get, jsonld_events, log, make_event, summarize, to_dt

SOURCE = {"name": "The VETS / Amica / RICC", "url": ""}

FEEDS = [
    {"key": "vets", "rss": "https://www.thevetsri.com/events/rss", "venue": "The VETS", "city": "Providence",
     "address": "1 Avenue of the Arts", "lat": 41.8289, "lon": -71.4099},
    {"key": "amica", "rss": "https://www.amicamutualpavilion.com/events/rss", "venue": "Amica Mutual Pavilion", "city": "Providence",
     "address": "1 La Salle Square", "lat": 41.8251, "lon": -71.4179},
    {"key": "ricc", "rss": "https://www.riconvention.com/events/rss", "venue": "Rhode Island Convention Center", "city": "Providence",
     "address": "1 Sabin St", "lat": 41.8237, "lon": -71.4168},
]
HDR = {"Accept": "application/rss+xml, application/xml, text/xml, */*"}
MAX_DETAIL = 40
TYPE_MAP = {"comedy": "comedy", "concert": "music", "concerts": "music", "music": "music", "family": "family", "theater": "theater",
            "theatre": "theater", "broadway": "theater", "dance": "dance", "sports": "sports", "hockey": "sports", "basketball": "sports",
            "trade show": "festival", "convention": "festival", "consumer show": "festival", "expo": "festival"}


def _detail(url: str) -> dict:
    """Ticket link, price and on-sale from a Carbonhouse detail page."""
    info: dict = {}
    try:
        soup = BeautifulSoup(get(url, timeout=30, headers={"Accept": "text/html,*/*"}).text, "lxml")
    except Exception as e:  # noqa: BLE001
        log.debug("carbonhouse detail %s: %s", url, e)
        return info
    a = soup.select_one("a.tickets[href^='http'], a[href*='ticketmaster.com/event'], a[href*='evenue.net'], a[href*='etix.com']")
    if a:
        info["ticket_url"] = a["href"]
        if re.search(r"sold ?out", a.get_text() + " ".join(a.get(" class", [])), re.I):
            info["sold_out"] = True
    for obj in jsonld_events(soup):
        offers = obj.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if offers.get("validFrom") or offers.get("availabilityStarts"):
            info["on_sale"] = offers.get("validFrom") or offers.get("availabilityStarts")
        if offers.get("url") and "ticket_url" not in info:
            info["ticket_url"] = offers["url"]
        if obj.get("image"):
            info["image"] = obj["image"] if isinstance(obj["image"], str) else obj["image"][0] if isinstance(obj["image"], list) else ""
    price = soup.select_one(".price, .ticket-price, .eventDetail .price")
    if price:
        info["price_text"] = clean(price.get_text())
    return info


def fetch() -> list[dict]:
    out: list[dict] = []
    for f in FEEDS:
        try:
            xml = get(f["rss"], headers=HDR, timeout=40).text
        except Exception as e:  # noqa: BLE001
            log.warning("carbonhouse rss %s: %s", f["key"], e)
            continue
        soup = BeautifulSoup(xml, "xml")
        rows = []
        for item in soup.find_all("item"):
            g = lambda tag: clean(item.find(tag).get_text()) if item.find(tag) else ""  # noqa: E731
            rows.append({"title": g("title"), "link": g("link"), "desc": clean(item.description.get_text()) if item.description else "",
                         "start": g("ev:startdate") or g("startdate"), "end": g("ev:enddate") or g("enddate"),
                         "loc": g("ev:location") or g("location"), "type": g("ev:type") or g("type")})
        rows.sort(key=lambda r: r["start"])
        details: dict[str, dict] = {}
        for i, r in enumerate(rows):
            if r["link"] and i < MAX_DETAIL:
                details[r["link"]] = details.get(r["link"]) or _detail(r["link"])
        n = 0
        for r in rows:
            d = details.get(r["link"], {})
            cat = TYPE_MAP.get(r["type"].lower(), None)
            on_sale = d.get("on_sale")
            if on_sale and to_dt(on_sale) and to_dt(on_sale) <= to_dt("now") if False else None:
                pass
            e = make_event(
                source=f"ch:{f['key']}", title=r["title"], start=r["start"], end=r["end"] if r["end"] != r["start"] else None,
                url=r["link"], venue=f["venue"], address=f["address"], city=f["city"], lat=f["lat"], lon=f["lon"],
                category=cat, tags=[r["type"]] if r["type"] else [], description=r["desc"], summary=summarize(r["desc"]),
                image=d.get("image", ""), ticket_url=d.get("ticket_url", ""), price_text=d.get("price_text", ""),
                on_sale=on_sale, sold_out=d.get("sold_out", False),
            )
            if e:
                if e["on_sale"] and to_dt(e["on_sale"]).timestamp() < __import__("time").time():
                    e["on_sale"] = None  # already on sale
                e["source_name"] = f["venue"]
                e["source_url"] = f["rss"].replace("/rss", "")
                out.append(e)
                n += 1
        log.info("carbonhouse rss %s: %d", f["key"], n)
    return out
