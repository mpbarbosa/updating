# updating

A repository to help me find the best sources of information on what is happening in the
world, so that I can stay up to date.

**Live site:** https://mpbarbosa.github.io/updating/

## Sources assessed

| Source | Verdict | Page |
| --- | --- | --- |
| Dan Moore | Worth following, with a filter. 159 posts on FusionAuth's blog since 2020, two thirds of it dev-rel work worth skipping — but since 2025 a fortnightly stream of long explainers on OAuth, identity standards and agent authorization. No per-author feed. | [index](docs/dan-moore.html) |
| Andrej Karpathy | Deep, slow. 11 posts in 2025, 3 in 2026. Two live blogs with separate feeds. Excellent for understanding, poor for news. | [index](docs/karpathy.html) |

## Feeds worth subscribing to

- `https://karpathy.bearblog.dev/feed/` — Karpathy's primary blog
- `https://karpathy.github.io/feed.xml` — his older blog, active again as of Feb 2026
- `https://github.com/karpathy.atom` — repository activity
- `https://fusionauth.io/blog/feed.xml` — carries Dan Moore, but it is the whole company
  blog: filter on `<author>Dan Moore</author>`, and note it is missing three of his 2026 posts
- `https://www.mooreds.com/wordpress/feed` — his personal blog; monthly, and a different
  subject entirely (engineering management and careers, no identity)

## Layout

- `docs/` — the published GitHub Pages site (source: `main` branch, `/docs` folder)
- `docs/index.html` — the hub: every source assessed, with the verdict and the feeds
- `docs/<source>.html` — one page per source
- `docs/style.css` — shared styles for every page

Each source page answers the same questions: where they publish and which channels are
live, how often they actually post, what they are writing about now, what is worth reading
first, and what to discount.

## Previewing locally

```
python3 -m http.server 8731 --directory docs
```

Then open http://localhost:8731/. There is no build step — the pages are plain HTML.
