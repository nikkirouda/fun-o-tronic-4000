"""Stadium Theatre (Woonsocket) — upcoming-shows cards, enriched with showtimes from the detail page."""
from __future__ import annotations

import re
from datetime import date, timedelta

from .common import clean, get_soup, log, make_event, to_dt

SOURCE = {"name": "Stadium Theatre", "url": "https://www.stadiumtheatre.com/shows-tickets/upcoming-shows", "venue": "Stadium Theatre",
          "city": "Woonsocket", "address": "28 Monument Sq", "lat": 42.0028, "lon": -71.5148}
MAX_DETAIL = 40
DT_RX = re.compile(r"((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+)?([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})\s*(?:at|@|-|–)?\s*(\d{1,2}(?::\d{2})?\s*[AaPp]\.?[Mm]\.?)?")


def fetch() -> list[dict]:
    soup = get_soup(SOURCE["url"], timeout=40)
    out = []
    today = date.today()
    cards = soup.select(".event-card")
    for i, c in enumerate(cards):
        a = c.select_one("h2 a, h3 a")
        when = c.select_one(".small-text")
        if not (a and when):
            continue
        title = clean(a.get_text())
        link = a["href"]
        blurb = clean(c.select_one(".card-content > p:not(.small-text)").get_text()) if c.select_one(".card-content > p:not(.small-text)") else ""
        cats = [clean(li.get_text()) for li in c.select(".category-list li")]
        img = c.select_one("img")
        img_url = img.get("src") or img.get("data-src") or "" if img else ""
        sold_out = "sold-out" in img_url.lower() or "sold out" in c.get_text().lower()
        wtxt = clean(when.get_text())  # "November 01 - 08, 2026" or "November 07, 2026"
        rm = re.match(r"([A-Z][a-z]+)\s+(\d{1,2})(?:\s*-\s*(?:([A-Z][a-z]+)\s+)?(\d{1,2}))?,\s*(\d{4})", wtxt)
        if not rm:
            continue
        m1, d1, m2, d2, yr = rm.groups()
        first = to_dt(f"{m1} {d1} {yr}")
        last = to_dt(f"{m2 or m1} {d2} {yr}") if d2 else first
        showtimes: list = []
        if i < MAX_DETAIL:
            try:
                ds = get_soup(link, timeout=30)
                text = clean(ds.get_text(" "))
                for m in DT_RX.finditer(text):
                    mon, day, y, t = m.group(2), m.group(3), m.group(4), m.group(5)
                    dt = to_dt(f"{mon} {day} {y} {t or ''}".strip())
                    if dt and first and first.date() <= dt.date() <= (last.date() if last else first.date()) and t:
                        showtimes.append(dt)
                tix = ds.select_one("a[href*='csstix'], a[href*='ticket']")
                tix_url = tix["href"] if tix else link
                price = re.search(r"\$\d[\d.]*(?:\s*[-–]\s*\$?\d[\d.]*)?", text)
            except Exception as e:  # noqa: BLE001
                log.debug("stadium detail %s: %s", link, e)
                tix_url, price = link, None
        else:
            tix_url, price = link, None
        showtimes = sorted({s for s in showtimes})
        cat = None
        joined = " ".join(cats).lower()
        for k, v in (("theatre", "theater"), ("comedy", "comedy"), ("music", "music"), ("dance", "dance"), ("film", "film"), ("family", "family")):
            if k in joined:
                cat = v
                break
        if not showtimes:
            d = first.date()
            while d <= (last.date() if last else d):
                showtimes.append(to_dt(f"{d.isoformat()} 19:30"))
                d += timedelta(days=1)
            all_day = False
        else:
            all_day = False
        for st in showtimes:
            if st.date() < today:
                continue
            ev = make_event(source="stadium", title=title, start=st, url=link, venue=SOURCE["venue"], address=SOURCE["address"],
                            city=SOURCE["city"], lat=SOURCE["lat"], lon=SOURCE["lon"], category=cat, tags=cats, summary=blurb,
                            image=img_url, ticket_url=tix_url, price_text=price.group(0) if price else "", sold_out=sold_out, all_day=all_day)
            if ev:
                out.append(ev)
    return out
