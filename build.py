#!/usr/bin/env python3
"""Run every scraper, merge, dedupe, diff against the last build, write the site data.

    python build.py            # all sources
    python build.py avon ppac  # just these modules (name = scrapers/<name>.py)
    python build.py --list

Outputs (all under site/data/ unless noted):
    events.json   the full upcoming list the app reads
    venues.json   one row per venue with coords and event counts
    changes.json  what's new / newly on sale since the previous build (rolling 21 days)
    meta.json     build time, per-source health
    ../feed.ics   subscribe-able calendar of everything (site/feed.ics)
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import importlib
import json
import logging
import pkgutil
import re
import sys
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import scrapers
from scrapers.common import TZ, clean, slugify

ROOT = Path(__file__).parent
SITE = ROOT / "site"
DATA = SITE / "data"
STATE = ROOT / "state"
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("build")

HORIZON_DAYS = 400
KEEP_PAST_HOURS = 6  # keep tonight's show listed until it is well over


def discover() -> dict[str, object]:
    mods = {}
    for m in pkgutil.iter_modules(scrapers.__path__):
        if m.name.startswith("_") or m.name == "common":
            continue
        mods[m.name] = m.name
    return mods


def run_one(name: str) -> tuple[str, list[dict], str | None]:
    try:
        mod = importlib.import_module(f"scrapers.{name}")
        evs = mod.fetch() or []
        meta = getattr(mod, "SOURCE", {})
        for e in evs:
            e["module"] = name
            e.setdefault("source_name", meta.get("name", name))
            e.setdefault("source_url", meta.get("url", ""))
            if not e.get("venue") and meta.get("venue"):
                e["venue"] = meta["venue"]
            if not e.get("city") and meta.get("city"):
                e["city"] = meta["city"]
            if e.get("lat") is None and meta.get("lat") is not None:
                e["lat"], e["lon"] = meta["lat"], meta["lon"]
            if not e.get("address") and meta.get("address"):
                e["address"] = meta["address"]
        return name, evs, None
    except Exception:  # noqa: BLE001
        return name, [], traceback.format_exc(limit=3)


_norm_rx = re.compile(r"[^a-z0-9]+")


def norm_title(t: str) -> str:
    t = clean(t).lower()
    t = re.sub(r"\b(the|a|an|live|in concert|presents?|tickets?|w/|with|feat\.?|featuring|university|college|men s|women s)\b", " ", t)
    return _norm_rx.sub(" ", t).strip()


def dedupe(events: list[dict]) -> list[dict]:
    """Same show, same start (±90 min), same venue (or same normalized title) → keep the richest."""
    by_key: dict[tuple, dict] = {}
    for e in events:
        try:
            st = datetime.fromisoformat(e["start"])
        except Exception:  # noqa: BLE001
            continue
        bucket = int(st.timestamp() // (90 * 60))
        tkey = norm_title(e["title"])[:40]
        key = (tkey, bucket)
        prev = by_key.get(key)
        if prev is None:
            by_key[key] = e
            continue
        # merge: prefer the one with ticket/price info, keep the other's gaps filled
        rich = e if score(e) > score(prev) else prev
        other = prev if rich is e else e
        for k, v in other.items():
            if rich.get(k) in (None, "", [], {}, False) and v not in (None, "", [], {}):
                rich[k] = v
        rich.setdefault("also_from", [])
        rich["also_from"] = sorted(set(rich["also_from"] + [other["source"]]))
        by_key[key] = rich
    return list(by_key.values())


def score(e: dict) -> int:
    return sum([
        bool(e.get("ticket_url")) * 3, e.get("price_min") is not None, bool(e.get("image")),
        len(e.get("description", "")) > 80, bool(e.get("on_sale")), bool(e.get("lat")),
    ])


def load_json(p: Path, default):
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return default


def write_ics(events: list[dict], path: Path) -> None:
    from icalendar import Calendar, Event as VEvent
    cal = Calendar()
    cal.add("prodid", "-//Fun-o-tronic 4000//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "Fun-o-tronic 4000 — RI events")
    cal.add("x-wr-timezone", "America/New_York")
    for e in events:
        try:
            v = VEvent()
            v.add("uid", f"{e['id']}@funotronic")
            v.add("summary", e["title"])
            st = datetime.fromisoformat(e["start"])
            if e.get("all_day"):
                v.add("dtstart", st.date())
            else:
                v.add("dtstart", st)
                if e.get("end"):
                    v.add("dtend", datetime.fromisoformat(e["end"]))
            loc = ", ".join(x for x in (e.get("venue"), e.get("address") or e.get("city")) if x)
            if loc:
                v.add("location", loc)
            desc = e.get("summary", "")
            if e.get("price_text"):
                desc += f"\n{e['price_text']}"
            if e.get("ticket_url") or e.get("url"):
                desc += f"\n{e.get('ticket_url') or e.get('url')}"
            v.add("description", desc.strip())
            if e.get("url"):
                v.add("url", e["url"])
            cal.add_component(v)
        except Exception as ex:  # noqa: BLE001
            log.debug("ics skip %s: %s", e.get("id"), ex)
    path.write_bytes(cal.to_ical())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("only", nargs="*")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    mods = discover()
    if args.list:
        print("\n".join(sorted(mods)))
        return 0
    names = args.only or sorted(mods)
    unknown = [n for n in names if n not in mods]
    if unknown:
        print("unknown scrapers:", unknown, file=sys.stderr)
        return 2

    DATA.mkdir(parents=True, exist_ok=True)
    STATE.mkdir(exist_ok=True)
    now = datetime.now(TZ)
    prev_events = {e["id"]: e for e in load_json(DATA / "events.json", {"events": []}).get("events", [])}
    prev_meta = load_json(DATA / "meta.json", {})
    prev_sources = prev_meta.get("sources", {})

    all_events: list[dict] = []
    health: dict[str, dict] = {}
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for name, evs, err in pool.map(run_one, names):
            if err:
                log.error("%s FAILED\n%s", name, err)
                # keep last good copy of this source so a blip doesn't blank it out
                carried = [e for e in prev_events.values() if e.get("module") == name]
                health[name] = {"ok": False, "count": len(carried), "error": err.strip().splitlines()[-1][:300],
                                "last_ok": prev_sources.get(name, {}).get("last_ok")}
                all_events.extend(carried)
            else:
                log.info("%s: %d events", name, len(evs))
                health[name] = {"ok": True, "count": len(evs), "last_ok": now.isoformat(timespec="minutes")}
                all_events.extend(evs)
    # sources not run this time keep their previous events
    if args.only:
        for e in prev_events.values():
            if e.get("module") not in names:
                all_events.append(e)
        for k, v in prev_sources.items():
            health.setdefault(k, v)

    # window
    lo = now - timedelta(hours=KEEP_PAST_HOURS)
    hi = now + timedelta(days=HORIZON_DAYS)
    kept = []
    for e in all_events:
        try:
            st = datetime.fromisoformat(e["start"])
            en = datetime.fromisoformat(e["end"]) if e.get("end") else None
        except Exception:  # noqa: BLE001
            continue
        if (en or st) >= lo and st <= hi:
            kept.append(e)
    events = dedupe(kept)
    import math
    def miles(lat, lon):
        p1, p2 = math.radians(41.8268), math.radians(lat)
        dp, dl = math.radians(lat - 41.8268), math.radians(lon + 71.4025)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * 3958.8 * math.asin(math.sqrt(a))
    for e in events:  # drop coordinates outside southern New England (bad geocodes, swapped lat/lon); flag the far ones
        try:
            if e.get("lat") is not None and not (41.0 <= float(e["lat"]) <= 42.9 and -72.6 <= float(e["lon"]) <= -70.0):
                e["lat"] = e["lon"] = None
        except (TypeError, ValueError):
            e["lat"] = e["lon"] = None
        if e.get("lat") is not None:
            e["miles"] = round(miles(float(e["lat"]), float(e["lon"])), 1)
            e["far"] = e["miles"] > 35
        else:
            e.setdefault("far", bool(re.search(r"\b(Mass\.|Conn\.|, MA\b|, CT\b|Boston|Worcester|New Haven|Hartford|Mansfield|Uncasville|New Bedford|Fall River)", e.get("city", "") + " " + e.get("address", ""))))
    events.sort(key=lambda e: (e["start"], e["title"].lower()))

    # first-seen / on-sale tracking, persisted in state/
    seen = load_json(STATE / "seen.json", {})
    changes = load_json(DATA / "changes.json", {"items": []})
    new_items = []
    for e in events:
        rec = seen.get(e["id"])
        if rec is None:
            seen[e["id"]] = {"first_seen": now.isoformat(timespec="minutes"), "ticket": bool(e.get("ticket_url")),
                             "on_sale": e.get("on_sale")}
            e["first_seen"] = seen[e["id"]]["first_seen"]
            if prev_events:  # don't flood on the very first build
                new_items.append({"kind": "new", "at": e["first_seen"], "id": e["id"], "title": e["title"],
                                  "start": e["start"], "venue": e.get("venue", ""), "category": e["category"]})
        else:
            e["first_seen"] = rec.get("first_seen")
            if e.get("ticket_url") and not rec.get("ticket"):
                rec["ticket"] = True
                new_items.append({"kind": "on_sale", "at": now.isoformat(timespec="minutes"), "id": e["id"],
                                  "title": e["title"], "start": e["start"], "venue": e.get("venue", ""),
                                  "category": e["category"]})
            if e.get("on_sale") and e.get("on_sale") != rec.get("on_sale"):
                rec["on_sale"] = e["on_sale"]
    # prune seen to ids still in window + 60 days grace
    cutoff = (now - timedelta(days=60)).isoformat()
    seen = {k: v for k, v in seen.items() if v.get("first_seen", "") >= cutoff or k in {e["id"] for e in events}}
    (STATE / "seen.json").write_text(json.dumps(seen, indent=0, sort_keys=True))
    keep_after = (now - timedelta(days=21)).isoformat(timespec="minutes")
    try:  # watch-list status changes (written by scrapers/onsale_watch.py)
        for w in load_json(DATA / "watch.json", {}).get("items", []):
            if w.get("changed") and w["changed"][:16] == now.isoformat(timespec="minutes")[:16]:
                new_items.append({"kind": "watch", "at": w["changed"], "id": f"watch:{w['key']}", "title": w["title"], "start": w.get("on_sale") or "",
                                  "venue": w.get("venue", ""), "category": w.get("category", "festival"), "status": w["status"], "prev": w.get("prev_status"),
                                  "evidence": w.get("evidence", ""), "url": w.get("url")})
    except Exception as ex:  # noqa: BLE001
        log.debug("watch changes: %s", ex)
    changes["items"] = [c for c in changes["items"] if c["at"] >= keep_after] + new_items
    changes["generated"] = now.isoformat(timespec="minutes")
    (DATA / "changes.json").write_text(json.dumps(changes, ensure_ascii=False))

    # venues
    venues: dict[str, dict] = {}
    for e in events:
        if not e.get("venue"):
            continue
        k = slugify(e["venue"])
        v = venues.setdefault(k, {"id": k, "name": e["venue"], "city": e.get("city", ""), "address": e.get("address", ""),
                                  "lat": e.get("lat"), "lon": e.get("lon"), "count": 0, "categories": Counter()})
        v["count"] += 1
        v["categories"][e["category"]] += 1
        if v["lat"] is None and e.get("lat") is not None:
            v["lat"], v["lon"] = e["lat"], e["lon"]
        if not v["city"] and e.get("city"):
            v["city"] = e["city"]
        e["venue_id"] = k
    for v in venues.values():
        v["categories"] = dict(v["categories"].most_common())
    (DATA / "venues.json").write_text(json.dumps(sorted(venues.values(), key=lambda v: -v["count"]), ensure_ascii=False))

    (DATA / "events.json").write_text(json.dumps({"generated": now.isoformat(timespec="minutes"),
                                                   "count": len(events), "events": events}, ensure_ascii=False))
    cats = Counter(e["category"] for e in events)
    meta = {"generated": now.isoformat(timespec="minutes"), "count": len(events), "sources": health,
            "categories": dict(cats.most_common()), "cities": dict(Counter(e.get("city", "") for e in events).most_common(30))}
    (DATA / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    write_ics(events, SITE / "feed.ics")

    bad = [k for k, v in health.items() if not v["ok"]]
    log.info("TOTAL %d events from %d sources (%d failed: %s)", len(events), len(health), len(bad), ", ".join(bad))
    return 0


if __name__ == "__main__":
    sys.exit(main())
