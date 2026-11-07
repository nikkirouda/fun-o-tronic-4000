"""Avon Cinema (Thayer St) — hand-built HTML. Flattened, the page reads
'TITLE  NOVEMBER 6–12, 2026  DAILY AT 4:10  <blurb> Directed by X  Rated R  Running time 1h 41m  NEXT TITLE ...'.
We locate every date range, take the ALL-CAPS run before it as the title, and the text up to the next range as the body."""
from __future__ import annotations

import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from .common import clean, get, log, make_event, to_dt

SOURCE = {"name": "Avon Cinema", "url": "https://www.avoncinema.com/now-playing.php", "venue": "Avon Cinema",
          "city": "Providence", "address": "260 Thayer St", "lat": 41.8290, "lon": -71.4007}
PAGES = ["https://www.avoncinema.com/now-playing.php", "https://www.avoncinema.com/coming-soon.php",
         "https://www.avoncinema.com/special-events.php"]
MONTHS = "JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER"
RANGE_RX = re.compile(rf"\b(?:(?:MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY),?\s+)?({MONTHS})\s+(\d{{1,2}})"
                      rf"(?:\s*[–—-]\s*(?:({MONTHS})\s+)?(\d{{1,2}}))?(?:,\s*(\d{{4}}))?\b")
TIME_RX = re.compile(r"(?:DAILY AT|SHOWTIMES?:?|AT)\s+((?:\d{1,2}(?::\d{2})?\s*(?:[AP]\.?M\.?)?(?:\s*(?:,|&|AND|\+)\s*)?){1,6})", re.I)
TITLE_RX = re.compile(r"((?:[A-Z0-9][A-Z0-9'’:!?&.,\-]*\s+){1,12})$")


def _times(s: str) -> list[str]:
    m = TIME_RX.search(s[:300])
    if not m:
        return []
    out = []
    for t in re.split(r"\s*(?:,|&|AND|\+)\s*", m.group(1), flags=re.I):
        t = t.strip()
        if not re.match(r"\d", t):
            continue
        if not re.search(r"[ap]", t, re.I):
            h = int(t.split(":")[0])
            t += " am" if 10 <= h <= 11 else " pm"
        out.append(t)
    return out


def fetch() -> list[dict]:
    out = []
    today = date.today()
    seen = set()
    for url in PAGES:
        try:
            html = get(url, timeout=30).content.decode("utf-8", "replace")  # served without a charset
        except Exception as e:  # noqa: BLE001
            log.info("avon %s: %s", url, e)
            continue
        soup = BeautifulSoup(html, "lxml")
        for s in soup(["script", "style", "nav", "header", "footer"]):
            s.decompose()
        text = clean(soup.get_text(" "))
        matches = list(RANGE_RX.finditer(text))
        for i, m in enumerate(matches):
            before = text[max(0, m.start() - 200):m.start()]
            tm = TITLE_RX.search(before)
            if not tm:
                continue
            title = clean(tm.group(1))
            title = re.sub(r"^(NOW PLAYING|COMING SOON|SPECIAL EVENTS)\s+", "", title)
            if len(title) < 2:
                continue
            body = text[m.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)]
            body = re.split(r"©|&copy;", body)[0]
            m1, d1, m2, d2, yr = m.groups()
            year = int(yr) if yr else today.year
            start_d = to_dt(f"{m1} {d1} {year}")
            if not start_d:
                continue
            end_d = to_dt(f"{m2 or m1} {d2} {year}") if d2 else start_d
            if not yr and start_d.date() < today - timedelta(days=60):
                start_d = start_d.replace(year=year + 1)
                end_d = end_d.replace(year=year + 1)
            if end_d < start_d:
                end_d = end_d.replace(year=end_d.year + 1)
            times = _times(body) or ["7:00 pm"]
            blurb = clean(TIME_RX.sub("", body, count=1))
            rating = re.search(r"\b(Rated [A-Z0-9-]+|Not rated)\b", blurb, re.I)
            runtime = re.search(r"Running time ([\dh ]+m?)", blurb, re.I)
            director = re.search(r"Directed by (.+?)(?=\s+(?:Rated|Not rated|Running time)|$)", blurb, re.I)
            summary = re.split(r"\s+Directed by\b", blurb, flags=re.I)[0]
            d = start_d.date()
            while d <= end_d.date():
                if d >= today:
                    for t in times:
                        st = to_dt(f"{d.isoformat()} {t}")
                        key = (title.lower(), st)
                        if not st or key in seen:
                            continue
                        seen.add(key)
                        ev = make_event(
                            source="avon", title=title.title() if title.isupper() else title, start=st, url=url,
                            venue=SOURCE["venue"], address=SOURCE["address"], city=SOURCE["city"], lat=SOURCE["lat"], lon=SOURCE["lon"],
                            category="film", summary=summary[:300], description=blurb,
                            tags=([rating.group(1).lower()] if rating else []) + ["movie"], price_text="$14 adult / $12.50 senior & child",
                            price_min=12.5, price_max=14.0, is_free=False, performer=director.group(1).strip() if director else "",
                            extra={"runtime": runtime.group(1).strip() if runtime else None, "run_start": start_d.date().isoformat(),
                                   "run_end": end_d.date().isoformat()},
                        )
                        if ev:
                            ev["kids"] = False
                            out.append(ev)
                d += timedelta(days=1)
    return out
