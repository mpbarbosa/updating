#!/usr/bin/env python3
"""Re-measure every figure quoted on docs/krugman.html.

Not a build step: the site has none, and the page is written by hand. Run
this when the index starts to look stale, or before trusting a number on it,
then reconcile the report against the page by eye.

    python3 tools/krugman-figures.py                 # as of today
    python3 tools/krugman-figures.py --as-of 2026-11-12
    python3 tools/krugman-figures.py --cache /tmp/archive.json
    python3 tools/krugman-figures.py --channels      # every channel in the table
    python3 tools/krugman-figures.py --links         # every outbound link on the page

Stdlib only. The archive walk is ~40 cursor-paginated requests and the
publication rate-limits after roughly sixty, so --cache is worth using while
iterating; it writes the file on the first run and reads it afterwards.

Every figure the page states should appear below it. Where the page and this
script disagree, this script is the one that just asked the source -- but
check the window first: the page fixes its 2026 statistics to a stated cutoff
so they stay reproducible, and --as-of must match that cutoff to compare.

Two things --channels prints that a status code alone would hide:

  * the CONTENT TYPE. karpathy.ai/feed.xml and x.com/karpathy/rss both answer
    200 with text/html; they are web pages wearing a feed's URL. A checker
    reading the status alone prints a dead channel as live.

  * a SECOND attempt at anything that failed. YouTube's feed endpoint answers
    a rate-limited request with 404, not 429 -- so a single 404 from it says
    nothing about whether the feed exists. That is not a hypothetical: this
    page recorded his 547-video channel as having no uploads and no feed for
    a day on the strength of one such 404, while YouTube's own channel
    metadata was advertising the feed URL the whole time. Two attempts a
    minute apart will usually separate "throttled" from "gone"; neither will
    if you only ever ask once.
"""
import argparse
import json
import os
import pathlib
import re
import statistics as st
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime

ARCHIVE = "https://paulkrugman.substack.com/api/v1/archive"
STONE = "https://stonecenter.gc.cuny.edu/wp-json/wp/v2/posts"
RELAUNCH = date(2024, 12, 11)

# A browser UA: the publication serves 403 to the urllib default.
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")

# Every channel the page lists, plus the three it marks dead. Checking the
# dead ones is the point: "dead" is a claim with a shelf life.
FEEDS = [
    ("substack, main",    "https://paulkrugman.substack.com/feed"),
    ("podcast, numbered", "https://api.substack.com/feed/podcast/277517.rss"),
    ("podcast shortcut",  "https://paulkrugman.substack.com/feed/podcast"),
    ("stone center",      "https://stonecenter.gc.cuny.edu/?s=krugman&feed=rss2"),
    ("bluesky",           "https://bsky.app/profile/pkrugman.bsky.social/rss"),
    ("korean mirror",     "https://pk2kr.substack.com/feed"),
]

# His YouTube channel id, as the channel's own metadata reports it (the
# channelMetadataRenderer on /@PKrugman gives both the id and this exact
# feed URL). The ?user=PKrugman form 404s even when the channel_id form
# works -- both were measured in the same minute, before any throttling --
# so use channel_id, and read the --channels note above about its 404s.
YT_CHANNEL = "UCjY8KAGllKyZZd2FYF1vbPw"

