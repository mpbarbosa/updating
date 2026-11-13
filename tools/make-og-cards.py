#!/usr/bin/env python3
"""Generate the 1200x630 link-preview cards in docs/og/.

Not a build step: the site has none, and the cards are committed. Run this
only when a page is added, renamed or re-pitched, then commit the PNGs.

    pip install Pillow
    python3 tools/make-og-cards.py

Cards are quantised to 128 colours, which is plenty for flat type on a flat
ground and keeps each one around 15 KB. The service worker does not precache
them -- crawlers and link unfurlers read them, visitors never do.
"""
import os

from PIL import Image, ImageDraw, ImageFont

F = "/usr/share/fonts/opentype/inter/Inter-%s.otf"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "og")

W, H = 1200, 630
BG      = (243, 243, 243)
CARD    = (255, 255, 255)
INK     = (27, 27, 27)
INK2    = (93, 93, 93)
FAINT   = (140, 140, 140)
ACCENT  = (15, 108, 189)
VIOLET  = (122, 90, 240)

CARDS = [
    ("home",         "Updating",                    "Reading indexes for the sources worth following",
                     "Four sources assessed · cadence, canonical reading and the feeds that work"),
    ("sources",      "All sources",                 "Every source assessed, with the verdict and the feeds",
                     "Dan Moore · Andrej Karpathy · Bright Lights Film Journal · Paul Krugman"),
    ("dan-moore",    "Dan Moore",                   "Source index · identity, OAuth, agent authorization",
                     "159 posts since 2020 · fortnightly since 2025 · no per-author feed"),
    ("karpathy",     "Andrej Karpathy",             "Source index · deep learning and LLMs",
                     "11 posts in 2025, 3 in 2026 · two live blogs, separate feeds"),
    ("brightlights", "Bright Lights Film Journal",  "Source index · film criticism since 1974",
                     "2,928 articles · an essay every three days · feeds per subject and author"),
    ("krugman",      "Paul Krugman",                "Source index · economics and politics",
                     "793 posts in 702 days · free weekdays, paid economics on Sundays"),
]


def font(style, size):
    return ImageFont.truetype(F % style, size)


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def badge(img, xy, d):
    """The 'UP' avatar, accent-to-violet gradient in a circle."""
    x, y = xy
    g = Image.new("RGB", (d, d))
    gd = ImageDraw.Draw(g)
    for i in range(d):
        t = i / max(d - 1, 1)
        gd.line(
            [(0, i), (d, i)],
            fill=tuple(round(ACCENT[c] + (VIOLET[c] - ACCENT[c]) * t) for c in range(3)),
        )
    mask = Image.new("L", (d * 4, d * 4), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, d * 4 - 1, d * 4 - 1], fill=255)
    img.paste(g, (x, y), mask.resize((d, d), Image.LANCZOS))
    f = font("SemiBold", round(d * 0.34))
    dr = ImageDraw.Draw(img)
    tw = dr.textlength("UP", font=f)
    dr.text((x + (d - tw) / 2, y + d * 0.30), "UP", font=f, fill=(255, 255, 255))


def card(slug, title, sub, meta):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    # inner card with a hairline border, mirroring the site's tiles
    M = 48
    d.rounded_rectangle([M, M, W - M, H - M], radius=28, fill=CARD,
                        outline=(228, 228, 228), width=2)
    # accent rule down the left edge of the card
    d.rounded_rectangle([M, M + 40, M + 7, H - M - 40], radius=4, fill=ACCENT)

    PAD = M + 56
    badge(im, (PAD, M + 56), 76)
    d = ImageDraw.Draw(im)

    f_eyebrow = font("Medium", 25)
    d.text((PAD + 100, M + 76), "UPDATING", font=f_eyebrow, fill=ACCENT)
    d.text((PAD + 100, M + 76 + 32), "mpbarbosa.github.io/updating",
           font=font("Regular", 22), fill=FAINT)

    maxw = W - PAD * 2
    y = M + 196

    f_title = font("Bold", 78)
    tl = wrap(d, title, f_title, maxw)
    if len(tl) > 2:
        f_title = font("Bold", 62)
        tl = wrap(d, title, f_title, maxw)
    for line in tl[:2]:
        d.text((PAD, y), line, font=f_title, fill=INK)
        y += round(f_title.size * 1.14)

    y += 14
    f_sub = font("Medium", 36)
    for line in wrap(d, sub, f_sub, maxw)[:2]:
        d.text((PAD, y), line, font=f_sub, fill=INK2)
        y += round(f_sub.size * 1.28)

    f_meta = font("Regular", 27)
    ml = wrap(d, meta, f_meta, maxw)[:2]
    my = H - M - 56 - (len(ml) - 1) * round(f_meta.size * 1.3)
    for line in ml:
        d.text((PAD, my), line, font=f_meta, fill=FAINT)
        my += round(f_meta.size * 1.3)

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{slug}.png")
    # 128-colour palette: these are flat cards, and it roughly halves the bytes
    im.convert("P", palette=Image.ADAPTIVE, colors=128).save(path, optimize=True)
    print(f"{path}  {os.path.getsize(path) / 1024:.1f} KB")


for c in CARDS:
    card(*c)
