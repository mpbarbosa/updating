#!/usr/bin/env python3
"""Re-measure every figure quoted on docs/brightlights.html.

Not a build step: the site has none, and the page is written by hand. Run
this when the index starts to look stale, or before trusting a number on it,
then reconcile the report against the page by eye.

    python3 tools/brightlights-figures.py                  # as of today
    python3 tools/brightlights-figures.py --as-of 2026-11-11
    python3 tools/brightlights-figures.py --links          # +~30 requests

Stdlib only, plus curl -- see below. The default run is about forty
requests and writes nothing.

Bright Lights is WordPress, so the whole corpus is readable through
/wp-json/wp/v2/ with no key. Two things about it shape this script:

  * X-WP-Total on a per_page=1 request is a count without a download, so
    every all-time figure here costs one small request. after=/before= take
    ISO timestamps and are compared against the post's LOCAL date, which is
    what the site prints, so the year boundaries line up with the page.

  * The host's CDN answers 403 to HTTP/1.1 and 200 to HTTP/2, whatever the
    headers say. urllib speaks only HTTP/1.1, so it cannot read this site
    at all, with any User-Agent -- which is a trap, because the failure is
    a flat 403 that reads like a blocked scraper or a dead API. So every
    fetch here goes through curl, which negotiates HTTP/2. Nothing else
    about the request is unusual: no key, no cookie, read-only, and the
    User-Agent below says what this is rather than imitating a browser.

Where a figure needs a judgement rather than a count, this prints the items
instead of bucketing them. "Zero reviews in 2026" is a claim about what the
articles ARE; a WordPress category is a label someone chose, and the two
come apart (the journal files book reviews under Books, and essays that
review a film under Essays). So the year's articles are listed with their
categories and the reader decides. A script that confidently contradicted
the page on a regex would be worse than no script.
"""
import argparse
import html
import json
import os
import re
import shutil
import statistics as st
import subprocess
import sys
import tempfile
import urllib.parse
from collections import Counter
from datetime import date, datetime

API = "https://brightlightsfilm.com/wp-json/wp/v2/"
SITE = "https://brightlightsfilm.com/"

# This script, named. The CDN wants some User-Agent; it does not want a
# particular one, so there is no reason to impersonate a browser. Everything
# fetched here is public, unauthenticated and read-only.
UA = "updating-source-index/1.0 (+https://mpbarbosa.github.io/updating/)"

# The categories the page tables, in the order it tables them. The left
# column is the page's label, which is not always the category's own name.
KIND_SLUGS = [
    ("Essays", "essays"),
    ("Reviews", "reviews"),
    ("Festivals & awards", "festivals"),
    ("Interviews", "interviews"),
    ("Books", "books"),
    ("DVD & Blu-ray", "dvd-and-blu-ray"),
    ("Documentaries", "documentaries"),
    # Two categories answer to "news" and both hold 5 posts: News (slug
    # "news", newest 2025) and BLFJ News (slug "blfj-news", newest 2014).
    # The page's single "Journal news / 5 / 0" row is true of either, so
    # print both rather than picking one and calling it the answer.
    ("Journal news", "news"),
    ("Journal news (BLFJ)", "blfj-news"),
]

# The second table: category feeds the page recommends taking.
FEED_SLUGS = ["essays", "directors", "horror", "asian",
              "experimental-underground", "books", "silents", "reviews"]

# The masthead, as the page's "What to discount" section names it.
MASTHEAD = ["Gary Morris", "Alan Vanneman", "Lesley Chow",
            "Gordon Thomas", "Andrew Grossman"]

