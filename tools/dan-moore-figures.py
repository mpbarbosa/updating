#!/usr/bin/env python3
"""Re-measure every figure quoted on docs/dan-moore.html.

Not a build step: the site has none, and the page is written by hand. Run
this when the index starts to look stale, or before trusting a number on it,
then reconcile the report against the page by eye.

    python3 tools/dan-moore-figures.py                    # as of today
    python3 tools/dan-moore-figures.py --as-of 2026-11-13
    python3 tools/dan-moore-figures.py --cache /tmp/dm.json
    python3 tools/dan-moore-figures.py --words            # +160 requests
    python3 tools/dan-moore-figures.py --links            # +27 requests

Stdlib only. The default run is the author page (23 requests) and the blog
feed (one); --words fetches every post to count them and --links checks the
posts the page recommends, so neither is on by default.

Every figure the page states should appear below it. Where the page and this
script disagree, this script is the one that just asked the source -- but
check the window first: the page fixes its 2026 statistics to a stated cutoff
so they stay reproducible, and --as-of must match that cutoff to compare.
"""
import argparse
import html
import json
import os
import re
import statistics as st
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime

AUTHOR = "https://fusionauth.io/blog/author/dan-moore"
FEED = "https://fusionauth.io/blog/feed.xml"
BLUESKY = ("https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile"
           "?actor=mooreds.com")
NAME = "Dan Moore"

# A browser UA: the site serves 403 to the urllib default.
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")

# The eras the page's "What he writes" table splits on, and the feed
# <category> each of its rows counts. These are NOT a partition: a post
# carries several categories (Product and Community are the common pair),
# so these five rows do not sum to the era totals and must not be made to.
ERAS = [("2020-22", 2020, 2022), ("2023-24", 2023, 2024), ("2025-26", 2025, 2026)]
KINDS = [("Education - explainers", "Education"),
         ("Customer case studies", "Community"),
         ("Release announcements", "Release Updates"),
         ("Step-by-step tutorials", "Tutorial"),
         ("Conference trailers", "Events")]

# Every channel the page lists, including the one it calls finished.
# Checking that one is the point: "finished" is a claim with a shelf life.
FEEDS = [
    ("fusionauth blog", FEED),
    ("mooreds.com", "https://www.mooreds.com/wordpress/feed"),
    ("bluesky", "https://bsky.app/profile/mooreds.com/rss"),
    ("github", "https://github.com/mooreds.atom"),
    ("letters (finished)", "https://letterstoanewdeveloper.com/feed/"),
]


def get(url, want_json=False, method="GET"):
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method=method)
    with urllib.request.urlopen(req, timeout=40) as r:
        body = r.read().decode("utf-8", "replace")
        return (json.loads(body) if want_json else body), r.status, r.headers


def walk_author_page():
    """Every slug on the author page, in order, with the page it came from.

    The pagination is /blog/author/dan-moore/N -- not /page/N/, which is the
    shape the rest of the site uses and which 404s here.
    """
    order, seen, pages = [], set(), 0
    skip = re.compile(r"^/blog/(author|category|tag|page)\b"
                      r"|^/blog/feed\.xml$|^/blog/?$")
    for p in range(1, 40):
        url = AUTHOR + ("" if p == 1 else "/%d" % p)
        try:
            body, _, _ = get(url)
        except urllib.error.HTTPError as e:
            sys.stderr.write("\n  page %d: HTTP %s, stopping\n" % (p, e.code))
            break
        pages = p
        links = [l.rstrip("/") for l in re.findall(r'href="(/blog/[^"#?]*)"', body)
                 if not skip.match(l)]
        new = [l for l in dict.fromkeys(links) if l not in seen]
        for l in new:
            seen.add(l)
            order.append((p, l))
        sys.stderr.write("\r  %d pages, %d posts" % (pages, len(seen)))
        if not new:
            break
        time.sleep(0.35)
    sys.stderr.write("\n")
    return pages, order


def read_feed():
    """Every item in the company feed, with its whole byline and categories."""
    body, _, _ = get(FEED)
    items = []
    for raw in re.findall(r"<item>(.*?)</item>", body, re.S):
        def one(tag):
            m = re.search(r"<%s>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</%s>"
                          % (tag, tag), raw, re.S)
            return html.unescape(m.group(1)).strip() if m else ""
        items.append({
            "title": one("title"),
            "slug": re.sub(r"^https?://fusionauth\.io", "", one("link")).rstrip("/"),
            "byline": one("author"),
            "date": one("pubDate"),
            "cats": [html.unescape(c).strip() for c in re.findall(
                r"<category>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</category>", raw, re.S)],
        })
    return items