# Every row of the page's channel table, live and dead, in its order. The
# dead ones are the point: "dead" is a claim with a shelf life, and it had
# expired on more than one page in this repository before anyone re-asked.
CHANNELS = [
    ("substack, main feed", "https://paulkrugman.substack.com/feed"),
    ("substack, about",     "https://paulkrugman.substack.com/about"),
    ("substack, archive",   "https://paulkrugman.substack.com/archive"),
    ("substack, podcast",   "https://paulkrugman.substack.com/podcast"),
    ("podcast feed",        "https://api.substack.com/feed/podcast/277517.rss"),
    ("podcast shortcut",    "https://paulkrugman.substack.com/feed/podcast"),
    ("archive API",         ARCHIVE + "?sort=new&limit=1"),
    ("stone center feed",   "https://stonecenter.gc.cuny.edu/?s=krugman&feed=rss2"),
    ("apple podcasts",      "https://podcasts.apple.com/us/podcast/"
                            "paul-krugman-podcast/id1877144831"),
    ("apple, episode count", "https://itunes.apple.com/lookup?id=1877144831"
                             "&entity=podcastEpisode&limit=200"),
    ("notes, his nav link", "https://paulkrugman.substack.com/notes"),
    ("notes, where it lives", "https://substack.com/@paulkrugman/notes"),
    ("bluesky feed",        "https://bsky.app/profile/pkrugman.bsky.social/rss"),
    ("bluesky profile API", "https://public.api.bsky.app/xrpc/"
                            "app.bsky.actor.getProfile?actor=pkrugman.bsky.social"),
    ("korean mirror feed",  "https://pk2kr.substack.com/feed"),
    ("youtube channel",     "https://www.youtube.com/@PKrugman"),
    ("youtube feed",        "https://www.youtube.com/feeds/videos.xml?channel_id="
                            + YT_CHANNEL),
    ("youtube feed, ?user", "https://www.youtube.com/feeds/videos.xml?user=PKrugman"),
    ("x",                   "https://x.com/paulkrugman"),
    ("project syndicate",   "https://www.project-syndicate.org/columnist/paul-krugman"),
    ("project syndicate feed", "https://www.project-syndicate.org/rss/"
                               "author/paul-krugman"),
    ("nyt column",          "https://www.nytimes.com/column/paul-krugman"),
    ("nyt blog archive",    "https://archive.nytimes.com/krugman.blogs.nytimes.com/"),
    ("nyt blog, first post", "https://archive.nytimes.com/"
                             "krugman.blogs.nytimes.com/2007/09/18/introducing-this-blog/"),
    ("mit page",            "https://web.mit.edu/krugman/www/"),
]


def get(url, want_json=True):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        body = r.read().decode("utf-8", "replace")
        return (json.loads(body) if want_json else body), r.status, r.headers


def probe(url, tries=2, pause=25):
    """Status, content type and body for one URL, retried once.

    The retry is the whole point; see the note in the module docstring. A
    failure that clears on a second attempt was about the client, and
    reporting the first one as the resource's verdict is how this page came
    to call a live channel empty.
    """
    last = None
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                body = r.read().decode("utf-8", "replace")
                return r.status, r.headers.get("Content-Type", "-"), body, attempt
        except urllib.error.HTTPError as ex:
            ct = ex.headers.get("Content-Type", "-") if ex.headers else "-"
            last = (ex.code, ct, "", attempt)
        except Exception as ex:                     # noqa: BLE001 - report, continue
            last = ("--", type(ex).__name__ + ": " + str(ex)[:40], "", attempt)
        if attempt < tries:
            time.sleep(pause)
    return last


