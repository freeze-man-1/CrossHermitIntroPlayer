# Cross Hermit — Intro Player (web / translatable)

A self-contained, frame-exact recreation of the *Cross Hermit* opening cutscene
that runs in any modern browser and can be hosted on **GitHub Pages**. It plays
back a captured per-frame draw log against the game's extracted sprite set, with
synced music — and supports **per-language sprite swaps** so the intro can be
translated.

## Quick start (host it)

1. Put the contents of this folder at the root of a repository (or in `/docs`).
2. Enable GitHub Pages for that branch/folder in the repo settings.
3. Open the Pages URL. That's it — no drag-and-drop, nothing to install.

Total size is ~25 MB (the textures are PNGs, not the 96 MB `OPDATA.BIN`).

```
index.html                         the player
assets/
  OPENING.mp3                      music
  replay.json.gz                   per-frame draw log
  overlay.json.gz                  overlays (orange rings, white flash, hands-orb)
  textures/
    manifest.json                  texture index + dimensions
    opdata/opdata_00.png … _47.png 48 sprite textures (the default set)
    opdata2/orb_00.png   … _52.png 53 orb animation frames
languages/
  languages.json                   the dropdown list
  en/opdata_00.png …               per-language texture overrides (example)
```

## How translation works

Almost all of the intro's text lives in a **single texture**, `opdata_00.png`
— it is one big atlas containing every line of narration, the "Welcome to the
Farthest" / "Cross Hermit" titles, the credits, and "presented by enterbrain".
The player draws sub-rectangles of it. A few extra characters are baked into the
orange-ring composite (`opdata_22.png` / `opdata_23.png`).

So to translate the intro you only need to repaint a handful of PNGs:

1. **Copy** the text textures into a new language folder, e.g.
   `languages/fr/opdata_00.png` (start from `assets/textures/opdata/opdata_00.png`).
2. **Repaint** the text in your language, keeping each text block roughly in the
   same place and size as the original (the draw log samples fixed rectangles).
   Keep the PNG the same pixel dimensions.
3. Add the language to `languages/languages.json`:
   ```json
   {
     "languages": [
       { "code": "__default__", "name": "Original (Japanese/Chinese)" },
       { "code": "fr", "name": "Français", "textures": [0, 22, 23] }
     ]
   }
   ```
   `textures` lists which texture indices your folder overrides. Anything not
   listed (or missing) falls back to the default set, so you only ship the PNGs
   you actually changed.
4. Reload — your language appears in the dropdown and plays with your sprites.

## Editing textures / putting them back in the game

Two scripts (Python 3, needs `pillow` and `numpy`):

**Extract** every sprite from the originals to PNG:

```bash
python extract_textures.py --opdata OPDATA.BIN --opdata2 OPDATA2.BIN --out textures/
```

The PNGs are lossless: the original 16-bit ARGB1555 pixels round-trip exactly
(the opacity bit becomes PNG alpha; the 5-bit colour channels expand reversibly).

**Repack** edited PNGs back into `.BIN` files (to test a translation in the real
game):

```bash
python repack_textures.py --in textures/ --opdata-out OPDATA.BIN --opdata2-out OPDATA2.BIN
```

Repacking unmodified PNGs reproduces the original `OPDATA.BIN` **byte-for-byte**,
so untouched textures are never altered. (`OPDATA2`'s orb frames are re-encoded
as indexed BMPs; the non-image entries are restored verbatim.)

## Notes / limitations

- The vertical text layout in the original suits CJK; long Latin strings may need
  you to lay the text out horizontally within the same texture region.
- A couple of bar/background colours and the scene-7 sage opacity were measured
  from the reference video rather than captured, so they're faithful but not
  ground-truth.
- The draw log, overlay data, and music are the same for every language — only
  the sprite textures are swapped.
