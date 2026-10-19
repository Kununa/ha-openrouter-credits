"""Render brand-src/icon.svg into the Home Assistant brand PNGs.

Usage: python brand-src/make_brand.py brand-src/icon.svg custom_components/openrouter_credits/brand

Writes icon.png (256), icon@2x.png (512) and dark_ variants. No logo.png is
shipped: Home Assistant falls back to the icon. Needs Pillow and a
Chromium-based browser (set BROWSER_BIN if Edge isn't at its default path).
"""

import os
import pathlib
import subprocess
import sys
import tempfile

from PIL import Image

svg_path, out_dir = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
browser = os.environ.get(
    "BROWSER_BIN", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
)
out_dir.mkdir(parents=True, exist_ok=True)
template = svg_path.read_text(encoding="utf-8")

RENDER = 1024  # render large, downscale for clean edges
THEMES = {
    "": {"BODY": "#1F2937", "DETAIL": "#F9FAFB"},  # light UI: dark artwork
    "dark_": {"BODY": "#E5E7EB", "DETAIL": "#111827"},  # dark UI: light artwork
}


def render(colors: dict[str, str]) -> Image.Image:
    svg = template
    for token, color in colors.items():
        svg = svg.replace(f'"{token}"', f'"{color}"')
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        (tmp / "icon.svg").write_text(svg, encoding="utf-8")
        (tmp / "page.html").write_text(
            "<html><body style='margin:0;background:transparent'>"
            f"<img src='icon.svg' width='{RENDER}' height='{RENDER}'>"
            "</body></html>",
            encoding="utf-8",
        )
        png = tmp / "shot.png"
        subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--default-background-color=00000000",
             f"--window-size={RENDER},{RENDER}",
             f"--user-data-dir={tmp / 'profile'}",
             f"--screenshot={png}", (tmp / "page.html").as_uri()],
            check=True, capture_output=True, timeout=60,
        )
        img = Image.open(png).convert("RGBA")
        img.load()
    return img


for prefix, colors in THEMES.items():
    art = render(colors)
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        art.resize((size, size), Image.LANCZOS).save(out_dir / f"{prefix}{name}", optimize=True)

for p in sorted(out_dir.iterdir()):
    print(p.name, Image.open(p).size)
