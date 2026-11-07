"""Shared plumbing for every source: HTTP, parsing helpers, the Event schema.

Every scraper module exposes `SOURCE = {...}` metadata and a `fetch() -> list[dict]`
returning events in the common schema (see `make_event`). Scrapers never raise on
bad individual items; they log and skip. The build runner catches module-level
failures so one dead venue never sinks the fleet.
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import re
import time
from datetime import date, datetime, timedelta
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparse

log = logging.getLogger("funotronic")
TZ = ZoneInfo("America/New_York")
UA = "Fun-o-tronic/1.0 (+https://github.com/nikkirouda/fun-o-tronic-4000; personal RI events calendar)"

CATEGORIES = [
    "theater", "music", "classical", "dance", "comedy", "film", "talk",
    "sports", "festival", "market", "art", "family", "food", "community", "other",
]

# ---------------------------------------------------------------- HTTP ------

_session = requests.Session()
_session.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})


def get(url: str, *, params: dict | None = None, headers: dict | None = None,
        timeout: int = 30, retries: int = 2, **kw) -> requests.Response:
    """GET with retries and a polite pause. Raises on final failure."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = _session.get(url, params=params, headers=headers, timeout=timeout, **kw)
            if r.status_code in (429, 502, 503, 504) and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:  # noqa: PERF203
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed: {last}")


def get_json(url: str, **kw) -> Any:
    return get(url, **kw).json()


def get_soup(url: str, **kw) -> BeautifulSoup:
    return BeautifulSoup(get(url, **kw).text, "lxml")


# --------------------------------------------------------------- dates ------

