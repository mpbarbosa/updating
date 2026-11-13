# updating

A repository to help me find the best sources of information on what is happening in the
world, so that I can stay up to date.

**Live site:** https://mpbarbosa.github.io/updating/

## Sources assessed

| Source | Verdict | Page |
| --- | --- | --- |
| Dan Moore | Worth following, with a filter. 159 posts on FusionAuth's blog since 2020, two thirds of it dev-rel work worth skipping — but since 2025 a fortnightly stream of long explainers on OAuth, identity standards and agent authorization. No per-author feed. | [index](docs/dan-moore.html) |
| Andrej Karpathy | Deep, slow. 11 posts in 2025, 3 in 2026. Two live blogs with separate feeds. Excellent for understanding, poor for news. | [index](docs/karpathy.html) |
| Bright Lights Film Journal | Worth following, by subject. A film journal from 1974, online since 1995, 2,928 articles deep and publishing an essay every three days — but zero reviews, festival reports or news in all of 2026. Feeds for every category and author, all working. 74 articles this year from 61 different writers, and the masthead's own critics have stopped filing. | [index](docs/brightlights.html) |
| Paul Krugman | Worth following, on the right day. 793 posts in the 702 days since he left the New York Times for Substack: free political commentary on weekdays, and one paid 3,000-word economics essay every Sunday — 42 for 42 in 2026. The economics is the reason to read him and it is the half behind the paywall. One feed, twenty items, sixteen days of memory — and a free back door at the CUNY Stone Center, which reposts whole paid series and carries the lectures. | [index](docs/krugman.html) |

## Feeds worth subscribing to

- `https://karpathy.bearblog.dev/feed/` — Karpathy's primary blog
- `https://karpathy.github.io/feed.xml` — his older blog, active again as of Feb 2026
- `https://github.com/karpathy.atom` — repository activity
- `https://fusionauth.io/blog/feed.xml` — carries Dan Moore, but it is the whole company
  blog: filter on `<author>Dan Moore</author>`, and note it is missing three of his 2026 posts
- `https://www.mooreds.com/wordpress/feed` — his personal blog; monthly, and a different
  subject entirely (engineering management and careers, no identity)
- `https://brightlightsfilm.com/category/essays/feed/` — the Bright Lights label that tracks
  what the journal is actually doing: 19 of its 74 articles this year. Any category works
  (`/category/<slug>/feed/`), as does any author (`/author/<slug>/feed/`)
- `https://brightlightsfilm.com/feed/` — the whole journal, ten items deep. Fine for a daily
  reader, lossy if you check in monthly; prefer a category feed
- `https://api.substack.com/feed/podcast/277517.rss` — Krugman's podcast and video, and the
  only deep feed on his site: 101 items back to January 2025
- `https://paulkrugman.substack.com/feed` — all of Krugman's writing, twenty items. At 33 posts
  a month that is about sixteen days, and there is no category or tag feed to narrow it with
- `https://stonecenter.gc.cuny.edu/?s=krugman&feed=rss2` — not his site: the CUNY Stone Center,
  where he is a senior scholar. Carries his lectures and reposts whole paid series free. A
  WordPress keyword feed, ten items, about one a month

## Layout

- `docs/` — the published GitHub Pages site (source: `main` branch, `/docs` folder)
- `docs/index.html` — the home page: a board of tiles, Windows-widgets style, showing what
  is newest across every source, the feeds, the cadence and what to watch out for. Filter
  box, light/dark toggle and copy-the-feed-URL buttons; no build step, no dependencies
- `docs/home.css` — styles for the home page only
- `docs/sources.html` — the reading hub: every source assessed, with the verdict and the feeds
- `docs/<source>.html` — one page per source
- `docs/style.css` — shared styles for the hub and the source pages
- `docs/manifest.webmanifest`, `docs/service-worker.js`, `docs/offline.html`,
  `docs/icon-*.png`, `docs/favicon.svg` — the installable/offline layer

Each source page answers the same questions: where they publish and which channels are
live, how often they actually post, what they are writing about now, what is worth reading
first, and what to discount.

## Installable and offline

The site is a progressive web app: it can be installed to a home screen or
desktop, and every page is readable with no connection. There is still no build
step and no dependency — the manifest and the service worker are two more static
files in `docs/`.

The service worker precaches the whole site (about 180 KB including the icons)
and then serves:

- **navigations** network-first, so a revised board always wins when you are online
- **stylesheets, images, icons** stale-while-revalidate — instant, and self-healing
- **Google Fonts** cache-first, so offline does not fall back to a different typeface
- **everything else** straight to the network, uncached

Same-origin requests deliberately bypass the *browser's* HTTP cache. Without
that, network-first is a lie: GitHub Pages serves HTML with `max-age=600`, so
`fetch()` hands back a ten-minute-old page without touching the network and the
service worker stores that as its idea of fresh. One cache layer is enough, and
it should be the one with the version stamp on it.

**When you change anything in `docs/`, bump `CACHE_VERSION` at the top of
`docs/service-worker.js`.** That is what evicts the previous cache outright.
Forgetting it is not fatal — navigations are network-first and assets revalidate
behind the scenes, so the cost is at most one stale load — but it is the one
piece of upkeep the PWA layer adds.

Caching is live on `localhost` too, so it can be tested the same way it runs in
production. While editing, use DevTools → Application → Service Workers →
*Bypass for network*, or just reload twice.

## Previewing locally

```
python3 -m http.server 8731 --directory docs
```

Then open http://localhost:8731/. There is no build step — the pages are plain HTML.
