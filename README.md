# Acrylic Finish Preview

Photoreal previews of printed / finished acrylic pieces, straight from the print files.
Drop in a print PDF that has named spot/finish channels (gloss, matte, mirror foil, etc.)
and get an interactive 3D render with real environment reflections — matte vs. gloss,
metallic foils, velvet black, clear/frosted acrylic layers, thickness, cutouts and more.

Built for sign / print shops (e.g. mirror-vinyl-on-acrylic jobs printed on a Mimaki JFX200).

## What's in here

```
tools/
  finish-preview-layers.html   ← MAIN app. Multi-layer laminated acrylic builder.
                                  Drop PDFs + add clear/frosted/colored sheets, stack
                                  them with real thickness, cutouts, lighting & scenes.
  finish-preview-drop.html     ← Single-piece version. Drop one PDF, get one rendered piece.
  finish-preview-3d.html       ← Early hard-coded demo (the original plaque), for reference.
cli/
  prep.py                      ← Command-line: turn a PDF into a self-contained preview .html
  README.md                    ← prep.py usage
docs/
  finish-preview-plan.md       ← Technical write-up of the approach
```

## Quick start (no installs)

Open **`tools/finish-preview-layers.html`** in a modern browser (Chrome/Edge/Safari/Firefox).
First load downloads the in-browser engine (~16 MB, cached after). Then:

1. **Drop a print PDF** onto the window → it becomes a printed layer.
2. **+ Add blank acrylic sheet** → set its type (clear / frosted / colored), thickness, opacity.
3. Stack and reorder layers (bottom → top), rename them, toggle individual finishes.
4. **Drag** to tilt · **middle/right-drag** to pan · **scroll** to zoom.
5. Set **Lighting** (key position + size), a **Backdrop**, or a **Photoreal scene** (free CC0 HDRIs),
   **drop a photo** to reflect your own room, or turn on **Stand on black glass** + auto-rotate.

## How it works

- The print PDF is separated into its named spot/finish channels entirely in the browser,
  using **Ghostscript compiled to WebAssembly** (`@jspawn/ghostscript-wasm`) + **UTIF** to decode
  the TIFF separations. No server, no install.
- Each finish is auto-classified from its channel name into a PBR material
  (`gloss/uv` → clearcoat mirror, `matt/soft` → matte + metallic flake, `silver/gold/mirror` → metal, etc.).
- Rendering is **three.js MeshPhysicalMaterial** with real prefiltered environment reflections
  (Fresnel, clearcoat, ACES tonemapping) — which is what makes the metal/foil read as real.

## The command-line route (`cli/prep.py`)

If you'd rather batch files, `prep.py` does the same separation server-side and writes a
self-contained preview `.html` per PDF. Needs Ghostscript (`brew install ghostscript`) +
`pip3 install pillow numpy`. See `cli/README.md`.

## Requirements / notes

- Print files must carry **named spot/finish channels** (this is how matte vs. gloss is known —
  they look identical in a flat render).
- Photoreal scenes load CC0 HDRIs from Poly Haven at runtime (needs internet).
- Acrylic thickness is shown relative to an assumed ~11" tall piece (visually proportional).

## Credits / licenses

- [three.js](https://threejs.org) (MIT)
- [@jspawn/ghostscript-wasm](https://github.com/jsscheller/ghostscript-wasm) — Ghostscript is **AGPL-3.0**
  (fine for internal/shop use; review before redistributing as a product)
- [UTIF.js](https://github.com/photopea/UTIF.js) (MIT)
- Photoreal HDRIs: [Poly Haven](https://polyhaven.com) (CC0)
