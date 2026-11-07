/* Fun-o-tronic 4000 — front end. Vanilla JS, no build step. Reads data/*.json produced by build.py.
   Everything personal (stars, taste, follows, hidden things) lives in this browser's localStorage only. */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const TZ = "America/New_York";
  const REPO = "https://github.com/nikkirouda/fun-o-tronic-4000";

  const CATS = {
    theater: "Theater", music: "Music", classical: "Classical", dance: "Dance", comedy: "Comedy",
    film: "Film", talk: "Talks", sports: "Sports", festival: "Festivals", market: "Markets",
    art: "Art", food: "Food & drink", family: "Family", community: "Community", other: "Other",
  };
  const AREAS = {
    metro: ["providence", "pawtucket", "cranston", "east providence", "warwick", "north providence", "johnston", "central falls", "lincoln", "smithfield", "seekonk", "attleboro", "barrington", "riverside", "rumford"],
    newport: ["newport", "middletown", "portsmouth", "jamestown", "tiverton", "bristol", "warren", "little compton"],
    south: ["westerly", "wakefield", "south kingstown", "narragansett", "kingston", "peace dale", "matunuck", "charlestown", "north kingstown", "east greenwich", "west greenwich", "exeter", "richmond", "hopkinton", "block island", "new shoreham", "west kingston"],
    north: ["woonsocket", "cumberland", "lincoln", "north smithfield", "burrillville", "glocester", "scituate", "foster", "smithfield", "pawtucket", "central falls"],
  };
  const HILL_VENUE_RX = /brown|risd|athenaeum|avon|lindemann|granoff|sayles|salomon|alumnae|john carter|list art|stuart theatre|leeds|pembroke|wriston|books on the square|hope street|thayer|wickenden|riffraff|fox point|cable car|first unitarian|providence public library|east side|wayland|pizzitola|meehan|stevenson|hillel|churchill house|manning chapel/i;
  const OUTDOOR_RX = /field|stadium|park\b|waterfire|bold point|fort adams|wharf|green\b|common\b|plaza|farm|market|beach|trail|hike|parade|fireworks|polo|race|5k|marathon/i;
  const PREMIER_RX = /trinity|ppac|gamm|vets|philharmonic|firstworks|amica|strand|odeum|stadium theatre|comedy connection|avon|athenaeum|risd museum|newport classical|wilbury|columbus/i;
  const BIG_RX = /amica|strand|vets|ppac|stadium|pavilion|bold point|comic con|festival|arena|garden/i;
  const RANK_W = { theater: 5, classical: 5, comedy: 4.5, music: 4, film: 3.5, dance: 4, festival: 4, talk: 2.5, art: 2.5, sports: 2, food: 2, market: 1.5, community: 0.5, family: 0.5, other: 0.5 };
  // the mood dial tilts these: quiet (0) favours the first set, big (100) the second
  const QUIET = { talk: 2, film: 2, classical: 2, art: 1.5, community: 1 }, BIG = { music: 2, comedy: 1.5, festival: 2, sports: 1.5, dance: 0.5 };

  // ------------------------------------------------------------- state ---
  const LS = (k, d) => { try { const v = localStorage.getItem("fot." + k); return v == null ? d : JSON.parse(v); } catch { return d; } };
  const save = (k, v) => { try { localStorage.setItem("fot." + k, JSON.stringify(v)); } catch { /* private mode */ } };
  const S = {
    events: [], venues: [], meta: null, changes: null, notes: {},
    when: "weekend", from: null, to: null, cats: new Set(), q: "",
    freeOnly: false, hideKids: true, ticketsOnly: false, farToo: false, maxPrice: null, area: "", venue: "",
    view: "list", sort: "time", shown: 60, calMonth: null, calSel: null, mood: 50, group: true,
    stars: new Set(LS("stars", [])), hidden: new Set(LS("hidden", [])), hiddenVenues: new Set(LS("hiddenVenues", [])),
    follows: LS("follows", []), taste: LS("taste", { cat: {}, venue: {}, tag: {}, source: {}, n: 0 }),
    votes: LS("votes", {}), lastVisit: LS("lastVisit", null), mode: "browse", // browse | stars | new | shortlist
    shortlist: null, shortlistFrom: "",
  };
  Object.assign(S, LS("filters", {}));
  if (Array.isArray(S.cats)) S.cats = new Set(S.cats);
  if (LS("theme", null)) document.documentElement.dataset.theme = LS("theme", null);
  function persist() {
    save("filters", { when: S.when, hideKids: S.hideKids, area: S.area, view: S.view, sort: S.sort, freeOnly: S.freeOnly, ticketsOnly: S.ticketsOnly, farToo: S.farToo, maxPrice: S.maxPrice, mood: S.mood, group: S.group, cats: [...S.cats] });
    save("stars", [...S.stars]); save("hidden", [...S.hidden]); save("hiddenVenues", [...S.hiddenVenues]);
    save("follows", S.follows); save("taste", S.taste); save("votes", S.votes);
  }

  // -------------------------------------------------------------- dates ---
  const fmt = (d, o) => new Intl.DateTimeFormat("en-US", { timeZone: TZ, ...o }).format(d);
  const dayKey = d => fmt(d, { year: "numeric", month: "2-digit", day: "2-digit" }).replace(/(\d+)\/(\d+)\/(\d+)/, "$3-$1-$2");
  const todayKey = () => dayKey(new Date());
  function addDays(key, n) { const [y, m, d] = key.split("-").map(Number); return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10); }
  function dow(key) { const [y, m, d] = key.split("-").map(Number); return new Date(Date.UTC(y, m - 1, d)).getUTCDay(); }
  function range() {
    const t = todayKey();
    switch (S.when) {
      case "tonight": return [t, t];
      case "tomorrow": { const n = addDays(t, 1); return [n, n]; }
      case "weekend": { const w = dow(t); let fri = addDays(t, (5 - w + 7) % 7); if (w === 6 || w === 0) fri = t; return [fri, addDays(fri, w === 0 ? 0 : (w === 6 ? 1 : 2))]; }
      case "week": return [t, addDays(t, 6)];
      case "month": return [t, addDays(t, 29)];
      case "custom": return [S.from || t, S.to || addDays(t, 30)];
      default: return [t, "9999-12-31"];
    }
  }
  function timeStr(e) {
    if (e.all_day) return "All day";
    return fmt(new Date(e.start), { hour: "numeric", minute: "2-digit" }).replace(":00", "").replace(" ", "").toLowerCase();
  }
  function dayLabel(key) {
    const t = todayKey();
    const [y, m, d] = key.split("-").map(Number); const dt = new Date(Date.UTC(y, m - 1, d, 17));
    const base = fmt(dt, { weekday: "long", month: "long", day: "numeric" });
    if (key === t) return ["Today", base];
    if (key === addDays(t, 1)) return ["Tomorrow", base];
    return [fmt(dt, { weekday: "long" }), fmt(dt, { month: "long", day: "numeric" })];
  }
  const hoursAgo = iso => Math.round((Date.now() - new Date(iso)) / 36e5);
  const hourOf = e => Number(fmt(new Date(e.start), { hour: "numeric", hour12: false }));
  function soonLabel(e) {  // "in 40m", "now", "ended" — only for today
    if (e._day !== todayKey() || e.all_day) return "";
    const m = Math.round((e._t - Date.now()) / 6e4);
    const end = e.end ? new Date(e.end).getTime() : e._t + 2 * 36e5;
    if (m > 180) return "";
    if (m > 0) return m >= 60 ? `in ${Math.floor(m / 60)}h ${m % 60}m` : `in ${m}m`;
    if (Date.now() < end) return "started";
    return "ended";
  }

  // -------------------------------------------------------------- data ---
  async function load() {
    const bust = `?v=${Math.floor(Date.now() / 6e5)}`;
    const j = (f, d) => fetch(`data/${f}${bust}`).then(r => r.json()).catch(() => d);
    const [ev, meta, venues, changes, notes, watch] = await Promise.all([j("events.json", { events: [], count: 0, generated: new Date().toISOString() }), j("meta.json", null), j("venues.json", []), j("changes.json", { items: [] }), j("venue_notes.json", {}), j("watch.json", { items: [] })]);
    S.watch = watch.items || [];
    S.events = ev.events.map(e => ({ ...e, _day: dayKey(new Date(e.start)), _t: new Date(e.start).getTime(),
      _hay: `${e.title} ${e.venue} ${e.city} ${e.performer} ${e.tags.join(" ")} ${e.summary} ${CATS[e.category] || ""}`.toLowerCase() }));
    S.meta = meta; S.venues = venues; S.changes = changes; S.notes = notes;
    const h = hoursAgo(ev.generated);
    $("#statusText").textContent = `${ev.count.toLocaleString()} events · updated ${h < 1 ? "just now" : h < 48 ? h + "h ago" : Math.round(h / 24) + "d ago"}`;
    $("#led").className = "led" + (h > 8 * 24 ? " bad" : h > 4 * 24 ? " warn" : "");  // listings refresh Mon & Thu
    $("#srcCount").textContent = meta ? Object.keys(meta.sources).length : 0;
    buildCatChips(); buildVenueSel();
    const since = S.lastVisit ? (S.lastVisit > new Date(Date.now() - 14 * 864e5).toISOString() ? S.lastVisit : new Date(Date.now() - 14 * 864e5).toISOString()) : "9999";
    S.newIds = new Set(S.events.filter(e => e.first_seen && e.first_seen > since).map(e => e.id));
    S.followIds = new Set(S.events.filter(isFollowed).map(e => e.id));
    const nb = $("#newCount"); const n = new Set([...S.newIds, ...S.followIds]).size; nb.textContent = n; nb.hidden = n === 0;
    readHash();
    const qp = new URLSearchParams(location.search).get("q"); if (qp) { S.q = qp; S.when = "all"; S.mode = "browse"; $("#q").value = qp; syncWhen(); }
    render();
    loadWeather().then(() => { if (S.view === "list") render(); });
  }
  function buildCatChips() {
    const counts = {};
    for (const e of S.events) counts[e.category] = (counts[e.category] || 0) + 1;
    const wrap = $("#catChips"); wrap.innerHTML = "";
    for (const [k, label] of Object.entries(CATS)) {
      if (!counts[k]) continue;
      const b = document.createElement("button");
      b.dataset.cat = k; b.style.setProperty("--cc", `var(--c-${k})`);
      b.innerHTML = `<span class="dot"></span>${label} <span class="n">${counts[k]}</span>`;
      b.classList.toggle("on", S.cats.has(k));
      b.onclick = () => { S.cats.has(k) ? S.cats.delete(k) : S.cats.add(k); b.classList.toggle("on"); S.shown = 60; persist(); render(); };
      wrap.appendChild(b);
    }
  }
  function buildVenueSel() {
    const sel = $("#venueSel");
    sel.innerHTML = `<option value="">Any venue</option>` + S.venues.filter(v => v.count >= 2 && !S.hiddenVenues.has(v.id)).map(v => `<option value="${v.id}">${esc(v.name)} (${v.count})</option>`).join("");
    sel.value = S.venue;
  }

  // ---------------------------------------------------------- weather ---
  let WX = LS("wx", null);
  async function loadWeather() {
    if (WX && Date.now() - WX.at < 3 * 36e5) return;
    try {
      const pt = await fetch("https://api.weather.gov/points/41.8268,-71.4025").then(r => r.json());
      const fc = await fetch(pt.properties.forecast).then(r => r.json());
      const days = {};
      for (const p of fc.properties.periods) {
        const k = p.startTime.slice(0, 10);
        const d = days[k] ||= { hi: null, lo: null, pop: 0, icon: "", short: "" };
        if (p.isDaytime) { d.hi = p.temperature; d.short = p.shortForecast; d.icon = wxIcon(p.shortForecast); } else d.lo = p.temperature;
        d.pop = Math.max(d.pop, (p.probabilityOfPrecipitation || {}).value || 0);
        if (!d.short) { d.short = p.shortForecast; d.icon = wxIcon(p.shortForecast); }
      }
      WX = { at: Date.now(), days }; save("wx", WX);
    } catch { /* offline or blocked: no badges */ }
  }
  const wxIcon = s => /thunder/i.test(s) ? "⛈" : /snow|flurr/i.test(s) ? "🌨" : /rain|shower|drizzle/i.test(s) ? "🌧" : /cloud|overcast|fog/i.test(s) ? "☁️" : /sunny|clear/i.test(s) ? "☀️" : "🌤";
  function wxBadge(e) {
    const indoors = /center|centre|hall|library|auditorium|theat|arena|pavilion|museum|church|chapel|club|room|gallery|cinema|school/i.test(e.venue);
    if (!WX || indoors || !(OUTDOOR_RX.test(`${e.venue} ${e.title} ${e.tags.join(" ")}`) || e.category === "market")) return "";
    const d = WX.days[e._day]; if (!d) return "";
    const hour = hourOf(e); const temp = (hour >= 18 || hour < 6) && d.lo != null ? d.lo : d.hi;
    return `<span class="flag wx" title="${esc(d.short)}">${d.icon} ${temp != null ? temp + "°" : ""}${d.pop >= 30 ? " " + d.pop + "%" : ""}</span>`;
  }

  // ------------------------------------------------------- taste & rank ---
  function learn(e, w) {  // w > 0 liked, w < 0 disliked
    const T = S.taste; T.n = (T.n || 0) + 1;
    const bump = (m, k, x) => { if (k) m[k] = Math.max(-20, Math.min(40, (m[k] || 0) + x)); };
    bump(T.cat, e.category, w); bump(T.venue, e.venue_id || e.venue, w); bump(T.source, e.source, w / 2);
    for (const t of e.tags.slice(0, 6)) bump(T.tag, t, w / 2);
    persist();
  }
  function taste(e) {
    const T = S.taste; if (!T.n) return 0;
    let s = (T.cat[e.category] || 0) + (T.venue[e.venue_id || e.venue] || 0) * 1.2 + (T.source[e.source] || 0) * .5;
    for (const t of e.tags.slice(0, 6)) s += (T.tag[t] || 0) * .4;
    return Math.max(-6, Math.min(6, s / 4));  // bounded so it tilts rather than dictates
  }
  function isFollowed(e) {
    if (!S.follows.length) return false;
    const hay = `${e.title} ${e.performer} ${e.venue} ${e.tags.join(" ")}`.toLowerCase();
    return S.follows.some(f => hay.includes(f.toLowerCase()));
  }
  function rank(e) {
    let r = RANK_W[e.category] ?? 1;
    const m = (S.mood - 50) / 50;  // -1 quiet … +1 big
    if (m < 0) r += (QUIET[e.category] || 0) * -m + (e.is_free ? .5 * -m : 0) - (BIG_RX.test(e.venue + " " + e.title) ? 1.5 * -m : 0);
    if (m > 0) r += (BIG[e.category] || 0) * m + (BIG_RX.test(e.venue + " " + e.title) ? 2 * m : 0) - (e.category === "talk" || e.category === "community" ? 1.5 * m : 0);
    if (e.sold_out) r -= 4;
    if (PREMIER_RX.test(`${e.venue} ${e.source_name || ""}`)) r += 2;
    if (e.ticket_url) r += .5;
    if (e.description && e.description.length > 120) r += .5;
    if (e.far) r -= 1.5;
    if (S.stars.has(e.id)) r += 10;
    if (S.followIds && S.followIds.has(e.id)) r += 5;
    return r + taste(e);
  }

  // ------------------------------------------------------------ filter ---
  function inArea(e) {
    if (!S.area) return true;
    const city = (e.city || "").toLowerCase();
    if (S.area === "hill") return city.includes("providence") && HILL_VENUE_RX.test(`${e.venue} ${e.address}`);
    if (S.area === "pvd") return city === "providence" || city === "";
    return AREAS[S.area].some(c => city === c || city.startsWith(c));
  }
  function matches(e, ignoreWhen = false) {
    if (S.mode === "shortlist") return S.shortlist && S.shortlist.has(e.id);
    if (S.hidden.has(e.id) || S.hiddenVenues.has(e.venue_id)) return false;
    if (S.mode === "stars") return S.stars.has(e.id);
    if (S.mode === "new" && !(S.newIds.has(e.id) || S.followIds.has(e.id))) return false;
    if (!ignoreWhen && S.mode === "browse") { const [a, b] = range(); if (e._day < a || e._day > b) return false; }
    if (S.dateNight) { const h = hourOf(e); if (e.all_day || h < 17 || h > 22) return false; }
    if (S.cats.size && !S.cats.has(e.category)) return false;
    if (S.hideKids && e.kids && !S.cats.has("family")) return false;
    if (S.freeOnly && !e.is_free) return false;
    if (S.ticketsOnly && !e.ticket_url) return false;
    if (e.far && !S.farToo && S.mode === "browse") return false;
    if (S.maxPrice != null && S.maxPrice !== "" && e.price_min != null && e.price_min > S.maxPrice) return false;
    if (S.venue && e.venue_id !== S.venue) return false;
    if (!inArea(e)) return false;
    if (S.q) { const terms = S.q.toLowerCase().split(/\s+/).filter(Boolean); if (!terms.every(t => e._hay.includes(t))) return false; }
    return true;
  }
  function sorted(list) {
    const l = [...list];
    if (S.sort === "you") l.sort((a, b) => rank(b) - rank(a) || a._t - b._t);
    else if (S.sort === "new") l.sort((a, b) => (b.first_seen || "").localeCompare(a.first_seen || "") || a._t - b._t);
    else if (S.sort === "price") l.sort((a, b) => (a.price_min ?? 1e9) - (b.price_min ?? 1e9) || a._t - b._t);
    else if (S.sort === "az") l.sort((a, b) => a.title.localeCompare(b.title));
    else l.sort((a, b) => a._t - b._t);
    return l;
  }
  // productions: same title + venue, 3+ performances over 2+ days → one card
  const runKey = e => `${e.title.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()}|${e.venue_id || e.venue}`;
  function groupRuns(list) {
    if (!S.group) return list.map(e => ({ e, perfs: [e] }));
    const by = new Map();
    for (const e of list) (by.get(runKey(e)) || by.set(runKey(e), []).get(runKey(e))).push(e);
    const out = [];
    for (const g of by.values()) {
      const days = new Set(g.map(e => e._day));
      if (g.length >= 3 && days.size >= 2) { g.sort((a, b) => a._t - b._t); out.push({ e: g[0], perfs: g }); }
      else for (const e of g) out.push({ e, perfs: [e] });
    }
    return out;
  }

  // ------------------------------------------------------------ render ---
  function render() {
    $$(".view").forEach(v => v.hidden = true);
    $$(".seg button").forEach(b => b.classList.toggle("on", b.dataset.view === S.view));
    $("#btnStars").classList.toggle("lit", S.mode === "stars");
    $("#btnNew").classList.toggle("lit", S.mode === "new");
    $("#btnDate").classList.toggle("lit", !!S.dateNight);
    const sc = $("#starCount"); sc.textContent = S.stars.size; sc.hidden = !S.stars.size;
    const list = sorted(S.events.filter(e => matches(e, S.view === "cal")));
    if (S.view === "list") { $("#listView").hidden = false; renderList(list); }
    else if (S.view === "cal") { $("#calView").hidden = false; renderCal(list); }
    else { $("#mapView").hidden = false; renderMap(list); }
    const label = S.mode === "stars" ? "saved" : S.mode === "new" ? "new or followed" : S.mode === "shortlist" ? "on the shortlist" : S.view === "cal" ? "upcoming" : ({ tonight: "today", tomorrow: "tomorrow", weekend: "this weekend", week: "in the next 7 days", month: "in the next 30 days", all: "upcoming", custom: "in your dates" })[S.when];
    $("#count").textContent = `${list.length} ${label}${S.dateNight ? " · date night" : ""}`;
  }

  function card(e, perfs = [e]) {
    const n = $("#tplCard").content.firstElementChild.cloneNode(true);
    n.style.setProperty("--cc", `var(--c-${e.category})`);
    n.dataset.id = e.id;
    $(".t", n).textContent = timeStr(e);
    $(".d", n).textContent = fmt(new Date(e.start), matchMedia("(min-width: 720px)").matches ? { weekday: "short", month: "short", day: "numeric" } : { month: "short", day: "numeric" });
    const soon = soonLabel(e); $(".soon", n).textContent = soon; if (soon === "ended") n.classList.add("ended"); if (soon === "started" || soon.startsWith("in")) n.classList.add("soon");
    $(".cat", n).textContent = CATS[e.category] || e.category;
    $(".flags", n).innerHTML = flags(e);
    $(".title", n).textContent = e.title;
    $(".where", n).textContent = [e.venue, e.city].filter(Boolean).join(" · ") + (e.price_text || e.price_min != null ? ` · ${priceStr(e)}` : "") + (e.far && e.miles ? ` · ${Math.round(e.miles)} mi` : "");
    $(".sum", n).textContent = e.summary || "";
    if (perfs.length > 1) { const last = perfs[perfs.length - 1]; $(".run", n).textContent = `Runs through ${fmt(new Date(last.start), { month: "short", day: "numeric" })} · ${perfs.length} performances`; }
    const st = $(".star", n); st.textContent = S.stars.has(e.id) ? "★" : "☆"; st.classList.toggle("on", S.stars.has(e.id));
    st.onclick = ev => { ev.stopPropagation(); toggleStar(e); st.textContent = S.stars.has(e.id) ? "★" : "☆"; st.classList.toggle("on", S.stars.has(e.id)); };
    $(".nope", n).onclick = ev => { ev.stopPropagation(); nope(e, perfs); };
    n.onclick = () => openSheet(e, null, perfs); n.onkeydown = ev => { if (ev.key === "Enter") openSheet(e, null, perfs); };
    return n;
  }
  function flags(e) {
    const f = [];
    if (e.is_free) f.push(`<span class="flag free">FREE</span>`);
    if (S.newIds && S.newIds.has(e.id)) f.push(`<span class="flag new">NEW</span>`);
    if (S.followIds && S.followIds.has(e.id)) f.push(`<span class="flag follow">✦ FOLLOWING</span>`);
    if (e.on_sale && new Date(e.on_sale) > new Date()) f.push(`<span class="flag sale">ON SALE ${fmt(new Date(e.on_sale), { month: "short", day: "numeric" })}</span>`);
    if (e.sold_out) f.push(`<span class="flag soldout">SOLD OUT</span>`);
    if (e.kids) f.push(`<span class="flag">KIDS</span>`);
    if (e.far) f.push(`<span class="flag">WORTH THE DRIVE</span>`);
    if (S.votes[e.id]) f.push(`<span class="flag vote">👍 ${esc(S.votes[e.id])}</span>`);
    f.push(wxBadge(e));
    return f.join("");
  }
  function priceStr(e) {
    if (e.is_free && !(e.price_max > 0)) return "Free";
    if (e.price_min != null && e.price_max != null && e.price_max !== e.price_min) return `$${trim(e.price_min)}–$${trim(e.price_max)}`;
    if (e.price_min != null) return `$${trim(e.price_min)}`;
    return e.price_text || "";
  }
  const trim = n => (Math.round(n * 100) / 100).toString().replace(/\.00$/, "");

  function renderList(list) {
    const root = $("#listView"); root.innerHTML = "";
    if (!list.length) {
      root.innerHTML = `<div class="empty"><h3>${S.mode === "stars" ? "Nothing saved yet" : S.mode === "new" ? "Nothing new, nothing followed" : "Nothing here"}</h3><p>${S.mode === "stars" ? "Tap ☆ on anything that looks like fun." : S.mode === "new" ? "Follow a venue, artist or word under ⋯ and it will show up here." : "Try a wider date range, fewer categories, or clear the search."}</p>${S.mode === "browse" ? `<button class="more" id="widen">Show the next 30 days instead</button>` : ""}</div>`;
      const w = $("#widen"); if (w) w.onclick = () => setWhen("month");
      return;
    }
    if (S.mode === "stars" && S.stars.size) {
      const bar = document.createElement("div"); bar.className = "listbar";
      bar.innerHTML = `<button class="btn" id="sendList">↗ Send this shortlist to Ms Belleville</button><span class="fine">She gets a link, thumbs-up what she likes, sends it back; her 👍 then show here.</span>`;
      root.appendChild(bar); $("#sendList").onclick = sendShortlist;
    }
    if (S.mode === "new") root.appendChild(ticketsBlock());
    if (S.mode === "shortlist") {
      const bar = document.createElement("div"); bar.className = "listbar";
      bar.innerHTML = `<b>${esc(S.shortlistFrom || "A")} shortlist</b> — tap 👍 on what appeals, then <button class="btn" id="sendVotes">↗ Send back</button> <button class="linkish" id="leaveList">leave</button>`;
      root.appendChild(bar); $("#sendVotes").onclick = sendVotes; $("#leaveList").onclick = () => { S.mode = "browse"; S.shortlist = null; location.hash = ""; render(); };
    }
    const items = (S.sort === "time" ? groupRuns(list) : list.map(e => ({ e, perfs: [e] })));
    if (S.sort === "time") items.sort((a, b) => (a.e._day === todayKey() && soonLabel(a.e) === "ended") - (b.e._day === todayKey() && soonLabel(b.e) === "ended") || a.e._t - b.e._t);
    const slice = items.slice(0, S.shown);
    let day = null, grid = null;
    for (const { e, perfs } of slice) {
      if (S.sort === "time" && e._day !== day) {
        day = e._day; const [a, b] = dayLabel(day);
        const h = document.createElement("div"); h.className = "day-head" + (day === todayKey() ? " today" : "");
        h.innerHTML = `${esc(a)} <small>${esc(b)}${WX && WX.days[day] && (WX.days[day].hi ?? WX.days[day].lo) != null ? ` · ${WX.days[day].icon} ${WX.days[day].hi ?? WX.days[day].lo}°` : ""}</small>`; root.appendChild(h);
        grid = document.createElement("div"); grid.className = "cards-grid"; root.appendChild(grid);
      } else if (S.sort !== "time" && !grid) { grid = document.createElement("div"); grid.className = "cards-grid"; root.appendChild(grid); }
      const c = card(e, perfs);
      if (S.mode === "shortlist") { const v = document.createElement("button"); v.className = "thumb" + (S.myVotes && S.myVotes.has(e.id) ? " on" : ""); v.textContent = "👍"; v.onclick = ev => { ev.stopPropagation(); S.myVotes ||= new Set(); S.myVotes.has(e.id) ? S.myVotes.delete(e.id) : S.myVotes.add(e.id); v.classList.toggle("on"); }; $(".side", c).prepend(v); }
      grid.appendChild(c);
    }
    if (items.length > S.shown) {
      const b = document.createElement("button"); b.className = "more"; b.textContent = `Show ${Math.min(60, items.length - S.shown)} more of ${items.length}`;
      b.onclick = () => { S.shown += 60; renderList(list); }; root.appendChild(b);
    }
  }

  function ticketsBlock() {
    const now = Date.now();
    const soon = S.events.filter(e => e.on_sale && new Date(e.on_sale) > now && !S.hidden.has(e.id)).sort((a, b) => a.on_sale.localeCompare(b.on_sale)).slice(0, 12);
    const pre = S.events.filter(e => e.tags.includes("presale") && e._t > now && !S.hidden.has(e.id)).slice(0, 8);
    const changed = (S.changes.items || []).filter(c => c.kind === "watch").slice(-6).reverse();
    const hot = (S.watch || []).filter(w => w.hot);
    const box = document.createElement("div"); box.className = "tickets";
    if (!soon.length && !pre.length && !changed.length && !hot.length) return box;
    box.innerHTML = `<h3>🎟 Tickets — on sale, presales, the watch list</h3><ul>` +
      changed.map(c => `<li><b class="chg">Changed:</b> <a href="${esc(c.url || "#")}" target="_blank" rel="noopener">${esc(c.title)}</a> is now <b>${esc(c.status)}</b> (was ${esc(c.prev || "?")})</li>`).join("") +
      soon.map(e => `<li>🕗 <b>${fmt(new Date(e.on_sale), { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</b> — <a href="#" data-id="${e.id}">${esc(e.title)}</a> <span class="fine">${esc(e.venue)} · ${fmt(new Date(e.start), { month: "short", day: "numeric" })}</span></li>`).join("") +
      pre.map(e => `<li>🔑 presale mentioned — <a href="#" data-id="${e.id}">${esc(e.title)}</a> <span class="fine">${esc(e.venue)} · ${fmt(new Date(e.start), { month: "short", day: "numeric" })}</span></li>`).join("") +
      hot.map(w => `<li>👀 <a href="${esc(w.url)}" target="_blank" rel="noopener">${esc(w.title)}</a>: <b>${esc(w.status)}</b>${w.evidence ? ` <span class="fine">— ${esc(w.evidence.slice(0, 100))}</span>` : ""}${w.checked ? ` <span class="fine">(checked ${fmt(new Date(w.checked), { month: "short", day: "numeric" })})</span>` : ""}</li>`).join("") + `</ul>`;
    $$("a[data-id]", box).forEach(a => a.onclick = ev => { ev.preventDefault(); openSheet(S.events.find(e => e.id === a.dataset.id)); });
    return box;
  }

  // ---------------------------------------------------------- calendar ---
  function renderCal(list) {
    const t = todayKey();
    const wide = matchMedia("(min-width: 720px)").matches;
    if (!S.calMonth) S.calMonth = t.slice(0, 7);
    const [y, m] = S.calMonth.split("-").map(Number);
    $("#calTitle").textContent = fmt(new Date(Date.UTC(y, m - 1, 1, 17)), { month: "long", year: "numeric" });
    const byDay = {};
    for (const e of list) (byDay[e._day] ||= []).push(e);
    const grid = $("#calGrid"); grid.innerHTML = "";
    for (const d of ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]) { const x = document.createElement("div"); x.className = "dow"; x.textContent = d; grid.appendChild(x); }
    const first = `${S.calMonth}-01`; const pad = dow(first);
    for (let i = 0; i < pad; i++) { const x = document.createElement("div"); x.className = "cal-cell pad"; grid.appendChild(x); }
    const days = new Date(y, m, 0).getDate();
    const max = Math.max(1, ...Object.values(byDay).map(a => a.length));
    for (let d = 1; d <= days; d++) {
      const key = `${S.calMonth}-${String(d).padStart(2, "0")}`;
      const evs = byDay[key] || [];
      const c = document.createElement("div");
      c.className = "cal-cell" + (key === t ? " today" : "") + (key === S.calSel ? " sel" : "");
      const cats = [...new Set(evs.map(e => e.category))].slice(0, 8);
      let top = [];
      if (wide) {
        const byTitle = new Map();
        for (const e of [...evs].sort((a, b) => a._t - b._t)) { const k = e.title.toLowerCase(); (byTitle.get(k) || byTitle.set(k, []).get(k)).push(e); }
        const venues = new Map();
        for (const g of [...byTitle.values()].sort((a, b) => rank(b[0]) - rank(a[0]))) {
          if (g[0].sold_out && byTitle.size > 6) continue;
          const v = g[0].venue_id || g[0].venue; if ((venues.get(v) || 0) >= 1 && byTitle.size > 6) continue;
          venues.set(v, (venues.get(v) || 0) + 1); top.push(g); if (top.length >= 6) break;
        }
      }
      const shown = top.reduce((n, g) => n + g.length, 0);
      c.innerHTML = `<span class="n">${d}${WX && WX.days[key] && wide ? ` <small class="wxd">${WX.days[key].icon}${WX.days[key].hi ?? ""}°</small>` : ""}</span>` +
        (wide ? `<span class="evs">${top.map(g => { const e = g[0]; const times = e.all_day ? "" : g.slice(0, 3).map(timeStr).join(" & ") + (g.length > 3 ? " +" : ""); return `<a class="ev" data-id="${e.id}" style="--cc:var(--c-${e.category})" title="${esc(e.title)} · ${esc(e.venue)}${times ? " · " + times : ""}">${times ? `<b>${times}</b> ` : ""}${esc(e.title)}</a>`; }).join("")}${evs.length > shown ? `<span class="morel">+${evs.length - shown} more</span>` : ""}</span>`
              : `<span class="dots">${cats.map(k => `<i style="background:var(--c-${k})"></i>`).join("")}</span>`) +
        (evs.length ? `<span class="cnt">${evs.length}</span><span class="heat" style="width:${Math.round(100 * evs.length / max)}%"></span>` : "");
      if (key < t) c.style.opacity = .45;
      c.onclick = ev => { const a = ev.target.closest("a.ev"); if (a) { ev.stopPropagation(); openSheet(S.events.find(e => e.id === a.dataset.id)); return; } S.calSel = key; renderCal(list); };
      grid.appendChild(c);
    }
    const dayRoot = $("#calDay"); dayRoot.innerHTML = "";
    if (S.calSel && S.calSel.startsWith(S.calMonth)) {
      const evs = [...(byDay[S.calSel] || [])].sort((a, b) => rank(b) - rank(a));
      const [a, b] = dayLabel(S.calSel);
      dayRoot.innerHTML = `<div class="day-head">${esc(a)} <small>${esc(b)} · ${evs.length} event${evs.length === 1 ? "" : "s"} · best first</small></div>`;
      const g = document.createElement("div"); g.className = "cards-grid"; dayRoot.appendChild(g);
      evs.forEach(e => g.appendChild(card(e)));
      if (!evs.length) dayRoot.innerHTML += `<p class="empty">Quiet day. Or the venues haven't posted yet.</p>`;
    }
  }
  $("#calPrev").onclick = () => { const [y, m] = S.calMonth.split("-").map(Number); S.calMonth = `${m === 1 ? y - 1 : y}-${String(m === 1 ? 12 : m - 1).padStart(2, "0")}`; render(); };
  $("#calNext").onclick = () => { const [y, m] = S.calMonth.split("-").map(Number); S.calMonth = `${m === 12 ? y + 1 : y}-${String(m === 12 ? 1 : m + 1).padStart(2, "0")}`; render(); };

  // --------------------------------------------------------------- map ---
  let map, layer;
  async function renderMap(list) {
    if (!window.L) {
      await Promise.all([
        new Promise(r => { const l = document.createElement("link"); l.rel = "stylesheet"; l.href = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"; l.onload = r; document.head.appendChild(l); }),
        new Promise(r => { const s = document.createElement("script"); s.src = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"; s.onload = r; document.head.appendChild(s); }),
      ]);
    }
    if (!map) {
      map = L.map("map", { zoomControl: true }).setView([41.8268, -71.4025], 12);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap contributors", maxZoom: 19 }).addTo(map);
      layer = L.layerGroup().addTo(map);
    }
    layer.clearLayers();
    const byVenue = {};
    for (const e of list) if (e.lat && e.lon) (byVenue[e.venue_id || e.venue] ||= { e, evs: [] }).evs.push(e);
    const groups = Object.values(byVenue);
    for (const g of groups) {
      const n = g.evs.length; g.evs.sort((a, b) => rank(b) - rank(a));
      const mk = L.circleMarker([g.e.lat, g.e.lon], { radius: 7 + Math.min(14, Math.sqrt(n) * 3), color: "#1b1a24", weight: 1.5, fillColor: catColor(g.evs), fillOpacity: .85 });
      mk.bindPopup(`<b>${esc(g.e.venue)}</b><br>${n} in this window` + g.evs.slice(0, 5).map(e => `<a href="#" data-id="${e.id}">${fmt(new Date(e.start), { month: "short", day: "numeric" })} · ${esc(e.title)}</a>`).join("") + (n > 5 ? `<a href="#" data-venue="${g.e.venue_id}">…see all ${n}</a>` : ""));
      mk.on("popupopen", ev => {
        $$("a[data-id]", ev.popup.getElement()).forEach(a => a.onclick = x => { x.preventDefault(); openSheet(S.events.find(e => e.id === a.dataset.id)); });
        $$("a[data-venue]", ev.popup.getElement()).forEach(a => a.onclick = x => { x.preventDefault(); S.venue = a.dataset.venue; $("#venueSel").value = S.venue; S.view = "list"; syncWhen(); render(); });
      });
      layer.addLayer(mk);
    }
    if (groups.length) { try { map.fitBounds(L.featureGroup(layer.getLayers()).getBounds().pad(.15), { maxZoom: 14 }); } catch { /* noop */ } }
    setTimeout(() => map.invalidateSize(), 50);
  }
  function catColor(evs) {
    const c = {}; for (const e of evs) c[e.category] = (c[e.category] || 0) + 1;
    const top = Object.entries(c).sort((a, b) => b[1] - a[1])[0][0];
    return getComputedStyle(document.documentElement).getPropertyValue(`--c-${top}`).trim() || "#94a3b8";
  }

  // ------------------------------------------------------------- sheet ---
  function openSheet(e, html, perfs) {
    const sh = $("#sheet"), bd = $("#backdrop");
    if (html) sh.innerHTML = `<div class="grip"></div><button class="close" aria-label="Close">×</button>${html}`;
    else {
      learn(e, 1);
      perfs = perfs && perfs.length > 1 ? perfs : S.events.filter(x => runKey(x) === runKey(e)).sort((a, b) => a._t - b._t);
      const start = new Date(e.start);
      const when = `${fmt(start, { weekday: "long", month: "long", day: "numeric" })}${e.all_day ? "" : " · " + timeStr(e)}${e.end && !e.all_day ? "–" + timeStr({ start: e.end }) : ""}`;
      const gcal = gcalLink(e);
      const maps = e.lat ? `https://www.google.com/maps/search/?api=1&query=${e.lat},${e.lon}` : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent([e.venue, e.address || e.city, "RI"].filter(Boolean).join(", "))}`;
      const note = S.notes[e.venue_id] || "";
      const soon = soonLabel(e);
      const issue = `${REPO}/issues/new?title=${encodeURIComponent("Listing: " + e.title)}&body=${encodeURIComponent(`id: ${e.id}\nsource: ${e.source}\nwhat's wrong: `)}`;
      sh.innerHTML = `<div class="grip"></div><button class="close" aria-label="Close">×</button>
        ${e.image ? `<img class="hero" src="${esc(e.image)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : ""}
        <div class="top" style="--cc:var(--c-${e.category})"><span class="cat">${CATS[e.category] || e.category}</span> <span class="flags">${flags(e)}</span></div>
        <h2>${esc(e.title)}</h2>
        ${e.performer && e.performer !== e.title ? `<div class="meta"><span>${esc(e.performer)}</span></div>` : ""}
        <div class="meta">
          <span>📅 <b>${when}</b>${soon ? ` <em class="soon-tag">${soon}</em>` : ""}</span>
          <span>📍 <b>${esc(e.venue || "TBD")}</b>${e.address || e.city ? ` — <a href="${maps}" target="_blank" rel="noopener">${esc(e.address || e.city)}</a>` : ""}${e.miles ? ` <small>(${e.miles} mi)</small>` : ""}</span>
          ${e.price_text || e.price_min != null || e.is_free ? `<span>🎟 <b>${esc(priceStr(e))}</b>${e.price_text && priceStr(e) !== e.price_text ? ` <small>(${esc(e.price_text)})</small>` : ""}</span>` : ""}
          ${e.on_sale ? `<span>🕗 Tickets on sale ${fmt(new Date(e.on_sale), { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</span>` : ""}
          ${note ? `<span>🚗 ${esc(note)}</span>` : ""}
        </div>
        <div class="actions">
          ${e.ticket_url ? `<a class="btn tickets" id="shTix" href="${esc(e.ticket_url)}" target="_blank" rel="noopener">🎟 Tickets</a>` : ""}
          ${e.url ? `<a class="btn" href="${esc(e.url)}" target="_blank" rel="noopener">Details ↗</a>` : ""}
          <button class="btn primary" id="shStar">${S.stars.has(e.id) ? "★ Saved" : "☆ Save"}</button>
          <a class="btn" href="${gcal}" target="_blank" rel="noopener">＋ Google Calendar</a>
          <button class="btn" id="shIcs">⬇ .ics</button>
          <button class="btn" id="shShare">↗ Share</button>
          <button class="btn" id="shNope" title="Hide this">✕ Not for me</button>
        </div>
        ${perfs.length > 1 ? `<h4 class="perfs-h">All ${perfs.length} performances</h4><div class="perfs">${perfs.map(p => `<a href="${esc(p.ticket_url || p.url || "#")}" target="_blank" rel="noopener" class="perf${p.sold_out ? " so" : ""}${p.id === e.id ? " cur" : ""}">${fmt(new Date(p.start), { weekday: "short", month: "short", day: "numeric" })} · ${timeStr(p)}${p.sold_out ? " · sold out" : ""}</a>`).join("")}</div>` : ""}
        ${e.description ? `<p class="desc clamp" id="shDesc">${esc(e.description)}</p><button class="linkish" id="shMore">read more</button>` : e.summary ? `<p class="desc">${esc(e.summary)}</p>` : ""}
        <p class="fine">Listed by ${esc(e.source_name || e.source)}${e.also_from ? ` (also ${e.also_from.join(", ")})` : ""}${e.first_seen ? ` · first seen ${fmt(new Date(e.first_seen), { month: "short", day: "numeric" })}` : ""}. Check the venue before you go; listings change. <a href="${issue}" target="_blank" rel="noopener">Report a wrong listing</a> · <button class="linkish" id="shHideVenue">hide this venue</button></p>`;
      $("#shStar").onclick = () => { toggleStar(e); $("#shStar").textContent = S.stars.has(e.id) ? "★ Saved" : "☆ Save"; render(); };
      $("#shIcs").onclick = () => downloadIcs(e);
      $("#shShare").onclick = () => share(e);
      $("#shNope").onclick = () => { closeSheet(); nope(e, perfs); };
      $("#shHideVenue").onclick = () => { if (e.venue_id) { S.hiddenVenues.add(e.venue_id); learn(e, -2); persist(); buildVenueSel(); closeSheet(); render(); toast(`${e.venue} hidden — undo under ⋯`); } };
      const tix = $("#shTix"); if (tix) tix.addEventListener("click", () => learn(e, 2));
      const more = $("#shMore"); if (more) more.onclick = () => { $("#shDesc").classList.toggle("clamp"); more.textContent = $("#shDesc").classList.contains("clamp") ? "read more" : "less"; };
    }
    sh.hidden = false; bd.hidden = false; document.body.style.overflow = "hidden";
    $(".close", sh).onclick = closeSheet; bd.onclick = closeSheet;
    sh.scrollTop = 0;
  }
  function closeSheet() { $("#sheet").hidden = true; $("#backdrop").hidden = true; document.body.style.overflow = ""; }
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeSheet(); });

  function toggleStar(e) { const on = !S.stars.has(e.id); on ? S.stars.add(e.id) : S.stars.delete(e.id); learn(e, on ? 3 : -1); persist(); const sc = $("#starCount"); sc.textContent = S.stars.size; sc.hidden = !S.stars.size; }
  function nope(e, perfs = [e]) {
    for (const p of perfs) S.hidden.add(p.id);
    learn(e, -4); persist(); render();
    toast(`Hidden${perfs.length > 1 ? " (whole run)" : ""} — undo under ⋯`);
  }
  function gcalLink(e) {
    const p = d => new Date(d).toISOString().replace(/[-:]|\.\d{3}/g, "");
    const end = e.end ? p(e.end) : p(new Date(new Date(e.start).getTime() + 2 * 36e5));
    const dates = e.all_day ? `${e.start.slice(0, 10).replace(/-/g, "")}/${addDays(e.start.slice(0, 10), 1).replace(/-/g, "")}` : `${p(e.start)}/${end}`;
    const u = new URL("https://calendar.google.com/calendar/render");
    u.searchParams.set("action", "TEMPLATE"); u.searchParams.set("text", e.title); u.searchParams.set("dates", dates);
    u.searchParams.set("details", `${e.summary || ""}\n${e.ticket_url || e.url || ""}`.trim());
    u.searchParams.set("location", [e.venue, e.address || e.city].filter(Boolean).join(", "));
    return u.toString();
  }
  function downloadIcs(e) {
    const p = d => new Date(d).toISOString().replace(/[-:]|\.\d{3}/g, "");
    const ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Fun-o-tronic 4000//EN", "BEGIN:VEVENT", `UID:${e.id}@funotronic`,
      `DTSTAMP:${p(new Date())}`, e.all_day ? `DTSTART;VALUE=DATE:${e.start.slice(0, 10).replace(/-/g, "")}` : `DTSTART:${p(e.start)}`,
      e.end && !e.all_day ? `DTEND:${p(e.end)}` : "", `SUMMARY:${icsEsc(e.title)}`, `LOCATION:${icsEsc([e.venue, e.address || e.city].filter(Boolean).join(", "))}`,
      `DESCRIPTION:${icsEsc((e.summary || "") + "\n" + (e.ticket_url || e.url || ""))}`, e.url ? `URL:${e.url}` : "", "END:VEVENT", "END:VCALENDAR"].filter(Boolean).join("\r\n");
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([ics], { type: "text/calendar" })); a.download = `${e.title.replace(/[^\w]+/g, "-").slice(0, 40)}.ics`; a.click();
  }
  const icsEsc = s => String(s).replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");
  async function share(e) {
    const text = `${e.title} — ${fmt(new Date(e.start), { weekday: "short", month: "short", day: "numeric" })}${e.all_day ? "" : " " + timeStr(e)} at ${e.venue}${e.price_text ? ` (${priceStr(e)})` : ""}`;
    const url = e.ticket_url || e.url || location.href;
    if (navigator.share) { try { await navigator.share({ title: e.title, text, url }); return; } catch { /* cancelled */ } }
    await navigator.clipboard.writeText(`${text}\n${url}`); toast("Copied to clipboard");
  }
  // --------------------------------------------------- shared shortlist ---
  const b64 = s => btoa(unescape(encodeURIComponent(s))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const unb64 = s => decodeURIComponent(escape(atob(s.replace(/-/g, "+").replace(/_/g, "/"))));
  async function sendShortlist() {
    const ids = [...S.stars].filter(id => S.events.some(e => e.id === id));
    const url = `${location.origin}${location.pathname}#list=${b64(JSON.stringify({ from: "Nikki", ids }))}`;
    const text = `My Fun-o-tronic shortlist (${ids.length}) — tap 👍 on what appeals and send it back:`;
    if (navigator.share) { try { await navigator.share({ title: "Shortlist", text, url }); return; } catch { /* cancelled */ } }
    await navigator.clipboard.writeText(`${text}\n${url}`); toast("Shortlist link copied — text it to her");
  }
  async function sendVotes() {
    const ids = [...(S.myVotes || [])];
    const url = `${location.origin}${location.pathname}#votes=${b64(JSON.stringify({ from: "Brenda", ids }))}`;
    const text = `${ids.length} thumbs-up from the shortlist:`;
    if (navigator.share) { try { await navigator.share({ title: "Shortlist votes", text, url }); return; } catch { /* cancelled */ } }
    await navigator.clipboard.writeText(`${text}\n${url}`); toast("Votes link copied — send it back");
  }
  function readHash() {
    const h = location.hash.slice(1); if (!h) return;
    try {
      if (h.startsWith("list=")) { const d = JSON.parse(unb64(h.slice(5))); S.shortlist = new Set(d.ids); S.shortlistFrom = d.from ? `${d.from}'s` : ""; S.mode = "shortlist"; S.view = "list"; S.sort = "time"; S.myVotes = new Set(); }
      else if (h.startsWith("votes=")) { const d = JSON.parse(unb64(h.slice(6))); for (const id of d.ids) S.votes[id] = d.from || "👍"; persist(); S.mode = "stars"; S.view = "list"; location.hash = ""; toast(`${d.ids.length} thumbs-up received`); }
    } catch { /* bad link */ }
  }
  function toast(msg) { const t = $("#toast"); t.textContent = msg; t.hidden = false; clearTimeout(t._h); t._h = setTimeout(() => t.hidden = true, 2600); }
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  // ---------------------------------------------------------- controls ---
  function setWhen(w) { S.when = w; S.mode = "browse"; S.shown = 60; syncWhen(); persist(); render(); }
  function syncWhen() {
    $$("#whenChips button").forEach(b => b.classList.toggle("on", b.dataset.when === S.when && S.mode === "browse"));
    $("#customRange").hidden = S.when !== "custom";
  }
  $$("#whenChips button").forEach(b => b.onclick = () => { if (b.dataset.when === "custom" && !S.from) { S.from = todayKey(); S.to = addDays(S.from, 30); $("#fromDate").value = S.from; $("#toDate").value = S.to; } setWhen(b.dataset.when); });
  $("#fromDate").onchange = e => { S.from = e.target.value; render(); };
  $("#toDate").onchange = e => { S.to = e.target.value; render(); };
  let qTimer; $("#q").oninput = e => { clearTimeout(qTimer); qTimer = setTimeout(() => { S.q = e.target.value.trim(); S.shown = 60; if (S.q && S.when !== "all" && S.when !== "custom") { S._whenBefore ||= S.when; S.when = "all"; syncWhen(); } else if (!S.q && S._whenBefore) { S.when = S._whenBefore; S._whenBefore = null; syncWhen(); } render(); }, 180); };
  $("#freeOnly").onchange = e => { S.freeOnly = e.target.checked; persist(); render(); };
  $("#hideKids").onchange = e => { S.hideKids = e.target.checked; persist(); render(); };
  $("#ticketsOnly").onchange = e => { S.ticketsOnly = e.target.checked; persist(); render(); };
  $("#farToo").onchange = e => { S.farToo = e.target.checked; persist(); render(); };
  $("#maxPrice").onchange = e => { S.maxPrice = e.target.value === "" ? null : Number(e.target.value); persist(); render(); };
  $("#areaSel").onchange = e => { S.area = e.target.value; persist(); render(); };
  $("#venueSel").onchange = e => { S.venue = e.target.value; if (S.venue && S.when !== "all") { S.when = "all"; syncWhen(); } render(); };
  $("#sortSel").onchange = e => { S.sort = e.target.value; persist(); render(); };
  let moodT; $("#mood").oninput = e => { S.mood = Number(e.target.value); clearTimeout(moodT); moodT = setTimeout(() => { persist(); if (S.sort === "you" || S.view !== "list") render(); }, 150); };
  $$(".seg button").forEach(b => b.onclick = () => { S.view = b.dataset.view; persist(); render(); });
  $("#btnReset").onclick = () => { Object.assign(S, { when: "weekend", cats: new Set(), q: "", freeOnly: false, hideKids: true, ticketsOnly: false, farToo: false, maxPrice: null, area: "", venue: "", mode: "browse", shown: 60, dateNight: false, sort: "time" }); syncControls(); persist(); render(); };
  $("#btnStars").onclick = () => { S.mode = S.mode === "stars" ? "browse" : "stars"; S.view = "list"; syncWhen(); render(); };
  $("#btnNew").onclick = () => { S.mode = S.mode === "new" ? "browse" : "new"; S.view = "list"; S.sort = S.mode === "new" ? "new" : "time"; $("#sortSel").value = S.sort; syncWhen(); render(); };
  $("#btnTheme").onclick = () => { const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"); const nx = cur === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = nx; save("theme", nx); };
  $("#btnDate").onclick = () => {
    S.dateNight = !S.dateNight;
    if (S.dateNight) {
      const w = dow(todayKey());
      Object.assign(S, { mode: "browse", when: (w === 5 || w === 6) ? "tonight" : "weekend", cats: new Set(["theater", "classical", "comedy", "music", "film", "dance"]), ticketsOnly: true, hideKids: true, area: S.area || "metro", sort: "you", view: "list", q: "" });
      toast("Date night: evening, sit-down, close to home, tickets available");
    } else { S.cats = new Set(); S.ticketsOnly = false; S.sort = "time"; S.area = ""; }
    syncControls(); persist(); render();
  };
  $("#btnSurprise").onclick = () => {
    const pool = S.events.filter(e => matches(e, true) && e._day >= todayKey() && e._day <= addDays(todayKey(), 14) && !e.kids && !e.sold_out && soonLabel(e) !== "ended");
    if (!pool.length) return toast("Nothing to surprise you with — widen the filters.");
    const weighted = pool.flatMap(e => Array(Math.max(1, Math.round(rank(e) + 4 + (e._day <= addDays(todayKey(), 3) ? 3 : 0)))).fill(e));
    const pick = weighted[Math.floor(Math.random() * weighted.length)];
    learn(pick, .5); openSheet(pick);
  };
  $("#btnSources").onclick = ev => { ev.preventDefault(); openSheet(null, healthHtml()); };
  $("#btnMore").onclick = () => { openSheet(null, settingsHtml()); wireSettings(); };

  function syncControls() {
    syncWhen();
    $("#q").value = S.q; $("#freeOnly").checked = S.freeOnly; $("#hideKids").checked = S.hideKids; $("#ticketsOnly").checked = S.ticketsOnly; $("#farToo").checked = S.farToo;
    $("#maxPrice").value = S.maxPrice ?? ""; $("#areaSel").value = S.area; $("#venueSel").value = S.venue; $("#sortSel").value = S.sort; $("#mood").value = S.mood;
    $$("#catChips button").forEach(b => b.classList.toggle("on", S.cats.has(b.dataset.cat)));
  }
  function healthHtml() {
    if (!S.meta) return "<p>No build info yet.</p>";
    const rows = Object.entries(S.meta.sources).sort((a, b) => Number(a[1].ok) - Number(b[1].ok) || b[1].count - a[1].count)
      .map(([k, v]) => `<tr class="${v.ok ? "" : "bad"}"><td>${v.ok ? "●" : "○"}</td><td>${esc(k)}</td><td>${v.count}</td><td>${v.ok ? "" : `<code>${esc(v.error || "failed")}</code>`}</td></tr>`).join("");
    const bad = Object.values(S.meta.sources).filter(v => !v.ok).length;
    return `<h2>Sources</h2><p class="fine">Built ${fmt(new Date(S.meta.generated), { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })} · ${S.meta.count} events · ${Object.keys(S.meta.sources).length} sources${bad ? ` · <b style="color:var(--accent2)">${bad} failing</b> (showing their last good listings)` : ""}</p>
      <div class="health"><table>${rows}</table></div>`;
  }
  function tasteSummary() {
    const T = S.taste; const top = (m, n = 6) => Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, n).filter(x => x[1] > 0).map(x => x[0]);
    const low = (m, n = 4) => Object.entries(m).sort((a, b) => a[1] - b[1]).slice(0, n).filter(x => x[1] < 0).map(x => x[0]);
    return `Fun-o-tronic taste summary (${T.n || 0} signals)\nlikes: ${top(T.cat).join(", ") || "—"}\nvenues: ${top(T.venue).join(", ") || "—"}\ntags: ${top(T.tag, 8).join(", ") || "—"}\nless of: ${[...low(T.cat), ...low(T.venue)].join(", ") || "—"}\nfollows: ${S.follows.join(", ") || "—"}\nhidden venues: ${[...S.hiddenVenues].join(", ") || "—"}\nmood dial: ${S.mood}\nstars: ${S.stars.size}`;
  }
  function settingsHtml() {
    const feed = new URL("feed.ics", location.href).href;
    const hv = [...S.hiddenVenues].map(id => (S.venues.find(v => v.id === id) || { name: id }).name);
    return `<h2>Follows, subscribe &amp; settings</h2>
      <div class="kv">
        <div><b>Follow</b> venues, artists or words — matches get a ✦ badge, rank higher, and appear under ✦.<br>
          <input type="text" id="followIn" placeholder="e.g. trinity, odeum, dave matthews, jazz" value="${esc(S.follows.join(", "))}"><button class="btn" id="followSave" style="margin-top:6px">Save follows</button></div>
        <div><b>Hidden.</b> ${S.hidden.size} event${S.hidden.size === 1 ? "" : "s"}${hv.length ? `, venues: ${esc(hv.join(", "))}` : ""}. <button class="linkish" id="unhide">Unhide everything</button></div>
        <div><label class="tog"><input type="checkbox" id="groupTog" ${S.group ? "checked" : ""}> Group a production's performances into one card</label></div>
        <div><b>Calendar feed.</b> Everything in one subscribable calendar. In Google Calendar: <i>Other calendars → + → From URL</i>, paste:<br><input type="url" readonly value="${esc(feed)}" onclick="this.select()"></div>
        <div><b>Install.</b> On your phone: browser menu → <i>Add to Home screen</i>. It opens like an app.</div>
        <div><b>Taste.</b> Stars, opens, ticket taps and ✕ teach the ranking (<i>Best for you</i>, Surprise me, calendar picks). Nothing leaves this browser. <button class="linkish" id="copyTaste">Copy a summary for the staff</button> · <button class="linkish" id="resetTaste">reset taste</button></div>
        <div><b>Data.</b> Stars and filters live only in this browser. <button class="linkish" id="clearAll">Forget everything</button></div>
      </div>`;
  }
  function wireSettings() {
    $("#followSave").onclick = () => { S.follows = $("#followIn").value.split(",").map(s => s.trim()).filter(Boolean); S.followIds = new Set(S.events.filter(isFollowed).map(e => e.id)); persist(); closeSheet(); render(); toast(`Following ${S.follows.length} thing${S.follows.length === 1 ? "" : "s"}`); };
    $("#unhide").onclick = () => { S.hidden.clear(); S.hiddenVenues.clear(); persist(); buildVenueSel(); closeSheet(); render(); toast("Everything unhidden"); };
    $("#groupTog").onchange = e => { S.group = e.target.checked; persist(); render(); };
    $("#copyTaste").onclick = async () => { await navigator.clipboard.writeText(tasteSummary()); toast("Copied — paste it to Jeeves"); };
    $("#resetTaste").onclick = () => { S.taste = { cat: {}, venue: {}, tag: {}, source: {}, n: 0 }; persist(); toast("Taste reset"); };
    $("#clearAll").onclick = () => { localStorage.clear(); location.reload(); };
  }

  // ------------------------------------------------------------- boot ---
  const setMast = () => document.documentElement.style.setProperty("--mast-h", $(".masthead").offsetHeight + "px");
  setMast(); addEventListener("resize", setMast); if (document.fonts) document.fonts.ready.then(setMast);
  syncControls();
  load().catch(err => { $("#statusText").textContent = "couldn't load listings"; $("#led").className = "led bad"; console.error(err); })
    .finally(() => save("lastVisit", new Date().toISOString()));
  setInterval(() => { if (S.view === "list" && S.when === "tonight") render(); }, 60e3);
  if ("serviceWorker" in navigator && location.protocol === "https:") navigator.serviceWorker.register("sw.js").catch(() => {});
})();
