#!/usr/bin/env python3
"""Re-measure every figure quoted on docs/karpathy.html.

Not a build step: the site has none, and the page is written by hand. Run
this when the index starts to look stale, or before trusting a number on it,
then reconcile the report against the page by eye.

    python3 tools/karpathy-figures.py                  # as of today
    python3 tools/karpathy-figures.py --as-of 2026-11-13
    python3 tools/karpathy-figures.py --links          # +20 requests

Stdlib only. The default run is about a dozen requests and writes nothing.

He publishes on two blogs with separate feeds, and the counts on the page
come from their archive INDEXES, not their feeds: both feeds are ten items
deep, which at his rate has already dropped March 2025 off the Bear blog.
A script that measured the feeds would under-report the year and look right
doing it, so this one reads the indexes and says what the feeds have lost.
"""
import argparse
import html
import re
import statistics as st
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime

BEAR_INDEX = "https://karpathy.bearblog.dev/blog/"
BEAR_FEED = "https://karpathy.bearblog.dev/feed/"
GH_PAGES_FEED = "https://karpathy.github.io/feed.xml"
GH_USER_FEED = "https://github.com/karpathy.atom"
GH_REPO_FEED = "https://github.com/karpathy/nanochat/commits/master.atom"
GH_API = "https://api.github.com/users/karpathy/repos?sort=pushed&per_page=5"
YT_FEED = ("https://www.youtube.com/feeds/videos.xml"
           "?channel_id=UCXUPKJO5MZQN11PqgIvyuvQ")

# A browser UA: some of these serve 403 to the urllib default.
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")

# Every channel the page lists. The last two are the point of the exercise:
# both answer 200 to a feed-shaped URL and hand back a web page, so a check
# that reads the status code alone calls them live. Read the content type.
CHANNELS = [
    ("bear blog", BEAR_FEED, True),
    ("karpathy.github.io", GH_PAGES_FEED, True),
    ("github, user", GH_USER_FEED, True),
    ("github, one repo", GH_REPO_FEED, True),
    ("youtube", YT_FEED, True),
    # The site answers 403 to an automated reader; this feed answers 200 and
    # carries the whole archive. Probing the site and calling Medium closed
    # is how the page came to say it could not be enumerated.
    ("medium, feed", "https://karpathy.medium.com/feed", True),
    ("medium, site", "https://karpathy.medium.com/", False),
    ("karpathy.ai", "https://karpathy.ai/feed.xml", False),
    ("x.com", "https://x.com/karpathy/rss", False),
]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace"), r.status, r.headers


def feed_entries(body):
    """(date, title) for an Atom or an RSS feed, oldest last."""
    out = []
    for raw in re.findall(r"(?s)<entry>(.*?)</entry>", body):
        t = re.search(r"(?s)<title[^>]*>(.*?)</title>", raw)
        d = (re.search(r"(?s)<published>(.*?)</published>", raw)
             or re.search(r"(?s)<updated>(.*?)</updated>", raw))
        out.append((d.group(1)[:10] if d else "?",
                    html.unescape(t.group(1)).strip() if t else "?"))
    for raw in re.findall(r"(?s)<item>(.*?)</item>", body):
        t = re.search(r"(?s)<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", raw)
        d = re.search(r"(?s)<pubDate>(.*?)</pubDate>", raw)
        when = "?"
        if d:
            for f in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
                try:
                    when = datetime.strptime(d.group(1).strip(), f).date().isoformat()
                    break
                except ValueError:
                    pass
        out.append((when, html.unescape(t.group(1)).strip() if t else "?"))
    return out


def bear_index():
    """Every post on the Bear blog, from its own archive index.

    This is the list the page counts. The feed holds ten, which is fine for
    reading him and useless for counting him.
    """
    body, _, _ = get(BEAR_INDEX)
    posts = {}
    for m in re.finditer(
            r'(?s)<time[^>]*>(.*?)</time>.{0,200}?href="(/[^"]+/)"[^>]*>(.*?)</a>',
            body):
        raw = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        try:                                        # "01 Oct, 2025"
            d = datetime.strptime(raw, "%d %b, %Y").date().isoformat()
        except ValueError:
            d = raw
        posts[m.group(2)] = (d, html.unescape(
            re.sub(r"<[^>]+>", "", m.group(3))).strip())
    return sorted(posts.values())


