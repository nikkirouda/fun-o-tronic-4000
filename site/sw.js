/* Offline copy: network first for everything on this site, falling back to the last saved copy when offline. */
const CACHE = "fot-v5";
self.addEventListener("install", e => { self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin || e.request.method !== "GET") return;
  e.respondWith(fetch(e.request).then(r => { if (r.ok) { const c = r.clone(); caches.open(CACHE).then(ca => ca.put(e.request, c)); } return r; })
    .catch(() => caches.match(e.request, { ignoreSearch: true })));
});
