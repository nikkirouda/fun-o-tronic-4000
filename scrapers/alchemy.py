"""Alchemy (Providence) — SpotHopper page, server-rendered .event-content rows."""
from __future__ import annotations

import re
from datetime import date

from .common import clean, get_soup, make_event, to_dt

SOURCE = {"name": "Alchemy", "url": "https://alchemyri.net/providence-downtown-alchemy-events", "venue": "Alchemy",
          "city": "Providence", "address": "71 Richmond St", "lat": 41.8206, "lon": -71.4106}


def fetch() -> list[dict]:
    soup = get_soup(SOURCE["url"], timeout=40)
    out = []
    today = date.today()
    for row in soup.select(".event-content"):
        h = row.select_one("h2, h3")
        day = row.select_one(".event-day")
        if not (h and day):
            continue
        dtxt = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", clean(day.get_text()))  # "Saturday November 7th"
        time_el = row.select_one(".event-time")
        ttxt = clean(time_el.get_text()) if time_el else ""
        start_t = (re.search(r"\d{1,2}:\d{2}\s*[AP]M", ttxt) or [None])[0] or "9:00 PM"
        end_t = (re.findall(r"\d{1,2}:\d{2}\s*[AP]M", ttxt) or ["", ""])[-1] if "-" in ttxt else ""
        start = to_dt(f"{dtxt} {today.year} {start_t}")
        if start and start.date() < today.replace(day=1):
            start = start.replace(year=start.year + 1)
        end = to_dt(f"{dtxt} {start.year} {end_t}") if start and end_t else None
        if end and end < start:
            from datetime import timedelta
            end = end + timedelta(days=1)
        info = row.select_one(".event-info-text")
        text = clean(info.get_text(" ")) if info else ""
        link = row.select_one("a[href*='opendate'], a[href*='ticketweb'], a[href*='eventbrite'], a[href*='dice.fm']")
        img = row.select_one("img.event-image")
        recurring = bool(row.select_one("[data-is-recurring='true']"))
        age = re.search(r"\b(18\+|21\+|All Ages)\b", text, re.I)
        ev = make_event(
            source="alchemy", title=h.get_text(), start=start, end=end, url=SOURCE["url"], venue=SOURCE["venue"],
            address=SOURCE["address"], city=SOURCE["city"], lat=SOURCE["lat"], lon=SOURCE["lon"], category="music",
            description=text, image=("https:" + img["src"]) if img and img.get("src", "").startswith("//") else (img["src"] if img else ""),
            ticket_url=link["href"].split("?fbclid")[0] if link else "", price_text=text,
            tags=(["weekly"] if recurring else []) + ([age.group(1).lower()] if age else []),
        )
        if ev:
            ev["kids"] = False
            if recurring and re.search(r"dj|dance night|saturdays|fridays", ev["title"] + text, re.I):
                ev["tags"] = sorted(set(ev["tags"] + ["dj night"]))
            out.append(ev)
    return out
