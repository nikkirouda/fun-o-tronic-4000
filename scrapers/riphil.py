"""Rhode Island Philharmonic — Spektrix public API v3 (events → instances)."""
from __future__ import annotations

import re

from .common import clean, get_json, log, make_event, summarize

SOURCE = {"name": "Rhode Island Philharmonic", "url": "https://www.riphil.org/events", "venue": "The VETS",
          "city": "Providence", "address": "1 Avenue of the Arts", "lat": 41.8289, "lon": -71.4099}
API = "https://boxoffice.riphil.org/riphil/api/v3"
HDR = {"Accept": "application/json"}


def fetch() -> list[dict]:
    events = get_json(f"{API}/events", headers=HDR, timeout=40)
    out = []
    for ev in events:
        name = clean(ev.get("name", ""))
        if re.search(r"subscription|gift|donation|parking", name, re.I):
            continue
        desc = clean(ev.get("description") or ev.get("htmlDescription") or "")
        youth = bool(re.search(r"\bRIPYO\b|youth orchestra|music school", name + desc, re.I))
        try:
            insts = get_json(f"{API}/events/{ev['id']}/instances", headers=HDR, timeout=40)
        except Exception as e:  # noqa: BLE001
            log.debug("riphil instances %s: %s", ev.get("id"), e)
            insts = [{"start": ev.get("firstInstanceDateTime"), "id": None}]
        for inst in insts:
            start = inst.get("start") or inst.get("startUtc") or ev.get("firstInstanceDateTime")
            # venue is not in the list payload; infer from the description, default The VETS
            vm = re.search(r"\bat ([A-Z][\w'.&\- ]{3,60}?)(?:[.,\n]|$)", desc)
            venue = SOURCE["venue"]
            if vm and not re.search(r"vets|veterans memorial", vm.group(1), re.I):
                venue = clean(vm.group(1))
            e = make_event(
                source="riphil", title=re.sub(r"^\d{2}/\d{2}\s+", "", name), start=start, url=SOURCE["url"],
                venue=venue, address=SOURCE["address"] if venue == SOURCE["venue"] else "", city=SOURCE["city"] if venue == SOURCE["venue"] else "",
                lat=SOURCE["lat"] if venue == SOURCE["venue"] else None, lon=SOURCE["lon"] if venue == SOURCE["venue"] else None,
                category="classical", description=desc, summary=summarize(desc), image=ev.get("imageUrl") or "",
                ticket_url=ev.get("webUrl") or f"https://boxoffice.riphil.org/riphil/website/EventDetails.aspx?EventId={ev.get('id')}",
                tags=["orchestra"] + (["youth orchestra"] if youth else []),
                extra={"on_sale_now": ev.get("isOnSale")},
            )
            if e:
                e["kids"] = False
                out.append(e)
    return out
