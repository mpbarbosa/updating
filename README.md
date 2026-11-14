# updating

A repository to help me find the best sources of information on what is happening in the
world, so that I can stay up to date.

**Live site:** https://mpbarbosa.github.io/updating/

## Sources assessed

| Source | Verdict | Page |
| --- | --- | --- |
| Dan Moore | Worth following, with a filter. 159 posts on FusionAuth's blog since 2020, two thirds of it dev-rel work worth skipping — but since 2025 a fortnightly stream of long explainers on OAuth, identity standards and agent authorization. No per-author feed. | [index](docs/dan-moore.html) |
| Andrej Karpathy | Deep, slow. 11 posts in 2025, 3 in 2026. Two live blogs with separate feeds. Excellent for understanding, poor for news. | [index](docs/karpathy.html) |
| Bright Lights Film Journal | Worth following, by subject. A film journal from 1974, online since 1995, 2,929 articles deep and publishing an essay every four days — but zero reviews, festival reports or news in all of 2026. Feeds for every category and author, all working. 75 articles this year from 62 different writers, and the masthead's own critics have stopped filing. | [index](docs/brightlights.html) |
| Paul Krugman | Worth following, on the right day. 794 posts in the 702 days since he left the New York Times for Substack: free political commentary on weekdays, and one paid 3,000-word economics essay every Sunday — 42 for 42 in 2026. The economics is the reason to read him and it is the half behind the paywall. One feed, twenty items, sixteen days of memory — and a free back door at the CUNY Stone Center, which reposts whole paid series and carries the lectures. | [index](docs/krugman.html) |

## Feeds worth subscribing to

- `https://karpathy.bearblog.dev/feed/` — Karpathy's primary blog. Ten items, which is
  years of cover at his rate — but it has already lost all three March 2025 posts, so
  count from the archive index at `karpathy.bearblog.dev/blog/`, not from the feed
- `https://karpathy.github.io/feed.xml` — his older blog, active again as of Feb 2026
- `https://github.com/karpathy/<repo>/commits/master.atom` — what he is building.
  **Not** `github.com/karpathy.atom`: that is a valid feed with zero entries, stamped
  2018, and it will never tell you anything
- `https://www.youtube.com/feeds/videos.xml?channel_id=UCXUPKJO5MZQN11PqgIvyuvQ` — his
  channel, which the page's own table omitted. High value, and dormant since Feb 2025
- `https://karpathy.medium.com/feed` — the Medium archive, finished in Nov 2017 with
  *Software 2.0*. The web pages answer 403 to an automated reader; the feed answers 200.
  Read it, don't subscribe
- `https://fusionauth.io/blog/feed.xml` — carries Dan Moore, but it is the whole company
  blog, and it carries every one of his posts. Match on *contains* `Dan Moore`, not equals:
  three posts are co-authored and the feed writes the whole byline into one `<author>` tag
- `https://www.mooreds.com/wordpress/feed` — his personal blog; monthly, and a different
  subject entirely (engineering management and careers, no identity)
- `https://brightlightsfilm.com/category/essays/feed/` — the Bright Lights label that tracks
  what the journal is actually doing: 19 of its 75 articles this year. Any category works
  (`/category/<slug>/feed/`), as does any author (`/author/<slug>/feed/`)
- `https://brightlightsfilm.com/feed/` — the whole journal, ten items deep. Fine for a daily
  reader, lossy if you check in monthly; prefer a category feed
- `https://api.substack.com/feed/podcast/277517.rss` — Krugman's podcast and video, and the
  only deep feed on his site: 101 items back to January 2025
- `https://www.youtube.com/feeds/videos.xml?channel_id=UCjY8KAGllKyZZd2FYF1vbPw` — his
  YouTube channel, which publishes *more* than the Substack does: 547 videos against 101
  posts, because the Substack videos get cut into clips. Expect intermittent failures:
  that endpoint answers a **rate-limited request with 404**, not 429, so a single 404 is
  not evidence the feed is gone — and is how this channel spent a day recorded as empty
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
- `docs/sitemap.xml`, `docs/robots.txt` — the crawl layer. Keep `lastmod` in the
  sitemap in step with the "compiled" date on each page
- `docs/og/*.png` — 1200×630 link-preview cards, one per page
- `tools/make-og-cards.py` — regenerates those cards (see *Search and sharing*)
- `tools/krugman-figures.py` — re-measures every number on the Krugman page
  against its sources (see *Checking the figures*)
- `tools/dan-moore-figures.py` — the same for the Dan Moore page
- `tools/karpathy-figures.py` — the same for the Karpathy page
- `tools/brightlights-figures.py` — the same for the Bright Lights page
- `tools/board-figures.py` — the board states almost nothing of its own, so this
  one compares rather than measures: the board against the four source pages,
  plus its own arithmetic (see *Checking the figures*)

Each source page answers the same questions: where they publish and which channels are
live, how often they actually post, what they are writing about now, what is worth reading
first, and what to discount.

## Search and sharing

Every indexable page carries a unique `<title>` and meta description, a
canonical URL, Open Graph and Twitter card tags with a 1200×630 image, and a
JSON-LD `@graph`. The source pages describe themselves as `Article` with an
`about` entity for the person or publication being indexed, plus a
`BreadcrumbList`; the hub pages use `WebSite`/`CollectionPage` and an `ItemList`
of the four indexes. `docs/sitemap.xml` lists the six indexable pages;
`offline.html` is `noindex` and deliberately absent from it.

Two things are worth knowing:

