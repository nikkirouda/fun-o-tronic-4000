"""NFL game windows (every game, regular season + playoffs) → site/data/nfl.json, for the 🏈 caution.
Not events: a listing that overlaps a kickoff-to-final window gets a visible reminder, never a block."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from .common import TZ, get_json, log, to_dt

SOURCE = {"name": "NFL schedule (ESPN)", "url": "https://www.espn.com/nfl/schedule"}
API = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
OUT = Path(__file__).resolve().parent.parent / "site" / "data" / "nfl.json"
GAME_HOURS = 3.33


def fetch() -> list[dict]:
    now = datetime.now(TZ)
    year = now.year if now.month >= 8 else now.year - 1  # NFL season year
    games = []
    for seasontype, weeks in ((2, range(1, 19)), (3, range(1, 6))):
        for wk in weeks:
            try:
                d = get_json(API, params={"week": wk, "seasontype": seasontype, "dates": year}, timeout=30)
            except Exception as e:  # noqa: BLE001
                log.debug("nfl wk %s/%s: %s", seasontype, wk, e)
                continue
            for ev in d.get("events", []):
                c = (ev.get("competitions") or [{}])[0]
                st = to_dt(ev.get("date"))
                if not st:
                    continue
                status = ((c.get("status") or {}).get("type") or {}).get("name", "")
                teams = {x.get("homeAway"): (x.get("team") or {}) for x in c.get("competitors", [])}
                home, away = teams.get("home", {}), teams.get("away", {})
                tba = bool((c.get("timeValid") is False) or (st.hour == 0 and st.minute == 0))
                start = st.replace(hour=13, minute=0) if tba else st
                end = (st.replace(hour=23, minute=30) if tba else st + timedelta(hours=GAME_HOURS))
                games.append({
                    "start": start.isoformat(timespec="minutes"), "end": end.isoformat(timespec="minutes"), "tba": tba,
                    "title": ev.get("shortName") or f"{away.get('abbreviation')} @ {home.get('abbreviation')}",
                    "home": home.get("abbreviation"), "away": away.get("abbreviation"),
                    "patriots": "NE" in (home.get("abbreviation"), away.get("abbreviation")),
                    "week": wk, "playoff": seasontype == 3, "label": (d.get("week") or {}).get("text") or (ev.get("name") if seasontype == 3 else ""),
                    "tv": (c.get("broadcast") or ""), "final": status == "STATUS_FINAL",
                })
    games = [g for g in games if not g["final"] and datetime.fromisoformat(g["end"]) > now - timedelta(days=1)]
    games.sort(key=lambda g: g["start"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generated": now.isoformat(timespec="minutes"), "season": year, "games": games}, ensure_ascii=False))
    log.info("nfl: %d upcoming game windows (%d Patriots)", len(games), sum(g["patriots"] for g in games))
    return []
