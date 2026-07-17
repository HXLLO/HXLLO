#!/usr/bin/env python3
"""Generate fastfetch-style profile card SVGs (dark/light) from an avatar image.

Pipeline: magick dumps a WxH pixel grid as text, we map each pixel to an
ASCII char (density by luminance) + color, group same-color runs into tspans,
and lay out a terminal card with the thomas.how palette and embedded Geist Mono.
"""
import base64
import re
import subprocess
import sys
from pathlib import Path

IMG = str(Path(__file__).parent / "assets" / "avatar.jpg")
FONT = "/Users/h/Documents/code/how/fonts/geist-mono-latin.woff2"
OUT_DIR = Path(__file__).parent / "assets"
SCRATCH = Path(__file__).parent

# grid geometry
COLS, ROWS = 72, 44
CROP = "500x500+220+10"  # tete seule dans l'image 930x930
CELL_W, CELL_H = 3.6, 6.0  # font 6px, advance 0.6em
ART_FS = 6

# thomas.how palette
DARK = dict(bg="#0b0c0e", text="#ededf0", text2="#9fa3ab", text3="#7d8087",
            line="#ffffff", line_op="0.08", accent="#6ea8ff", ok="#4fbf7e")
LIGHT = dict(bg="#fafaf8", text="#17181a", text2="#575a60", text3="#7d8087",
             line="#000000", line_op="0.10", accent="#3b76d6", ok="#2f9e5f")

RAMP = " .`':;=+*#%@"


def pixels():
    # floodfill des 4 coins pour virer le fond tatami, puis boost contraste/saturation
    txt = subprocess.run(
        ["magick", IMG, "-crop", CROP, "+repage",
         "-fuzz", "14%", "-fill", "none",
         "-draw", "alpha 1,1 floodfill", "-draw", "alpha 498,1 floodfill",
         "-draw", "alpha 1,498 floodfill", "-draw", "alpha 498,498 floodfill",
         "-draw", "alpha 250,1 floodfill", "-draw", "alpha 1,250 floodfill",
         "-modulate", "100,140,100", "-sigmoidal-contrast", "5x50%",
         "-resize", f"{COLS}x{ROWS}!", "-colorspace", "sRGB", "-depth", "8", "txt:-"],
        capture_output=True, text=True, check=True).stdout
    grid = [[None] * COLS for _ in range(ROWS)]
    pat = r"^(\d+),(\d+):\s*\([^)]*\)\s+#([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?"
    for m in re.finditer(pat, txt, re.M):
        x, y = int(m.group(1)), int(m.group(2))
        h = m.group(3)
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = int(m.group(4), 16) if m.group(4) else 255
        grid[y][x] = None if a < 110 else (r, g, b)
    return grid


def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def quant(c, step=28):
    return tuple(min(255, int(round(v / step) * step)) for v in c)


def hexc(c):
    return "#%02x%02x%02x" % c


def art_lines(grid, mode):
    """Rows of (char, color-or-None). Meme silhouette dark/light, couleurs adaptees au fond."""
    rows = []
    for row in grid:
        line = []
        for c in row:
            if c is None:
                line.append((" ", None))
                continue
            l = lum(c) / 255
            # ramp resseree: la couleur porte l'image, la densite ne fait
            # que moduler la texture
            vis = "=+*#%@"
            ch = vis[int(l * (len(vis) - 1) + 0.5)]
            if mode == "dark":
                # lift: garde la teinte mais assure la visibilite sur #0b0c0e
                boost = max(0.0, 0.38 - l) * 255 * 0.85
                col = tuple(min(255, int(v * 1.1 + boost)) for v in c)
            else:
                # assombrit pour contraster sur fond clair, en gardant la teinte
                col = tuple(int(v * 0.62) for v in c)
            line.append((ch, quant(col)))
        rows.append(line)
    return rows


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def art_svg(rows, x0, y0):
    out = []
    for j, row in enumerate(rows):
        y = y0 + j * CELL_H
        spans, cur, buf = [], "SKIP", []
        def flush():
            if buf:
                if cur is None:
                    spans.append("<tspan>%s</tspan>" % esc("".join(buf)))
                else:
                    spans.append('<tspan fill="%s">%s</tspan>' % (hexc(cur), esc("".join(buf))))
        for ch, col in row:
            key = col
            if key != cur:
                flush()
                cur, buf = key, []
            buf.append(ch)
        flush()
        out.append('<text x="%g" y="%g" xml:space="preserve" class="art">%s</text>'
                   % (x0, y, "".join(spans)))
    return "\n".join(out)


