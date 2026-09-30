"""
Render the album's 248 frames with a TRANSPARENT background, for the website.

Run it from inside Blender with NB_album.blend open:
    Scripting workspace -> Open -> this file -> Run Script

It writes PNGs with alpha to frames_web/, and leaves the .blend's own render
settings exactly as it found them. Converting those PNGs to the WebP the site
serves is a separate step, described at the bottom.

Why this exists, rather than just re-running build_book.py:
  * build_book.py rebuilds the scene and would discard the lighting and leather
    tweaks that were made by hand in the .blend afterwards. This script only
    touches render settings.
  * The site's hero sits on an apricot page, so the frames cannot carry the
    grey backdrop the archival JPEG render has baked in.

The one thing lost by going transparent: EEVEE has no shadow catcher, so the
book's contact shadow does not survive. Setting Table.is_shadow_catcher does
nothing here - that is a Cycles feature, and Cycles on this machine's GTX 970
turns a 12-minute render into an hours-long one. The shadow is drawn in CSS
instead, in styles.css under `.book-side::after, .album-shadow`.
"""

import bpy
import os

OUT = os.path.join(os.path.dirname(bpy.data.filepath), "frames_web")
WIDTH, HEIGHT = 1600, 900

scene = bpy.context.scene
render = scene.render
table = bpy.data.objects["Table"]

# remember everything we are about to change
before = {
    "engine": render.engine,
    "film_transparent": render.film_transparent,
    "filepath": render.filepath,
    "file_format": render.image_settings.file_format,
    "color_mode": render.image_settings.color_mode,
    "resolution_x": render.resolution_x,
    "resolution_y": render.resolution_y,
    "frame_start": scene.frame_start,
    "frame_end": scene.frame_end,
    "table_hide_render": table.hide_render,
}

try:
    os.makedirs(OUT, exist_ok=True)

    render.engine = "BLENDER_EEVEE"
    render.film_transparent = True
    table.hide_render = True          # the backdrop must not render at all
    render.resolution_x, render.resolution_y = WIDTH, HEIGHT
    render.resolution_percentage = 100
    render.image_settings.file_format = "PNG"   # Blender's WebP writer drops alpha
    render.image_settings.color_mode = "RGBA"
    render.image_settings.color_depth = "8"
    render.image_settings.compression = 15
    render.filepath = OUT + os.sep

    scene.frame_start, scene.frame_end, scene.frame_step = 1, 248, 1
    bpy.ops.render.render(animation=True)

    print("Rendered 248 transparent frames to %s" % OUT)

finally:
    render.engine = before["engine"]
    render.film_transparent = before["film_transparent"]
    render.filepath = before["filepath"]
    render.image_settings.file_format = before["file_format"]
    render.image_settings.color_mode = before["color_mode"]
    render.resolution_x = before["resolution_x"]
    render.resolution_y = before["resolution_y"]
    scene.frame_start = before["frame_start"]
    scene.frame_end = before["frame_end"]
    table.hide_render = before["table_hide_render"]
    print("Render settings restored.")


# ---------------------------------------------------------------------------
# Turning the PNGs into the frames the site serves
#
# The site wants WebP with alpha at two sizes. Blender cannot write those, so
# do it outside Blender with sharp (Node):
#
#     npm install sharp
#     node convert_frames.js frames_web nb-photography-site
#
# convert_frames.js writes nb-photography-site/frames/desktop (1600x900,
# quality 72) and .../frames/mobile (960x540, quality 70), and clears both
# folders first so old frames cannot linger.
#
# Afterwards, confirm alpha actually survived - a WebP silently flattened to
# opaque looks fine in isolation and wrong on the page:
#
#     node -e "const b=require('fs').readFileSync('nb-photography-site/frames/desktop/0001.webp'); \
#              console.log(b.slice(12,16).toString('ascii'), (b[20]&0x10)?'has alpha':'NO ALPHA')"
#
# It must print: VP8X has alpha
#
# If the frame count ever changes, update data-frame-count on the hero section
# in index.html to match.
# ---------------------------------------------------------------------------
