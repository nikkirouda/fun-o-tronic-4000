"""Providence Improv Guild — shows are Shopify products; the date lives in the title ("Friday Show - 11/27 - ...")."""
from __future__ import annotations

import re
from datetime import date

from .common import clean, get_json, make_event, to_dt

SOURCE = {"name": "Providence Improv Guild", "url": "https://improvpig.com", "venue": "Providence Improv Guild",
          "city": "Providence", "address": "95 Empire St", "lat": 41.8231, "lon": -71.4121}
DEFAULT_TIMES = {"friday": "8:00 PM", "saturday": "8:00 PM", "sunday": "7:00 PM", "thursday": "8:00 PM"}


def fetch() -> list[dict]:
    data = get_json(f"{SOURCE['url']}/products.json?limit=250", timeout=40)
    out = []
    today = date.today()
    for p in data.get("products", []):
        title = clean(p.get("title", ""))
        m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", title)
        if not m:
            continue
        mo, d = int(m.group(1)), int(m.group(2))
        yr = int(m.group(3)) if m.group(3) else today.year
        if yr < 100:
            yr += 2000
        if not m.group(3) and (mo, d) < (today.month, today.day) and today.month - mo > 6:
            yr += 1
        body = clean(p.get("body_html", ""))
        tm = re.search(r"\b(\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?)", body + " " + title, re.I)
        wd = re.search(r"(friday|saturday|sunday|thursday|monday|tuesday|wednesday)", title, re.I)
        time_txt = tm.group(1) if tm else DEFAULT_TIMES.get(wd.group(1).lower() if wd else "", "8:00 PM")
        start = to_dt(f"{yr}-{mo:02d}-{d:02d} {time_txt}")
        if not start or start.date() < today:
            continue
        show = re.sub(r"^.*?\d{1,2}/\d{1,2}(?:/\d{2,4})?\s*[-–:]\s*", "", title) or title
        price = None
        try:
            price = min(float(v["price"]) for v in p.get("variants", []) if v.get("price"))
        except ValueError:
            pass
        sold_out = p.get("variants") and not any(v.get("available", True) for v in p["variants"])
        imgs = p.get("images") or []
        ev = make_event(
            source="pig", title=f"PIG: {show}", start=start, url=f"{SOURCE['url']}/products/{p.get('handle', '')}",
            venue=SOURCE["venue"], address=SOURCE["address"], city=SOURCE["city"], lat=SOURCE["lat"], lon=SOURCE["lon"],
            category="comedy", description=body, image=imgs[0].get("src", "") if imgs else "",
            ticket_url=f"{SOURCE['url']}/products/{p.get('handle', '')}", price_min=price, price_max=price,
            is_free=price == 0 if price is not None else None, sold_out=bool(sold_out), tags=["improv"],
        )
        if ev:
            ev["kids"] = False
            out.append(ev)
    return out
