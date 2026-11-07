#!/usr/bin/env python3
"""Compose the twice-weekly email digest from the published data.

    python digest.py weekend   # Thursday: Fri–Sun picks + new on-sales
    python digest.py week      # Monday: the week ahead
    python digest.py week --html out.html --json out.json

Reads site/data/*.json locally if present, else fetches from the live site. Prints the
plain-text body; --html writes an HTML version. Sending is done by whoever runs it
(the household staff's scheduled session uses the Gmail connector).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")
SITE_URL = "https://nikkirouda.github.io/fun-o-tronic-4000/"
DATA = Path(__file__).parent / "site" / "data"
CAT_LABEL = {"theater": "Theater", "music": "Music", "classical": "Classical", "dance": "Dance", "comedy": "Comedy", "film": "Film",
             "talk": "Talks", "sports": "Sports", "festival": "Festivals", "market": "Markets", "art": "Art", "family": "Family",
             "food": "Food & drink", "community": "Community", "other": "Other"}
# what the Captain leans toward (ranking only; nothing is hidden)
WEIGHT = {"theater": 3, "classical": 3, "comedy": 2.5, "music": 2, "film": 2, "talk": 2, "dance": 2, "festival": 2, "sports": 1.5,
          "art": 1.5, "food": 1, "market": 1, "community": 0.3, "other": 0.5, "family": 0}
PREMIER = ("trinity", "ppac", "gamm", "vets", "riphil", "firstworks", "amica", "strand", "odeum", "stadium", "comedy", "columbus",
           "newport_classical", "avon", "brown", "athenaeum", "risd")


def load(name: str):
    p = DATA / f"{name}.json"
    if p.exists():
        return json.loads(p.read_text())
    import urllib.request
    with urllib.request.urlopen(f"{SITE_URL}data/{name}.json", timeout=30) as r:
        return json.load(r)


def blurb(e: dict, n: int = 170) -> str:
    """Summary minus venue boilerplate ('THIS EVENT TAKES PLACE AT ...')."""
    import re
    t = e.get("summary") or ""
    t = re.sub(r"^(THIS EVENT TAKES PLACE AT [^.]*\.\s*|[A-Z][a-z]+day, [A-Z][a-z]+ \d{1,2}, \d{4}\s*(Doors [^|]*\|\s*)?(Show [^A-Za-z]*)?\s*)", "", t)
    return t[:n].rstrip() + ("…" if len(t) > n else "")


def score(e: dict) -> float:
    s = WEIGHT.get(e["category"], 1)
    if e.get("kids"):
        s -= 2
    if e.get("sold_out") or "sold out" in e["title"].lower():
        s -= 5
    if any(t in ("youth orchestra", "student", "recital") for t in e.get("tags", [])) or "school" in (e.get("venue") or "").lower():
        s -= 2
    if any(k in (e.get("source", "") + e.get("venue", "")).lower() for k in PREMIER):
        s += 1.5
    if e.get("ticket_url"):
        s += 0.5
    if e.get("description") and len(e["description"]) > 120:
        s += 0.5
    if e.get("is_free"):
        s += 0.3
    if "providence" in (e.get("city") or "").lower():
        s += 0.5
    return s


def fmt_when(e: dict) -> str:
    st = datetime.fromisoformat(e["start"])
    if e.get("all_day"):
        return st.strftime("%a %b %-d")
    return st.strftime("%a %b %-d · %-I:%M %p").replace(":00 ", " ").replace(" PM", "pm").replace(" AM", "am")


def price(e: dict) -> str:
    if e.get("is_free") and not (e.get("price_max") or 0) > 0:
        return "Free"
    if e.get("price_min") is not None:
        lo, hi = e["price_min"], e.get("price_max")
        return f"${lo:g}" + (f"–${hi:g}" if hi and hi != lo else "")
    return e.get("price_text") or ""


def build(mode: str) -> dict:
    events = load("events")["events"]
    changes = load("changes").get("items", [])
    now = datetime.now(TZ)
    today = now.date()
    if mode == "weekend":
        # Thu/earlier: the coming Fri–Sun; Fri–Sun: the rest of this weekend
        fri = today if today.weekday() >= 4 else today + timedelta(days=(4 - today.weekday()) % 7)
        sun = fri + timedelta(days=(6 - fri.weekday()) % 7)
        lo, hi = fri, sun
        title = f"Weekend ahead · {fri.strftime('%b %-d')}–{hi.strftime('%-d')}"
    else:
        lo, hi = today, today + timedelta(days=6)
        title = f"The week ahead · {lo.strftime('%b %-d')}–{hi.strftime('%b %-d')}"
    window = [e for e in events if lo <= datetime.fromisoformat(e["start"]).date() <= hi and not e.get("kids")]
    ranked = sorted(window, key=score, reverse=True)
    # one pick per title, spread across categories: top 12
    picks, seen_titles, cat_count = [], set(), defaultdict(int)
    for e in ranked:
        k = e["title"].lower()[:40]
        if k in seen_titles or cat_count[e["category"]] >= 4:
            continue
        seen_titles.add(k)
        cat_count[e["category"]] += 1
        picks.append(e)
        if len(picks) >= 12:
            break
    by_cat = defaultdict(list)
    seen2 = set()
    for e in sorted(window, key=lambda e: e["start"]):
        k = (e["title"].lower()[:40], e["venue"])
        if k in seen2:
            continue
        seen2.add(k)
        by_cat[e["category"]].append(e)
    since = (now - timedelta(days=4 if mode == "weekend" else 3)).isoformat(timespec="minutes")
    on_sale = [c for c in changes if c["kind"] == "on_sale" and c["at"] >= since]
    new = [c for c in changes if c["kind"] == "new" and c["at"] >= since]
    ids = {e["id"]: e for e in events}
    new_big = sorted((ids[c["id"]] for c in new if c["id"] in ids and ids[c["id"]]["category"] not in ("sports", "community")),
                     key=score, reverse=True)[:10]
    upcoming_onsale = [e for e in events if e.get("on_sale") and datetime.fromisoformat(e["on_sale"]) > now][:10]
    return {"title": title, "lo": lo.isoformat(), "hi": hi.isoformat(), "picks": picks, "by_cat": by_cat, "total": len(window),
            "on_sale": [ids[c["id"]] for c in on_sale if c["id"] in ids][:10], "new": new_big, "upcoming_onsale": upcoming_onsale}


def as_text(d: dict) -> str:
    L = [f"FUN-O-TRONIC 4000 — {d['title']}", f"{d['total']} things on. Full list: {SITE_URL}", ""]
    if d["picks"]:
        L += ["IF YOU ONLY DO A FEW", ""]
        for e in d["picks"]:
            L.append(f"• {fmt_when(e)} — {e['title']}")
            line = f"   {e['venue']}" + (f", {e['city']}" if e.get("city") else "") + (f" · {price(e)}" if price(e) else "")
            L.append(line)
            if blurb(e):
                L.append(f"   {blurb(e)}")
            L.append(f"   {e.get('ticket_url') or e.get('url')}")
            L.append("")
    if d["new"] or d["on_sale"]:
        L += ["NEWLY LISTED / ON SALE", ""]
        for e in d["on_sale"]:
            L.append(f"• Tickets now on sale: {e['title']} — {fmt_when(e)} at {e['venue']} {e.get('ticket_url') or ''}")
        for e in d["new"]:
            L.append(f"• New: {e['title']} — {fmt_when(e)} at {e['venue']}")
        L.append("")
    if d["upcoming_onsale"]:
        L += ["GOING ON SALE SOON", ""]
        for e in d["upcoming_onsale"]:
            L.append(f"• {datetime.fromisoformat(e['on_sale']).strftime('%a %b %-d %-I:%M%p')}: {e['title']} ({fmt_when(e)}, {e['venue']})")
        L.append("")
    L += ["BY CATEGORY", ""]
    for cat in sorted(d["by_cat"], key=lambda c: -WEIGHT.get(c, 1)):
        evs = d["by_cat"][cat]
        L.append(f"{CAT_LABEL.get(cat, cat).upper()} ({len(evs)})")
        for e in evs[:8]:
            L.append(f"  {fmt_when(e)} · {e['title']} — {e['venue']}" + (f" · {price(e)}" if price(e) else ""))
        if len(evs) > 8:
            L.append(f"  …and {len(evs) - 8} more on the site")
        L.append("")
    L.append("Listings come from the venues; check before you go. — the staff")
    return "\n".join(L)


def as_html(d: dict) -> str:
    def esc(s):
        return str(s or "").replace("&", "&amp;").replace("<", "&lt;")
    h = [f"<h2 style='font-family:Georgia,serif;margin:0 0 4px'>Fun-o-tronic 4000 — {esc(d['title'])}</h2>",
         f"<p style='color:#666;margin:0 0 16px'>{d['total']} things on · <a href='{SITE_URL}'>open the full list</a></p>"]
    if d["picks"]:
        h.append("<h3>If you only do a few</h3><ul style='padding-left:18px'>")
        for e in d["picks"]:
            link = e.get("ticket_url") or e.get("url") or SITE_URL
            h.append(f"<li style='margin-bottom:10px'><b>{esc(fmt_when(e))}</b> — <a href='{esc(link)}'>{esc(e['title'])}</a><br>"
                     f"<span style='color:#444'>{esc(e['venue'])}{', ' + esc(e['city']) if e.get('city') else ''}{' · ' + esc(price(e)) if price(e) else ''}</span>"
                     f"{'<br><span style=color:#666>' + esc(blurb(e)) + '</span>' if blurb(e) else ''}</li>")
        h.append("</ul>")
    if d["new"] or d["on_sale"]:
        h.append("<h3>Newly listed / on sale</h3><ul style='padding-left:18px'>")
        for e in d["on_sale"]:
            h.append(f"<li>🎟 <b>Now on sale:</b> <a href='{esc(e.get('ticket_url') or e.get('url'))}'>{esc(e['title'])}</a> — {esc(fmt_when(e))}, {esc(e['venue'])}</li>")
        for e in d["new"]:
            h.append(f"<li>✦ <a href='{esc(e.get('url') or e.get('ticket_url'))}'>{esc(e['title'])}</a> — {esc(fmt_when(e))}, {esc(e['venue'])}</li>")
        h.append("</ul>")
    if d["upcoming_onsale"]:
        h.append("<h3>Going on sale soon</h3><ul style='padding-left:18px'>")
        for e in d["upcoming_onsale"]:
            h.append(f"<li>{datetime.fromisoformat(e['on_sale']).strftime('%a %b %-d, %-I:%M %p')}: <a href='{esc(e.get('url'))}'>{esc(e['title'])}</a> ({esc(fmt_when(e))}, {esc(e['venue'])})</li>")
        h.append("</ul>")
    h.append("<h3>By category</h3>")
    for cat in sorted(d["by_cat"], key=lambda c: -WEIGHT.get(c, 1)):
        evs = d["by_cat"][cat]
        h.append(f"<p style='margin:10px 0 2px'><b>{esc(CAT_LABEL.get(cat, cat))}</b> <span style='color:#888'>({len(evs)})</span></p><ul style='margin:0;padding-left:18px;color:#333'>")
        for e in evs[:8]:
            h.append(f"<li>{esc(fmt_when(e))} · <a href='{esc(e.get('url') or e.get('ticket_url') or SITE_URL)}' style='color:#222'>{esc(e['title'])}</a> — {esc(e['venue'])}{' · ' + esc(price(e)) if price(e) else ''}</li>")
        if len(evs) > 8:
            h.append(f"<li style='color:#888'>…and {len(evs) - 8} more on the site</li>")
        h.append("</ul>")
    h.append("<p style='color:#888;font-size:12px;margin-top:18px'>Listings come from the venues; check before you go. — the staff</p>")
    return "\n".join(h)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["weekend", "week"])
    ap.add_argument("--html")
    ap.add_argument("--json")
    a = ap.parse_args()
    d = build(a.mode)
    print(as_text(d))
    if a.html:
        Path(a.html).write_text(as_html(d))
    if a.json:
        Path(a.json).write_text(json.dumps({"title": d["title"], "text": as_text(d), "html": as_html(d)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
