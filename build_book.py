import bpy, bmesh, math, os
from mathutils import Vector

TEX = r"C:\Users\Muhundan\Documents\NB Album Animation\textures"
def tex(name): return os.path.join(TEX, name)

# ---------------- clean scene ----------------
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
             bpy.data.images, bpy.data.node_groups, bpy.data.curves):
    for d in list(coll):
        try: coll.remove(d)
        except Exception: pass
scene = bpy.context.scene
col = scene.collection

# ---------------- dimensions (metres) ----------------
W, H, TC = 0.300, 0.310, 0.004          # cover board
PW, PH = 0.294, 0.302                   # leaves
LT, LS = 0.0010, 0.0012                 # leaf thickness / spacing
NLEAF = 6
FB = 0.006                              # blank page block under the leaves
TOP = TC + FB + NLEAF * LS              # top of leaf stack
HB = TOP + TC                           # total closed thickness
ZP = HB / 2                             # cover pivot height (spine centre)
CL = 0.042                              # brass corner size

def zR(i): return TC + FB + (NLEAF - i) * LS + LT   # top surface of leaf i when on the right
def zL(i): return TC + (i - 1) * LS                 # bottom surface of leaf i when on the left

# ---------------- helpers ----------------
def link(obj, parent=None):
    col.objects.link(obj)
    if parent: obj.parent = parent
    return obj

def box_mesh(name, x0, x1, y0, y1, z0, z1):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 if v.co.x < 0 else x1
        v.co.y = y0 if v.co.y < 0 else y1
        v.co.z = z0 if v.co.z < 0 else z1
    bm.to_mesh(me); bm.free()
    return me

def grid_mesh(name, x0, x1, y0, y1, nx, ny, uv_fn, z=0.0, flip=False):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    verts = [[bm.verts.new((x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny, z)) for j in range(ny + 1)] for i in range(nx + 1)]
    for i in range(nx):
        for j in range(ny):
            vs = [verts[i][j], verts[i + 1][j], verts[i + 1][j + 1], verts[i][j + 1]]
            if flip: vs = vs[::-1]
            f = bm.faces.new(vs)
            for lp in f.loops:
                u = (lp.vert.co.x - x0) / (x1 - x0); v = (lp.vert.co.y - y0) / (y1 - y0)
                lp[uvl].uv = uv_fn(u, v)
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    return me

def img(path, colorspace="sRGB"):
    im = bpy.data.images.load(path, check_existing=True)
    im.colorspace_settings.name = colorspace
    return im

def new_mat(name):
    m = bpy.data.materials.new(name)
    try: m.use_nodes = True
    except Exception: pass
    nt = m.node_tree
    return m, nt, nt.nodes, nt.links, nt.nodes["Principled BSDF"]