def when(s):
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def words_of(slug):
    """Approximate body word count. Validate it, do not trust it blind.

    The page states a word count for each post it recommends; compare a
    handful of those against this column before believing a median that
    contradicts the page.
    """
    body, _, _ = get("https://fusionauth.io" + slug)
    m = (re.search(r"(?s)<article[^>]*>(.*?)</article>", body)
         or re.search(r"(?s)<main[^>]*>(.*?)</main>", body))
    txt = m.group(1) if m else body
    txt = re.sub(r"(?s)<(script|style|nav|footer|svg)\b.*?</\1>", " ", txt)
    return len(re.sub(r"<[^>]+>", " ", html.unescape(txt)).split())


def section(title):
    print("\n" + title)
    print("-" * len(title))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--as-of", default=date.today().isoformat(),
                    help="cutoff for the 'since last post' and 2026 figures")
    ap.add_argument("--cache", help="read/write the author page and feed here")
    ap.add_argument("--words", action="store_true",
                    help="fetch every post and count its words (~160 requests)")
    ap.add_argument("--links", action="store_true",
                    help="check that every post the page recommends resolves")
    args = ap.parse_args()
    cutoff = date.fromisoformat(args.as_of)

    if args.cache and os.path.exists(args.cache):
        d = json.load(open(args.cache))
        pages, order, feed = d["pages"], d["order"], d["feed"]
        print("author page and feed from cache %s" % args.cache)
    else:
        print("walking the author page (~23 requests)...")
        pages, order = walk_author_page()
        feed = read_feed()
        if args.cache:
            json.dump({"pages": pages, "order": order, "feed": feed},
                      open(args.cache, "w"))

    slugs = [s for _, s in order]
    mine = [i for i in feed if NAME in i["byline"]]
    exact = [i for i in mine if i["byline"] == NAME]
    shared = [i for i in mine if i["byline"] != NAME]
    for i in feed:
        i["_d"] = when(i["date"])

    section("The author page")
    print("  pages walked           %d" % pages)
    print("  distinct posts         %d" % len(slugs))

    # The page's central claim is about the filter, so report both filters
    # and name every co-authored item: that difference IS the finding.
    section("The feed, and what a filter catches")
    print("  items in the feed      %d" % len(feed))
    print("  author contains %-6s %d" % ('"' + NAME + '"', len(mine)))
    print("  author equals   %-6s %d  <- an equals filter loses %d"
          % ('"' + NAME + '"', len(exact), len(mine) - len(exact)))
    for i in sorted(shared, key=lambda i: i["_d"] or date.min):
        print("    %s  %-28s  byline: %s"
              % (i["_d"], i["slug"].replace("/blog/", "")[:28], i["byline"]))

    section("Author page against feed, slug by slug")
    fs = {i["slug"] for i in mine}
    missing = [s for s in slugs if s not in fs]
    extra = sorted(fs - set(slugs))
    print("  on the author page, not in the feed   %d" % len(missing))
    for s in missing:
        print("    %s" % s)
    print("  in the feed, not on the author page   %d" % len(extra))
    for s in extra:
        print("    %s" % s)

    # From here on, count the set the PAGE counts: the author page's posts,
    # dated from the feed. The feed's contains-filter holds one post more --
    # see the reconciliation above -- and counting that one would put every
    # year and era total one ahead of the page for no stated reason.
    dated = [i for i in mine if i["_d"] and i["slug"] in set(slugs)]
    print("\n  counting the %d author-page posts below, not the %d the feed"
          % (len(dated), len(mine)))
    print("  matches; the difference is the co-authored post listed above.")

    section("Posts per year")
    per = Counter(i["_d"].year for i in dated)
    print("  " + ", ".join("%d: %d" % (y, per[y]) for y in sorted(per)))
    print("  oldest                 %s" % min(i["_d"] for i in dated))
    print("  newest                 %s  (%d days before %s)" % (
        max(i["_d"] for i in dated),
        (cutoff - max(i["_d"] for i in dated)).days, cutoff))

    section("What he writes, by era")
    print("  %-24s %10s %10s %10s" % ("", *[e[0] for e in ERAS]))
    buckets = [[i for i in dated if lo <= i["_d"].year <= hi] for _, lo, hi in ERAS]
    print("  %-24s %10d %10d %10d" % ("posts in the era",
                                      *[len(b) for b in buckets]))
    for lab, cat in KINDS:
        print("  %-24s %10d %10d %10d" % (
            lab, *[sum(1 for i in b if cat in i["cats"]) for b in buckets]))
    print("  (categories overlap; these rows are not a partition of the era)")

    section("Cadence")
    year = cutoff.year
    this = sorted(i["_d"] for i in dated if i["_d"].year == year
                  and i["_d"] <= cutoff)
    print("  posts in %d so far     %d" % (year, len(this)))
    if len(this) > 1:
        gaps = [(b - a).days for a, b in zip(this, this[1:])]
        print("  median gap, %d        %d days" % (year, st.median(gaps)))
        print("  longest silence, %d   %d days (%s to %s)" % (
            year, max(gaps), this[gaps.index(max(gaps))],
            this[gaps.index(max(gaps)) + 1]))
    for lab, cat in [("release announcement", "Release Updates"),
                     ("conference trailer", "Events")]:
        got = [i for i in dated if cat in i["cats"]]
        if got:
            last = max(got, key=lambda i: i["_d"])
            print("  last %-20s %s  %s" % (lab, last["_d"], last["title"][:44]))

    if args.words:
        section("Word counts")
        counts = {}
        for n, s in enumerate(slugs, 1):
            try:
                counts[s] = words_of(s)
            except Exception:                       # noqa: BLE001 - keep going
                counts[s] = None
            sys.stderr.write("\r  %d/%d" % (n, len(slugs)))
            time.sleep(0.35)
        sys.stderr.write("\n")
        ok = {s: v for s, v in counts.items() if v}
        print("  measured               %d of %d" % (len(ok), len(slugs)))
        print("  median, all time       %.0f" % st.median(ok.values()))
        recent = {i["slug"]: ok[i["slug"]] for i in dated
                  if i["_d"].year >= 2025 and i["slug"] in ok}
        if recent:
            v = sorted(recent.values())
            print("  median, 2025-26        %.0f  (range %d to %d over %d posts)"
                  % (st.median(v), v[0], v[-1], len(v)))
        print("  the ten longest, to check against the page's own figures:")
        for s, v in sorted(ok.items(), key=lambda kv: -kv[1])[:10]:
            print("    %6d  %s" % (v, s))

    if args.links:
        section("Every post the page recommends")
        page = open("docs/dan-moore.html", encoding="utf-8").read()
        for url in sorted(set(re.findall(
                r'href="(https://fusionauth\.io/blog/[^"#?]+)"', page))):
            if "/author/" in url or url.endswith("feed.xml"):
                continue
            try:
                _, status, _ = get(url, method="HEAD")
                print("  %3s  %s" % (status, url.replace("https://fusionauth.io", "")))
            except urllib.error.HTTPError as e:
                print("  %3s  %s  <- the page links this" % (
                    e.code, url.replace("https://fusionauth.io", "")))

    section("Channels")
    for name, url in FEEDS:
        try:
            body, status, _ = get(url)
            items = len(re.findall(r"<(?:item|entry)[ >]", body))
            dates = (re.findall(r"<pubDate>([^<]+)</pubDate>", body)
                     or re.findall(r"<updated>([^<]+)</updated>", body))
            print("  %-19s %3s  %3d items  newest %s" % (
                name, status, items, (dates[0] if dates else "-")[:31]))
        except urllib.error.HTTPError as e:
            print("  %-19s %3s" % (name, e.code))
        except Exception as e:                      # noqa: BLE001 - report, continue
            print("  %-19s  --  %s" % (name, e))
    try:
        d, _, _ = get(BLUESKY, want_json=True)
        print("  %-19s      %s posts, %s following, %s followers" % (
            "bluesky profile", d.get("postsCount"), d.get("followsCount"),
            d.get("followersCount")))
    except Exception as e:                          # noqa: BLE001
        print("  %-19s  --  %s" % ("bluesky profile", e))

    # The page makes a claim about this URL shape, so it has to be probed:
    # an LLM-friendly .md mirror would change how the blog is worth reading.
    section("The Markdown mirror")
    # Probe a real slug AND a missing one, in that order. A single probe
    # against a slug that does not exist returns the site's 404 page and
    # reads exactly like "there is no mirror" -- which is how this page came
    # to say so for a day. The pair distinguishes the two.
    real = slugs[0] if slugs else "/blog/what-is-scim"
    for lab, url in [("a post that exists", "https://fusionauth.io" + real + ".md"),
                     ("one that does not",
                      "https://fusionauth.io/blog/no-such-post-xyz.md"),
                     ("the blog's index", "https://fusionauth.io/blog/llms.txt"),
                     ("the site's index", "https://fusionauth.io/llms.txt")]:
        try:
            body, status, h = get(url)
            code, ctype = status, h.get("Content-Type", "?")
        except urllib.error.HTTPError as e:
            body, code, ctype = (e.read().decode("utf-8", "replace"), e.code,
                                 e.headers.get("Content-Type", "?"))
        title = re.search(r"<title>(.*?)</title>", body, re.S)
        print("  %-19s %3s  %-26s %6d bytes%s" % (
            lab, code, ctype.split(";")[0], len(body),
            "  title %r" % html.unescape(title.group(1)).strip() if title else ""))
    # The index is what a reader would want for following one author. It is
    # not: it carries titles and descriptions, no bylines. Measure, do not
    # assume -- if that ever changes, the feed stops being the only filter.
    try:
        body, _, _ = get("https://fusionauth.io/blog/llms.txt")
        print("  index entries        %d, of which naming him %d"
              % (len(re.findall(r"^- \[", body, re.M)),
                 len(re.findall(NAME, body))))
    except Exception as e:                          # noqa: BLE001
        print("  index entries        -- %s" % e)


if __name__ == "__main__":
    main()