def report_channels():
    section("Channels: status, content type, and a second try for anything that failed")
    print("  %-24s %4s  %-34s %s" % ("channel", "code", "content-type", "shape"))
    for name, url in CHANNELS:
        status, ctype, body, attempt = probe(url)
        shape = ""
        if body:
            n = len(re.findall(r"<item[ >]", body)) or len(re.findall(r"<entry[ >]", body))
            if n:
                shape = "%d items" % n
            elif body.lstrip().startswith("{"):
                shape = "%d bytes of JSON" % len(body)
            else:
                shape = "%d bytes" % len(body)
        ok = status == 200
        if attempt > 1:
            flag = "  (passed on retry)" if ok else "  (still failing after 2 tries)"
        else:
            flag = ""
        # Only a 200 can be a page wearing a feed's URL. Printing this
        # against a 404 would be the very mistake the docstring warns
        # about: reading a status that is about the client as a verdict
        # on the resource.
        warn = ""
        if ok and "xml" not in (ctype or "") and ("feed" in name or "rss" in url):
            warn = "   <-- 200 but NOT XML: a page wearing a feed's URL"
        elif not ok and ("feed" in name or "rss" in url):
            warn = "   <-- a failure, not a verdict: ask again later"
        print("  %-24s %4s  %-34s %s%s%s" % (
            name, status, (ctype or "-")[:34], shape, flag, warn))

    section("Every active subscription price")
    print("  The page quotes $7/$70/$210. The publication's own JSON lists more than")
    print("  one active pair; print them all rather than picking the one that agrees.")
    try:
        _, _, body, _ = probe("https://paulkrugman.substack.com/")
        plans, seen = [], set()
        for m in re.finditer(r'"id"\s*:\s*"([a-z0-9]+usd)"[^{}]{0,200}?'
                             r'"amount"\s*:\s*(\d+)[^{}]{0,120}?'
                             r'"interval"\s*:\s*"(\w+)"', body):
            key = m.groups()
            if key in seen:
                continue
            seen.add(key)
            plans.append(key)
        for plan_id, amount, interval in plans:
            print("    %-20s $%-9.2f per %s" % (plan_id, int(amount) / 100, interval))
        if len({p[1] for p in plans if p[2] == "month"}) > 1:
            print("    NOTE: two monthly amounts are active at once. Which one a new")
            print("          subscriber is charged cannot be read from outside, and")
            print("          finding out means subscribing. Do not guess on the page.")
    except Exception as ex:                         # noqa: BLE001
        print("    -- could not read the plans: %s" % ex)


def report_links(page="docs/krugman.html"):
    section("Every outbound link on " + page)
    try:
        html = pathlib.Path(page).read_text(encoding="utf-8")
    except OSError as ex:
        print("  -- %s" % ex)
        return
    urls = sorted({u.replace("&amp;", "&") for u in
                   re.findall(r'href="(https?://[^"]+)"', html)})
    skip = ("fonts.googleapis.com", "fonts.gstatic.com", "mpbarbosa.com",
            "github.com/mpbarbosa", "linkedin.com/in/mpbarbosa",
            "mpbarbosa.github.io")
    checked = [u for u in urls if not any(s in u for s in skip)]
    bad = 0
    for u in checked:
        status, _, _, attempt = probe(u, tries=2)
        if status != 200:
            bad += 1
            print("  %-4s %s" % (status, u))
    print("  %d links checked, %d not 200%s" % (
        len(checked), bad, " -- every one resolves" if not bad else ""))


def walk_archive():
    """Every post, oldest first. Cursor-paginated; limit=20 is the ceiling."""
    posts, seen, cursor, pages = [], set(), None, 0
    while True:
        q = {"sort": "new", "limit": "20"}
        if cursor:
            q["cursor"] = cursor
        d, _, _ = get(ARCHIVE + "?" + urllib.parse.urlencode(q))
        fresh = [p for p in d.get("posts", []) if p["id"] not in seen]
        seen.update(p["id"] for p in fresh)
        posts.extend(fresh)
        pages += 1
        cursor = d.get("nextCursor")
        sys.stderr.write("\r  %d pages, %d posts" % (pages, len(posts)))
        if not cursor or not fresh or pages > 60:
            break
        time.sleep(0.6)
    sys.stderr.write("\n")
    posts.sort(key=lambda p: p["post_date"])
    return posts


def when(p):
    return datetime.strptime(p["post_date"][:19], "%Y-%m-%dT%H:%M:%S")


def classify(rows):
    """The four kinds the page's 'What changed' table counts."""
    video = [p for p in rows if p.get("type") == "podcast"]
    text = [p for p in rows if p.get("type") != "podcast"]
    paid = [p for p in text if p.get("audience") == "only_paid"]
    free = [p for p in text if p.get("audience") != "only_paid"]
    short = [p for p in free if (p.get("wordcount") or 0) < 100]
    long_ = [p for p in free if (p.get("wordcount") or 0) >= 100]
    return long_, paid, video, short


