#!/usr/bin/env python3
"""Re-check every figure on docs/index.html -- the board.

The board is the only page here that states almost nothing of its own. Its
numbers are copied from the four source pages, so it goes wrong in a way
none of the other scripts can catch: a source page gets corrected and the
board keeps the figure that was just overturned. That has happened twice.
On 13 November 2026 the board was still advertising a median of 3,700 words
for Bright Lights two commits after that page had been corrected to 2,500,
and still flagging a Dan Moore post as "not in feed" after the audit that
established the feed carries every one of his posts.

So this script compares, rather than measures. It reads the board and the
four source pages and reports where they disagree -- and it checks the
board's arithmetic, which is the other thing nothing else looks at:

    posts counted across them    3,901
    2,929 + 800 + 159 + 14       = 3,902

That was live for a day. The addends had been corrected one at a time and
the total was never re-added. A derived figure needs its derivation checked,
not just its parts.

    python3 tools/board-figures.py            # the cross-check, offline
    python3 tools/board-figures.py --live     # also re-ask the sources
    python3 tools/board-figures.py --links    # follow every outbound link

    git show HEAD~1:docs/index.html > /tmp/old.html
    python3 tools/board-figures.py --board /tmp/old.html    # see it fail

Stdlib only. --live needs curl for brightlightsfilm.com, whose CDN answers
403 to HTTP/1.1 and 200 to HTTP/2; urllib speaks only HTTP/1.1. See
tools/brightlights-figures.py for the full story.
"""
import argparse
import html
import json
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"
BOARD = DOCS / "index.html"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0 Safari/537.36")

# Each source page's own headline figures live in its .stat tiles. The board
# repeats a subset of them, in its own words, which is where drift gets in.
SOURCES = {
    "dan-moore": "Dan Moore",
    "karpathy": "Andrej Karpathy",
    "brightlights": "Bright Lights Film Journal",
    "krugman": "Paul Krugman",
}

# Where the board's "posts counted across them" addends come from. Three are
# all-time archive totals; Karpathy has no all-time stat tile, so his came
# from adding two year counts -- which is how an apples-and-oranges addend
# ended up in the row. Counted here from both archive indexes instead.
KARPATHY_INDEXES = [
    ("bearblog", "https://karpathy.bearblog.dev/blog/", r'href="(/[a-z0-9\-]+/)"'),
    ("github.io", "https://karpathy.github.io/", r'href="(/20[0-9]{2}/[0-9]{2}/[0-9]{2}/[^"]+)"'),
]

# The newest item the board lists per source, against what the source serves.
NEWEST = [
    ("Krugman", "https://paulkrugman.substack.com/api/v1/archive?sort=new&limit=1"),
    ("Bright Lights", "https://brightlightsfilm.com/wp-json/wp/v2/posts"
                      "?per_page=1&orderby=date&order=desc&_fields=date,title"),
    ("Dan Moore", "https://fusionauth.io/blog/feed.xml"),
    ("Karpathy", "https://karpathy.bearblog.dev/blog/"),
]


def section(title):
    print("\n" + title)
    print("-" * len(title))


