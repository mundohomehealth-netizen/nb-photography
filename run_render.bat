@echo off
"D:\Downloads\blender.exe" -b "C:\Users\Muhundan\Documents\NB Album Animation\NB_album.blend" -a > "C:\Users\Muhundan\Documents\NB Album Animation\render_log.txt" 2>&1
"D:\Downloads\blender.exe" -b --factory-startup --python "C:\Users\Muhundan\Documents\NB Album Animation\encode_mp4.py" > "C:\Users\Muhundan\Documents\NB Album Animation\encode_log.txt" 2>&1
echo ALL_DONE > "C:\Users\Muhundan\Documents\NB Album Animation\render_done.txt"
