/**
 * Service worker for Updating.
 *
 * The whole site is a handful of static files and no API, so the strategy is
 * deliberately plain: precache every page and stylesheet on install, then
 *
 *   - navigations        network-first  (a revised board always wins online)
 *   - same-origin assets stale-while-revalidate (instant, self-healing)
 *   - Google Fonts       cache-first    (so offline does not fall back to a
 *                                        different typeface)
 *   - everything else    not handled    (straight to the network)
 *
 * Because navigations are network-first and assets revalidate in the
 * background, a forgotten CACHE_VERSION bump costs one stale load at most, not
 * a permanently wrong board. Bump it anyway when you change anything in docs/:
 * it is what evicts the previous cache outright.
 *
 * Note that same-origin requests deliberately bypass the *browser's* HTTP
 * cache (see fromNetwork). Without that, "network-first" is a lie: GitHub Pages
 * serves HTML with max-age=600, so fetch() would hand back a ten-minute-old
 * page without touching the network, and the service worker would then store
 * that as its own idea of fresh. One cache layer is enough, and it should be
 * the one with the version stamp on it.
 */

const CACHE_VERSION = '2026-11-13b';
const CACHE_NAME = `updating-${CACHE_VERSION}`;

/**
 * Every file the site is made of — small enough to take all of it offline.
 *
 * Deliberately absent: og/*.png, sitemap.xml and robots.txt. Those are read by
 * crawlers and link unfurlers, never by a visitor, so precaching them would add
 * ~95 KB to every install and serve nobody offline.
 */
const PRECACHE = [
  './',
  './index.html',
  './sources.html',
  './karpathy.html',
  './dan-moore.html',
  './brightlights.html',
  './krugman.html',
  './offline.html',
  './home.css',
  './style.css',
  './favicon.svg',
  './icon-192.png',
  './icon-512.png',
  './manifest.webmanifest',
];

/** Cross-origin hosts worth keeping a copy of. Fonts only. */
const FONT_HOSTS = ['fonts.googleapis.com', 'fonts.gstatic.com'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
      .catch((error) => {
        console.error('[sw] precache failed:', error);
      })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((name) => name.startsWith('updating-') && name !== CACHE_NAME)
            .map((name) => caches.delete(name))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;

  if (request.method !== 'GET') return;
  if (request.headers.has('range')) return;

  const url = new URL(request.url);
  const sameOrigin = url.origin === self.location.origin;

  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(event));
    return;
  }

  if (sameOrigin) {
    event.respondWith(staleWhileRevalidate(event));
    return;
  }

  if (FONT_HOSTS.includes(url.hostname)) {
    event.respondWith(cacheFirst(event));
    return;
  }

  // Anything else (the outbound links' favicons, say) is left to the network.
});

/**
 * A same-origin request that skips the browser's HTTP cache.
 *
 * Rebuilding the Request rather than passing init to fetch() is deliberate:
 * fetch(navigationRequest, init) silently downgrades mode "navigate" to
 * "same-origin", which breaks redirect handling. Cross-origin requests are
 * never rebuilt — a no-cors font request would come back as mode "cors" and
 * fail — so only the same-origin paths call this.
 *
 * @param {Request} request
 * @param {'no-store'|'no-cache'} mode
 *   no-store for navigations (never read or write the HTTP cache),
 *   no-cache for background revalidation (ask the server, 304s are cheap).
 * @returns {Promise<Response>}
 */
function fromNetwork(request, mode) {
  return fetch(
    new Request(request.url, {
      cache: mode,
      credentials: 'same-origin',
      redirect: 'follow',
    })
  );
}

/** Put a response in the cache without holding up the one being returned. */
function put(event, response) {
  const copy = response.clone();
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.put(event.request, copy))
      .catch((error) => {
        console.warn('[sw] could not cache', event.request.url, error);
      })
  );
}

/** Opaque responses have status 0 and cannot be inspected; keep them anyway. */
function worthCaching(response) {
  return Boolean(response) && (response.ok || response.type === 'opaque');
}

function networkFirst(event) {
  return fromNetwork(event.request, 'no-store')
    .then((response) => {
      if (worthCaching(response)) put(event, response);
      return response;
    })
    .catch(() =>
      caches
        .match(event.request, { ignoreSearch: true })
        .then((hit) => hit || caches.match('./offline.html'))
    );
}

function cacheFirst(event) {
  return caches.match(event.request).then((hit) => {
    if (hit) return hit;
    return fetch(event.request).then((response) => {
      if (worthCaching(response)) put(event, response);
      return response;
    });
  });
}

function staleWhileRevalidate(event) {
  return caches.match(event.request).then((hit) => {
    const fresh = fromNetwork(event.request, 'no-cache')
      .then((response) => {
        if (worthCaching(response)) put(event, response);
        return response;
      })
      .catch(() => hit);

    // Serve the cached copy at once and let the network catch up behind it.
    if (hit) {
      event.waitUntil(fresh.catch(() => {}));
      return hit;
    }
    return fresh;
  });
}

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting();
});
