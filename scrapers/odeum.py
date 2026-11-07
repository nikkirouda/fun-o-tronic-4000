"""Greenwich Odeum — public Sanity CMS read API."""
from __future__ import annotations

from datetime import date
from urllib.parse import quote

from .common import clean, get_json, make_event, to_dt

SOURCE = {"name": "Greenwich Odeum", "url": "https://www.greenwichodeum.com/events", "venue": "Greenwich Odeum",
          "city": "East Greenwich", "address": "59 Main St", "lat": 41.6603, "lon": -71.4531}
API = "https://kh2h9w5a.api.sanity.io/v2021-10-21/data/query/production"


def _blocks_text(blocks) -> str:
    if not isinstance(blocks, list):
        return clean(blocks or "")
    paras = []
    for b in blocks:
        if isinstance(b, dict) and b.get("_type") == "block":
            paras.append("".join(c.get("text", "") for c in b.get("children", []) if isinstance(c, dict)))
    return "\n".join(p for p in paras if p)


def fetch() -> list[dict]:
    q = (f'*[_type=="event" && date>="{date.today().isoformat()}"]|order(date)'
         '{title,date,doorsTime,showTime,price,ticketUrl,"slug":slug.current,shortBlurb,bio,'
         '"image":heroImage.asset->url,soldOut,genre}')
    data = get_json(f"{API}?query={quote(q)}", timeout=40)
    out = []
    for r in data.get("result", []):
        d = r.get("date", "")[:10]
        t = clean(r.get("showTime") or r.get("doorsTime") or "8:00 PM")
        start = to_dt(f"{d} {t}") or to_dt(d)
        ev = make_event(
            source="odeum", title=r.get("title", ""), start=start, url=f"https://www.greenwichodeum.com/events/{r.get('slug', '')}",
            venue=SOURCE["venue"], address=SOURCE["address"], city=SOURCE["city"], lat=SOURCE["lat"], lon=SOURCE["lon"],
            category=None, tags=[r["genre"]] if r.get("genre") else [], summary=clean(r.get("shortBlurb", "")),
            description=_blocks_text(r.get("bio")), image=r.get("image") or "", ticket_url=r.get("ticketUrl") or "",
            price_text=r.get("price") or "", sold_out=bool(r.get("soldOut")),
            extra={"doors": r.get("doorsTime"), "show": r.get("showTime")},
        )
        if ev:
            if ev["category"] == "other":
                ev["category"] = "music"
            out.append(ev)
    return out
