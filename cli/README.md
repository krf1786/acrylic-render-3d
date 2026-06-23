# Finish Preview — `prep.py`

Turn any print PDF that has **named spot/finish channels** into a self-contained,
photoreal 3D finish preview — one `.html` file you can open and share. This is the
reliable "works on any file" tool; the browser drag-and-drop version is being built
on the same engine.

## One-time setup (Mac)

1. Install Ghostscript (does the spot-channel separation):

   ```
   brew install ghostscript
   ```

2. Install the two Python packages:

   ```
   pip3 install pillow numpy
   ```

## Use it

```
python3 prep.py "My Print File.pdf"
```

That writes `My Print File — preview.html` next to your PDF. Double-click to open.

Options:

```
python3 prep.py "file.pdf" output.html --width 1600   # custom name + resolution
```

It prints what it found, e.g.:

```
Detected 6 finish channel(s):
  • Black Matt            -> ink, matte
  • Black Gloss           -> ink, gloss
  • Mirror Silver Gloss   -> metal, gloss
  • Mirror Silver Matt    -> metal, matte +flake
  • Mirror gold gloss     -> metal, gloss
  • Mirror gold Matt      -> metal, matte +flake
```

## In the viewer

- **Drag** to tilt the piece; **scroll** to zoom.
- **Drop a photo** anywhere on the canvas (or "Load photo…") to make the metal reflect
  *your* environment — a shot of your shop or a studio HDRI gets you closest to real.
- Each detected finish has a **toggle** and an **auto / gloss / matte / mirror** override
  if the auto-guess is off.
- **Exposure** and **Env brightness** sliders control the lighting.

## How finishes are auto-assigned

The tool reads each spot channel's **name** and assigns a material:

| Name contains…            | Becomes |
|---------------------------|---------|
| silver / chrome / mirror  | neutral mirror metal |
| gold / brass              | gold metal |
| copper / bronze / rose    | copper metal |
| black / (process K)       | black ink |
| white                     | white ink |
| **gloss / uv / shiny**    | smooth + clear coat (mirror-shiny) |
| **matt / soft / velvet**  | rough (matte); metals get the glitter flake |
| satin                     | semi-gloss |

If a name doesn't match, it falls back to a neutral finish you can fix with the
override dropdown in the viewer.

## Known limits (v1)

- Needs a PDF with **named spot/finish channels** (like the JFX200 files). Process-only
  CMYK files with no spot finishes won't separate into finishes.
- The piece is rendered **flat** (the real print is flat); the slab has a black back but
  no modeled side-edge yet.
- Embossing / debossing / dimensional varnish are treated as flat finishes for now.