# ---------------- materials ----------------
def leather_mat(name, monogram=False):
    m, nt, N, L, b = new_mat(name)
    tc = N.new("ShaderNodeTexCoord")
    # colour mottling
    n1 = N.new("ShaderNodeTexNoise"); n1.inputs["Scale"].default_value = 9.0
    n1.inputs["Detail"].default_value = 6.0; n1.inputs["Roughness"].default_value = 0.6
    L.new(tc.outputs["Object"], n1.inputs["Vector"])
    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.30; cr.color_ramp.elements[0].color = (0.085, 0.030, 0.012, 1)
    cr.color_ramp.elements[1].position = 0.72; cr.color_ramp.elements[1].color = (0.215, 0.080, 0.032, 1)
    L.new(n1.outputs["Fac"], cr.inputs["Fac"])
    # fine swirl texture (the reference has a fine tooled/marbled grain)
    n2 = N.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 260.0
    n2.inputs["Detail"].default_value = 8.0; n2.inputs["Distortion"].default_value = 2.5
    L.new(tc.outputs["Object"], n2.inputs["Vector"])
    mixc = N.new("ShaderNodeMix"); mixc.data_type = 'RGBA'; mixc.blend_type = 'MULTIPLY'
    mixc.inputs["Factor"].default_value = 0.35
    L.new(cr.outputs["Color"], mixc.inputs[6])
    grain_col = N.new("ShaderNodeValToRGB")
    grain_col.color_ramp.elements[0].color = (0.55, 0.55, 0.55, 1); grain_col.color_ramp.elements[1].color = (1, 1, 1, 1)
    L.new(n2.outputs["Fac"], grain_col.inputs["Fac"])
    L.new(grain_col.outputs["Color"], mixc.inputs[7])
    base_out = mixc.outputs[2]
    # pebble grain bump
    vor = N.new("ShaderNodeTexVoronoi"); vor.feature = 'DISTANCE_TO_EDGE'; vor.inputs["Scale"].default_value = 700.0
    L.new(tc.outputs["Object"], vor.inputs["Vector"])
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.18; bump.inputs["Distance"].default_value = 0.0004
    L.new(vor.outputs["Distance"], bump.inputs["Height"])
    bump2 = N.new("ShaderNodeBump"); bump2.inputs["Strength"].default_value = 0.12; bump2.inputs["Distance"].default_value = 0.0003
    L.new(n2.outputs["Fac"], bump2.inputs["Height"]); L.new(bump.outputs["Normal"], bump2.inputs["Normal"])
    normal_out = bump2.outputs["Normal"]
    # roughness variation
    rr = N.new("ShaderNodeMapRange"); rr.inputs[3].default_value = 0.42; rr.inputs[4].default_value = 0.62
    L.new(n1.outputs["Fac"], rr.inputs[0])
    rough_out = rr.outputs[0]
    if monogram:
        mp = N.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1 / W, 1 / H, 1)
        mp.inputs["Location"].default_value = (0, 0.5, 0)
        L.new(tc.outputs["Object"], mp.inputs["Vector"])
        mt = N.new("ShaderNodeTexImage"); mt.image = img(tex("monogram_mask.png"), "Non-Color")
        mt.extension = 'CLIP'
        L.new(mp.outputs["Vector"], mt.inputs["Vector"])
        dk = N.new("ShaderNodeMix"); dk.data_type = 'RGBA'; dk.blend_type = 'MULTIPLY'
        L.new(mt.outputs["Color"], dk.inputs["Factor"])
        dk.inputs[7].default_value = (0.55, 0.50, 0.48, 1)
        L.new(base_out, dk.inputs[6]); base_out = dk.outputs[2]
        mb = N.new("ShaderNodeBump"); mb.invert = True
        mb.inputs["Strength"].default_value = 0.9; mb.inputs["Distance"].default_value = 0.0012
        L.new(mt.outputs["Color"], mb.inputs["Height"]); L.new(normal_out, mb.inputs["Normal"])
        normal_out = mb.outputs["Normal"]
        rm = N.new("ShaderNodeMath"); rm.operation = 'MULTIPLY_ADD'
        L.new(mt.outputs["Color"], rm.inputs[0]); rm.inputs[1].default_value = -0.15
        L.new(rough_out, rm.inputs[2]); rough_out = rm.outputs[0]
    L.new(base_out, b.inputs["Base Color"])
    L.new(normal_out, b.inputs["Normal"])
    L.new(rough_out, b.inputs["Roughness"])
    b.inputs["Specular IOR Level"].default_value = 0.45
    if "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = 0.15; b.inputs["Coat Roughness"].default_value = 0.35
    return m

