# Print Finish Preview — Technical Plan

A tool that takes a real print file and renders it as a finished acrylic piece: matte where it's matte, gloss where it's gloss, mirror metal where it's foil, with real acrylic color, thickness, and glued-layer depth.

---

## 1. Why this is achievable (what your file already gives us)

Your `Print SC All 1_outlines.pdf` is not a flat image. It carries **six named spot-finish channels**, each one a separate stencil telling the press *which region gets which finish*:

| Spot channel in your file | What it is |
|---|---|
| Black Matt | flat black, no sheen |
| Black Gloss | black spot-gloss / raised UV |
| Mirror Silver Matt | satin silver foil |
| Mirror Silver Gloss | polished mirror silver |
| Mirror Gold Matt | satin gold foil |
| Mirror Gold Gloss | polished mirror gold |

**The analogy:** it's a coloring book where every region is already labeled with which finish to use — except the labels are finishes, not colors. We don't have to guess what's matte vs. gloss vs. mirror. We just read each labeled region and assign it a *material* (how it catches light), then shine a virtual light on it.

This is the whole reason the prototype works: extraction is deterministic, not AI-guessed.

### The real physical stack (Mimaki JFX200)

This specific job is **mirror vinyl mounted to 1/4" black acrylic**, printed on a Mimaki JFX200 UV flatbed (CMYK + White + Clear). The mirror vinyl is the source of *all* the metallic look — the inks just decide what happens to that mirror:

| Printed finish | What the ink does to the mirror | Result |
|---|---|---|
| Silver | clear ink over bare mirror | neutral mirror shows through |
| Gold | clear + a little CMYK over mirror | warm-tinted mirror |
| Black | opaque ink | mirror hidden, reads black |
| Gloss (any color) | smooth clear **top coat** on top | sharp, mirror-smooth reflection |
| Matte (any color) | **no top coat** — bare UV-cured surface | grainy, metallic, non-reflective |

Two consequences for the renderer, both now built in: the metal is modeled as a **real mirror reflecting an environment** (not flat paint), and **matte vs. gloss is the roughness of that mirror** — gloss = smooth mirror under a clear top coat, matte = the bare UV-cured surface whose micro-texture scatters the mirror into a grainy metallic sheen.

---

## 2. How the prototype works (the pipeline)

```
PDF (spot channels)
   │  Ghostscript "tiffsep" — splits the file into one grayscale mask per finish
   ▼
6 finish masks  +  die-cut silhouette  +  base color
   │  each mask drives a material: base color, metalness, roughness, surface height
   ▼
Real-time shader (WebGL)
   • movable light  → matte stays flat, gloss/foil throw a moving highlight
   • height map     → raised UV & stacked layers catch light on their edges
   • acrylic model  → substrate tint, edge bevel, cast shadow scaled by thickness
   • layer stack    → finishes on different glued sheets, parallax + shadow on tilt
   ▼
Interactive proof in the browser
```

The interactive prototype (`acrylic-print-preview.html`) runs this end to end on your actual plaque. It is a single self-contained file — no install, no server.

---

## 3. Finish → material mapping

Two physical principles drive the model:

1. **A matte/gloss pair is the *same material*** — gloss just adds a smooth **clear top coat** on top. So glossy black is piano-black shiny and glossy silver/gold is mirror-shiny, but neither *changes color*. Matte has no top coat at all.
2. **Silver and gold are a real mirror, not paint** — their color comes from *tinted reflection* of the surrounding environment (silver = neutral clear over the mirror, gold = CMYK-tinted clear over the mirror). That's what makes them read as actual mirror metal rather than gray or yellow fill.

| Finish | Material | Color source | Metallic | Clear coat |
|---|---|---|---|---|
| Black matte | opaque ink | pigment (diffuse) | mirror hidden | — |
| Black gloss | same black + top coat | pigment + sharp surface reflection | mirror hidden | yes |
| Silver matte | bare cured mirror | grainy neutral reflection | mirror | — |
| Silver gloss | mirror + clear top coat | sharp neutral reflection | mirror | yes |
| Gold matte | bare cured mirror + CMYK | grainy warm reflection | mirror | — |
| Gold gloss | mirror + CMYK + top coat | sharp warm reflection | mirror | yes |

**How the light behaves:** glossy metals reflect a procedural room (dark floor, mid wall, bright softbox overhead) tinted by their color — and because the reflection vector is **tilted by the piece**, a flat mirror *sweeps* that room as you tilt, exactly like real mirror vinyl. The clear top coat adds a separate **white, Fresnel-weighted** reflection (strongest at glancing angles), independent of the base — which is why a glossy top coat looks shiny over *any* color.

**Matte is the bare UV-cured surface.** With no top coat, the cured ink over the mirror has a micro-texture that scatters the reflection into a **grainy metallic** that twinkles as the light moves but never becomes a mirror. The renderer models this as a frosted version of the same mirror plus a hash-based cured-grain sparkle; a "matte cure grain" slider controls its strength. Black matte (opaque ink, no mirror underneath) simply scatters light softly and stays flat.