def to_dt(value: Any, default_tz=TZ) -> datetime | None:
    """Parse almost anything into an aware datetime in Eastern time."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime(value.year, value.month, value.day, tzinfo=default_tz)
        return dt
    else:
        s = str(value).strip()
        if re.fullmatch(r"\d{10,13}", s):  # epoch
            n = int(s)
            dt = datetime.fromtimestamp(n / 1000 if n > 1e11 else n, tz=default_tz)
        else:
            try:
                dt = dtparse.parse(s)
            except (ValueError, OverflowError):
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_tz)
    return dt.astimezone(default_tz)


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="minutes") if dt else None


# ---------------------------------------------------------------- text ------

def clean(s: Any) -> str:
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    s = BeautifulSoup(s, "lxml").get_text(" ") if "<" in s else html.unescape(s)
    s = s.replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def summarize(text: str, limit: int = 240) -> str:
    """First sentence or two, trimmed to ~limit chars on a word boundary."""
    t = clean(text)
    if len(t) <= limit:
        return t
    cut = t[:limit]
    for sep in (". ", "! ", "? "):
        i = cut.rfind(sep)
        if i > limit * 0.5:
            return cut[: i + 1]
    return cut[: cut.rfind(" ")].rstrip(",;:") + "…"


_PRICE_RE = re.compile(r"\$\s?(\d{1,4}(?:\.\d{2})?)")


def parse_price(text: Any) -> tuple[float | None, float | None, bool | None]:
    """Return (min, max, is_free) from a free-form price string."""
    t = clean(text).lower()
    if not t:
        return None, None, None
    if re.search(r"\bfree\b|no charge|pay[- ]what[- ]you[- ]can|donation", t):
        nums = [float(x) for x in _PRICE_RE.findall(t)]
        return (0.0, max(nums) if nums else 0.0, True)
    nums = [float(x) for x in _PRICE_RE.findall(t)]
    if not nums:
        return None, None, None
    return min(nums), max(nums), min(nums) == 0


KIDS_RE = re.compile(
    r"\b(kids?|children(?:'s)?|family|families|toddler|preschool|story ?time|"
    r"ages? \d{1,2}[-–]\d{1,2}|all ages welcome|youth|teens?|puppet|junior|"
    r"little ones|sensory[- ]friendly|school vacation)\b", re.I)


def looks_kids(*texts: str) -> bool:
    blob = " ".join(clean(t) for t in texts if t)
    # "all ages" shows at bars too; require two signals or a strong one
    strong = re.search(r"\b(kids?|children(?:'s)?|toddler|preschool|story ?time|puppet)\b", blob, re.I)
    hits = len(KIDS_RE.findall(blob))
    return bool(strong) or hits >= 2


_CAT_RULES: list[tuple[str, re.Pattern]] = [
    ("music", re.compile(r"\b(tribute|tribute band|cover band|the music of|zeppelin|beatles|pink floyd|grateful dead|"
                         r"rock|metal|punk|hip[- ]hop|dj)\b", re.I)),
    ("classical", re.compile(r"\b(symphony|philharmonic|orchestra|chamber|quartet|recital|sonata|"
                             r"concerto|opera|choral|chorus|oratorio|baroque|string ensemble|"
                             r"piano trio|cantata)\b", re.I)),
    ("dance", re.compile(r"\b(ballet|dance company|contemporary dance|modern dance|choreograph|"
                         r"flamenco|tap dance|step afrika|dance theater)\b", re.I)),
    ("comedy", re.compile(r"\b(comedy|comedian|stand[- ]?up|improv|sketch|open mic comedy|roast)\b", re.I)),
    ("film", re.compile(r"\b(film|movie|screening|cinema|documentary|premiere|double feature|"
                        r"35 ?mm|shorts program)\b", re.I)),
    ("talk", re.compile(r"\b(lecture|talk|panel|discussion|author|book launch|reading|conversation with|"
                        r"symposium|colloquium|seminar|keynote|q ?& ?a|salon|book club|poetry)\b", re.I)),
    ("sports", re.compile(r"\b(vs\.?|versus|football|basketball|hockey|soccer|lacrosse|baseball|softball|"
                          r"volleyball|wrestling|track|rowing|crew|swim|game|match|bruins|friars|bears|"
                          r"rams|bulldogs|rhode island fc|5k|marathon|race|polo|rugby)\b", re.I)),
    ("market", re.compile(r"\b(farmers'? market|flea|craft fair|makers market|holiday market|bazaar|"
                          r"vintage market|night market|artisan market)\b", re.I)),
    ("festival", re.compile(r"\b(festival|fest\b|waterfire|parade|fireworks|block party|celebration|"
                            r"carnival|oyster fest|pvdfest|comic con|expo|home show|boat show|convention|"
                            r"con \d{4}|tree lighting)\b", re.I)),
    ("art", re.compile(r"\b(exhibition|exhibit|gallery|opening reception|artist talk|art show|"
                       r"gallery night|museum)\b", re.I)),
    ("food", re.compile(r"\b(tasting|wine dinner|beer dinner|restaurant week|brunch|cooking class|"
                        r"food truck|chef'?s table|pairing)\b", re.I)),
    ("theater", re.compile(r"\b(theat(?:re|er)|play|musical|drama|cabaret|broadway|one[- ]woman|one[- ]man|"
                           r"staged reading|shakespeare|pantomime|revue|burlesque|magic show|circus)\b", re.I)),
    ("music", re.compile(r"\b(concert|live music|band|tour|dj|singer|songwriter|jazz|blues|folk|"
                         r"rock|indie|punk|hip[- ]hop|rap|r&b|soul|funk|metal|country|bluegrass|"
                         r"acoustic|album|ep release|open mic|tribute|karaoke|reggae|latin night|"
                         r"salsa|electronic|house music|techno)\b", re.I)),
]


def guess_category(*texts: str, default: str = "other") -> str:
    blob = " ".join(clean(t) for t in texts if t)
    for cat, rx in _CAT_RULES:
        if rx.search(blob):
            return cat
    return default


# ------------------------------------------------------------- venues -------

def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", clean(s).lower()).strip("-")
    return s[:80] or "x"


def make_id(source: str, title: str, start: str | None, venue: str = "") -> str:
    h = hashlib.sha1(f"{source}|{clean(title).lower()}|{start or ''}|{clean(venue).lower()}".encode()).hexdigest()
    return f"{slugify(source)}-{h[:12]}"


def make_event(*, source: str, title: str, start: Any, url: str,
               end: Any = None, venue: str = "", address: str = "", city: str = "",
               lat: float | None = None, lon: float | None = None,
               category: str | None = None, tags: Iterable[str] = (),
               summary: str = "", description: str = "", image: str = "",
               ticket_url: str = "", price_text: str = "", price_min: float | None = None,
               price_max: float | None = None, is_free: bool | None = None,
               on_sale: Any = None, sold_out: bool = False, kids: bool | None = None,
               all_day: bool = False, performer: str = "", extra: dict | None = None) -> dict | None:
    """Build one event in the common schema. Returns None if unusable."""
    title = clean(title)
    sdt = to_dt(start)
    if not title or not sdt:
        return None
    edt = to_dt(end)
    if edt and edt < sdt:
        edt = None
    description = clean(description)
    summary = clean(summary) or summarize(description)
    if price_text and price_min is None and price_max is None and is_free is None:
        price_min, price_max, is_free = parse_price(price_text)
    if is_free is None and price_min is not None:
        is_free = price_min == 0 and (price_max or 0) == 0
    cat = category if category in CATEGORIES else guess_category(title, " ".join(tags), summary, description)
    if kids is None:
        kids = looks_kids(title, summary) or cat == "family"
    return {
        "id": make_id(source, title, iso(sdt), venue),
        "source": source,
        "title": title,
        "start": iso(sdt),
        "end": iso(edt),
        "all_day": bool(all_day),
        "venue": clean(venue),
        "address": clean(address),
        "city": clean(city),
        "lat": lat,
        "lon": lon,
        "category": cat,
        "tags": sorted({clean(t).lower() for t in tags if clean(t)})[:12],
        "summary": summary[:400],
        "description": description[:2000],
        "image": image or "",
        "url": url or "",
        "ticket_url": ticket_url or "",
        "price_text": clean(price_text)[:80],
        "price_min": price_min,
        "price_max": price_max,
        "is_free": is_free,
        "on_sale": iso(to_dt(on_sale)) if on_sale else None,
        "sold_out": bool(sold_out),
        "kids": bool(kids),
        "performer": clean(performer)[:200],
        "extra": extra or {},
    }


# ------------------------------------------------------- generic parsers ----

def parse_ics(text: str, *, source: str, venue: str = "", city: str = "",
              address: str = "", url_base: str = "", category: str | None = None,
              horizon_days: int = 400) -> list[dict]:
    """Turn an iCalendar feed into events (one per occurrence for simple RRULEs)."""
    from icalendar import Calendar  # local import: optional dep for some runs
    out: list[dict] = []
    try:
        cal = Calendar.from_ical(text)
    except Exception as e:  # noqa: BLE001
        log.warning("%s: bad ics: %s", source, e)
        return out
    now = datetime.now(TZ)
    horizon = now + timedelta(days=horizon_days)
    for comp in cal.walk("VEVENT"):
        try:
            title = str(comp.get("SUMMARY", ""))
            dtstart = comp.decoded("DTSTART", None)
            dtend = comp.decoded("DTEND", None)
            all_day = isinstance(dtstart, date) and not isinstance(dtstart, datetime)
            starts = [dtstart]
            rr = comp.get("RRULE")
            if rr and dtstart is not None:
                try:
                    from dateutil.rrule import rrulestr
                    base = to_dt(dtstart)
                    rule = rrulestr(rr.to_ical().decode(), dtstart=base)
                    starts = list(rule.between(now - timedelta(days=1), horizon, inc=True))[:60]
                except Exception:  # noqa: BLE001
                    starts = [dtstart]
            dur = None
            if dtstart is not None and dtend is not None:
                dur = to_dt(dtend) - to_dt(dtstart)
            for st in starts:
                s = to_dt(st)
                if not s or s < now - timedelta(days=1) or s > horizon:
                    continue
                loc = str(comp.get("LOCATION", "")) or venue
                ev = make_event(
                    source=source, title=title, start=s, end=(s + dur) if dur else None,
                    url=str(comp.get("URL", "")) or url_base, venue=venue or loc,
                    address=address or (loc if venue else ""), city=city,
                    description=str(comp.get("DESCRIPTION", "")), category=category,
                    all_day=all_day,
                    tags=[str(c) for c in (comp.get("CATEGORIES").cats if comp.get("CATEGORIES") else [])]
                    if hasattr(comp.get("CATEGORIES"), "cats") else [],
                )
                if ev:
                    out.append(ev)
        except Exception as e:  # noqa: BLE001
            log.debug("%s: skip vevent: %s", source, e)
    return out


def jsonld_events(soup_or_html: BeautifulSoup | str) -> list[dict]:
    """Extract schema.org Event-like objects (flattened) from a page."""
    soup = soup_or_html if isinstance(soup_or_html, BeautifulSoup) else BeautifulSoup(soup_or_html, "lxml")
    found: list[dict] = []

    def walk(obj: Any):
        if isinstance(obj, list):
            for o in obj:
                walk(o)
        elif isinstance(obj, dict):
            t = obj.get("@type", "")
            types = t if isinstance(t, list) else [t]
            if any(str(x).endswith("Event") for x in types):
                found.append(obj)
            for k in ("@graph", "itemListElement", "mainEntity", "subEvent", "item"):
                if k in obj:
                    walk(obj[k])

    for tag in soup.find_all("script", type=re.compile("ld\\+json")):
        raw = tag.string or tag.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            walk(json.loads(raw, strict=False))
        except json.JSONDecodeError:
            # some sites concatenate objects or leave trailing commas
            for m in re.finditer(r"\{.*\}", raw, re.S):
                try:
                    walk(json.loads(m.group(0), strict=False))
                except json.JSONDecodeError:
                    pass
    return found


def event_from_jsonld(obj: dict, *, source: str, default_venue: str = "", default_city: str = "",
                      category: str | None = None, url: str = "") -> dict | None:
    loc = obj.get("location") or {}
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    addr = loc.get("address") if isinstance(loc, dict) else None
    if isinstance(addr, dict):
        address = " ".join(clean(addr.get(k, "")) for k in ("streetAddress", "addressLocality", "addressRegion", "postalCode"))
        city = clean(addr.get("addressLocality", "")) or default_city
    else:
        address = clean(addr or "")
        city = default_city
    geo = loc.get("geo") if isinstance(loc, dict) else None
    offers = obj.get("offers") or []
    if isinstance(offers, dict):
        offers = [offers]
    prices = [o.get("price") for o in offers if isinstance(o, dict) and o.get("price") not in (None, "")]
    pmin = pmax = None
    try:
        nums = [float(str(p).replace(",", "")) for p in prices]
        if nums:
            pmin, pmax = min(nums), max(nums)
    except ValueError:
        pass
    for o in offers:
        if isinstance(o, dict):
            if o.get("lowPrice") not in (None, ""):
                pmin = float(o["lowPrice"])
            if o.get("highPrice") not in (None, ""):
                pmax = float(o["highPrice"])
    ticket = next((o.get("url") for o in offers if isinstance(o, dict) and o.get("url")), "")
    on_sale = next((o.get("validFrom") for o in offers if isinstance(o, dict) and o.get("validFrom")), None)
    sold_out = any("SoldOut" in str(o.get("availability", "")) for o in offers if isinstance(o, dict))
    image = obj.get("image")
    if isinstance(image, list):
        image = image[0] if image else ""
    if isinstance(image, dict):
        image = image.get("url", "")
    perf = obj.get("performer")
    if isinstance(perf, list):
        perf = ", ".join(clean(p.get("name", "")) if isinstance(p, dict) else clean(p) for p in perf)
    elif isinstance(perf, dict):
        perf = perf.get("name", "")
    return make_event(
        source=source, title=obj.get("name", ""), start=obj.get("startDate"), end=obj.get("endDate"),
        url=obj.get("url") or url, venue=clean(loc.get("name", "")) if isinstance(loc, dict) else default_venue,
        address=address, city=city,
        lat=float(geo["latitude"]) if isinstance(geo, dict) and geo.get("latitude") else None,
        lon=float(geo["longitude"]) if isinstance(geo, dict) and geo.get("longitude") else None,
        category=category, description=obj.get("description", ""), image=image or "",
        ticket_url=ticket or "", price_min=pmin, price_max=pmax, on_sale=on_sale, sold_out=sold_out,
        performer=perf or "", tags=[obj.get("eventAttendanceMode", "")] if False else [],
    )


def tribe_events(base: str, *, source: str, venue: str = "", city: str = "",
                 category: str | None = None, per_page: int = 50, max_pages: int = 6,
                 path: str = "/wp-json/tribe/events/v1/events") -> list[dict]:
    """WordPress 'The Events Calendar' REST API."""
    out: list[dict] = []
    today = date.today().isoformat()
    for page in range(1, max_pages + 1):
        try:
            data = get_json(base.rstrip("/") + path, params={
                "per_page": per_page, "page": page, "start_date": today, "status": "publish"})
        except Exception as e:  # noqa: BLE001
            if page == 1:
                raise
            log.debug("%s: tribe page %s: %s", source, page, e)
            break
        for ev in data.get("events", []):
            v = ev.get("venue") or {}
            if isinstance(v, list):
                v = v[0] if v else {}
            cost = ev.get("cost") or ""
            cats = [c.get("name", "") for c in ev.get("categories", [])] + [t.get("name", "") for t in ev.get("tags", [])]
            img = ev.get("image") or {}
            e = make_event(
                source=source, title=ev.get("title", ""), start=ev.get("start_date"), end=ev.get("end_date"),
                url=ev.get("url", ""), venue=v.get("venue") or venue, city=v.get("city") or city,
                address=" ".join(clean(v.get(k, "")) for k in ("address", "city", "state_province", "zip")),
                lat=float(v["geo_lat"]) if v.get("geo_lat") else None,
                lon=float(v["geo_lng"]) if v.get("geo_lng") else None,
                category=category, tags=cats, description=ev.get("description", ""),
                image=img.get("url", "") if isinstance(img, dict) else "",
                ticket_url=ev.get("website", "") or "", price_text=cost, all_day=bool(ev.get("all_day")),
            )
            if e:
                out.append(e)
        total_pages = int(data.get("total_pages") or 1)
        if page >= total_pages:
            break
    return out
