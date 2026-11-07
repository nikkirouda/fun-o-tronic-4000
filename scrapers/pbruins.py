"""Providence Bruins (AHL) home games via the league's HockeyTech feed (public key)."""
from __future__ import annotations

from .common import get_json, make_event

SOURCE = {"name": "Providence Bruins", "url": "https://www.providencebruins.com", "city": "Providence",
          "venue": "Amica Mutual Pavilion", "address": "1 La Salle Square", "lat": 41.8251, "lon": -71.4179}
URL = ("https://lscluster.hockeytech.com/feed/?feed=modulekit&view=schedule&key=50c2cd9b5e18e390"
       "&fmt=json&client_code=ahl&lang=en&team_id=309")


def fetch() -> list[dict]:
    data = get_json(URL, timeout=40)
    games = data.get("SiteKit", {}).get("Schedule", [])
    out = []
    for g in games:
        if str(g.get("home_team")) != "309" and "Providence" not in (g.get("home_team_name") or ""):
            continue
        if g.get("game_status") and "Final" in g["game_status"]:
            continue
        opp = g.get("visiting_team_name", "")
        ev = make_event(
            source="pbruins", title=f"Providence Bruins vs {opp}", start=g.get("GameDateISO8601") or g.get("date_time_played"),
            url="https://www.providencebruins.com/schedule", venue=g.get("venue_name") or SOURCE["venue"],
            city="Providence", lat=SOURCE["lat"], lon=SOURCE["lon"], category="sports",
            ticket_url="https://am.ticketmaster.com/providence/", tags=["hockey", "ahl", "home game"],
            summary=f"AHL hockey: the P-Bruins host the {opp} at the Amica Mutual Pavilion.", performer=opp,
        )
        if ev:
            ev["kids"] = False
            out.append(ev)
    return out