def section(title):
    print("\n" + title)
    print("-" * len(title))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--as-of", default=date.today().isoformat(),
                    help="cutoff for year-to-date figures (YYYY-MM-DD)")
    ap.add_argument("--cache", help="read/write the archive JSON here")
    ap.add_argument("--channels", action="store_true",
                    help="re-fetch every channel in the page's table, with content "
                         "types, retries and the active subscription prices")
    ap.add_argument("--links", action="store_true",
                    help="follow every outbound link on docs/krugman.html")
    args = ap.parse_args()
    cutoff = date.fromisoformat(args.as_of)
    year = cutoff.year

    # Either of these answers on its own, without the forty-page archive walk,
    # so that checking a channel does not cost a rate limit.
    if args.channels or args.links:
        if args.channels:
            report_channels()
        if args.links:
            report_links()
        return

    if args.cache and os.path.exists(args.cache):
        posts = json.load(open(args.cache))
        print("archive: %d posts from cache %s" % (len(posts), args.cache))
    else:
        print("walking the archive (~40 requests)...")
        posts = walk_archive()
        if args.cache:
            json.dump(posts, open(args.cache, "w"))

    for p in posts:
        p["_d"] = when(p)
    posts.sort(key=lambda p: p["_d"])          # a cache may hold any order

    section("Totals")
    pre = [p for p in posts if p["_d"].date() < RELAUNCH]
    since = [p for p in posts if RELAUNCH <= p["_d"].date() <= cutoff]
    days = (cutoff - RELAUNCH).days
    words = sum(p.get("wordcount") or 0 for p in since)
    print("  archive, all time      %d posts" % len(posts))
    print("  before the relaunch    %d (%s to %s)" % (
        len(pre), pre[0]["_d"].date() if pre else "-",
        pre[-1]["_d"].date() if pre else "-"))
    print("  since the relaunch     %d posts over %d days, %.2f a day" % (
        len(since), days, len(since) / days))
    print("  words since relaunch   %s (%.2f million)" % (
        format(words, ","), words / 1e6))

    ytd = [p for p in posts if p["_d"].year == year and p["_d"].date() <= cutoff]
    doy = (cutoff - date(year, 1, 1)).days + 1
    wc = [p["wordcount"] for p in ytd if p.get("wordcount")]
    by_day = Counter(p["_d"].date() for p in ytd)
    section("%d, 1 January to %s" % (year, cutoff))
    print("  items                  %d across %d of %d days, %.2f a day" % (
        len(ytd), len(by_day), doy, len(ytd) / doy))
    print("  median words           %.0f" % st.median(wc))
    print("  days carrying two      %d" % sum(1 for n in by_day.values() if n >= 2))

    section("Cadence")
    months = Counter(p["_d"].month for p in ytd)
    full = [m for m in months if m < cutoff.month]
    print("  per month              %s" % ", ".join(
        "%d:%d" % (m, months[m]) for m in sorted(months)))
    if full:
        print("  full months, min/max   %d / %d" % (
            min(months[m] for m in full), max(months[m] for m in full)))
    prev, longest = date(year, 1, 1), (None, 0)
    for d in sorted(by_day):
        if (d - prev).days > longest[1]:
            longest = (prev, (d - prev).days)
        prev = d
    print("  longest silence        %d days, after %s" % (longest[1], longest[0]))
    # The page claims a posting window; state both so the claim is checkable.
    mins = [p["_d"].hour * 60 + p["_d"].minute for p in ytd]
    for lo, hi, lab in [(630, 690, "10:30-11:30"), (600, 720, "10:00-12:00")]:
        print("  posted %s UTC   %d of %d" % (
            lab, sum(1 for m in mins if lo <= m <= hi), len(ytd)))

    section("Mix, the same calendar window a year apart")
    print("  %-26s %8s %8s" % ("kind", year - 1, year))
    prior = [p for p in posts if p["_d"].year == year - 1
             and (p["_d"].month, p["_d"].day) <= (cutoff.month, cutoff.day)]
    rows = list(zip(classify(prior), classify(ytd)))
    for lab, (a, b) in zip(["free posts, 100+ words", "paid essays",
                            "podcast & video", "notices under 100 words"], rows):
        print("  %-26s %8d %8d" % (lab, len(a), len(b)))
    print("  %-26s %8d %8d" % ("all items", len(prior), len(ytd)))

    section("Paid, free and engagement")
    free, paid, video, short = classify(ytd)
    sundays = [p for p in paid if p["_d"].weekday() == 6]
    pw = sorted(p["wordcount"] for p in paid if p.get("wordcount"))
    print("  paid                   %d, of which Sunday %d" % (len(paid), len(sundays)))
    if pw:
        print("  paid word range        %d to %d, median %.0f" % (pw[0], pw[-1], st.median(pw)))
    print("  free 100+ median words %.0f over %d posts" % (
        st.median([p["wordcount"] for p in free]), len(free)))
    for lab, rows_ in [("free, all non-video", free + short), ("free, 100+ only", free),
                       ("paid", paid)]:
        print("  %-22s reactions %6.0f   comments %5.0f" % (
            lab, st.median([p.get("reaction_count") or 0 for p in rows_]),
            st.median([p.get("comment_count") or 0 for p in rows_])))
    if video:
        d = sorted((p.get("podcast_duration") or 0) / 60 for p in video)
        print("  video                  %d items, median %.0f min, longest %.0f min" % (
            len(video), st.median(d), d[-1]))

    section("Subject, by title and by title+subtitle")
    pats = [("Trump or MAGA", r"trump|maga"),
            ("oligarchy/corruption/Musk", r"oligarch|corrupt|musk"),
            ("tariffs or trade", r"tariff|trade")]
    print("  %-28s %8s %16s" % ("", "title", "title+subtitle"))
    for lab, pat in pats:
        t = sum(1 for p in ytd if re.search(pat, p.get("title") or "", re.I))
        ts = sum(1 for p in ytd if re.search(
            pat, (p.get("title") or "") + " " + (p.get("subtitle") or ""), re.I))
        print("  %-28s %8d %16d" % (lab, t, ts))

    section("What the notices actually are")
    # Listed rather than bucketed on purpose. The page says twelve of these
    # are day-off notes, which is a judgement about what they say -- "Dental
    # Surgery Today" and "I'm Outta Here" are two of them and no title
    # pattern catches both. Read the list; do not trust a regex to.
    print("  %d items under 100 words, %d of them with no body at all:" % (
        len(short), sum(1 for p in short if not (p.get("wordcount") or 0))))
    for p in sorted(short, key=lambda p: p["_d"]):
        print("    %s %4d  %-44s %s" % (
            p["_d"].date(), p.get("wordcount") or 0,
            (p.get("title") or "")[:44], (p.get("subtitle") or "")[:38]))

    section("Feeds")
    for name, url in FEEDS:
        try:
            body, status, _ = get(url, want_json=False)
            items = len(re.findall(r"<item[ >]", body))
            dates = re.findall(r"<pubDate>([^<]+)</pubDate>", body)
            print("  %-18s %3s  %3d items  newest %s" % (
                name, status, items, dates[0] if dates else "-"))
        except urllib.error.HTTPError as e:
            print("  %-18s %3s  (the page calls this one dead)" % (name, e.code))
        except Exception as e:                      # noqa: BLE001 - report, continue
            print("  %-18s  --  %s" % (name, e))

    section("Stone Center")
    for lab, q in [("all time", ""),
                   ("in %d" % (year - 1), "&after=%d-01-01T00:00:00&before=%d-01-01T00:00:00"
                    % (year - 1, year)),
                   ("in %d" % year, "&after=%d-01-01T00:00:00&before=%d-01-01T00:00:00"
                    % (year, year + 1))]:
        try:
            _, _, h = get(STONE + "?search=krugman&per_page=1" + q, want_json=False)
            print("  posts mentioning him, %-9s %s" % (lab, h.get("X-WP-Total", "?")))
        except Exception as e:                      # noqa: BLE001
            print("  posts mentioning him, %-9s -- %s" % (lab, e))


if __name__ == "__main__":
    main()
