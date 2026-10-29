"""Pulls frames out of the hero video.

Blender does the decoding because it is already installed and ffmpeg is not.
The video goes into the sequencer as a single strip, the scene takes the
clip's own pixel dimensions so nothing is resampled, and the range is written
out as PNG.

    blender -b -P extract_frames.py -- <video> <outdir> [step] [pct] [first] [last]

step samples every Nth frame (default 1); pct scales the output (default 100),
which is only ever used for the cheap analysis passes - the frames the site
serves are written at the clip's full resolution.
"""
import bpy, sys, os

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SRC = os.path.abspath(argv[0])
OUT = os.path.abspath(argv[1])   # Blender resolves a relative one against C:\
STEP = int(argv[2]) if len(argv) > 2 else 1
PCT = int(argv[3]) if len(argv) > 3 else 100
os.makedirs(OUT, exist_ok=True)

sc = bpy.context.scene
se = sc.sequence_editor_create()
st = se.strips.new_movie("clip", SRC, channel=1, frame_start=1)
el = st.elements[0]
W, H = el.orig_width, el.orig_height

r = sc.render
r.resolution_x, r.resolution_y = W, H
r.resolution_percentage = PCT
r.image_settings.file_format = "PNG"
r.image_settings.color_mode = "RGB"           # the clip has no alpha
r.image_settings.compression = 15
sc.view_settings.view_transform = "Standard"  # no grade over the source

first = int(argv[4]) if len(argv) > 4 else 1
last = int(argv[5]) if len(argv) > 5 else st.frame_final_duration

print("CLIP %dx%d, %d frames; writing %d..%d step %d at %d%%"
      % (W, H, st.frame_final_duration, first, last, STEP, PCT), flush=True)

n = 0
for f in range(first, last + 1, STEP):
    sc.frame_set(f)
    r.filepath = os.path.join(OUT, "%04d" % f)
    bpy.ops.render.render(write_still=True)
    n += 1
print("WROTE %d frames" % n, flush=True)