def paper_mat(name, image_name, flip_u=False, rough=0.55):
    m, nt, N, L, b = new_mat(name)
    ti = N.new("ShaderNodeTexImage"); ti.image = img(tex(image_name)); ti.interpolation = 'Cubic'
    ti.extension = 'EXTEND'
    uv = N.new("ShaderNodeUVMap"); uv.uv_map = "UVMap"
    if flip_u:
        sep = N.new("ShaderNodeSeparateXYZ"); L.new(uv.outputs["UV"], sep.inputs[0])
        inv = N.new("ShaderNodeMath"); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
        L.new(sep.outputs["X"], inv.inputs[1])
        com = N.new("ShaderNodeCombineXYZ"); L.new(inv.outputs[0], com.inputs["X"]); L.new(sep.outputs["Y"], com.inputs["Y"])
        L.new(com.outputs[0], ti.inputs["Vector"])
    else:
        L.new(uv.outputs["UV"], ti.inputs["Vector"])
    L.new(ti.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = 0.35
    # fine paper tooth
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 900.0; nz.inputs["Detail"].default_value = 4
    tcn = N.new("ShaderNodeTexCoord"); L.new(tcn.outputs["Object"], nz.inputs["Vector"])
    bp = N.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.06; bp.inputs["Distance"].default_value = 0.0002
    L.new(nz.outputs["Fac"], bp.inputs["Height"]); L.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m

def simple_mat(name, color, rough=0.6, metallic=0.0):
    m, nt, N, L, b = new_mat(name)
    b.inputs["Base Color"].default_value = color
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    return m

def page_edge_mat():
    m, nt, N, L, b = new_mat("PageEdge")
    tc = N.new("ShaderNodeTexCoord")
    wv = N.new("ShaderNodeTexWave"); wv.wave_type = 'BANDS'; wv.bands_direction = 'Z'
    wv.inputs["Scale"].default_value = 350.0; wv.inputs["Distortion"].default_value = 2.0
    L.new(tc.outputs["Object"], wv.inputs["Vector"])
    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].color = (0.58, 0.52, 0.42, 1); cr.color_ramp.elements[1].color = (0.80, 0.75, 0.65, 1)
    L.new(wv.outputs["Fac"], cr.inputs["Fac"]); L.new(cr.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.8
    return m

def brass_mat():
    m, nt, N, L, b = new_mat("AntiqueBrass")
    uv = N.new("ShaderNodeUVMap")
    hi = N.new("ShaderNodeTexImage"); hi.image = img(tex("corner_height.png"), "Non-Color")
    al = N.new("ShaderNodeTexImage"); al.image = img(tex("corner_alpha.png"), "Non-Color")
    for t in (hi, al):
        t.extension = 'CLIP'; L.new(uv.outputs["UV"], t.inputs["Vector"])
    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.30; cr.color_ramp.elements[0].color = (0.10, 0.06, 0.02, 1)
    cr.color_ramp.elements[1].position = 0.80; cr.color_ramp.elements[1].color = (0.78, 0.55, 0.24, 1)
    L.new(hi.outputs["Color"], cr.inputs["Fac"]); L.new(cr.outputs["Color"], b.inputs["Base Color"])
    rr = N.new("ShaderNodeMapRange"); rr.inputs[3].default_value = 0.65; rr.inputs[4].default_value = 0.28
    L.new(hi.outputs["Color"], rr.inputs[0]); L.new(rr.outputs[0], b.inputs["Roughness"])
    b.inputs["Metallic"].default_value = 1.0
    bp = N.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 1.0; bp.inputs["Distance"].default_value = 0.0008
    L.new(hi.outputs["Color"], bp.inputs["Height"]); L.new(bp.outputs["Normal"], b.inputs["Normal"])
    L.new(al.outputs["Color"], b.inputs["Alpha"])
    return m

M_COVER = leather_mat("Leather_Cover", monogram=True)
M_LEATHER = leather_mat("Leather")
M_EDGE = page_edge_mat()
M_BRASS = brass_mat()

# ---------------- geometry-nodes: page turn ----------------
def make_page_turn_ng():
    ng = bpy.data.node_groups.new("PageTurn", 'GeometryNodeTree')
    try: ng.is_modifier = True
    except Exception: pass
    I = ng.interface
    I.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    for nm in ("Theta", "Curl", "RootZ", "Width"):
        I.new_socket(nm, in_out='INPUT', socket_type='NodeSocketFloat')
    I.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi = N.new("NodeGroupInput"); go = N.new("NodeGroupOutput")
    pos = N.new("GeometryNodeInputPosition")
    sep = N.new("ShaderNodeSeparateXYZ"); L.new(pos.outputs[0], sep.inputs[0])
    def M(op, a, b=None, c=None):
        n = N.new("ShaderNodeMath"); n.operation = op
        for k, v in enumerate((a, b, c)):
            if v is None: continue
            if isinstance(v, (int, float)): n.inputs[k].default_value = v
            else: L.new(v, n.inputs[k])
        return n.outputs[0]
    s = sep.outputs["X"]
    a = M('DIVIDE', gi.outputs["Curl"], gi.outputs["Width"])
    ge = M('GREATER_THAN', a, -1e-9)
    sgn = M('MULTIPLY_ADD', ge, 2.0, -1.0)
    a = M('MULTIPLY_ADD', sgn, 2e-4, a)
    th = gi.outputs["Theta"]
    ang = M('MULTIPLY_ADD', a, s, th)             # theta + a*s
    x = M('DIVIDE', M('SUBTRACT', M('SINE', ang), M('SINE', th)), a)
    z = M('DIVIDE', M('SUBTRACT', M('COSINE', th), M('COSINE', ang)), a)
    z = M('ADD', z, gi.outputs["RootZ"])
    z = M('ADD', z, sep.outputs["Z"])
    com = N.new("ShaderNodeCombineXYZ")
    L.new(x, com.inputs["X"]); L.new(sep.outputs["Y"], com.inputs["Y"]); L.new(z, com.inputs["Z"])
    sp = N.new("GeometryNodeSetPosition")
    L.new(gi.outputs["Geometry"], sp.inputs["Geometry"]); L.new(com.outputs[0], sp.inputs["Position"])
    L.new(sp.outputs[0], go.inputs[0])
    return ng

def make_spine_ng():
    ng = bpy.data.node_groups.new("SpineArc", 'GeometryNodeTree')
    try: ng.is_modifier = True
    except Exception: pass
    I = ng.interface
    I.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    I.new_socket("Open", in_out='INPUT', socket_type='NodeSocketFloat')
    I.new_socket("Radius", in_out='INPUT', socket_type='NodeSocketFloat')
    I.new_socket("PivotZ", in_out='INPUT', socket_type='NodeSocketFloat')
    I.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi = N.new("NodeGroupInput"); go = N.new("NodeGroupOutput")
    pos = N.new("GeometryNodeInputPosition")
    sep = N.new("ShaderNodeSeparateXYZ"); L.new(pos.outputs[0], sep.inputs[0])
    def M(op, a, b=None, c=None):
        n = N.new("ShaderNodeMath"); n.operation = op
        for k, v in enumerate((a, b, c)):
            if v is None: continue
            if isinstance(v, (int, float)): n.inputs[k].default_value = v
            else: L.new(v, n.inputs[k])
        return n.outputs[0]
    p = sep.outputs["X"]                            # 0..1 along the arc
    op = gi.outputs["Open"]                          # 0..pi
    start = M('ADD', op, math.pi / 2)
    span = M('SUBTRACT', math.pi, op)
    ang = M('MULTIPLY_ADD', p, span, start)
    x = M('MULTIPLY', M('COSINE', ang), gi.outputs["Radius"])
    z = M('MULTIPLY_ADD', M('SINE', ang), gi.outputs["Radius"], gi.outputs["PivotZ"])
    com = N.new("ShaderNodeCombineXYZ")
    L.new(x, com.inputs["X"]); L.new(sep.outputs["Y"], com.inputs["Y"]); L.new(z, com.inputs["Z"])
    sp = N.new("GeometryNodeSetPosition")
    L.new(gi.outputs["Geometry"], sp.inputs["Geometry"]); L.new(com.outputs[0], sp.inputs["Position"])
    L.new(sp.outputs[0], go.inputs[0])
    return ng

NG_PAGE = make_page_turn_ng()
NG_SPINE = make_spine_ng()

def socket_id(ng, name):
    for it in ng.interface.items_tree:
        if getattr(it, "in_out", None) == 'INPUT' and it.name == name:
            return it.identifier

def set_in(mod, ident, val):
    getattr(mod.properties.inputs, ident).value = val

def in_path(mod, ident):
    return f'modifiers["{mod.name}"].properties.inputs.{ident}.value'

# ---------------- build ----------------
root = bpy.data.objects.new("Book", None); link(root)
root.empty_display_size = 0.05

# back cover
bc = link(bpy.data.objects.new("BackCover", box_mesh("BackCover", 0, W, -H / 2, H / 2, 0, TC)), root)
bc.data.materials.append(M_LEATHER)
bv = bc.modifiers.new("Bevel", 'BEVEL'); bv.width = 0.0015; bv.segments = 3

# blank page block
pb = link(bpy.data.objects.new("PageBlock", box_mesh("PageBlock", 0.0005, PW, -PH / 2, PH / 2, TC, TC + FB)), root)
pb.data.materials.append(M_EDGE)

# front cover (origin on the spine pivot)
cov = link(bpy.data.objects.new("FrontCover", box_mesh("FrontCover", 0, W, -H / 2, H / 2, ZP - TC, ZP)), root)
cov.location = (0, 0, ZP)
cov.data.materials.append(M_COVER)
bv = cov.modifiers.new("Bevel", 'BEVEL'); bv.width = 0.0015; bv.segments = 3
# endpaper on the inside of the cover (faces down while closed); U flipped so it reads correctly once opened
m_end = paper_mat("Endpaper_Text1", "page_text_1.jpg")
ins = 0.005
ep = link(bpy.data.objects.new("Endpaper", grid_mesh("Endpaper", ins, W - ins, -H / 2 + ins, H / 2 - ins, 1, 1,
                                                     lambda u, v: (1 - u, v), z=ZP - TC - 0.0002, flip=True)), cov)
ep.data.materials.append(m_end)
# brass corners (top-right and bottom-right of the front cover)
def corner(name, top):
    y0, y1 = (H / 2 - CL, H / 2 + 0.0004) if top else (-H / 2 - 0.0004, -H / 2 + CL)
    uvf = (lambda u, v: (u, v)) if top else (lambda u, v: (u, 1 - v))
    me = grid_mesh(name, W - CL, W + 0.0004, y0, y1, 1, 1, uvf, z=ZP + 0.0003)
    o = link(bpy.data.objects.new(name, me), cov)
    o.data.materials.append(M_BRASS)
    return o
corner("Corner_TR", True); corner("Corner_BR", False)

# spine (arc that shrinks as the cover opens)
sp_me = grid_mesh("Spine", 0, 1, -H / 2, H / 2, 24, 1, lambda u, v: (u, v))
spine = link(bpy.data.objects.new("Spine", sp_me), root)
spine.data.materials.append(M_LEATHER)
gm = spine.modifiers.new("SpineArc", 'NODES'); gm.node_group = NG_SPINE
set_in(gm, socket_id(NG_SPINE, "Radius"), HB / 2 - TC / 2)
set_in(gm, socket_id(NG_SPINE, "PivotZ"), ZP)
so = spine.modifiers.new("Solidify", 'SOLIDIFY'); so.thickness = TC; so.offset = 0.0
open_id = socket_id(NG_SPINE, "Open")
fc = spine.driver_add(in_path(gm, open_id))
drv = fc.driver; drv.type = 'SCRIPTED'
var = drv.variables.new(); var.name = "r"; var.type = 'TRANSFORMS'
var.targets[0].id = cov; var.targets[0].transform_type = 'ROT_Y'; var.targets[0].transform_space = 'LOCAL_SPACE'
drv.expression = "-r"

# leaves
TH_ID, CU_ID, RZ_ID, WI_ID = (socket_id(NG_PAGE, n) for n in ("Theta", "Curl", "RootZ", "Width"))
leaves = []
for i in range(1, NLEAF + 1):
    me = grid_mesh(f"Leaf{i}", 0, PW, -PH / 2, PH / 2, 72, 4, lambda u, v: (u, v))
    lf = link(bpy.data.objects.new(f"Leaf{i}", me), root)
    front = paper_mat(f"Leaf{i}_Front_Photo{i}", f"page_photo_{i}.jpg", rough=0.42)
    back_img = f"page_text_{i + 1}.jpg" if i < NLEAF else "page_blank.jpg"
    back = paper_mat(f"Leaf{i}_Back", back_img, flip_u=True)
    for m in (front, back, M_EDGE): lf.data.materials.append(m)
    g = lf.modifiers.new("PageTurn", 'NODES'); g.node_group = NG_PAGE
    set_in(g, TH_ID, 0.0); set_in(g, CU_ID, 0.0); set_in(g, RZ_ID, zR(i)); set_in(g, WI_ID, PW)
    s = lf.modifiers.new("Solidify", 'SOLIDIFY'); s.thickness = LT; s.offset = -1.0
    s.material_offset = 1; s.material_offset_rim = 2; s.use_rim = True
    leaves.append(lf)

# ---------------- table, camera, lights ----------------
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, -0.0002))
table = bpy.context.active_object; table.name = "Table"
tm, tnt, TN, TL, tb = new_mat("Table")
tb.inputs["Base Color"].default_value = (0.62, 0.57, 0.50, 1)
tb.inputs["Roughness"].default_value = 0.85
tn = TN.new("ShaderNodeTexNoise"); tn.inputs["Scale"].default_value = 400; tn.inputs["Detail"].default_value = 6
tbp = TN.new("ShaderNodeBump"); tbp.inputs["Strength"].default_value = 0.05
TL.new(tn.outputs["Fac"], tbp.inputs["Height"]); TL.new(tbp.outputs["Normal"], tb.inputs["Normal"])
table.data.materials.append(tm)

