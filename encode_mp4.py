
import bpy, os
proj = r"C:\Users\Muhundan\Documents\NB Album Animation"
fd = os.path.join(proj, "frames")
frames = sorted(f for f in os.listdir(fd) if f.lower().endswith(".jpg"))
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1920, 1080, 100
sc.render.fps = 24
sc.view_settings.view_transform = 'Standard'
se = sc.sequence_editor_create()
coll = se.strips if hasattr(se, "strips") else se.sequences
st = coll.new_image("frames", os.path.join(fd, frames[0]), 1, 1)
for f in frames[1:]:
    st.elements.append(f)
sc.frame_start = 1; sc.frame_end = len(frames)
ims = sc.render.image_settings
try: ims.media_type = 'VIDEO'
except Exception: pass
ims.file_format = 'FFMPEG'
ff = sc.render.ffmpeg
ff.format = 'MPEG4'; ff.codec = 'H264'
ff.constant_rate_factor = 'HIGH'; ff.ffmpeg_preset = 'GOOD'
ff.gopsize = 1
ff.audio_codec = 'NONE'
sc.render.use_sequencer = True
sc.render.filepath = os.path.join(proj, "video", "NB_album_scroll.mp4")
sc.render.use_file_extension = False
bpy.ops.render.render(animation=True)
print("ENCODE_DONE", len(frames))