def section(title):
    print("\n" + title)
    print("-" * len(title))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--as-of", default=date.today().isoformat(),
                    help="cutoff for the 'since last post' figure (YYYY-MM-DD)")
    ap.add_argument("--links", action="store_true",
                    help="check that every post the page links still resolves")
    args = ap.parse_args()
    cutoff = date.fromisoformat(args.as_of)

    bear = bear_index()
    gh_body, _, _ = get(GH_PAGES_FEED)
    gh = sorted(feed_entries(gh_body))
    bear_feed = sorted(feed_entries((get(BEAR_FEED))[0]))

    section("The Bear blog: index against feed")
    print("  posts on the archive index   %d  (%s to %s)" % (
        len(bear), bear[0][0], bear[-1][0]))
    print("  entries in the feed          %d" % len(bear_feed))
    lost = [p for p in bear if p[1] not in {t for _, t in bear_feed}]
    print("  on the index, not in the feed %d:" % len(lost))
    for d, t in lost:
        print("    %s  %s" % (d, t[:58]))

    section("karpathy.github.io")
    print("  entries in the feed          %d  (%s to %s)" % (
        len(gh), gh[0][0], gh[-1][0]))
    print("  newest                       %s  %s" % (gh[-1][0], gh[-1][1][:48]))

    # Count both blogs together: that is what the page's chart covers.
    both = sorted(bear + gh)
    dated = [(d, t) for d, t in both if re.match(r"\d{4}-\d{2}-\d{2}", d)]
    section("Both blogs, by year")
    per = Counter(d[:4] for d, _ in dated)
    print("  " + ", ".join("%s: %d" % (y, per[y]) for y in sorted(per)))

    year = cutoff.year
    section("The chart window: %d to %s" % (year - 1, cutoff))
    window = [(d, t) for d, t in dated if d >= "%d-01-01" % (year - 1)
              and d <= cutoff.isoformat()]
    months = Counter(d[:7] for d, _ in window)
    for y in (year - 1, year):
        got = [(m, months.get("%d-%02d" % (y, m), 0)) for m in range(1, 13)]
        print("  %d  %s" % (y, " ".join(
            "%s%d" % (date(y, m, 1).strftime("%b")[0], n)
            for m, n in got if n)))
        print("      total %d" % sum(n for _, n in got))
    print("  every post in the window, newest first:")
    for d, t in reversed(window):
        print("    %s  %s" % (d, t[:58]))

    section("Cadence")
    days = [date.fromisoformat(d) for d, _ in dated]
    print("  last post                    %s  (%d days before %s)" % (
        days[-1], (cutoff - days[-1]).days, cutoff))
    this = [d for d in days if d.year == year and d <= cutoff]
    if len(this) > 1:
        gaps = [(b - a).days for a, b in zip(this, this[1:])]
        big = gaps.index(max(gaps))
        print("  longest %d gap              %d days (%s to %s), %.1f months" % (
            year, max(gaps), this[big], this[big + 1], max(gaps) / 30.44))
        print("  median %d gap               %d days" % (year, st.median(gaps)))

    section("Channels")
    # A feed is XML. Status 200 with text/html is a web page wearing a feed's
    # URL, and the page names two of those; print the type so they cannot be
    # mistaken for live-but-empty feeds.
    for name, url, expect_feed in CHANNELS:
        try:
            body, status, h = get(url)
            ctype = h.get("Content-Type", "?").split(";")[0]
        except urllib.error.HTTPError as e:
            print("  %-21s %3s  (no feed)" % (name, e.code))
            continue
        except Exception as e:                      # noqa: BLE001 - report, continue
            print("  %-21s  --  %s" % (name, e))
            continue
        entries = feed_entries(body)
        is_xml = "xml" in ctype or body.lstrip().startswith("<?xml")
        verdict = ("%d entries" % len(entries) if is_xml
                   else "NOT A FEED: %s" % ctype)
        newest = max((d for d, _ in entries if d != "?"), default="-")
        print("  %-21s %3s  %-22s %-26s newest %s" % (
            name, status, ctype, verdict, newest))
        if expect_feed and is_xml and not entries:
            upd = re.search(r"(?s)<updated>(.*?)</updated>", body)
            print("    %s: a valid feed carrying nothing; <updated> says %s"
                  % (name, upd.group(1)[:10] if upd else "?"))

    section("GitHub: he pushes, the user feed does not say so")
    try:
        import json
        body, _, _ = get(GH_API)
        for r in json.loads(body):
            print("  %s  %s" % (r["pushed_at"][:10], r["name"]))
    except Exception as e:                          # noqa: BLE001
        print("  -- %s" % e)

    if args.links:
        section("Every post the page links")
        page = open("docs/karpathy.html", encoding="utf-8").read()
        urls = sorted(set(re.findall(
            r'href="(https://(?:karpathy\.bearblog\.dev|karpathy\.github\.io)'
            r'/[^"#?]+)"', page)))
        for url in urls:
            try:
                _, status, _ = get(url)
                print("  %3s  %s" % (status, url))
            except urllib.error.HTTPError as e:
                print("  %3s  %s  <- the page links this" % (e.code, url))


if __name__ == "__main__":
    main()
