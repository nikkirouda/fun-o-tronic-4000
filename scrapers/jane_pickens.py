"""JPT Film + Event Center (Jane Pickens Theater, Newport) — the /shows listing: poster cards with a date range
but no showtimes (those live behind Veezi). One all-day entry per date, runs capped at 14 days; the
sheet links to the show page where the times are."""
from __future__ import annotations

import re
from datetime import date, timedelta

from .common import clean, get_soup, log, make_event, to_dt

SOURCE = {"name": "Jane Pickens Theater", "url": "https://janepickens.com/shows", "venue": "Jane Pickens Theater",
          "city": "Newport", "address": "49 Touro St, Newport", "lat": 41.4886, "lon": -71.3097}
MONTHS = "JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER"
RANGE_RX = re.compile(rf"({MONTHS})\s+(\d{{1,2}})(?:\s*-\s*(?:({MONTHS})\s+)?(\d{{1,2}}))?", re.I)
LIVE_RX = re.compile(r"\blive\b|concert|comedy|comedian|in conversation|tasting|party|the play\b|tenors|brass|ballet", re.I)


def fetch() -> list[dict]:
    soup = get_soup(SOURCE["url"], timeout=40)
    today = date.today()
    out = []
    for card in soup.select(".loop .col"):
        h = card.select_one("h2 a")
        dr = card.select_one("p.daterange")
        if not (h and dr):
            continue
        title = clean(h.get_text())
        m = RANGE_RX.search(clean(dr.get_text()))
        if not m:
            continue
        m1, d1, m2, d2 = m.groups()
        start = to_dt(f"{m1} {d1} {today.year}")
        if not start:
            continue
        if start.date() < today - timedelta(days=60):
            start = start.replace(year=start.year + 1)
        end = to_dt(f"{m2 or m1} {d2} {start.year}") if d2 else start
        if end < start:
            end = end.replace(year=end.year + 1)
        status = card.select_one("p.status")
        sold_out = bool(re.search(r"sold out", card.get_text(), re.I))
        desc = card.select_one("p.descrip")
        img = card.select_one("img.poster")
        link = h["href"]
        live = bool(LIVE_RX.search(title))
        cat = ("theater" if re.search(r"theatre live|nt live|royal ballet|ballet|the play\b|opera", title, re.I)
               else "comedy" if re.search(r"comedy|comedian", title, re.I)
               else "music" if re.search(r"concert|tenors|brass|w/ live|live music|celebration of the music", title, re.I)
               else "film")
        d = start.date()
        while d <= end.date() and (d - start.date()).days < 14:
            if d >= today:
                e = make_event(
                    source="jpt", title=title, start=to_dt(d.isoformat()), url=link, venue=SOURCE["venue"], address=SOURCE["address"],
                    city=SOURCE["city"], lat=SOURCE["lat"], lon=SOURCE["lon"], category=cat, all_day=True,
                    description=clean(desc.get_text()) if desc else "", image=img["src"] if img else "", ticket_url=link,
                    sold_out=sold_out, tags=[clean(status.get_text()).lower()] if status else [],
                    summary=(clean(desc.get_text())[:200] if desc else "") + " Showtimes on the theater's page.",
                )
                if e:
                    e["kids"] = False
                    out.append(e)
            d += timedelta(days=1)
    log.info("jpt: %d", len(out))
    return out