def build(theme_name, P):
    grid = pixels()
    rows = art_lines(grid, theme_name)
    font_b64 = base64.b64encode(Path(FONT).read_bytes()).decode()

    W = 880
    art_x, art_y = 36, 88
    art_w = COLS * CELL_W
    col_x = art_x + art_w + 44
    art_bottom = art_y + ROWS * CELL_H

    info = [
        ("user", None, "thomas@housset"),
        ("rule", None, None),
        ("role", "ai & security engineer", None),
        ("work", "@advens · ex deputy ciso @mercedes-benz", None),
        ("mission", "deploys ai & security in large enterprises", None),
        ("stack", "python · ts · go · rust · cloud", None),
        ("ai", "agentic coding · agent apps · llm apis", None),
        ("based", "paris, france", None),
    ]

    projects = [
        ("acquis.app", "OSINT platform for M&A cyber due diligence"),
        ("RegulAIte", "multi-agent RAG over EU cyber regulation"),
        ("FishSentinel", "phishing simulation framework"),
        ("WayTrace", "Wayback Machine intelligence toolkit, crash-resumable"),
        ("research.thomas.how", "public research hub: thesis, projects, certifications, notes"),
    ]

    y = art_y + 6
    lh = 26
    lines = []
    for key, val, special in info:
        if key == "user":
            lines.append('<text x="%g" y="%g" class="k b">%s</text>' % (col_x, y, special))
        elif key == "rule":
            lines.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-opacity="%s" stroke-width="1"/>'
                         % (col_x, y - 5, col_x + 130, y - 5, P["line"], P["line_op"]))
            y += lh - 14
            continue
        else:
            lines.append('<text x="%g" y="%g" class="k">%s</text>' % (col_x, y, key))
            lines.append('<text x="%g" y="%g" class="v">%s</text>' % (col_x + 96, y, esc(val)))
        y += lh

    # rangee de swatches facon fastfetch, dans la palette du site
    sw = ["#6ea8ff", "#8dbbff", "#4fbf7e", P["text"], P["text2"], P["text3"]]
    sx = col_x
    swatches = []
    for c in sw:
        swatches.append('<rect x="%g" y="%g" width="18" height="10" rx="2" fill="%s"/>' % (sx, y - 2, c))
        sx += 24

    # section projets + contact, fusionnee dans la carte
    extra = []
    div_y = art_bottom + 18
    extra.append('<line x1="0" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-opacity="%s"/>'
                 % (div_y, W, div_y, P["line"], P["line_op"]))
    py = div_y + 38
    extra.append('<text x="%g" y="%g" class="v"><tspan fill="%s">$</tspan> <tspan fill="%s">ls projects/</tspan></text>'
                 % (art_x, py, P["ok"], P["text2"]))
    py += 30
    for name, desc in projects:
        extra.append('<text x="%g" y="%g" class="k">%s</text>' % (art_x, py, esc(name)))
        extra.append('<text x="%g" y="%g" class="v">%s</text>' % (art_x + 196, py, esc(desc)))
        py += 24
    py += 22
    extra.append('<text x="%g" y="%g" class="v"><tspan fill="%s">$</tspan> <tspan fill="%s">cat links</tspan></text>'
                 % (art_x, py, P["ok"], P["text2"]))
    py += 26
    extra.append('<text x="%g" y="%g" class="k">&#8595;&#160;&#160;&#8595;&#160;&#160;&#8595;</text>'
                 % (art_x, py))
    H = int(py + 26)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" fill="none">
<style>
@font-face {{
  font-family: 'Geist Mono';
  font-weight: 400 500;
  src: url(data:font/woff2;base64,{font_b64}) format('woff2');
}}
text {{ font-family: 'Geist Mono', ui-monospace, SFMono-Regular, Menlo, monospace; }}
.art {{ font-size: {ART_FS}px; }}
.k {{ font-size: 13px; font-weight: 500; fill: {P["accent"]}; }}
.b {{ font-weight: 500; }}
.v {{ font-size: 13px; fill: {P["text"]}; }}
.t {{ font-size: 12px; fill: {P["text3"]}; }}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="{P["bg"]}" stroke="{P["line"]}" stroke-opacity="{P["line_op"]}"/>
<circle cx="26" cy="26" r="5.5" fill="#ff5f57"/>
<circle cx="46" cy="26" r="5.5" fill="#febc2e"/>
<circle cx="66" cy="26" r="5.5" fill="#28c840"/>
<text x="{W / 2}" y="30" text-anchor="middle" class="t">thomas@housset — zsh</text>
<line x1="0" y1="52" x2="{W}" y2="52" stroke="{P["line"]}" stroke-opacity="{P["line_op"]}"/>
{art_svg(rows, art_x, art_y)}
{"".join(lines)}
{"".join(swatches)}
{"".join(extra)}
</svg>
'''
    return svg


def main():
    OUT_DIR.mkdir(exist_ok=True)
    for name, P in (("dark", DARK), ("light", LIGHT)):
        svg = build(name, P)
        out = OUT_DIR / f"fetch-{name}.svg"
        out.write_text(svg)
        print(out, len(svg) // 1024, "KB")


if __name__ == "__main__":
    main()
