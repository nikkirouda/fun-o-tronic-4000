"""Rockhouse Partners / Etix venue sites (The Strand, The Met): RSS where pubDate is the show date,
description text carries doors/show/price. We parse the human date line in the description when present."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .common import clean, get, log, make_event, parse_price, to_dt

SOURCE = {"name": "Strand / Met (Etix venues)", "url": ""}

SITES = [
    {"key": "strand", "feed": "https://thestrandri.com/events/feed/", "list": "https://thestrandri.com/events/", "venue": "The Strand Ballroom & Theatre",
     "city": "Providence", "address": "79 Washington St", "lat": 41.8236, "lon": -71.4138},
    {"key": "met", "feed": "https://themetri.com/events/feed/", "list": "https://themetri.com/events/", "venue": "The Met",
     "city": "Pawtucket", "address": "1005 Main St", "lat": 41.8698, "lon": -71.3853},
    {"key": "park", "feed": "https://theparkri.com/tickets-events/feed/", "list": "https://theparkri.com/tickets-events/", "venue": "Park Theatre",
     "city": "Cranston", "address": "848 Park Ave", "lat": 41.7705, "lon": -71.4356},
]
DATE_RX = re.compile(r"((?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,?\s+[A-Z][a-z]+\s+\d{1,2},?\s+\d{4})")
TIME_RX = re.compile(r"Show\s*(\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?)", re.I)
DOORS_RX = re.compile(r"Doors\s*(\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?)", re.I)


def fetch() -> list[dict]:
    out: list[dict] = []
    for s in SITES:
        try:
            xml = get(s["feed"], timeout=40).text
        except Exception as e:  # noqa: BLE001
            log.info("rhp %s feed: %s", s["key"], str(e)[:100])
            xml = ""
        n = 0
        if xml:
            soup = BeautifulSoup(xml, "xml")
            for item in soup.find_all("item"):
                title = clean(item.title.get_text() if item.title else "")
                link = clean(item.link.get_text() if item.link else "")
                desc_html = item.description.get_text() if item.description else ""
                desc = clean(desc_html)
                # the description runs "Friday, December 4, 2026Doors 6 pm | Show 6:30 pm..." without spaces
                desc_sp = re.sub(r"(\d{4})(Doors|Show)", r"\1 \2", desc)
                dm = DATE_RX.search(desc_sp)
                tm = TIME_RX.search(desc_sp) or DOORS_RX.search(desc_sp)
                start = None
                if dm:
                    start = to_dt(f"{dm.group(1)} {tm.group(1) if tm else '8:00 pm'}")
                if not start and item.pubDate:
                    start = to_dt(item.pubDate.get_text())
                pmin, pmax, free = parse_price(desc_sp)
                ptxt = re.search(r"\$\d[\d.]*(?:\s*(?:Advance|adv|ADV)[^|$]{0,12})?(?:\s*\|?\s*\$\d[\d.]*\s*(?:Day of|door|DOS)?)?", desc_sp)
                age = re.search(r"\b(All Ages|18\+|21\+)\b", desc_sp)
                tickets = re.search(r"https?://(?:www\.)?etix\.com/[^\s\"'<>]+", desc_html)
                ev = make_event(
                    source=f"rhp:{s['key']}", title=title, start=start, url=link, venue=s["venue"], address=s["address"],
                    city=s["city"], lat=s["lat"], lon=s["lon"], category="music", description=desc_sp[:1200],
                    tags=[age.group(1).lower()] if age else [], ticket_url=tickets.group(0) if tickets else link,
                    price_min=pmin, price_max=pmax, is_free=free, price_text=ptxt.group(0) if ptxt else "",
                )
                if ev:
                    ev["kids"] = False
                    ev["source_name"] = s["venue"]
                    ev["source_url"] = s["list"]
                    out.append(ev)
                    n += 1
        if n == 0:
            n = _scrape_list(s, out)
        log.info("rhp %s: %d", s["key"], n)
    return out


def _scrape_list(s: dict, out: list) -> int:
    """Fallback: the HTML list with .rhp-event-* classes."""
    try:
        soup = BeautifulSoup(get(s["list"], timeout=40).text, "lxml")
    except Exception as e:  # noqa: BLE001
        log.info("rhp %s list: %s", s["key"], str(e)[:100])
        return 0
    n = 0
    for card in soup.select(".rhp-event-list-item, .rhp-event__item, article.rhp-event"):
        t = card.select_one(".rhp-event__title--list, .rhp-event-title, h2, h3")
        d = card.select_one(".rhp-event__date--list, .rhp-event-date")
        c = card.select_one(".rhp-event__cost-text--list, .rhp-event-cost")
        a = card.select_one("a[href]")
        tm = card.select_one(".rhp-event__time-text--list, .rhp-event-time")
        if not (t and d):
            continue
        start = to_dt(f"{clean(d.get_text())} {clean(tm.get_text()) if tm else '8pm'}".replace("Show:", "").replace("Doors:", ""))
        ev = make_event(source=f"rhp:{s['key']}", title=t.get_text(), start=start, url=a["href"] if a else s["list"],
                        venue=s["venue"], address=s["address"], city=s["city"], lat=s["lat"], lon=s["lon"], category="music",
                        price_text=c.get_text() if c else "", ticket_url=a["href"] if a else "")
        if ev:
            ev["kids"] = False
            ev["source_name"] = s["venue"]
            out.append(ev)
            n += 1
    return n