cam_d = bpy.data.cameras.new("Camera"); cam_d.lens = 70; cam_d.sensor_fit = 'HORIZONTAL'; cam_d.sensor_width = 36
cam = bpy.data.objects.new("Camera", cam_d); link(cam)
cam.location = (0, 0, 0.70 * 70 / 36); cam.rotation_euler = (0, 0, 0)
cam_d.clip_start = 0.05; cam_d.clip_end = 20
scene.camera = cam

key_d = bpy.data.lights.new("Key", 'AREA'); key_d.shape = 'DISK'; key_d.size = 1.2; key_d.energy = 260
key_d.color = (1.0, 0.95, 0.88)
key = bpy.data.objects.new("Key", key_d); link(key)
key.location = (-1.1, 0.9, 1.9)
key.rotation_euler = (Vector((0, 0, 0)) - key.location).to_track_quat('-Z', 'Y').to_euler()
fill_d = bpy.data.lights.new("Fill", 'AREA'); fill_d.size = 2.0; fill_d.energy = 60; fill_d.color = (0.92, 0.95, 1.0)
fill = bpy.data.objects.new("Fill", fill_d); link(fill)
fill.location = (1.3, -1.0, 1.6)
fill.rotation_euler = (Vector((0, 0, 0)) - fill.location).to_track_quat('-Z', 'Y').to_euler()

