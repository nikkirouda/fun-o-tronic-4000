"""Machines with Magnets (Pawtucket) — Webflow list; four h4.upcoming_datetime per item: title, date, time, price."""
from __future__ import annotations

from .common import clean, get_soup, log, make_event, to_dt

SOURCE = {"name": "Machines with Magnets", "url": "https://machineswithmagnets.com/performance", "venue": "Machines with Magnets",
          "city": "Pawtucket", "address": "400 Main St, Pawtucket", "lat": 41.8766, "lon": -71.3826}


def fetch() -> list[dict]:
    soup = get_soup(SOURCE["url"], timeout=40)
    out = []
    for item in soup.select(".upcoming_cms-item"):
        h4s = [clean(h.get_text()) for h in item.select("h4.upcoming_datetime:not(.description)")]
        h4s = [h for h in h4s if h]
        if len(h4s) < 2:
            continue
        title, date_txt = h4s[0], h4s[1]
        time_txt = next((h for h in h4s[2:] if ":" in h and ("am" in h.lower() or "pm" in h.lower())), "8:00 pm")
        price_txt = next((h for h in h4s[2:] if "$" in h or "free" in h.lower()), "")
        desc_el = item.select_one("h4.description")
        kind = item.select_one("h5.e-modal-description")
        tix = item.select_one("a.tickets-button[href^='http']")
        start = to_dt(f"{date_txt} {time_txt}")
        if not start:
            log.debug("mwm: bad date %r", date_txt)
            continue
        artists = [clean(a.get_text()) for a in item.select("a.link-2") if clean(a.get_text())]
        e = make_event(
            source="machines", title=title, start=start, url=SOURCE["url"], venue=SOURCE["venue"], address=SOURCE["address"],
            city=SOURCE["city"], lat=SOURCE["lat"], lon=SOURCE["lon"], category="music",
            description=clean(desc_el.get_text()) if desc_el else "", price_text=price_txt,
            ticket_url=tix["href"].split("?aff")[0] if tix else "", performer=", ".join(artists),
            tags=[clean(kind.get_text()).lower()] if kind else [],
        )
        if e:
            e["kids"] = False
            out.append(e)
    return out