def fetch(url, tries=2):
    """urllib first, curl --http2 second.

    Not belt and braces: brightlightsfilm.com is unreachable over HTTP/1.1,
    which is all urllib speaks, and it fails as a flat 403 that reads like a
    blocked scraper. The retry also covers YouTube's feed endpoint, which
    answers a rate-limited request with 404 rather than 429.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.headers.get("Content-Type", "-"), \
                r.read().decode("utf-8", "replace")
    except Exception:                               # noqa: BLE001 - fall through
        pass
    try:
        out = subprocess.run(
            ["curl", "-sS", "-L", "--http2", "-A", UA, "-m", "45",
             "-w", "\n%{http_code}\t%{content_type}", url],
            capture_output=True, text=True, timeout=90)
        body, _, tail = out.stdout.rpartition("\n")
        status, _, ctype = tail.partition("\t")
        return int(status or 0), ctype or "-", body
    except Exception as ex:                         # noqa: BLE001
        return 0, "curl: %s" % str(ex)[:40], ""


def text_of(path):
    return pathlib.Path(path).read_text(encoding="utf-8")


def stats_of(page):
    """The .stat tiles on a source page: {label: value}."""
    t = text_of(page)
    out = {}
    for m in re.finditer(
            r'<div class="stat"><div class="n">([^<]*)</div>'
            r'<div class="k">([^<]*)</div></div>', t):
        out[html.unescape(m.group(2)).strip()] = html.unescape(m.group(1)).strip()
    return out


def num(s):
    """'2,929' -> 2929, '~1.4' -> 1.4, '0 d' -> 0. None when there is no number."""
    m = re.search(r"-?[\d,]+(?:\.\d+)?", s or "")
    if not m:
        return None
    v = m.group(0).replace(",", "")
    return float(v) if "." in v else int(v)


def check_arithmetic(board):
    section("The board's own arithmetic")
    m = re.search(r'<div class="num">([\d,]+)</div>\s*'
                  r'<p class="cap">posts counted across them</p>\s*'
                  r'<p class="foot">([^<]+)</p>', board)
    if not m:
        print("  -- could not find the 'posts counted across them' tile")
        return
    total = num(m.group(1))
    addends = [num(x) for x in m.group(2).split("+")]
    got = sum(a for a in addends if a is not None)
    print("  stated total   %s" % f"{total:,}")
    print("  addends        %s  = %s" % (m.group(2).strip(), f"{got:,}"))
    if got == total:
        print("  OK             they agree")
    else:
        print("  MISMATCH       off by %s -- the addends were corrected and the"
              % f"{got - total:,}")
        print("                 total was never re-added")


def check_against_sources(board):
    section("The board against the four source pages")
    print("  Each row is a figure the board repeats. The source page is the")
    print("  authority: it is the one that was measured against the source.")

    # (board regex, which source page, which .stat label on it, what it is)
    rows = [
        (r'(\d[\d,]*) posts on an identity vendor', "dan-moore",
         "posts since 2020", "Dan Moore, posts all-time"),
        (r'Eleven posts in 2025, three in 2026', "karpathy",
         "posts in 2025", "Karpathy, 2025 (spelled out on the board)"),
        (r'([\d,]+) articles deep', "brightlights",
         "posts online", "Bright Lights, posts all-time"),
        (r'a median ([\d,]+) words', "brightlights",
         "median words", "Bright Lights, median words"),
        (r'(\d[\d,]*) posts in 702 days', "krugman",
         "posts since Dec 2024", "Krugman, posts since the relaunch"),
        (r'<span class="cnt">([\d.]+) / day</span>', "krugman",
         "posts per day in 2026", "Krugman, posts per day"),
    ]
    bad = 0
    for pat, src, label, what in rows:
        m = re.search(pat, board)
        stats = stats_of(DOCS / (src + ".html"))
        want = stats.get(label)
        if not m:
            print("  %-42s board: NOT FOUND" % what)
            bad += 1
            continue
        got = m.group(1) if m.groups() else m.group(0)
        a, b = num(got), num(want)
        if a is not None and b is not None and a == b:
            print("  %-42s %-10s agrees with %s.html" % (what, got, src))
        elif m.groups() == ():
            print("  %-42s %-10s (prose; %s.html says %s)"
                  % (what, "present", src, want))
        else:
            print("  %-42s board %-8s  %s.html %-8s  <-- DISAGREE"
                  % (what, got, src, want))
            bad += 1
    print("\n  %d disagreement(s)" % bad)

    # Claims the board states that a source page has since overturned. These
    # are not figures, so no number comparison would catch them.
    section("Claims the source pages have overturned")
    stale = [
        ("not in feed",
         "dan-moore.html establishes the feed carries all 159 of his posts; "
         "what drops three is an exact-match filter on the byline"),
        ("the blog feed carries 156",
         "same correction: the feed carries 159, not 156"),
        ("median 3,700 words",
         "brightlights.html measured the median at 2,500; 3,700 is the "
         "third quartile"),
        ("every three days",
         "brightlights.html measured the median gap at four days"),
        ("no feed</span>\n            <td class=\"feed\">a 79-video",
         "krugman.html: the YouTube channel has 547 videos and a feed"),
    ]
    hits = 0
    for needle, why in stale:
        if needle in board:
            hits += 1
            print("  FOUND  %r" % needle)
            print("         %s" % why)
    if not hits:
        print("  none of the known-overturned claims is on the board")


def check_feeds(board, live):
    section("The feeds the board hands out")
    urls = [u.replace("&amp;", "&")
            for u in re.findall(r'<span class="url">([^<]+)</span>', board)]
    stated = re.search(r'<h2>Feeds worth subscribing to</h2>\s*'
                       r'<span class="cnt">(\d+)</span>', board)
    said = num(stated.group(1)) if stated else None
    print("  listed %d, tile says %s%s" % (
        len(urls), said,
        "" if said == len(urls) else "   <-- MISMATCH"))
    if not live:
        return
    for u in urls:
        status, ctype, body = fetch(u)
        n = len(re.findall(r"<item[ >]", body)) or len(re.findall(r"<entry[ >]", body))
        note = ""
        if status == 200 and "xml" not in (ctype or ""):
            note = "   <-- 200 but not XML: a page wearing a feed's URL"
        elif status != 200:
            note = "   <-- a failure, not a verdict: ask again later"
        print("  %-58s %3s  %-34s %s items%s"
              % (u[:58], status, (ctype or "-")[:34], n, note))


def check_newest(board):
    section("The newest item the board lists, against what each source serves")
    for name, url in NEWEST:
        status, _, body = fetch(url)
        live = None
        if name == "Krugman" and body.lstrip().startswith("{"):
            d = json.loads(body)
            posts = d["posts"] if isinstance(d, dict) else d
            live = posts[0]["post_date"][:10] if posts else None
        elif name == "Bright Lights" and body.lstrip().startswith("["):
            rows = json.loads(body)
            live = rows[0]["date"][:10] if rows else None
        elif name == "Dan Moore":
            from email.utils import parsedate_to_datetime
            best = None
            for item in re.findall(r"<item>(.*?)</item>", body, re.S):
                a = re.search(r"<author>(.*?)</author>", item, re.S)
                if not a or "Dan Moore" not in a.group(1):
                    continue
                d = re.search(r"<pubDate>([^<]*)</pubDate>", item)
                if d:
                    got = parsedate_to_datetime(d.group(1)).date().isoformat()
                    best = max(best, got) if best else got
            live = best
        elif name == "Karpathy":
            m = re.search(r"<time[^>]*>([^<]+)</time>", body) or \
                re.search(r"(\d{2} [A-Z][a-z]{2}, 20\d{2})", body)
            live = m.group(1).strip() if m else None

        # What the board's "Latest across all four" list has for this source
        pat = r'<span class="sub"><i class="src-dot \w+"></i>%s &middot; ([^<]+?)(?: <span|</span>)' \
              % re.escape(name)
        dates = re.findall(pat, board)
        print("  %-14s source serves %-14s board's newest: %s"
              % (name, live or "?", dates[0].strip() if dates else "NOT LISTED"))
    print("\n  Dates are formatted differently on each side on purpose: read")
    print("  them, do not diff them. The question is whether the board is")
    print("  missing something newer, which it was on 13 November 2026.")


def check_karpathy_total():
    section("Karpathy's all-time total, for the addends row")
    print("  He has no all-time stat tile, so the board's addend came from")
    print("  adding his 2025 and 2026 counts -- a two-year figure sitting in")
    print("  a row of all-time ones. Counted from both archive indexes:")
    total = 0
    for name, url, pat in KARPATHY_INDEXES:
        status, _, body = fetch(url)
        found = {u for u in re.findall(pat, body)}
        found -= {"/blog/", "/", "/feed/"}
        total += len(found)
        print("    %-12s %3s  %d posts" % (name, status, len(found)))
    print("    %-12s      %d posts all-time" % ("total", total))


def check_links(board):
    section("Every outbound link on the board")
    urls = sorted({u.replace("&amp;", "&")
                   for u in re.findall(r'href="(https?://[^"]+)"', board)})
    skip = ("fonts.googleapis", "fonts.gstatic", "mpbarbosa.com",
            "linkedin.com/in/mpbarbosa", "github.com/mpbarbosa",
            "mpbarbosa.github.io")
    checked = [u for u in urls if not any(s in u for s in skip)]
    bad = 0
    for u in checked:
        status, _, _ = fetch(u)
        if status != 200:
            bad += 1
            print("  %-4s %s" % (status, u))
    print("  %d links checked, %d not 200%s"
          % (len(checked), bad, " -- every one resolves" if not bad else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--live", action="store_true",
                    help="also re-ask each source for its newest item, fetch "
                         "every feed, and count Karpathy's archives")
    ap.add_argument("--links", action="store_true",
                    help="follow every outbound link on the board")
    ap.add_argument("--board", default=str(BOARD),
                    help="check a different copy of the board -- point it at "
                         "an older revision (git show HEAD~1:docs/index.html) "
                         "to confirm this script still catches what it says "
                         "it catches. A check nobody has seen fail is not a "
                         "check.")
    args = ap.parse_args()

    board = text_of(args.board)

    # The board carries its own revision date in two places and they have
    # drifted apart before.
    section("The board's revision date")
    bar = re.search(r'last revised <time datetime="([\d-]+)">([^<]+)</time>', board)
    jsonld = re.search(r'"dateModified":\s*"([\d-]+)"', board)
    print("  bar          %s  (%s)" % (bar.group(1), bar.group(2)) if bar
          else "  bar          NOT FOUND")
    print("  JSON-LD      %s" % (jsonld.group(1) if jsonld else "NOT FOUND"))
    if bar and jsonld and bar.group(1) != jsonld.group(1):
        print("  MISMATCH     these two should be the same date")

    check_arithmetic(board)
    check_against_sources(board)
    check_feeds(board, args.live)
    if args.live:
        check_newest(board)
        check_karpathy_total()
    if args.links:
        check_links(board)


if __name__ == "__main__":
    main()
