# NB Album Animation + narrated by nb website

Wedding photography site whose hero is a scroll-driven 3D leather album (rendered in Blender).
Owner is not a developer: explain changes in plain language and keep the site dependency-free.

## Folder map
- `nb-photography-site/` — **the live website** (plain HTML/CSS/JS, no build step). Deploy this folder to Netlify.
  - `index.html` — one page: album hero, intro, portfolio, about, packages, inquiry form, footer, lightbox
  - `thank-you.html` — form success page
  - `assets/css/styles.css` — design tokens at the top (`--table`, `--paper`, `--leather`, `--brass`, fonts)
  - `assets/js/album.js` — canvas player that maps scroll progress to frames 1–248; sets `--nb-p` (0–1) on the hero for CSS
  - `assets/js/main.js` — header state, mobile menu, portfolio filters, lightbox, package preselect
  - `assets/img/portfolio/` — each photo at 800/1600/2400 px WebP; `og-image.jpg`; `favicon.svg`
  - `frames/desktop/0001–0248.webp` (1600×900, q72) and `frames/mobile/` (960×540, q70), chosen by screen size
  - `_headers` — Netlify cache headers for frames and images
- `website/` — older standalone copy of just the hero snippet. Superseded by `nb-photography-site/`.
- `NB_album.blend` — Blender 5.2 scene (source of truth for the look).
- `build_book.py` — script that builds the base scene. Later tweaks made only in the .blend: key light 52 W, fill 8 W,
  world strength 0.10, EEVEE engine, darker/warmer leather ramps, antique-brass ramp. Re-applying the script loses these.
- `textures/` — page images (photos mounted on paper, handwritten captions), monogram mask, brass corner maps.
- `frames/` — full-quality JPEG render (frame_0001–0248.jpg). `video/NB_album_scroll.mp4` (all-intra, 24 fps).
- `run_render.bat` / `encode_mp4.py` — background render of all frames, then MP4 encode.

## Hero composition (the homepage)
The landing view is three square albums in a row behind a large `narrated` wordmark, with
`by nb` in script to its right. The middle album is the animated one, drawn on a full-bleed
canvas; the outer two are static WebPs (`assets/img/book-left.webp`, `book-right.webp`),
recoloured copies of the same model in cream and terracotta.

Scrolling drives `--nb-p` (0-1) on the hero, and everything keys off it:
- 0 to 0.05: the outer two books slide outward and fade, clearing before the cover starts
  opening at frame 10 (p = 0.036).
- 0 to 0.08: the wordmark fades.
- 0 to 0.18: the album grows from book-size to full-bleed (`GROW_UNTIL` in album.js).

All three books share the `--book-h` token. album.js **measures** it off the `.album-shadow`
element rather than parsing the custom property, because it is a `min()` expression that
`parseFloat` cannot resolve - parsing it silently yielded a 46px album.

Under 700px wide the outer books are hidden and the album takes 62% of the screen width;
three square albums cannot share a phone row.

## Frames are transparent
The frames the site serves carry an alpha channel, so the album sits straight on the apricot
page. Re-render them with `render_web_frames.py` (run inside Blender), then
`node convert_frames.js frames_web nb-photography-site`. Do not re-run `build_book.py` for
this - it rebuilds the scene and discards the hand-made lighting and leather tweaks.

Two traps:
- Blender's WebP writer drops alpha. Render PNG RGBA and convert outside Blender.
- EEVEE has no shadow catcher, so the contact shadow cannot be baked in; it is drawn in CSS
  (`.book-side::after, .album-shadow`). `Table.is_shadow_catcher` is a Cycles-only flag and
  does nothing here.

`data-frames-alpha` on the hero section tells album.js whether the frames have alpha. It must
stay `true` while the transparent frames are in place.
## Animation facts
- 248 frames @ 24 fps: closed 1–10, cover opens 10–50, then 5 page turns of 32 frames with 6-frame holds
  (56–88, 94–126, 132–164, 170–202, 208–240). Straight top-down camera, 1920×1080.
- Page turns use a Geometry Nodes group `PageTurn` (inputs Theta, Curl, RootZ, Width). In Blender 5.2 modifier inputs are
  set via `mod.properties.inputs.Socket_N.value`, keyframe path `modifiers["PageTurn"].properties.inputs.Socket_N.value`.
- GPU is a GTX 970: OptiX fails to load, use CUDA for Cycles. EEVEE (~5.5 s/frame) looks the same and is what's used.
- After re-rendering, rebuild the web frames: resize each JPEG to 1600×900 WebP (quality ~72) and 960×540 (quality ~70),
  named `0001.webp`… and replace `nb-photography-site/frames/desktop` and `/mobile`. Keep the frame count in
  `data-frame-count` on the hero section in sync.

## Captions (left pages) ↔ photos (right pages)
1 Petals, prayers and a thousand blessings — ceremony-petals · 2 The laughter in between the rituals — couple-laughter ·
3 Golden light, quiet grace — bride-golden-light · 4 A still moment before forever — bride-veil-bw ·
5 Barefoot at sunset, hand in hand — engagement-beach · 6 Showered in marigolds and pure joy — haldi-marigolds

## Still placeholders (search `EDIT:` in index.html)
Location "Toronto & destination", About copy, package prices ($3,200 / $4,800 / $6,900)
and inclusions, email `hello@yourdomain.com`, Instagram `@yourhandle`.

## Deploying
Netlify, manual drag-and-drop deploy of `nb-photography-site/`. The inquiry form uses Netlify Forms
(`data-netlify="true"`, honeypot `bot-field`, redirects to `/thank-you.html`); form detection must be enabled in the Netlify
site settings and an email notification added. A good next step is putting the site folder in git/GitHub and linking it to
Netlify so pushes deploy automatically.

## Ideas not done yet
- Portrait (9:16) render of the album for phones — on tall screens the widescreen frames make the book small.
- More portfolio photos; optional per-couple gallery pages.

## Working conventions
- No frameworks or build tools; vanilla JS, works when opened straight from disk.
- Test at 1440×900 and 390×844; check hero scroll forward and back, filters, lightbox, mobile menu, no horizontal scroll.
- Keep the album palette: cream paper, leather brown, antique brass; fonts Cormorant Garamond, Jost, La Belle Aurore.
