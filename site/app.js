/* Fun-o-tronic 4000 — front end. Vanilla JS, no build step. Reads data/*.json produced by build.py. */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const TZ = "America/New_York";

  const CATS = {
    theater: "Theater", music: "Music", classical: "Classical", dance: "Dance", comedy: "Comedy",
    film: "Film", talk: "Talks", sports: "Sports", festival: "Festivals", market: "Markets",
    art: "Art", food: "Food & drink", family: "Family", community: "Community", other: "Other",
  };
  const AREAS = {
    hill: ["providence"], // refined by venue list below
    pvd: ["providence"],
    metro: ["providence", "pawtucket", "cranston", "east providence", "warwick", "north providence", "johnston", "central falls", "lincoln", "smithfield", "seekonk", "attleboro", "barrington", "riverside", "rumford"],
    newport: ["newport", "middletown", "portsmouth", "jamestown", "tiverton", "bristol", "warren", "little compton"],
    south: ["westerly", "wakefield", "south kingstown", "narragansett", "kingston", "peace dale", "matunuck", "charlestown", "north kingstown", "east greenwich", "west greenwich", "exeter", "richmond", "hopkinton", "block island", "new shoreham", "west kingston"],
    north: ["woonsocket", "cumberland", "lincoln", "north smithfield", "burrillville", "glocester", "scituate", "foster", "smithfield", "pawtucket", "central falls"],
  };
  const HILL_VENUE_RX = /brown|risd|athenaeum|avon|lindemann|granoff|sayles|salomon|alumnae|john carter|list art|stuart theatre|leeds|pembroke|wriston|books on the square|hope street|thayer|wickenden|riffraff|fox point|cable car|first unitarian|providence public library|east side|wayland/i;

  // ------------------------------------------------------------- state ---
  const S = {
    events: [], venues: [], meta: null, changes: null,
    when: "weekend", from: null, to: null, cats: new Set(), q: "",
    freeOnly: false, hideKids: true, ticketsOnly: false, maxPrice: null, area: "", venue: "",
    view: "list", sort: "time", shown: 60, calMonth: null, calSel: null,
    stars: new Set(JSON.parse(localStorage.getItem("fot.stars") || "[]")),
    lastVisit: localStorage.getItem("fot.lastVisit"),
    mode: "browse", // browse | stars | new
  };
  const saved = JSON.parse(localStorage.getItem("fot.filters") || "{}");
  Object.assign(S, pick(saved, ["when", "hideKids", "area", "view", "sort", "cats", "freeOnly", "ticketsOnly", "maxPrice"]));
  if (Array.isArray(S.cats)) S.cats = new Set(S.cats);
  if (localStorage.getItem("fot.theme")) document.documentElement.dataset.theme = localStorage.getItem("fot.theme");

  function pick(o, keys) { const r = {}; for (const k of keys) if (k in o) r[k] = o[k]; return r; }
  function persist() {
    localStorage.setItem("fot.filters", JSON.stringify({ ...pick(S, ["when", "hideKids", "area", "view", "sort", "freeOnly", "ticketsOnly", "maxPrice"]), cats: [...S.cats] }));
    localStorage.setItem("fot.stars", JSON.stringify([...S.stars]));
  }

  // -------------------------------------------------------------- dates ---
  const fmt = (d, o) => new Intl.DateTimeFormat("en-US", { timeZone: TZ, ...o }).format(d);
  const dayKey = d => fmt(d, { year: "numeric", month: "2-digit", day: "2-digit" }).replace(/(\d+)\/(\d+)\/(\d+)/, "$3-$1-$2");
  const todayKey = () => dayKey(new Date());
  function addDays(key, n) { const [y, m, d] = key.split("-").map(Number); const dt = new Date(Date.UTC(y, m - 1, d + n)); return dt.toISOString().slice(0, 10); }
  function dow(key) { const [y, m, d] = key.split("-").map(Number); return new Date(Date.UTC(y, m - 1, d)).getUTCDay(); }
  function range() {
    const t = todayKey();
    switch (S.when) {
      case "tonight": return [t, t];
      case "tomorrow": { const n = addDays(t, 1); return [n, n]; }
      case "weekend": { // Fri–Sun of this week (or today–Sun if already the weekend; next weekend if Mon it's far but fine)
        const w = dow(t); let fri = addDays(t, (5 - w + 7) % 7); if (w === 6 || w === 0) fri = t; return [fri, addDays(fri, w === 0 ? 0 : (w === 6 ? 1 : 2))];
      }
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
    if (key === t) return ["Tonight", base];
    if (key === addDays(t, 1)) return ["Tomorrow", base];
    return [fmt(dt, { weekday: "long" }), fmt(dt, { month: "long", day: "numeric" })];
  }
  const hoursAgo = iso => Math.round((Date.now() - new Date(iso)) / 36e5);

  // -------------------------------------------------------------- data ---
  async function load() {
    const bust = `?v=${Math.floor(Date.now() / 6e5)}`;
    const [ev, meta, venues, changes] = await Promise.all([
      fetch(`data/events.json${bust}`).then(r => r.json()),
      fetch(`data/meta.json${bust}`).then(r => r.json()).catch(() => null),
      fetch(`data/venues.json${bust}`).then(r => r.json()).catch(() => []),
      fetch(`data/changes.json${bust}`).then(r => r.json()).catch(() => ({ items: [] })),
    ]);
    S.events = ev.events.map(e => ({ ...e, _day: dayKey(new Date(e.start)), _t: new Date(e.start).getTime(),
      _hay: `${e.title} ${e.venue} ${e.city} ${e.performer} ${e.tags.join(" ")} ${e.summary} ${CATS[e.category] || ""}`.toLowerCase() }));
    S.meta = meta; S.venues = venues; S.changes = changes;
    const h = hoursAgo(ev.generated);
    const led = $("#led");
    $("#statusText").textContent = `${ev.count.toLocaleString()} events · updated ${h < 1 ? "just now" : h < 48 ? h + "h ago" : Math.round(h / 24) + "d ago"}`;
    led.className = "led" + (h > 30 ? " bad" : h > 14 ? " warn" : "");
    const srcs = meta ? Object.keys(meta.sources).length : 0;
    $("#srcCount").textContent = srcs;
    buildCatChips(); buildVenueSel();
    // "new since last visit"
    // first visit: nothing is "new" yet; afterwards, anything first seen since you were last here (max 14 days back)
    const since = S.lastVisit ? (S.lastVisit > new Date(Date.now() - 14 * 864e5).toISOString() ? S.lastVisit : new Date(Date.now() - 14 * 864e5).toISOString()) : "9999";
    const newIds = new Set(S.events.filter(e => e.first_seen && e.first_seen > since).map(e => e.id));
    S.newIds = newIds;
    const nb = $("#newCount"); nb.textContent = newIds.size; nb.hidden = newIds.size === 0;
    render();
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
    sel.innerHTML = `<option value="">Any venue</option>` + S.venues.filter(v => v.count >= 2).map(v => `<option value="${v.id}">${esc(v.name)} (${v.count})</option>`).join("");
    sel.value = S.venue;
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
    if (S.mode === "stars") return S.stars.has(e.id);
    if (S.mode === "new" && !S.newIds.has(e.id)) return false;
    if (!ignoreWhen && S.mode === "browse") { const [a, b] = range(); if (e._day < a || e._day > b) return false; }
    if (S.cats.size && !S.cats.has(e.category)) return false;
    if (S.hideKids && e.kids && !S.cats.has("family")) return false;
    if (S.freeOnly && !e.is_free) return false;
    if (S.ticketsOnly && !e.ticket_url) return false;
    if (S.maxPrice != null && S.maxPrice !== "" && e.price_min != null && e.price_min > S.maxPrice) return false;
    if (S.venue && e.venue_id !== S.venue) return false;
    if (!inArea(e)) return false;
    if (S.q) { const terms = S.q.toLowerCase().split(/\s+/).filter(Boolean); if (!terms.every(t => e._hay.includes(t))) return false; }
    return true;
  }
  function sorted(list) {
    const l = [...list];
    if (S.sort === "new") l.sort((a, b) => (b.first_seen || "").localeCompare(a.first_seen || "") || a._t - b._t);
    else if (S.sort === "price") l.sort((a, b) => (a.price_min ?? 1e9) - (b.price_min ?? 1e9) || a._t - b._t);
    else if (S.sort === "az") l.sort((a, b) => a.title.localeCompare(b.title));
    else l.sort((a, b) => a._t - b._t);
    return l;
  }

  // ------------------------------------------------------------ render ---
  function render() {
    $$(".view").forEach(v => v.hidden = true);
    $$(".seg button").forEach(b => b.classList.toggle("on", b.dataset.view === S.view));
    $("#btnStars").classList.toggle("lit", S.mode === "stars");
    $("#btnNew").classList.toggle("lit", S.mode === "new");
    const sc = $("#starCount"); sc.textContent = S.stars.size; sc.hidden = !S.stars.size;
    const list = sorted(S.events.filter(e => matches(e, S.view !== "list")));
    if (S.view === "list") { $("#listView").hidden = false; renderList(list); }
    else if (S.view === "cal") { $("#calView").hidden = false; renderCal(list); }
    else { $("#mapView").hidden = false; renderMap(list); }
    const label = S.mode === "stars" ? "saved" : S.mode === "new" ? "new since last visit" : S.view !== "list" ? "upcoming" : ({ tonight: "tonight", tomorrow: "tomorrow", weekend: "this weekend", week: "in the next 7 days", month: "in the next 30 days", all: "upcoming", custom: "in your dates" })[S.when];
    $("#count").textContent = `${list.length} ${label}`;
  }

  function card(e) {
    const n = $("#tplCard").content.firstElementChild.cloneNode(true);
    n.style.setProperty("--cc", `var(--c-${e.category})`);
    n.dataset.id = e.id;
    $(".t", n).textContent = timeStr(e);
    $(".d", n).textContent = fmt(new Date(e.start), { weekday: "short", month: "short", day: "numeric" });
    $(".cat", n).textContent = CATS[e.category] || e.category;
    $(".flags", n).innerHTML = flags(e);
    $(".title", n).textContent = e.title;
    $(".where", n).textContent = [e.venue, e.city].filter(Boolean).join(" · ") + (e.price_text || e.price_min != null ? ` · ${priceStr(e)}` : "");
    $(".sum", n).textContent = e.summary || "";
    const st = $(".star", n); st.textContent = S.stars.has(e.id) ? "★" : "☆"; st.classList.toggle("on", S.stars.has(e.id));
    st.onclick = ev => { ev.stopPropagation(); toggleStar(e.id); st.textContent = S.stars.has(e.id) ? "★" : "☆"; st.classList.toggle("on", S.stars.has(e.id)); };
    n.onclick = () => openSheet(e); n.onkeydown = ev => { if (ev.key === "Enter") openSheet(e); };
    return n;
  }
  function flags(e) {
    const f = [];
    if (e.is_free) f.push(`<span class="flag free">FREE</span>`);
    if (S.newIds && S.newIds.has(e.id)) f.push(`<span class="flag new">NEW</span>`);
    if (e.on_sale && new Date(e.on_sale) > new Date()) f.push(`<span class="flag sale">ON SALE ${fmt(new Date(e.on_sale), { month: "short", day: "numeric" })}</span>`);
    if (e.sold_out) f.push(`<span class="flag soldout">SOLD OUT</span>`);
    if (e.kids) f.push(`<span class="flag">KIDS</span>`);
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
      root.innerHTML = `<div class="empty"><h3>${S.mode === "stars" ? "Nothing saved yet" : "Nothing here"}</h3><p>${S.mode === "stars" ? "Tap ☆ on anything that looks like fun." : "Try a wider date range, fewer categories, or clear the search."}</p>${S.mode === "browse" ? `<button class="more" id="widen">Show the next 30 days instead</button>` : ""}</div>`;
      const w = $("#widen"); if (w) w.onclick = () => { setWhen("month"); };
      return;
    }
    const slice = list.slice(0, S.shown);
    let day = null, grid = null;
    for (const e of slice) {
      if (e._day !== day) {
        day = e._day; const [a, b] = dayLabel(day);
        const h = document.createElement("div"); h.className = "day-head" + (day === todayKey() ? " today" : "");
        h.innerHTML = `${esc(a)} <small>${esc(b)}</small>`; root.appendChild(h);
        grid = document.createElement("div"); grid.className = "cards-grid"; root.appendChild(grid);
      }
      grid.appendChild(card(e));
    }
    if (list.length > S.shown) {
      const b = document.createElement("button"); b.className = "more"; b.textContent = `Show ${Math.min(60, list.length - S.shown)} more of ${list.length}`;
      b.onclick = () => { S.shown += 60; renderList(list); }; root.appendChild(b);
    }
  }

  // ---------------------------------------------------------- calendar ---
  function renderCal(list) {
    const t = todayKey();
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
      c.innerHTML = `<span class="n">${d}</span><span class="dots">${cats.map(k => `<i style="background:var(--c-${k})"></i>`).join("")}</span>` +
        (evs.length ? `<span class="cnt">${evs.length}</span><span class="heat" style="width:${Math.round(100 * evs.length / max)}%"></span>` : "");
      if (key < t) c.style.opacity = .45;
      c.onclick = () => { S.calSel = key; renderCal(list); };
      grid.appendChild(c);
    }
    const dayRoot = $("#calDay"); dayRoot.innerHTML = "";
    if (S.calSel && S.calSel.startsWith(S.calMonth)) {
      const evs = sorted(byDay[S.calSel] || []);
      const [a, b] = dayLabel(S.calSel);
      dayRoot.innerHTML = `<div class="day-head">${esc(a)} <small>${esc(b)} · ${evs.length} event${evs.length === 1 ? "" : "s"}</small></div>`;
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
      const n = g.evs.length;
      const mk = L.circleMarker([g.e.lat, g.e.lon], { radius: 7 + Math.min(14, Math.sqrt(n) * 3), color: "#1b1a24", weight: 1.5, fillColor: catColor(g.evs), fillOpacity: .85 });
      mk.bindPopup(`<b>${esc(g.e.venue)}</b><br>${n} upcoming` + g.evs.slice(0, 5).map(e => `<a href="#" data-id="${e.id}">${fmt(new Date(e.start), { month: "short", day: "numeric" })} · ${esc(e.title)}</a>`).join("") + (n > 5 ? `<a href="#" data-venue="${g.e.venue_id}">…see all ${n}</a>` : ""));
      mk.on("popupopen", ev => {
        $$("a[data-id]", ev.popup.getElement()).forEach(a => a.onclick = x => { x.preventDefault(); openSheet(S.events.find(e => e.id === a.dataset.id)); });
        $$("a[data-venue]", ev.popup.getElement()).forEach(a => a.onclick = x => { x.preventDefault(); S.venue = a.dataset.venue; $("#venueSel").value = S.venue; S.view = "list"; S.when = "all"; syncWhen(); render(); });
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
  function openSheet(e, html) {
    const sh = $("#sheet"), bd = $("#backdrop");
    if (html) sh.innerHTML = `<div class="grip"></div><button class="close" aria-label="Close">×</button>${html}`;
    else {
      const start = new Date(e.start);
      const when = `${fmt(start, { weekday: "long", month: "long", day: "numeric" })}${e.all_day ? "" : " · " + timeStr(e)}${e.end && !e.all_day ? "–" + timeStr({ start: e.end }) : ""}`;
      const gcal = gcalLink(e);
      const maps = e.lat ? `https://www.google.com/maps/search/?api=1&query=${e.lat},${e.lon}` : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent([e.venue, e.address || e.city, "RI"].filter(Boolean).join(", "))}`;
      sh.innerHTML = `<div class="grip"></div><button class="close" aria-label="Close">×</button>
        ${e.image ? `<img class="hero" src="${esc(e.image)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : ""}
        <div class="top" style="--cc:var(--c-${e.category})"><span class="cat">${CATS[e.category] || e.category}</span> <span class="flags">${flags(e)}</span></div>
        <h2>${esc(e.title)}</h2>
        ${e.performer && e.performer !== e.title ? `<div class="meta"><span>${esc(e.performer)}</span></div>` : ""}
        <div class="meta">
          <span>📅 <b>${when}</b></span>
          <span>📍 <b>${esc(e.venue || "TBD")}</b>${e.address || e.city ? ` — <a href="${maps}" target="_blank" rel="noopener">${esc(e.address || e.city)}</a>` : ""}</span>
          ${e.price_text || e.price_min != null || e.is_free ? `<span>🎟 <b>${esc(priceStr(e))}</b>${e.price_text && priceStr(e) !== e.price_text ? ` <small>(${esc(e.price_text)})</small>` : ""}</span>` : ""}
          ${e.on_sale ? `<span>🕗 Tickets on sale ${fmt(new Date(e.on_sale), { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</span>` : ""}
        </div>
        <div class="actions">
          ${e.ticket_url ? `<a class="btn tickets" href="${esc(e.ticket_url)}" target="_blank" rel="noopener">🎟 Tickets</a>` : ""}
          ${e.url ? `<a class="btn" href="${esc(e.url)}" target="_blank" rel="noopener">Details ↗</a>` : ""}
          <button class="btn primary" id="shStar">${S.stars.has(e.id) ? "★ Saved" : "☆ Save"}</button>
          <a class="btn" href="${gcal}" target="_blank" rel="noopener">＋ Google Calendar</a>
          <button class="btn" id="shIcs">⬇ .ics</button>
          <button class="btn" id="shShare">↗ Share</button>
        </div>
        ${e.description ? `<p class="desc clamp" id="shDesc">${esc(e.description)}</p><button class="linkish" id="shMore">read more</button>` : e.summary ? `<p class="desc">${esc(e.summary)}</p>` : ""}
        <p class="fine">Listed by ${esc(e.source_name || e.source)}${e.also_from ? ` (also ${e.also_from.join(", ")})` : ""}${e.first_seen ? ` · first seen ${fmt(new Date(e.first_seen), { month: "short", day: "numeric" })}` : ""}. Check the venue before you go; listings change.</p>`;
      $("#shStar").onclick = () => { toggleStar(e.id); $("#shStar").textContent = S.stars.has(e.id) ? "★ Saved" : "☆ Save"; render(); };
      $("#shIcs").onclick = () => downloadIcs(e);
      $("#shShare").onclick = () => share(e);
      const more = $("#shMore"); if (more) more.onclick = () => { $("#shDesc").classList.toggle("clamp"); more.textContent = $("#shDesc").classList.contains("clamp") ? "read more" : "less"; };
    }
    sh.hidden = false; bd.hidden = false; document.body.style.overflow = "hidden";
    $(".close", sh).onclick = closeSheet; bd.onclick = closeSheet;
    sh.scrollTop = 0;
  }
  function closeSheet() { $("#sheet").hidden = true; $("#backdrop").hidden = true; document.body.style.overflow = ""; }
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeSheet(); });

  function toggleStar(id) { S.stars.has(id) ? S.stars.delete(id) : S.stars.add(id); persist(); const sc = $("#starCount"); sc.textContent = S.stars.size; sc.hidden = !S.stars.size; }
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
  function toast(msg) { const t = $("#toast"); t.textContent = msg; t.hidden = false; clearTimeout(t._h); t._h = setTimeout(() => t.hidden = true, 2200); }
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
  $("#maxPrice").onchange = e => { S.maxPrice = e.target.value === "" ? null : Number(e.target.value); persist(); render(); };
  $("#areaSel").onchange = e => { S.area = e.target.value; persist(); render(); };
  $("#venueSel").onchange = e => { S.venue = e.target.value; if (S.venue && S.when !== "all") { S.when = "all"; syncWhen(); } render(); };
  $("#sortSel").onchange = e => { S.sort = e.target.value; persist(); render(); };
  $$(".seg button").forEach(b => b.onclick = () => { S.view = b.dataset.view; persist(); render(); });
  $("#btnReset").onclick = () => { Object.assign(S, { when: "weekend", cats: new Set(), q: "", freeOnly: false, hideKids: true, ticketsOnly: false, maxPrice: null, area: "", venue: "", mode: "browse", shown: 60 }); syncControls(); persist(); render(); };
  $("#btnStars").onclick = () => { S.mode = S.mode === "stars" ? "browse" : "stars"; S.view = "list"; syncWhen(); render(); };
  $("#btnNew").onclick = () => { S.mode = S.mode === "new" ? "browse" : "new"; S.view = "list"; S.sort = S.mode === "new" ? "new" : "time"; $("#sortSel").value = S.sort; syncWhen(); render(); };
  $("#btnTheme").onclick = () => { const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"); const nx = cur === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = nx; localStorage.setItem("fot.theme", nx); };
  $("#btnSurprise").onclick = () => {
    const pool = S.events.filter(e => matches(e, true) && e._day >= todayKey() && e._day <= addDays(todayKey(), 14) && !e.kids);
    if (!pool.length) return toast("Nothing to surprise you with — widen the filters.");
    // weight toward sooner + has a description
    const weighted = pool.flatMap(e => Array(1 + (e.description ? 1 : 0) + (e._day <= addDays(todayKey(), 3) ? 2 : 0)).fill(e));
    openSheet(weighted[Math.floor(Math.random() * weighted.length)]);
  };
  $("#btnSources").onclick = ev => { ev.preventDefault(); openSheet(null, healthHtml()); };
  $("#btnMore").onclick = () => openSheet(null, settingsHtml());

  function syncControls() {
    syncWhen();
    $("#q").value = S.q; $("#freeOnly").checked = S.freeOnly; $("#hideKids").checked = S.hideKids; $("#ticketsOnly").checked = S.ticketsOnly;
    $("#maxPrice").value = S.maxPrice ?? ""; $("#areaSel").value = S.area; $("#venueSel").value = S.venue; $("#sortSel").value = S.sort;
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
  function settingsHtml() {
    const feed = new URL("feed.ics", location.href).href;
    return `<h2>Subscribe &amp; settings</h2>
      <div class="kv">
        <div><b>Calendar feed.</b> Everything in one subscribable calendar. In Google Calendar: <i>Other calendars → + → From URL</i>, paste:<br><input type="url" readonly value="${esc(feed)}" onclick="this.select()"></div>
        <div><b>Your picks feed.</b> Star events, then add each one with <i>＋ Google Calendar</i> or <i>.ics</i> from its page.</div>
        <div><b>Install.</b> On your phone: browser menu → <i>Add to Home screen</i>. It opens like an app.</div>
        <div><b>Data.</b> Stars and filters live only in this browser. <button class="linkish" id="clearAll">Forget everything</button></div>
      </div>`;
  }
  document.addEventListener("click", e => { if (e.target.id === "clearAll") { localStorage.clear(); location.reload(); } });

  // ------------------------------------------------------------- boot ---
  const setMast = () => document.documentElement.style.setProperty("--mast-h", $(".masthead").offsetHeight + "px");
  setMast(); addEventListener("resize", setMast); if (document.fonts) document.fonts.ready.then(setMast);
  syncControls();
  load().catch(err => { $("#statusText").textContent = "couldn't load listings"; $("#led").className = "led bad"; console.error(err); })
    .finally(() => { localStorage.setItem("fot.lastVisit", new Date().toISOString()); });
  if ("serviceWorker" in navigator && location.protocol === "https:") navigator.serviceWorker.register("sw.js").catch(() => {});
})();
