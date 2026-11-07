"""Carbonhouse venue sites (PPAC, The VETS, Amica Mutual Pavilion, RI Convention Center).

The /events page is server-rendered: each `.eventItem` carries title, detail URL, tickets link,
thumbnail, tagline, and a `.event_showings` block with one `.listItem` per performance
(weekday/month/day + time). JSON-LD gives the run's description and on-sale date.
"""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from .common import clean, get, jsonld_events, log, make_event, to_dt

VENUES = {
    "ppac": {"name": "Providence Performing Arts Center", "url": "https://www.ppacri.org/events",
             "address": "220 Weybosset St", "city": "Providence", "lat": 41.8217, "lon": -71.4136, "category": "theater"},
    "vets": {"name": "The VETS", "url": "https://www.thevetsri.com/events",
             "address": "1 Avenue of the Arts", "city": "Providence", "lat": 41.8289, "lon": -71.4099, "category": None},
    "amica": {"name": "Amica Mutual Pavilion", "url": "https://www.amicamutualpavilion.com/events",
              "address": "1 La Salle Square", "city": "Providence", "lat": 41.8251, "lon": -71.4179, "category": None},
    "ricc": {"name": "Rhode Island Convention Center", "url": "https://www.riconvention.com/events",
             "address": "1 Sabin St", "city": "Providence", "lat": 41.8237, "lon": -71.4168, "category": "festival"},
}
SOURCE = {"name": "PPAC / VETS / Amica / RICC", "url": "https://www.ppacri.org/events", "city": "Providence"}

_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def fetch() -> list[dict]:
    out: list[dict] = []
    for key, v in VENUES.items():
        try:
            out.extend(scrape_venue(key, v))
        except Exception as e:  # noqa: BLE001
            log.warning("carbonhouse %s failed: %s", key, e)
    return out


def _parse_showing(li, year_hint: int) -> tuple | None:
    md = li.select_one(".m-date__month")
    dd = li.select_one(".m-date__day")
    if not md or not dd:
        return None
    mon = _MONTHS.get(clean(md.get_text()).lower()[:3])
    day = int(re.sub(r"\D", "", dd.get_text()) or 0)
    if not mon or not day:
        return None
    yr_el = li.select_one(".m-date__year")
    year = int(re.sub(r"\D", "", yr_el.get_text())) if yr_el and re.search(r"\d{4}", yr_el.get_text()) else year_hint
    t_el = li.select_one(".time")
    time_txt = clean(t_el.get_text()) if t_el else ""
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*([AP]M)", time_txt, re.I)
    if m:
        h = int(m.group(1)) % 12 + (12 if m.group(3).upper() == "PM" else 0)
        start = f"{year:04d}-{mon:02d}-{day:02d}T{h:02d}:{int(m.group(2) or 0):02d}:00"
        all_day = False
    else:
        start = f"{year:04d}-{mon:02d}-{day:02d}"
        all_day = True
    link = li.select_one("a.tickets, a[href*='evenue'], a[href*='ticketmaster'], a[href*='etix']")
    return start, all_day, link["href"] if link else ""


def scrape_venue(key: str, v: dict) -> list[dict]:
    r = get(v["url"], timeout=40)
    soup = BeautifulSoup(r.text, "lxml")
    ld = {}
    for obj in jsonld_events(soup):
        ld[clean(obj.get("name", "")).lower()] = obj
    today = date.today()
    out = []
    for item in soup.select(".eventItem"):
        a = item.select_one("h3.title a, .title a")
        if not a:
            continue
        title = clean(a.get_text())
        url = a.get("href", "")
        tagline = clean(item.select_one(".tagline").get_text()) if item.select_one(".tagline") else ""
        img = item.select_one(".thumb img")
        tickets = item.select_one("a.tickets")
        ticket_url = tickets["href"] if tickets and tickets.get("href", "").startswith("http") else ""
        sold_out = bool(tickets and re.search(r"sold ?out", tickets.get_text() + " ".join(tickets.get("class", [])), re.I))
        meta = ld.get(title.lower(), {})
        offers = meta.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        on_sale = offers.get("validFrom") or offers.get("availabilityStarts")
        if on_sale and to_dt(on_sale) and to_dt(on_sale).date() <= today:
            on_sale = None  # already on sale; only keep future on-sale dates
        desc = clean(meta.get("description", ""))
        loc = meta.get("location") or {}
        venue_name = clean(loc.get("name", "")) if isinstance(loc, dict) else ""
        venue_name = venue_name or v["name"]
        # year hint: the range header has the year; else assume this/next year by month order
        yr = item.select_one(".m-date__year")
        year_hint = int(re.sub(r"\D", "", yr.get_text())) if yr and re.search(r"\d{4}", yr.get_text()) else today.year
        showings = [s for s in (_parse_showing(li, year_hint) for li in item.select(".event_showings .listItem")) if s]
        if not showings and meta.get("startDate"):
            showings = [(meta["startDate"], False, ticket_url)]
        for start, all_day, turl in showings:
            sdt = to_dt(start)
            if sdt and sdt.date() < today.replace(day=1) and not yr:
                # month earlier than now and no explicit year → next year
                sdt = sdt.replace(year=sdt.year + 1)
            ev = make_event(
                source="carbonhouse", title=title, start=sdt or start, url=url, venue=venue_name,
                address=v["address"] if venue_name == v["name"] else "", city=v["city"],
                lat=v["lat"] if venue_name == v["name"] else None, lon=v["lon"] if venue_name == v["name"] else None,
                category=v["category"], tags=[tagline] if tagline else [], summary=tagline if not desc else "",
                description=desc, image=img["src"] if img and img.get("src", "").startswith("http") else "",
                ticket_url=turl or ticket_url, on_sale=on_sale, sold_out=sold_out, all_day=all_day,
            )
            if ev:
                out.append(ev)
    log.info("carbonhouse %s: %d showings", key, len(out))
    return out