# Every channel the page's "Where to follow it" table lists. The third
# column says whether the page calls it a working feed. A feed is XML; a
# 200 with text/html is a web page wearing a feed's URL, and reading the
# status code alone is how a dead channel gets printed as live and empty.
CHANNELS = [
    ("main RSS", SITE + "feed/", True),
    ("main Atom", SITE + "feed/atom/", True),
    ("category, flat", SITE + "category/essays/feed/", True),
    ("category, nested", SITE + "category/genres/horror/feed/", True),
    ("category, flat horror", SITE + "category/horror/feed/", True),
    ("author feed", SITE + "author/mike-thorn/feed/", True),
    ("REST API", API + "posts?per_page=1&_fields=id", True),
    # Listed on the page as linked-but-unchecked or dead. Checked anyway:
    # the page hands these URLs to readers, so a wrong state here costs
    # somebody a subscription.
    ("subscribe page", SITE + "subscribe/", False),
    ("issue archive", SITE + "issue-archive/", False),
    ("about page", SITE + "about/", False),
]


class Fetched:
    """A response: body, status, and headers that read case-insensitively."""

    def __init__(self, body, status, headers):
        self.body = body
        self.status = status
        self._h = headers

    def get(self, name, default=None):
        return self._h.get(name.lower(), default)

    @property
    def ctype(self):
        return self.get("content-type", "?").split(";")[0].strip()


def get(url, timeout=60):
    """GET a URL through curl over HTTP/2. Returns a Fetched.

    Raises RuntimeError if curl itself fails (DNS, TLS, timeout). An HTTP
    error status is NOT an exception: a 403 or a 404 is a finding about a
    channel the page recommends, and callers want to print it.
    """
    fd, hpath = tempfile.mkstemp(prefix="blfj-hdr-")
    os.close(fd)
    try:
        proc = subprocess.run(
            ["curl", "-sS", "--http2", "-L", "--max-time", str(timeout),
             "-A", UA, "-H", "Accept: */*", "-D", hpath, url],
            capture_output=True, timeout=timeout + 15)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip()
                               or "curl exit %d" % proc.returncode)
        with open(hpath, "rb") as f:
            raw = f.read().decode("utf-8", "replace")
    finally:
        os.unlink(hpath)
    # With -L the file holds one header block per hop; the last one is the
    # response that actually answered.
    block = [b for b in re.split(r"\r?\n\r?\n", raw) if b.strip()][-1]
    lines = block.splitlines()
    status = int(re.search(r"\s(\d{3})\b", lines[0]).group(1))
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return Fetched(proc.stdout.decode("utf-8", "replace"), status, headers)


def api(path, **params):
    """GET an API path. Returns (parsed json, X-WP-Total)."""
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    r = get(url)
    if r.status != 200:
        raise RuntimeError("%s -> HTTP %d" % (url, r.status))
    return json.loads(r.body), int(r.get("x-wp-total", "-1"))


def count(path, **params):
    """How many items match, without downloading any of them."""
    params.update(per_page=1, _fields="id")
    return api(path, **params)[1]


def year_bounds(y):
    """after=/before= for a whole calendar year.

    These compare against the post's local date, which is the date the site
    prints and the date the page counts by. A UTC-based window would move a
    handful of posts across each year boundary.
    """
    return {"after": "%d-01-01T00:00:00" % y,
            "before": "%d-01-01T00:00:00" % (y + 1)}


def strip_tags(s):
    s = re.sub(r"(?s)<(script|style)\b.*?</\1>", " ", s)
    return html.unescape(re.sub(r"<[^>]+>", " ", s))


def words(post):
    return len(strip_tags(post.get("content", {}).get("rendered", "")).split())


def feed_entries(body):
    """(date, title) for an Atom or an RSS feed."""
    out = []
    for raw in re.findall(r"(?s)<entry>(.*?)</entry>", body):
        t = re.search(r"(?s)<title[^>]*>(.*?)</title>", raw)
        d = (re.search(r"(?s)<published>(.*?)</published>", raw)
             or re.search(r"(?s)<updated>(.*?)</updated>", raw))
        out.append((d.group(1)[:10] if d else "?",
                    html.unescape(strip_tags(t.group(1))).strip() if t else "?"))
    for raw in re.findall(r"(?s)<item>(.*?)</item>", body):
        t = re.search(r"(?s)<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", raw)
        d = re.search(r"(?s)<pubDate>(.*?)</pubDate>", raw)
        when = "?"
        if d:
            for f in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
                try:
                    when = datetime.strptime(
                        d.group(1).strip(), f).date().isoformat()
                    break
                except ValueError:
                    pass
        out.append((when, html.unescape(strip_tags(t.group(1))).strip()
                    if t else "?"))
    return out


