"""WordPress 'The Events Calendar' sites, one entry each. Cheap to add: name, base URL, defaults."""
from __future__ import annotations

import re

from .common import guess_category, log, tribe_events

COMMUNITY_KEYS = {"clpvd", "pvdcity"}
SKIP_RX = re.compile(r"\b(meeting|hearing|commission|council|board of|public comment|office hours|passport|tax|voter|registration fair|"
                     r"yoga|aerobics|zumba|fitness|pilates|step class|boot ?camp|drop-in|tutoring|homework|esl|citizenship|"
                     r"notary|blood drive|vaccin|flu shot)\b", re.I)

SOURCE = {"name": "Tribe calendars (libraries, museums, theaters)", "url": ""}

SITES = [
    {"key": "athenaeum", "base": "https://providenceathenaeum.org", "venue": "Providence Athenaeum", "city": "Providence",
     "lat": 41.8262, "lon": -71.4047, "category": "talk", "address": "251 Benefit St"},
    {"key": "clpvd", "base": "https://clpvd.org", "venue": "", "city": "Providence", "category": None},
    {"key": "rwpzoo", "base": "https://www.rwpzoo.org", "venue": "Roger Williams Park Zoo", "city": "Providence",
     "lat": 41.7925, "lon": -71.4165, "category": None, "address": "1000 Elmwood Ave"},
    {"key": "pvdcity", "base": "https://www.providenceri.gov", "venue": "", "city": "Providence", "category": None},
    {"key": "riiff", "base": "https://film-festival.org", "venue": "", "city": "Providence", "category": "film"},
    {"key": "pcff", "base": "https://providencechildrensfilmfestival.org", "venue": "", "city": "Providence", "category": "film"},
    {"key": "rihs", "base": "https://www.rihs.org", "venue": "", "city": "Providence", "category": "talk"},
    {"key": "newporthistory", "base": "https://newporthistory.org", "venue": "", "city": "Newport", "category": "talk"},
    {"key": "rihumanities", "base": "https://rihumanities.org", "venue": "", "city": "Providence", "category": "talk"},
    {"key": "gamm", "base": "https://www.gammtheatre.org", "venue": "The Gamm Theatre", "city": "Warwick",
     "lat": 41.7249, "lon": -71.4459, "category": "theater", "address": "1245 Jefferson Blvd"},
    {"key": "wilbury", "base": "https://www.thewilburygroup.org", "venue": "Wilbury Theatre Group", "city": "Providence",
     "lat": 41.8186, "lon": -71.4259, "category": "theater", "address": "475 Valley St"},
    {"key": "as220", "base": "https://as220.org", "venue": "AS220", "city": "Providence",
     "lat": 41.8232, "lon": -71.4119, "category": None, "address": "115 Empire St"},
    {"key": "firstworks", "base": "https://first-works.org", "venue": "", "city": "Providence", "category": None},
    {"key": "riphil", "base": "https://www.riphil.org", "venue": "The VETS", "city": "Providence",
     "lat": 41.8289, "lon": -71.4099, "category": "classical", "address": "1 Avenue of the Arts"},
    {"key": "communitymusicworks", "base": "https://communitymusicworks.org", "venue": "", "city": "Providence", "category": "classical"},
    {"key": "blackstonerivertheatre", "base": "https://www.riverfolk.org", "venue": "Blackstone River Theatre", "city": "Cumberland",
     "lat": 41.9707, "lon": -71.4007, "category": "music", "address": "549 Broad St"},
    {"key": "commonfence", "base": "https://commonfencemusic.org", "venue": "Common Fence Music", "city": "Portsmouth", "category": "music"},
    {"key": "pumphouse", "base": "https://www.pumphousemusicworks.com", "venue": "Pump House Music Works", "city": "Peace Dale", "category": "music"},
    {"key": "knickerbocker", "base": "https://www.knickmusic.com", "venue": "Knickerbocker Music Center", "city": "Westerly",
     "lat": 41.3773, "lon": -71.8290, "category": "music", "address": "35 Railroad Ave"},
    {"key": "unitedtheatre", "base": "https://unitedtheatre.org", "venue": "United Theatre", "city": "Westerly", "category": None},
    {"key": "odeum", "base": "https://www.greenwichodeum.com", "venue": "Greenwich Odeum", "city": "East Greenwich",
     "lat": 41.6603, "lon": -71.4531, "category": "music", "address": "59 Main St"},
    {"key": "stadium", "base": "https://www.stadiumtheatre.com", "venue": "Stadium Theatre", "city": "Woonsocket",
     "lat": 42.0028, "lon": -71.5148, "category": None, "address": "28 Monument Sq"},
    {"key": "contemporarytheater", "base": "https://www.contemporarytheatercompany.com", "venue": "The Contemporary Theater Company",
     "city": "Wakefield", "category": "theater"},
    {"key": "burbage", "base": "https://www.burbagetheatre.org", "venue": "Burbage Theatre Co", "city": "Pawtucket", "category": "theater"},
    {"key": "festivalballet", "base": "https://www.festivalballetprovidence.org", "venue": "", "city": "Providence", "category": "dance"},
    {"key": "newportclassical", "base": "https://www.newportclassical.org", "venue": "", "city": "Newport", "category": "classical"},
    {"key": "narrows", "base": "https://narrowscenter.org", "venue": "Narrows Center for the Arts", "city": "Fall River",
     "lat": 41.7027, "lon": -71.1612, "category": "music", "address": "16 Anawan St"},
    {"key": "newportartmuseum", "base": "https://newportartmuseum.org", "venue": "Newport Art Museum", "city": "Newport", "category": "art"},
    {"key": "pps", "base": "https://ppsri.org", "venue": "", "city": "Providence", "category": "talk"},
    {"key": "hanover", "base": "https://thehanovertheatre.org", "venue": "The Hanover Theatre", "city": "Worcester, MA",
     "lat": 42.2615, "lon": -71.8012, "category": None, "address": "2 Southbridge St, Worcester, MA", "force_venue": True},
    {"key": "bowenswharf", "base": "https://bowenswharf.com", "venue": "Bowen's Wharf", "city": "Newport", "category": "festival"},
]


def fetch() -> list[dict]:
    out: list[dict] = []
    for s in SITES:
        try:
            evs = tribe_events(s["base"], source=f"tribe:{s['key']}", venue=s.get("venue", ""), city=s.get("city", ""),
                               category=s.get("category"))
        except Exception as e:  # noqa: BLE001
            log.info("tribe %s: no feed (%s)", s["key"], str(e)[:90])
            continue
        if s["key"] in COMMUNITY_KEYS:
            kept = []
            for e in evs:
                if SKIP_RX.search(e["title"]):
                    continue
                e["category"] = guess_category(e["title"], " ".join(e.get("tags", [])), default="community")
                kept.append(e)
            evs = kept
        for e in evs:
            if s.get("force_venue"):
                room = e.get("venue") or ""
                e["venue"] = s["venue"] if not room or room == s["venue"] else f"{s['venue']} — {room}"
                e["city"] = s.get("city", e.get("city", ""))
            if e.get("lat") is None and s.get("lat") is not None:
                e["lat"], e["lon"] = s["lat"], s["lon"]
            if not e.get("address") and s.get("address"):
                e["address"] = s["address"]
            e["source"] = f"tribe:{s['key']}"
            e["source_name"] = s.get("venue") or s["base"].split("//")[1]
            e["source_url"] = s["base"]
        log.info("tribe %s: %d", s["key"], len(evs))
        out.extend(evs)
    return out
