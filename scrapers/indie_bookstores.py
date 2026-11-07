"""IndieCommerce (Drupal) bookstore event lists: Books on the Square, Symposium Books.
Markup: article.event-list → h3.event-list__title a[href=/event/YYYY-MM-DD/slug], .event-list__body,
.event-list__details--item (Date:, Time:, Place:), .event-tag__term. Symposium sits behind Cloudflare and
may refuse some networks; the build keeps its last good copy when that happens."""
from __future__ import annotations

import re
from datetime import date

from .common import clean, get_soup, log, make_event, to_dt

SOURCE = {"name": "Bookstores (IndieCommerce)", "url": ""}
STORES = [
    {"key": "booksq", "base": "https://www.booksq.com", "pages": ["/events"], "venue": "Books on the Square", "city": "Providence",
     "address": "471 Angell St", "lat": 41.8276, "lon": -71.3936},
    {"key": "symposium", "base": "https://symposiumbooks.com", "pages": ["/events", "/events/{y}/{m}", "/events/{y2}/{m2}"], "venue": "Symposium Books",
     "city": "Providence", "address": "240 Westminster St", "lat": 41.8236, "lon": -71.4126},
]
HREF_RX = re.compile(r"/event/(\d{4}-\d{2}-\d{2})/")


def _pages(st: dict) -> list[str]:
    t = date.today()
    y2, m2 = (t.year + (t.month // 12), t.month % 12 + 1)
    return [st["base"] + p.format(y=t.year, m=f"{t.month:02d}", y2=y2, m2=f"{m2:02d}") for p in st["pages"]]


def fetch() -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for st in STORES:
        n = 0
        for url in _pages(st):
            try:
                soup = get_soup(url, headers={"Accept": "text/html,application/xhtml+xml"}, timeout=30)
            except Exception as e:  # noqa: BLE001
                log.info("bookstore %s %s: %s", st["key"], url, str(e)[:80])
                continue
            for art in soup.select("article.event-list, .views-row"):
                a = art.select_one("h3.event-list__title a, h3 a[href*='/event/']") or art.select_one("a[href*='/event/']")
                if not a:
                    continue
                m = HREF_RX.search(a.get("href", ""))
                if not m:
                    continue
                link = st["base"] + a["href"] if a["href"].startswith("/") else a["href"]
                if link in seen:
                    continue
                seen.add(link)
                details = {clean(d.select_one(".event-list__details--label").get_text()).rstrip(": ").lower(): clean(d.get_text().replace(d.select_one(".event-list__details--label").get_text(), ""))
                           for d in art.select(".event-list__details--item") if d.select_one(".event-list__details--label")}
                time_txt = details.get("time", "")
                tm = re.search(r"(\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?)", time_txt, re.I)
                end_m = re.findall(r"(\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?)", time_txt, re.I)
                start = to_dt(f"{m.group(1)} {tm.group(1) if tm else '6:00 pm'}")
                end = to_dt(f"{m.group(1)} {end_m[1]}") if len(end_m) > 1 else None
                place = details.get("place", "")
                venue = st["venue"]
                if place and st["venue"].lower() not in place.lower():
                    venue = clean(place.split("\n")[0])[:80] or st["venue"]
                tags = [clean(t.get_text()).lower() for t in art.select(".event-tag__term")]
                body = art.select_one(".event-list__body")
                img = art.select_one(".event-list__image img")
                e = make_event(
                    source=f"books:{st['key']}", title=a.get_text(), start=start, end=end, url=link, venue=venue,
                    address=st["address"] if venue == st["venue"] else "", city=st["city"],
                    lat=st["lat"] if venue == st["venue"] else None, lon=st["lon"] if venue == st["venue"] else None,
                    category="talk", tags=tags + ["bookstore"], description=clean(body.get_text()) if body else "",
                    image=(st["base"] + img["src"]) if img and img.get("src", "").startswith("/") else (img["src"] if img else ""),
                    is_free=True if not re.search(r"\$\d", (body.get_text() if body else "")) else None,
                )
                if e:
                    if "virtual" in e["title"].lower() or "zoom" in (e["venue"] + e["description"]).lower():
                        e["tags"].append("online")
                    e["source_name"] = st["venue"]
                    out.append(e)
                    n += 1
        log.info("bookstore %s: %d", st["key"], n)
    return out
