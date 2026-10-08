# Bundled game font

`glyphs.png` is a 12×24 RGBA atlas; `glyphs.json` maps its cells to Unicode.
It contains the glyphs from the following fonts, in fallback order:

- DejaVu Sans Mono and DejaVu Sans, version 2.37: https://github.com/dejavu-fonts/dejavu-fonts/releases/tag/version_2_37
- Noto Sans Symbols 2: https://github.com/google/fonts/tree/main/ofl/notosanssymbols2

The original TTF files and their licenses are included here. The game loads the
atlas directly through python-tcod and needs no system fonts or Pillow at runtime.
To rebuild after changing fonts: `python -m pip install Pillow`, then
`python scripts/build_font.py` from the project root.
