# Fun-o-tronic 4000

What's on in Providence and across Rhode Island — theater, music, classical, comedy, film, talks,
sports, festivals and more — gathered from the venues themselves into one searchable, filterable,
self-updating page with a calendar view, a map, a subscribable feed and a twice-weekly email digest.

Live (unlisted, `noindex`): https://nikkirouda.github.io/fun-o-tronic-4000/

## How it works

```
scrapers/*.py   one module per source → events in a common schema (scrapers/common.py: make_event)
build.py        runs them all in parallel, dedupes, diffs against the last build, writes site/data/*
site/           static app (vanilla JS, no build step) + feed.ics + PWA manifest
digest.py       composes the Monday "week ahead" / Thursday "weekend" email body from the data
.github/workflows/update.yml   Mon & Thu ~5 AM ET (an hour before each digest), and on every push: build → commit data → deploy
```

A failing source keeps its last good listings and shows up in **Sources & health** on the page footer,
so one dead website never blanks the list.

### Data schema (site/data/events.json)

`id, source, title, start, end, all_day, venue, address, city, lat, lon, category, tags, summary,
description, image, url, ticket_url, price_text, price_min, price_max, is_free, on_sale, sold_out,
kids, performer, first_seen`. Categories: theater, music, classical, dance, comedy, film, talk, sports,
festival, market, art, family, food, community, other.

## Run locally

```
pip install -r requirements.txt
python build.py            # or: python build.py avon odeum   (just those modules)
python -m http.server -d site 8000
python digest.py weekend   # prints the email body
```

## Adding a source

Drop a module in `scrapers/` with `SOURCE = {...}` and `fetch() -> list[dict]` built from
`make_event(...)`. Helpers exist for the common platforms: `tribe_events` (WordPress Events Calendar
REST), `parse_ics`, `jsonld_events` + `event_from_jsonld`, and `get`/`get_json`/`get_soup`.
Platform-specific modules already cover: LiveWhale (Brown), Carbonhouse (PPAC/VETS/Amica/RICC),
PatronManager (Trinity, Gamm), Spektrix (RI Phil), Squarespace collections, Rockhouse/Etix RSS
(Strand, Met, Park), Sanity (Odeum), Sidearm ICS (college sports), HockeyTech (P-Bruins),
CampusLabs Engage (RISD), Shopify (PIG), accesso ShoWare (Narrows), Webflow (Machines with Magnets).
"Worth the drive" venues (TD Garden, Boch Center, Shubert New Haven, Hanover Worcester) are flagged `far` and hidden unless asked for.

Scraping is polite: identified User-Agent, retries with backoff, and feeds (ICS/JSON/RSS) preferred
over HTML wherever a venue offers one. Listings belong to the venues; this is a personal reader.