- **The homepage `<h1>` is not the greeting.** The board rewrites a `<p>` with
  "Good morning / afternoon / evening"; the `<h1>` underneath it is fixed text.
  Search engines render JavaScript, so putting the greeting in the `<h1>` made
  the page's main heading read "Good evening" to a crawler. If you restyle the
  header, keep those two elements distinct.
- **`robots.txt` is inert here.** It is only honoured at the origin root, and
  this is a GitHub Pages *project* page, so `/updating/robots.txt` is ignored.
  The file is kept because it becomes correct the moment the site gets a domain
  of its own. Until then the sitemap is discovered by submitting it in Google
  Search Console and Bing Webmaster Tools.

The link-preview cards are generated, not hand-drawn:

```
pip install Pillow
python3 tools/make-og-cards.py
```

It is *not* a build step — the cards are committed, and it only needs running when
a page is added, renamed or re-pitched. Edit the `CARDS` table at the top of the
script to change what a card says.

## Checking the figures

Every source page states counts, medians and dates, and every one of them was read
from the source's own API rather than recalled. Those numbers go stale, and a stale
number on a page about staying current is the worst kind. Every source page has a script that re-reads its sources:

```
python3 tools/krugman-figures.py --as-of 2026-11-12
```

```
python3 tools/dan-moore-figures.py --as-of 2026-11-13
```

```
python3 tools/karpathy-figures.py --as-of 2026-11-13
```

```
python3 tools/brightlights-figures.py --as-of 2026-11-13
```

```
python3 tools/board-figures.py --live --links
```

The first walks the Substack archive, queries the Stone Center, and prints each
figure the page quotes. `--cache FILE` saves the archive so repeated runs do not
re-walk forty pages. `--channels` re-fetches all 25 URLs behind the page's channel
table — the ones it marks dead included — printing each one's content type beside
its status and **trying twice**, because a failure that clears on the second
attempt was about the client, not the resource. It also prints every active
subscription price, since the publication's own JSON lists two monthly ones and
there is no way to tell from outside which a new subscriber pays. `--links`
follows every outbound link on the page.

The second walks all 23 pages of the FusionAuth author page, reads the company
feed, and reconciles the two slug by slug — which is the check that matters there,
because the page's advice turns on which posts a feed filter catches. It reproduces
the era table from the feed's category tags and probes the Markdown mirror with
both a real slug and a missing one. `--words` adds a fetch per post to re-measure
the medians, `--links` checks that every post the page recommends still resolves,
and `--cache FILE` saves the walk.

The third reads both of his blogs' archive indexes rather than their feeds, because
both feeds are ten items deep and the Bear blog's has already dropped the March 2025
posts — a script measuring the feed would under-report the year and look right doing
it. It also prints each channel's **content type**, since `karpathy.ai/feed.xml` and
`x.com/karpathy/rss` both answer `200` with `text/html`.

That content-type rule has a second half, learned on the Krugman page: **check whether
the status is about the resource at all.** YouTube's feed endpoint answers a
rate-limited request with `404`, not `429`. On 13 November its feed for Krugman's
547-video channel returned a valid Atom document at 23:26 and `404` from 23:33, while
two other channels' feeds still answered `200` from the same machine — and six minutes
later all three were `404`. One probe had already been enough to record a live channel
as having no uploads and no feed. Ask twice, minutes apart, before believing a failure.

The fourth reads the journal's WordPress REST API, where `X-WP-Total` gives a count
without downloading anything, so most of its figures cost one small request each. It
goes through `curl` rather than `urllib`, and that is not a style choice: the host's
CDN answers **403 to HTTP/1.1 and 200 to HTTP/2**, whatever User-Agent you send, and
`urllib` speaks only HTTP/1.1. The failure looks exactly like a blocked scraper.

The fifth is a different kind of check. The board copies its figures from the four
source pages, so it fails in a way none of the others can see: a source page gets
corrected and the board keeps the figure that was just overturned. It had done that
twice by 13 November 2026 — still advertising a 3,700-word median for Bright Lights
two commits after that page was corrected to 2,500, and still flagging a Dan Moore
post as "not in feed" after the audit that proved the feed carries all of them. So
`board-figures.py` compares the board against the source pages, which are the ones
that were actually measured, and keeps a list of claims known to have been
overturned.

It also re-adds the board's own sums. That is worth doing on its own:

```
posts counted across them    3,901
2,929 + 800 + 159 + 14       = 3,902
```

That was live for a day. The addends had been corrected one at a time, each time
correctly, and the total was never re-added — and the Karpathy addend turned out to
be a two-year count sitting in a row of all-time ones. **Check a derived figure's
derivation, not only its parts.** `--board PATH` runs the whole check against an
older copy (`git show HEAD~1:docs/index.html`), which is how you confirm it still
catches what it claims to; a check nobody has watched fail is not a check.

Reconcile by eye, and pass `--as-of` the cutoff in the page's footer or the
year-to-date numbers will not line up.

Stdlib only (the Bright Lights one shells out to `curl`, for the reason above), no
build step, and none of them writes anything into `docs/`.

All five print a little more than the page states, on purpose. Where a figure needs a
judgement — which short Krugman posts are day-off notices, which FusionAuth
categories belong to which table row — the script lists the items instead of
bucketing them, because a regex that confidently contradicts the page is worse
than no check at all.

The service worker deliberately does **not** precache `og/`, `sitemap.xml` or
`robots.txt`: crawlers and link unfurlers read those, visitors never do, and
precaching them would put ~95 KB of dead weight into every install.

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