def section(title):
    print("\n" + title)
    print("-" * len(title))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--as-of", default=date.today().isoformat(),
                    help="cutoff for every 'this year' and 'since last post' "
                         "figure (YYYY-MM-DD)")
    ap.add_argument("--links", action="store_true",
                    help="check that every article the page links resolves")
    args = ap.parse_args()
    cutoff = date.fromisoformat(args.as_of)
    year = cutoff.year
    if not shutil.which("curl"):
        sys.exit("needs curl: the host answers 403 to HTTP/1.1, which is all "
                 "urllib speaks. See the module docstring.")
    print("Bright Lights Film Journal, measured as of %s" % cutoff)

    # ---------------------------------------------------------------- corpus
    section("The corpus")
    total = count("posts")
    oldest, _ = api("posts", per_page=1, order="asc", orderby="date",
                    _fields="date,title,link")
    newest, _ = api("posts", per_page=1, _fields="date,title,link")
    o, n = oldest[0], newest[0]
    last = date.fromisoformat(n["date"][:10])
    print("  posts published, all time    %d" % total)
    print("  oldest                       %s  %s" % (
        o["date"][:10], strip_tags(o["title"]["rendered"])[:50]))
    print("  newest                       %s  %s" % (
        n["date"][:10], strip_tags(n["title"]["rendered"])[:50]))
    print("  days since the last post     %d  (before %s)" % (
        (cutoff - last).days, cutoff))
    # The page's "since 1974 / online since 1995" split: the API only knows
    # what was posted online, so 1974-93 print is out of its reach entirely.
    print("  note: the API sees only what is online; the 1974-93 print run")
    print("        and the pre-1995 material are not in these counts.")

    # ------------------------------------------------------------- per year
    section("Posts per year (the chart)")
    per_year = {}
    for y in range(2014, year + 1):
        per_year[y] = count("posts", **year_bounds(y))
    for y in sorted(per_year):
        bar = "#" * max(1, round(per_year[y] / 3))
        print("  %d  %4d  %s" % (y, per_year[y], bar))
    # The year in progress is not comparable with a finished one. Say so in
    # the report rather than leaving a partial year next to twelve whole
    # ones for someone to read as a decline.
    done = cutoff.timetuple().tm_yday / (366 if cutoff.year % 4 == 0 else 365)
    print("  %d is %.0f%% elapsed; at this rate it ends on about %d." % (
        year, done * 100, round(per_year[year] / done)))

    # ------------------------------------------------------- the year itself
    section("%d month by month" % year)
    posts, _ = api("posts", per_page=100, after="%d-01-01T00:00:00" % year,
                   before=(cutoff.isoformat() + "T23:59:59"),
                   _fields="date,title,link,categories,author,content")
    posts.sort(key=lambda p: p["date"])
    months = Counter(p["date"][:7] for p in posts)
    for m in range(1, 13):
        key = "%d-%02d" % (year, m)
        if key > cutoff.isoformat()[:7]:
            break
        print("  %s  %2d  %s" % (date(year, m, 1).strftime("%b"),
                                 months.get(key, 0), "#" * months.get(key, 0)))
    print("  total %d to %s" % (len(posts), cutoff))

    section("Cadence")
    days = [date.fromisoformat(p["date"][:10]) for p in posts]
    if len(days) > 1:
        gaps = [(b - a).days for a, b in zip(days, days[1:])]
        print("  median gap in %d          %d days" % (year, st.median(gaps)))
        print("  mean gap in %d            %.1f days" % (
            year, sum(gaps) / len(gaps)))
        print("  longest gap               %d days (%s to %s)" % (
            max(gaps), days[gaps.index(max(gaps))],
            days[gaps.index(max(gaps)) + 1]))
    wc = sorted(words(p) for p in posts)
    if wc:
        print("  median words in %d        %d" % (year, st.median(wc)))
        print("  quartiles                 %d / %d / %d" % (
            wc[len(wc) // 4], st.median(wc), wc[3 * len(wc) // 4]))
        print("  longest                   %d words" % wc[-1])
        # The page quotes a ceiling "around 9,000". Word counts come from
        # content.rendered, so they include image captions and pull quotes
        # and run a little high against anybody's manual count.

    # ----------------------------------------------------------- categories
    cats, cat_total = api("categories", per_page=100, _fields="id,slug,name,count")
    page2, _ = api("categories", per_page=100, page=2,
                   _fields="id,slug,name,count") if cat_total > 100 else ([], 0)
    cats += page2
    by_slug = {c["slug"]: c for c in cats}
    by_id = {c["id"]: c for c in cats}
    print("\n  categories on the site       %d" % cat_total)

    section("What changed: the page's kinds, all-time and %d" % year)
    print("  %-22s %9s %6s   %s" % ("kind (slug)", "all-time", year, "newest"))
    for label, slug in KIND_SLUGS:
        c = by_slug.get(slug)
        if not c:
            print("  %-22s   MISSING SLUG - the page tables it" % label)
            continue
        this = sum(1 for p in posts if c["id"] in p["categories"])
        recent, _ = api("posts", per_page=1, categories=c["id"],
                        _fields="date")
        print("  %-22s %9d %6d   %s" % (
            "%s (%s)" % (label, slug), c["count"], this,
            recent[0]["date"][:10] if recent else "-"))

    section("Subject feeds worth taking")
    print("  %-34s %9s %6s" % ("feed", "all-time", year))
    for slug in FEED_SLUGS:
        c = by_slug.get(slug)
        if not c:
            print("  /category/%s/feed/   MISSING" % slug)
            continue
        this = sum(1 for p in posts if c["id"] in p["categories"])
        print("  %-34s %9d %6d" % (
            "/category/%s/feed/" % slug, c["count"], this))

    # ------------------------------------------------- the judgement calls
    section("Every %d article, with its categories" % year)
    # This is the "zero reviews, zero festival reports, zero journal news"
    # claim, unbucketed. Read the list: a category is a label an editor
    # picked, and whether a piece is a review is not settled by it.
    users, user_total = api("users", per_page=100, _fields="id,name,slug")
    names = {u["id"]: u["name"] for u in users}
    for p in posts[::-1]:
        labels = ", ".join(sorted(
            by_id[i]["name"] for i in p["categories"] if i in by_id))
        print("  %s  %-52s %s" % (
            p["date"][:10], strip_tags(p["title"]["rendered"])[:52],
            names.get(p["author"], "author %d" % p["author"])))
        print("        %5d words  %s" % (words(p), labels[:92]))

    # ------------------------------------------------------------- bylines
    section("Bylines")
    bylines = Counter(p["author"] for p in posts)
    print("  distinct bylines in %d     %d, over %d articles" % (
        year, len(bylines), len(posts)))
    once = sum(1 for n in bylines.values() if n == 1)
    print("  of those, with one article   %d" % once)
    # The page calls this "contributor accounts". /users lists only accounts
    # the site exposes as authors, so it is a count of people who have been
    # published, not of registered logins -- which is the honest reading of
    # "745 contributor accounts for 2,928 articles" anyway.
    print("  contributor accounts         %d  (accounts /users reports)"
          % user_total)
    print("  busiest in %d:" % year)
    for aid, n in bylines.most_common(6):
        print("    %2d  %s" % (n, names.get(aid, "author %d" % aid)))

    section("The masthead")
    print("  %-18s %6s  %-12s %s" % ("name", "posts", "last post", "in %d" % year))
    for who in MASTHEAD:
        found, _ = api("users", search=who, per_page=3, _fields="id,name,slug")
        exact = [u for u in found if u["name"].lower() == who.lower()] or found
        if not exact:
            print("  %-18s   no such contributor account" % who)
            continue
        uid = exact[0]["id"]
        n = count("posts", author=uid)
        recent, _ = api("posts", per_page=1, author=uid, _fields="date")
        this = sum(1 for p in posts if p["author"] == uid)
        print("  %-18s %6d  %-12s %d" % (
            exact[0]["name"], n,
            recent[0]["date"][:10] if recent else "-", this))

    # ------------------------------------------------------------ channels
    section("Channels")
    # Content type, not status code. Several of these answer 200 with
    # text/html to a feed-shaped URL; a checker that reads the status alone
    # reports a dead feed as live and empty forever.
    for name, url, want_feed in CHANNELS:
        try:
            r = get(url, timeout=45)
        except RuntimeError as e:
            print("  %-22s  --  %s" % (name, e))
            continue
        ctype, body = r.ctype, r.body
        is_xml = "xml" in ctype or body.lstrip().startswith("<?xml")
        is_json = "json" in ctype
        if r.status != 200:
            verdict = "HTTP %d, no content" % r.status
        elif is_json:
            verdict = "json, ok"
        elif is_xml:
            entries = feed_entries(body)
            newest = max((d for d, _ in entries if d != "?"), default="-")
            verdict = "%d entries, newest %s" % (len(entries), newest)
        else:
            verdict = "NOT A FEED: %s" % ctype
        flag = ""
        if want_feed and not (r.status == 200 and (is_xml or is_json)):
            flag = "  <- the page calls this a working feed"
        print("  %-22s %3s  %-26s %s%s" % (
            name, r.status, ctype, verdict, flag))

    section("The site's own chrome, as the page describes it")
    # The page says the header's "RSS" button points at FeedBurner, that it
    # links a dead Google+, and that /about/ is still placeholder text.
    # These are claims about HTML, so read the HTML.
    try:
        home = get(SITE).body
        for label, pat in (("feedburner link", r"feedburner"),
                           ("google+ link", r"plus\.google\.com"),
                           ("twitter/x link", r"(?:twitter|x)\.com/blfj"),
                           ("facebook link", r"facebook\.com/[A-Za-z0-9.]+"),
                           ("instagram link", r"instagram\.com/[A-Za-z0-9._]+")):
            m = re.search(pat, home, re.I)
            print("  %-18s %s" % (
                label, m.group(0)[:60] if m else "not in the home page HTML"))
    except Exception as e:                          # noqa: BLE001
        print("  home page -- %s" % e)
    try:
        about = get(SITE + "about/").body
        text = " ".join(strip_tags(about).split())
        low = text.lower()
        ph = any(k in low for k in (
            "this is an example of a wordpress page",   # the sample page
            "just another wordpress site",              # the default tagline
            "lorem ipsum"))
        print("  /about/ placeholder  %s" % ("yes" if ph else "no"))
        print("  /about/ first words  %s" % text[:150])
    except Exception as e:                          # noqa: BLE001
        print("  /about/ -- %s" % e)

    if args.links:
        section("Every brightlightsfilm.com URL the page links")
        page = open("docs/brightlights.html", encoding="utf-8").read()
        urls = sorted(set(re.findall(
            r'href="(https://brightlightsfilm\.com/[^"#?]*)"', page)))
        for url in urls:
            try:
                r = get(url, timeout=45)
            except RuntimeError as e:
                print("   --  %s  (%s)" % (url, e))
                continue
            print("  %3s  %s%s" % (r.status, url,
                                   "" if r.status == 200 else
                                   "  <- the page links this"))


if __name__ == "__main__":
    main()