world = scene.world or bpy.data.worlds.new("World"); scene.world = world
world.use_nodes = True
wb = world.node_tree.nodes.get("Background")
wb.inputs[0].default_value = (0.80, 0.76, 0.70, 1); wb.inputs[1].default_value = 0.35

# ---------------- animation ----------------
FPS = 24
scene.render.fps = FPS
OPEN0, OPEN1 = 10, 50
TURN_LEN, HOLD = 32, 6
CLOSED_X = -(W / 2 - HB / 4)

root.location.x = CLOSED_X; root.keyframe_insert("location", index=0, frame=OPEN0)
root.location.x = 0.0; root.keyframe_insert("location", index=0, frame=OPEN1)
cov.rotation_euler.y = 0.0; cov.keyframe_insert("rotation_euler", index=1, frame=OPEN0)
cov.rotation_euler.y = -math.pi; cov.keyframe_insert("rotation_euler", index=1, frame=OPEN1)

def key_mod(obj, ident, frame, val):
    md = obj.modifiers["PageTurn"]
    set_in(md, ident, val)
    obj.keyframe_insert(data_path=in_path(md, ident), frame=frame)

start = OPEN1 + HOLD
turns = []
for i, lf in enumerate(leaves[:NLEAF - 1], 1):
    f0 = start; f1 = start + TURN_LEN
    key_mod(lf, TH_ID, f0, 0.0); key_mod(lf, TH_ID, f1, math.pi)
    key_mod(lf, RZ_ID, f0, zR(i)); key_mod(lf, RZ_ID, f1, zL(i))
    key_mod(lf, CU_ID, f0, 0.0)
    key_mod(lf, CU_ID, f0 + round(TURN_LEN * 0.30), 1.1)
    key_mod(lf, CU_ID, f0 + round(TURN_LEN * 0.55), 0.0)
    key_mod(lf, CU_ID, f0 + round(TURN_LEN * 0.80), -0.85)
    key_mod(lf, CU_ID, f1, 0.0)
    turns.append((f0, f1))
    start = f1 + HOLD
END = start + 2
scene.frame_start = 1; scene.frame_end = END
scene.frame_set(1)

# ---------------- render settings ----------------
r = scene.render
r.resolution_x, r.resolution_y, r.resolution_percentage = 1920, 1080, 100
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
scene.cycles.samples = 64
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6

result = {"END": END, "turns": turns, "HB": HB, "closed_x": CLOSED_X,
          "objs": [o.name for o in bpy.data.objects], "ids": [TH_ID, CU_ID, RZ_ID, WI_ID]}
