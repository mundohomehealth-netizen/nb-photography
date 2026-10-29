"""Cuts the hero video down to the frames the site actually needs.

    blender -b -P extract_hero.py -- <video> <outdir>

Blender does the decoding because it is installed and ffmpeg is not.

Why a curated list rather than every Nth frame. The clip is 721 frames and a
long way from uniform: it holds on the closed cover, spends five seconds
opening, then alternates between page turns and settled spreads that barely
move for two seconds at a time. Sampling it evenly would spend a quarter of
the payload on frames that are identical to their neighbours, and - worse -
the scroll would map a quarter of its travel onto nothing happening, which
reads as the page having stuck.

So the bands below were measured off the clip rather than guessed: the mean
absolute frame-to-frame difference was taken every third frame, and the
boundaries are where it rises out of and falls back into the noise floor.
Motion is kept at every second frame; the holds keep just enough to register
as a pause before the next page lifts.

The manifest it writes alongside is what the site reads - the renumbered
frames, and which of them are the settled spreads the scroll comes to rest on.
"""
import bpy, sys, os, json

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SRC = os.path.abspath(argv[0])
# Absolute, always. Blender resolves a bare relative render path against the
# drive root rather than the working directory, so "frames_hero" quietly
# wrote 245 files to C:\frames_hero the first time this was run.
OUT = os.path.abspath(argv[1])
os.makedirs(OUT, exist_ok=True)

# (first, last, step, is_stop) - is_stop marks the band whose FIRST kept frame
# is a settled spread the scroll can rest on.
BANDS = [
    (1,   55,  11, True),    # the closed cover, held
    (58,  177,  2, False),   # the case opening - the longest move in the clip
    (178, 183,  3, True),    # first spread, settled
    (184, 240,  2, False),   # turn 1
    (241, 297, 14, True),    # spread 2
    (298, 363,  2, False),   # turn 2
    (364, 402, 13, True),    # spread 3
    (403, 468,  2, False),   # turn 3
    (469, 501, 11, True),    # spread 4
    (502, 570,  2, False),   # turn 4
    (571, 606, 12, True),    # spread 5
    (607, 663,  2, False),   # turn 5
    (664, 721, 12, True),    # the last spread, held
]

sc = bpy.context.scene
se = sc.sequence_editor_create()
st = se.strips.new_movie("clip", SRC, channel=1, frame_start=1)
el = st.elements[0]
W, H = el.orig_width, el.orig_height

r = sc.render
r.resolution_x, r.resolution_y = W, H
r.resolution_percentage = 100
r.image_settings.file_format = "PNG"
r.image_settings.color_mode = "RGB"           # the clip carries no alpha
r.image_settings.compression = 15
sc.view_settings.view_transform = "Standard"  # no grade over the source

wanted, stops = [], []
for first, last, step, is_stop in BANDS:
    band = list(range(first, min(last, st.frame_final_duration) + 1, step))
    if not band:
        continue
    if is_stop:
        stops.append(len(wanted) + 1)         # 1-based index of this band's first frame
    wanted.extend(band)

print("CLIP %dx%d, %d frames -> keeping %d, %d stops"
      % (W, H, st.frame_final_duration, len(wanted), len(stops)), flush=True)

for i, src_frame in enumerate(wanted, start=1):
    sc.frame_set(src_frame)
    r.filepath = os.path.join(OUT, "%04d" % i)
    bpy.ops.render.render(write_still=True)
    if i % 25 == 0:
        print("  %d/%d" % (i, len(wanted)), flush=True)

manifest = {
    "source": os.path.basename(SRC),
    "sourceFrames": st.frame_final_duration,
    "width": W, "height": H,
    "count": len(wanted),
    "stops": stops,
    "map": wanted,                            # new index i -> source frame map[i-1]
}
with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2)
print("MANIFEST " + json.dumps({"count": len(wanted), "stops": stops}), flush=True)
