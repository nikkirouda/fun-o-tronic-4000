"""The on-sale watch list (watch.json): reads each page and records what it says about tickets now.

Produces site/data/watch.json (status per item, with the sentence that said so and any date near it)
and returns no events. A status change between builds is recorded in site/data/changes.json by build.py.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from .common import TZ, clean, get, log, to_dt

SOURCE = {"name": "On-sale watch list", "url": ""}
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "data" / "watch.json"

STATUS_RX = [
    ("sold out", re.compile(r"\bsold[ -]out\b", re.I)),
    ("on sale", re.compile(r"\b(tickets? (?:are |is )?(?:now )?on sale(?: now)?|buy tickets|get tickets|purchase tickets|on sale now)\b", re.I)),
    ("presale", re.compile(r"\b(pre-?sale|early access|members? (?:only )?(?:pre)?sale|fan club)\b", re.I)),
    ("announced", re.compile(r"\b(on sale (?:on |starting |begins? |this )?(?:mon|tue|wed|thu|fri|sat|sun|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? ?\d{0,2}|tickets (?:go )?on sale [A-Z][a-z]+ \d{1,2}|lineup announce)", re.I)),
    ("not yet", re.compile(r"\b(not (?:yet )?(?:on sale|available)|coming soon|stay tuned|sign up (?:for|to) (?:be the first|updates|alerts|our (?:news|mailing) ?list)|check back)\b", re.I)),
]
DATE_NEAR_RX = re.compile(r"on sale\b[^.]{0,60}?((?:mon|tue|wed|thu|fri|sat|sun)[a-z]*,?\s+)?((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:,?\s+\d{4})?(?:\s*(?:at|@)\s*\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?)?)", re.I)


def _status(text: str) -> tuple[str, str, str | None]:
    """→ (status, evidence sentence, on_sale date iso or None). Order of precedence: a dated 'on sale <date>' wins."""
    m = DATE_NEAR_RX.search(text)
    on_sale = None
    if m:
        dt = to_dt(m.group(2))
        if dt and dt > datetime.now(TZ):
            on_sale = dt.isoformat(timespec="minutes")
    for status, rx in STATUS_RX:
        mm = rx.search(text)
        if mm:
            i = mm.start()
            sent = text[max(0, text.rfind(".", 0, i) + 1): text.find(".", i) + 1 or None]
            return (status if not on_sale else "announced"), clean(sent)[:220], on_sale
    return "unclear", "", on_sale


def fetch() -> list[dict]:
    cfg = json.loads((ROOT / "watch.json").read_text())
    prev = {}
    if OUT.exists():
        try:
            prev = {w["key"]: w for w in json.loads(OUT.read_text()).get("items", [])}
        except Exception:  # noqa: BLE001
            prev = {}
    now = datetime.now(TZ).isoformat(timespec="minutes")
    items = []
    for it in cfg["items"]:
        rec = {**it, "checked": now, "status": "unreachable", "evidence": "", "on_sale": None,
               "prev_status": prev.get(it["key"], {}).get("status"), "changed": prev.get(it["key"], {}).get("changed")}
        for url in [it["url"], *it.get("alt_urls", [])]:
            try:
                html = get(url, timeout=30).text
            except Exception as e:  # noqa: BLE001
                log.debug("watch %s %s: %s", it["key"], url, e)
                continue
            soup = BeautifulSoup(html, "lxml")
            for s in soup(["script", "style", "noscript"]):
                s.decompose()
            text = clean(soup.get_text(" "))
            status, evidence, on_sale = _status(text)
            # "ALL 2026 TICKETS ARE SOLD OUT" on a page we watch for 2027 means: next year not announced yet
            ty = re.search(r"\b(20\d{2})\b", it["title"])
            ey = re.search(r"\b(20\d{2})\b", evidence)
            if ty and ey and int(ey.group(1)) < int(ty.group(1)) and status in ("sold out", "on sale"):
                status = f"not yet announced ({ey.group(1)} {status})"
            rec.update({"status": status, "evidence": evidence, "on_sale": on_sale, "checked_url": url})
            if status != "unclear":
                break
        if rec["prev_status"] and rec["prev_status"] != rec["status"]:
            rec["changed"] = now
        elif not rec["prev_status"]:
            rec["changed"] = None
        items.append(rec)
        log.info("watch %s: %s — %s", it["key"], rec["status"], rec["evidence"][:80])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generated": now, "items": items}, ensure_ascii=False, indent=1))
    return []
