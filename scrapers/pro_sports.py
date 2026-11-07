"""Pro sports home games: Bruins, Celtics, Patriots, Revolution (ESPN public schedule JSON), Red Sox and WooSox
(MLB statsapi), Rhode Island FC (ESPN USL). Only home games; distance flags Boston/Worcester as 'worth the drive'."""
from __future__ import annotations

from datetime import date, timedelta

from .common import clean, get_json, log, make_event

SOURCE = {"name": "Pro sports (ESPN / MLB)", "url": ""}
ESPN = "https://site.api.espn.com/apis/site/v2/sports"
TEAMS = [
    {"key": "bruins", "path": "hockey/nhl/teams/bos/schedule", "abbr": "BOS", "name": "Boston Bruins", "sport": "hockey",
     "venue": "TD Garden", "city": "Boston, MA", "address": "100 Legends Way, Boston, MA", "lat": 42.3662, "lon": -71.0621,
     "tickets": "https://www.nhl.com/bruins/tickets"},
    {"key": "celtics", "path": "basketball/nba/teams/bos/schedule", "abbr": "BOS", "name": "Boston Celtics", "sport": "basketball",
     "venue": "TD Garden", "city": "Boston, MA", "address": "100 Legends Way, Boston, MA", "lat": 42.3662, "lon": -71.0621,
     "tickets": "https://www.nba.com/celtics/tickets"},
    {"key": "patriots", "path": "football/nfl/teams/ne/schedule", "abbr": "NE", "name": "New England Patriots", "sport": "football",
     "venue": "Gillette Stadium", "city": "Foxborough, MA", "address": "1 Patriot Pl, Foxborough, MA", "lat": 42.0909, "lon": -71.2643,
     "tickets": "https://www.patriots.com/tickets/"},
    {"key": "revolution", "path": "soccer/usa.1/teams/189/schedule", "abbr": "NE", "name": "New England Revolution", "sport": "soccer",
     "venue": "Gillette Stadium", "city": "Foxborough, MA", "address": "1 Patriot Pl, Foxborough, MA", "lat": 42.0909, "lon": -71.2643,
     "tickets": "https://www.revolutionsoccer.net/tickets"},
    {"key": "rifc", "path": "soccer/usa.usl.1/teams/22164/schedule", "abbr": "RHI", "name": "Rhode Island FC", "sport": "soccer",
     "venue": "Centreville Bank Stadium", "city": "Pawtucket", "address": "30 Tidewater St, Pawtucket", "lat": 41.8755, "lon": -71.3850,
     "tickets": "https://www.rhodeislandfc.com/tickets/"},
]
MLB_TEAMS = [
    {"key": "redsox", "sport_id": 1, "team_id": 111, "name": "Boston Red Sox", "venue": "Fenway Park", "city": "Boston, MA",
     "address": "4 Jersey St, Boston, MA", "lat": 42.3467, "lon": -71.0972, "tickets": "https://www.mlb.com/redsox/tickets"},
    {"key": "woosox", "sport_id": 11, "team_id": 533, "name": "Worcester Red Sox", "venue": "Polar Park", "city": "Worcester, MA",
     "address": "100 Madison St, Worcester, MA", "lat": 42.2553, "lon": -71.7996, "tickets": "https://www.milb.com/worcester/tickets"},
]


def _espn(t: dict) -> list[dict]:
    out = []
    for season_param in ("", "?seasontype=2"):
        try:
            d = get_json(f"{ESPN}/{t['path']}{season_param}", timeout=30)
        except Exception as e:  # noqa: BLE001
            log.info("pro %s: %s", t["key"], e)
            continue
        for ev in d.get("events", []):
            c = (ev.get("competitions") or [{}])[0]
            status = ((c.get("status") or {}).get("type") or {}).get("name", "")
            if status and status != "STATUS_SCHEDULED":
                continue
            home = next((x for x in c.get("competitors", []) if x.get("homeAway") == "home"), {})
            if (home.get("team") or {}).get("abbreviation") != t["abbr"]:
                continue
            away = next((x for x in c.get("competitors", []) if x.get("homeAway") == "away"), {})
            opp = clean((away.get("team") or {}).get("displayName", ""))
            venue = clean((c.get("venue") or {}).get("fullName", "")) or t["venue"]
            tix = c.get("tickets") or []
            price = tix[0].get("startingPrice") if tix else None
            e = make_event(
                source=f"pro:{t['key']}", title=f"{t['name']} vs {opp}", start=ev.get("date"), url=t["tickets"],
                venue=venue, address=t["address"] if venue == t["venue"] else "", city=t["city"],
                lat=t["lat"] if venue == t["venue"] else None, lon=t["lon"] if venue == t["venue"] else None,
                category="sports", tags=[t["sport"], "pro", "home game"], ticket_url=t["tickets"],
                price_min=float(price) if price else None, price_text=f"resale from ${price:g}" if price else "",
                summary=f"{t['name']} host the {opp}" + (f" at {venue}." if venue else "."), performer=opp,
                extra={"espn_id": ev.get("id"), "season_type": (ev.get("seasonType") or {}).get("name")},
            )
            if e and not any(x["id"] == e["id"] for x in out):
                e["kids"] = False
                e["source_name"] = t["name"]
                out.append(e)
        if out:
            break
    return out


def _mlb(t: dict) -> list[dict]:
    today = date.today()
    out = []
    try:
        d = get_json("https://statsapi.mlb.com/api/v1/schedule", params={
            "sportId": t["sport_id"], "teamId": t["team_id"], "startDate": today.isoformat(),
            "endDate": (today + timedelta(days=400)).isoformat(), "hydrate": "venue"}, headers={"Accept": "application/json"}, timeout=40)
    except Exception as e:  # noqa: BLE001
        log.info("mlb %s: %s", t["key"], e)
        return out
    for day in d.get("dates", []):
        for g in day.get("games", []):
            home = (g.get("teams") or {}).get("home") or {}
            if (home.get("team") or {}).get("id") != t["team_id"]:
                continue
            st = (g.get("status") or {}).get("detailedState", "")
            if st and st not in ("Scheduled", "Pre-Game", "Warmup"):
                continue
            opp = clean((((g.get("teams") or {}).get("away") or {}).get("team") or {}).get("name", ""))
            e = make_event(
                source=f"pro:{t['key']}", title=f"{t['name']} vs {opp}", start=g.get("gameDate"), url=t["tickets"],
                venue=clean((g.get("venue") or {}).get("name", "")) or t["venue"], address=t["address"], city=t["city"],
                lat=t["lat"], lon=t["lon"], category="sports", tags=["baseball", "pro" if t["sport_id"] == 1 else "minor league", "home game"],
                ticket_url=t["tickets"], summary=f"{t['name']} host the {opp} at {t['venue']}.", performer=opp,
                all_day=bool((g.get("status") or {}).get("startTimeTBD")),
                extra={"game_pk": g.get("gamePk"), "series": g.get("seriesDescription")},
            )
            if e:
                e["kids"] = False
                e["source_name"] = t["name"]
                out.append(e)
    return out


def fetch() -> list[dict]:
    out = []
    for t in TEAMS:
        evs = _espn(t)
        log.info("pro %s: %d home games", t["key"], len(evs))
        out.extend(evs)
    for t in MLB_TEAMS:
        evs = _mlb(t)
        log.info("mlb %s: %d home games", t["key"], len(evs))
        out.extend(evs)
    return out
