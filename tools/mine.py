#!/usr/bin/env python3
"""Build the Captain's private layer: match his calendar to the listings and write a small JSON file
that he imports into the app (⋯ → Import your calendar layer). It is emailed to him, never committed,
never published: the public site must not carry anything derived from his calendar.

    python tools/mine.py calendar.json --out /some/private/place/fun-o-tronic-mine.json [--report]

calendar.json: a list of {summary, start, end, allDay, location, status} (ISO times with offsets).
Output: {"generated", "going": [event ids], "busy": [{"start","end","title","allDay"}], "matches": [...]}.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent.parent
STOP = set("the a an at of and vs v to in on for with by pm am live tour show night night! @ presents".split())
ALIASES = {"bruins": ["providence bruins"], "waterfire": ["waterfire"], "hockey": ["ice hockey"], "meehan": ["meehan auditorium"],
           "comedy connection": ["comedy connection"], "ppac": ["providence performing arts center"], "vets": ["the vets"],
           "trinity": ["trinity repertory", "dowling theater"], "gatsby": ["great gatsby"], "cirque": ["cirque du soleil"],
           "marlies": ["toronto marlies"], "checkers": ["charlotte checkers"], "wolfpack": ["hartford wolf pack", "wolf pack"],
           "americans": ["rochester americans"], "bears": ["hershey bears"], "belleville": ["belleville senators"]}


def toks(s: str) -> set[str]:
    s = re.sub(r"\d{1,2}(?::\d{2})?\s*(?:am|pm)?", " ", s.lower())
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    out = {t for t in s.split() if t not in STOP and len(t) > 2}
    for t in list(out):
        for a in ALIASES.get(t, []):
            out.update(a.split())
    return out


def parse(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def match(cal: list[dict], events: list[dict]) -> tuple[list[str], list[dict]]:
    by_day: dict[str, list[dict]] = {}
    for e in events:
        by_day.setdefault(e["start"][:10], []).append(e)
    going, matches = [], []
    for c in cal:
        if c.get("allDay"):
            continue
        st = parse(c["start"])
        day = st.date().isoformat()
        ct = toks(c["summary"] + " " + (c.get("location") or ""))
        best, best_score = None, 0
        for e in by_day.get(day, []):
            et = toks(e["title"] + " " + e.get("venue", "") + " " + e.get("performer", ""))
            overlap = len(ct & et)
            if not overlap:
                continue
            est = parse(e["start"])
            gap = abs((est - st).total_seconds()) / 3600
            score = overlap * 2 - min(gap, 6) * 0.5 + (2 if gap <= 1.5 else 0)
            if score > best_score:
                best, best_score = e, score
        if best and best_score >= 5.0:  # two real tokens plus a close time; "catch up" ≠ a lecture
            going.append(best["id"])
            matches.append({"cal": c["summary"], "event": best["title"], "venue": best.get("venue", ""), "when": best["start"], "id": best["id"], "score": round(best_score, 1)})
    return going, matches



def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("calendar")
    ap.add_argument("--out", required=True, help="a private path — never inside site/")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    cal = json.load(open(a.calendar))
    events = json.load(open(ROOT / "site" / "data" / "events.json"))["events"]
    going, matches = match(cal, events)
    busy = []
    for c in cal:
        if c.get("status") == "cancelled":
            continue
        busy.append({"start": c["start"], "end": c.get("end") or c["start"], "title": c.get("summary", ""), "allDay": bool(c.get("allDay"))})
    payload = {"generated": datetime.now(TZ).isoformat(timespec="minutes"), "going": going, "busy": busy, "matches": matches}
    out = Path(a.out).resolve()
    if str(out).startswith(str((ROOT / "site").resolve())):
        sys.exit("refusing to write the private layer under site/ — it must never be published")
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    if a.report:
        print(f"{len(cal)} calendar items → {len(going)} matched to listings, {len(busy)} busy windows")
        for m in matches:
            print(f"  ✓ {m['cal'][:38]:38} → {m['when'][:16]} {m['event'][:50]} ({m['venue'][:24]}) s={m['score']}")
        unmatched = [c["summary"] for c in cal if not c.get("allDay") and c["summary"] not in {m["cal"] for m in matches}]
        print("  unmatched timed:", unmatched)
    return 0


if __name__ == "__main__":
    sys.exit(main())