The exact reflectance numbers are the part most worth calibrating against physical samples — see Roadmap.

---

## 4. The acrylic model (your follow-up requirements)

Three things you flagged are built into the prototype as live controls:

**Acrylic color** — the substrate tint, defaulting to **1/4" black** (the real base for this job), with swatches for smoke, frost-white, clear, and colored acrylics plus a custom picker. Clear/colored acrylic shows a Fresnel edge rim so it reads as a transparent slab, not paint.

**Thickness** — a 1–12 mm slider (default 6 mm ≈ 1/4") that scales three physical cues at once: the bevel highlight on the die-cut edge, the depth/softness of the cast shadow, and how far stacked layers float above each other.

**Multiple glued layers** — finishes can be assigned to different acrylic sheets:
- *Single sheet* — all finishes flush on one layer.
- *2 layers* — gloss/UV raised on a second sheet over the matte base.
- *3 layers* — black, silver, and gold each on their own sheet, glued into a stack.

Higher layers cast shadows on the ones below and shift slightly when you tilt (parallax), which is exactly how laminated acrylic reads in the hand. An "explode" toggle separates the stack so you can see the construction.

---

## 5. Form factor — recommendation

You said you weren't sure whether this should be a plugin or an app. Here's the trade-off, with a recommendation.

| Option | Strengths | Weaknesses | Best when |
|---|---|---|---|
| **Web app** (recommended start) | No install; runs anywhere; you can send clients a link to a live proof; fastest to build — the prototype already proves it | Not inside the design tool; relies on a clean exported PDF | You want client-facing proofs and the quickest path to something real |
| **Adobe plugin** (Acrobat / Illustrator / InDesign) | Lives where the files are made; one click from the artwork; reads spot channels natively | Slower to build & test; sandboxed UI; tied to Adobe's plugin platform | The main user is the prepress/design operator and never leaves Adobe |
| **Desktop app** (Mac/Win) | Batch-proof whole folders; heaviest rendering; works offline on huge files | Most to build, sign, and distribute; update friction | High-volume shop proofing many jobs a day |

**Recommended path:** start as the **web app** (you already have a working core), then wrap the same rendering engine as an **Acrobat/Illustrator panel** once the material library is dialed in. The hard part — turning spot channels into a believable lit surface — is identical across all three, so it's built once and reused.

---

## 6. Architecture for a real product

The engine is the asset; the wrapper is interchangeable.

1. **Ingest** — accept print PDF (or TIFF/PSD with spot channels). Detect spot/separation names automatically.
2. **Separate** — Ghostscript `tiffsep` (server-side) or a PDF.js + canvas separation path (fully in-browser) to produce one mask per finish + the die silhouette.
3. **Map** — match each spot name to a material via a rules table ("*Gloss*" → low roughness; "*Mirror*"/"*Foil*" → metallic; "*Matt*" → high roughness). Names it doesn't recognize fall back to sensible defaults and are flagged for the user to assign.
4. **Render** — the WebGL engine from the prototype: per-finish materials, height-driven normals, acrylic substrate, layer stack, movable light + environment.
5. **Wrap** — web page, Adobe panel, or desktop shell around the same engine.
6. **Output** — interactive viewer, plus exportable still images / a turntable GIF for client sign-off.

---

## 7. Roadmap

**Phase 1 — Prototype (done).** Hard-coded to your plaque's six finishes; proves the visual concept and the acrylic/layer controls.

**Phase 2 — Generalize ingest.** Auto-detect any spot names from any uploaded PDF; map by name rules; let the user re-assign unrecognized finishes. For JFX200-style files, also read the **White / Clear / CMYK** channels directly and infer the substrate behavior (clear-over-mirror = silver, clear+CMYK = gold, white/opaque = hide mirror, top-coat clear = gloss). Removes the hard-coding.

**Phase 3 — Calibrate materials.** Photograph real printed/foiled/UV samples under known light and tune the material table so silver, gold, soft-touch matte, and raised UV match physical proofs. This is what moves it from "convincing" to "trusted for sign-off."

**Phase 4 — Real layer geometry.** Replace the faked layer parallax with true per-layer depth (edge thickness, refraction through colored acrylic, proper inter-layer shadows) for accurate glued-stack previews.

**Phase 5 — Ship the wrapper.** Adobe panel and/or hosted client-proof links with image/GIF export.

---

## 8. Honest limitations of the prototype

- The six finishes are currently **hard-coded** to this file; Phase 2 generalizes it.
- Materials are **art-directed, not photometrically calibrated** — they look right but aren't yet matched to physical samples (Phase 3).
- Layer depth is a **convincing approximation** (parallax + shadow), not true 3D refraction (Phase 4).
- Best results need a **clean exported PDF** with named spot channels — which is exactly what your file already is.

None of these are blockers; they're the difference between a prototype and a production tool, and each has a clear path above.
