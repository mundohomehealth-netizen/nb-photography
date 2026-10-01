"""
Builds the v2 album: portrait soft-leather cover, 4 leaves, 5 spreads.

Run inside Blender (Scripting -> Open -> Run Script), or let the MCP bridge
exec it. It builds the whole scene from nothing, so it is safe to re-run.

Differences from the v1 book that matter:
  * Portrait 2:3 instead of square, matching the reference cover.
  * The cover is SOFT. It goes through the same PageTurn bend as the leaves,
    with more curl, so it flexes like leather rather than swinging as a rigid
    board on a hinge.
  * No table. The film is transparent and nothing sits under the book, so the
    only shadows are the ones the cover and pages cast on the book itself -
    which is what sells the floating look.
  * Each leaf is a single flat grid whose material picks the recto or verso
    image from Geometry > Backfacing, so one object carries both page faces.
"""

import bpy
import os
from math import pi, radians

HERE = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else \
    r"C:\Users\Muhundan\Documents\NB Album Animation"
TEX = os.path.join(HERE, "textures_v2")

def _logo_size():
    """PNG header: width and height are big-endian u32 at byte 16."""
    with open(os.path.join(TEX, "logo.png"), "rb") as fh:
        head = fh.read(26)
    return (int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big"))

LOGO_W, LOGO_H = _logo_size()

# ---------------------------------------------------------------- dimensions
PW, PH = 1.0, 1.491          # page: spine->fore-edge, and height (0.671)
OVER = 0.022                 # how far the cover overhangs the page block
CW, CH = PW + OVER, PH + 2 * OVER
LEAF_GAP = 0.0045
COVER_T = 0.011
SPINE_W = 0.038

N_LEAVES = 4                 # 4 flips -> 5 spreads

# One explicit z ladder for the whole stack. Everything above the block has to
# clear its top face, or the block simply renders over the leaves.
BLOCK_TOP = 0.016
Z_FINAL = BLOCK_TOP + 0.0007
def z_leaf(i):
    return Z_FINAL + 0.0015 + (N_LEAVES - 1 - i) * LEAF_GAP
Z_INSIDE = Z_FINAL + 0.0015 + (N_LEAVES - 1) * LEAF_GAP + 0.003
Z_COVER = Z_INSIDE + 0.001

# Turned pages stack up on the left in the order they were turned, so the last
# one turned has to finish ON TOP - the reverse of their order on the right.
# RootZ is animated across each turn to carry the sheet to its new height.
Z_LEFT_BASE = Z_FINAL + 0.0015
def z_leaf_left(i):
    return Z_LEFT_BASE + i * LEAF_GAP
Z_COVER_LEFT = Z_LEFT_BASE - LEAF_GAP
SEG_X, SEG_Y = 56, 6         # enough cuts along X for a smooth bend

# --------------------------------------------------------------- frame plan
FPS = 24
F_HOLD_START = 12
F_COVER = 48                 # a soft cover takes longer to peel open
F_SETTLE = 14
F_TURN = 34
F_PAUSE = 13


def clear():
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials,
                 bpy.data.images, bpy.data.node_groups, bpy.data.lights,
                 bpy.data.cameras):
        for item in list(coll):
            coll.remove(item)


# ------------------------------------------------------------- the bend itself
def page_turn_group():
    """Circular-arc bend rooted at the spine (x=0).

    Theta rotates the whole sheet about the spine; Curl adds progressive
    bending along its length, which is what makes a page look like it has
    give rather than being a flat board on a hinge.
    """
    ng = bpy.data.node_groups.new("PageTurn", "GeometryNodeTree")
    try:
        ng.is_modifier = True
    except Exception:
        pass
    I = ng.interface
    I.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    for nm in ("Theta", "Curl", "RootZ", "Width"):
        I.new_socket(nm, in_out="INPUT", socket_type="NodeSocketFloat")
    I.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    N, L = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    pos = N.new("GeometryNodeInputPosition")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(pos.outputs[0], sep.inputs[0])

    def M(op, a, b=None, c=None):
        n = N.new("ShaderNodeMath")
        n.operation = op
        for k, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[k].default_value = v
            else:
                L.new(v, n.inputs[k])
        return n.outputs[0]

    s = sep.outputs["X"]
    a = M("DIVIDE", gi.outputs["Curl"], gi.outputs["Width"])
    ge = M("GREATER_THAN", a, -1e-9)
    sgn = M("MULTIPLY_ADD", ge, 2.0, -1.0)
    a = M("MULTIPLY_ADD", sgn, 2e-4, a)      # keep a away from exactly zero
    th = gi.outputs["Theta"]
    ang = M("MULTIPLY_ADD", a, s, th)
    x = M("DIVIDE", M("SUBTRACT", M("SINE", ang), M("SINE", th)), a)
    z = M("DIVIDE", M("SUBTRACT", M("COSINE", th), M("COSINE", ang)), a)
    z = M("ADD", z, gi.outputs["RootZ"])
    z = M("ADD", z, sep.outputs["Z"])

    com = N.new("ShaderNodeCombineXYZ")
    L.new(x, com.inputs["X"])
    L.new(sep.outputs["Y"], com.inputs["Y"])
    L.new(z, com.inputs["Z"])
    sp = N.new("GeometryNodeSetPosition")
    L.new(gi.outputs["Geometry"], sp.inputs["Geometry"])
    L.new(com.outputs[0], sp.inputs["Position"])
    L.new(sp.outputs[0], go.inputs[0])
    return ng


# ---------------------------------------------------------------- materials
def img(name):
    path = os.path.join(TEX, name)
    im = bpy.data.images.load(path, check_existing=True)
    return im


def leather_mat(name, with_logo, back_image=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    for n in list(N):
        N.remove(n)

    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    L.new(bsdf.outputs[0], out.inputs[0])

    coord = N.new("ShaderNodeTexCoord")

    # mottled colour, sampled from the reference cover
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 13.0
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.48
    L.new(coord.outputs["Object"], noise.inputs["Vector"])

    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.34
    ramp.color_ramp.elements[0].color = (0.028, 0.010, 0.005, 1)
    ramp.color_ramp.elements[1].position = 0.70
    ramp.color_ramp.elements[1].color = (0.072, 0.030, 0.019, 1)
    L.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    L.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

    bsdf.inputs["Roughness"].default_value = 0.52
    try:
        bsdf.inputs["Specular IOR Level"].default_value = 0.32
    except KeyError:
        pass

    # fine grain + a coarser pebble, the two scales real leather reads at
    grain = N.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 320.0
    grain.inputs["Detail"].default_value = 4.0
    L.new(coord.outputs["Object"], grain.inputs["Vector"])

    vor = N.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 85.0
    L.new(coord.outputs["Object"], vor.inputs["Vector"])

    b1 = N.new("ShaderNodeBump")
    b1.inputs["Strength"].default_value = 0.55
    b1.inputs["Distance"].default_value = 0.012
    L.new(grain.outputs["Fac"], b1.inputs["Height"])

    b2 = N.new("ShaderNodeBump")
    b2.inputs["Strength"].default_value = 0.42
    b2.inputs["Distance"].default_value = 0.016
    L.new(vor.outputs["Distance"], b2.inputs["Height"])
    L.new(b1.outputs["Normal"], b2.inputs["Normal"])

    last = b2
    if with_logo:
        # the logo is debossed: white in the map means pressed INTO the leather,
        # so the height is inverted before it reaches the bump node
        tex = N.new("ShaderNodeTexImage")
        tex.image = img("logo.png")
        tex.extension = "CLIP"
        tex.interpolation = "Cubic"
        mapping = N.new("ShaderNodeMapping")
        # Mapping does result = uv * Scale + Location. To land a square logo
        # centred on the cover, covering LOGO_U of its width, the scale is
        # 1/size and the offset is 0.5 - 0.5/size on each axis. The v size is
        # narrowed by the cover ratio so the logo stays square, not stretched.
        # logo.png is trimmed to the mark itself, so its own aspect decides the
        # v extent - mapping it as a square would squash it badly
        LOGO_U = 0.52                      # share of the cover width
        LOGO_ASPECT = LOGO_W / LOGO_H
        LOGO_V = (LOGO_U * CW / LOGO_ASPECT) / CH
        mapping.inputs["Scale"].default_value = (1 / LOGO_U, 1 / LOGO_V, 1)
        mapping.inputs["Location"].default_value = (0.5 - 0.5 / LOGO_U,
                                                    0.5 - 0.5 / LOGO_V, 0)
        L.new(coord.outputs["UV"], mapping.inputs["Vector"])
        L.new(mapping.outputs["Vector"], tex.inputs["Vector"])

        inv = N.new("ShaderNodeMath")
        inv.operation = "MULTIPLY"
        inv.inputs[1].default_value = -1.0
        L.new(tex.outputs["Color"], inv.inputs[0])

        b3 = N.new("ShaderNodeBump")
        b3.inputs["Strength"].default_value = 1.0
        b3.inputs["Distance"].default_value = 0.055
        L.new(inv.outputs[0], b3.inputs["Height"])
        L.new(b2.outputs["Normal"], b3.inputs["Normal"])

        # the pressed leather darkens slightly in the deboss
        dark = N.new("ShaderNodeMixRGB")
        dark.blend_type = "MULTIPLY"
        dark.inputs["Fac"].default_value = 0.55
        L.new(ramp.outputs["Color"], dark.inputs["Color1"])
        dark.inputs["Color2"].default_value = (0.55, 0.52, 0.50, 1)
        mixc = N.new("ShaderNodeMixRGB")
        L.new(tex.outputs["Color"], mixc.inputs["Fac"])
        L.new(ramp.outputs["Color"], mixc.inputs["Color1"])
        L.new(dark.outputs["Color"], mixc.inputs["Color2"])
        L.new(mixc.outputs["Color"], bsdf.inputs["Base Color"])
        last = b3

    L.new(last.outputs["Normal"], bsdf.inputs["Normal"])

    if back_image:
        # The inside of a soft cover is lined, so the far side of this same
        # sheet is a printed endpaper rather than more leather. U is mirrored
        # because the cover turns over to show it.
        pg = N.new("ShaderNodeBsdfPrincipled")
        pg.inputs["Roughness"].default_value = 0.74
        tex = N.new("ShaderNodeTexImage")
        tex.image = img(back_image)
        mp = N.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (-1.0, 1.0, 1.0)
        mp.inputs["Location"].default_value = (1.0, 0.0, 0.0)
        L.new(coord.outputs["UV"], mp.inputs["Vector"])
        L.new(mp.outputs["Vector"], tex.inputs["Vector"])
        L.new(tex.outputs["Color"], pg.inputs["Base Color"])

        geo = N.new("ShaderNodeNewGeometry")
        mix = N.new("ShaderNodeMixShader")
        L.new(geo.outputs["Backfacing"], mix.inputs["Fac"])
        L.new(bsdf.outputs[0], mix.inputs[1])
        L.new(pg.outputs[0], mix.inputs[2])
        L.new(mix.outputs[0], out.inputs[0])
    return m


def leaf_mat(name, recto_file, verso_file):
    """One material carrying both faces of a leaf.

    Geometry > Backfacing picks which image to show, and the verso's U is
    mirrored so the image is not reversed when seen from behind.
    """
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    for n in list(N):
        N.remove(n)

    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.72
    try:
        bsdf.inputs["Specular IOR Level"].default_value = 0.22
    except KeyError:
        pass
    L.new(bsdf.outputs[0], out.inputs[0])

    coord = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(coord.outputs["UV"], sep.inputs[0])
    flip = N.new("ShaderNodeMath")
    flip.operation = "SUBTRACT"
    flip.inputs[0].default_value = 1.0
    L.new(sep.outputs["X"], flip.inputs[1])
    comb = N.new("ShaderNodeCombineXYZ")
    L.new(flip.outputs[0], comb.inputs["X"])
    L.new(sep.outputs["Y"], comb.inputs["Y"])

    t_front = N.new("ShaderNodeTexImage")
    t_front.image = img(recto_file)
    L.new(coord.outputs["UV"], t_front.inputs["Vector"])

    t_back = N.new("ShaderNodeTexImage")
    t_back.image = img(verso_file)
    L.new(comb.outputs[0], t_back.inputs["Vector"])

    geo = N.new("ShaderNodeNewGeometry")
    mix = N.new("ShaderNodeMixRGB")
    L.new(geo.outputs["Backfacing"], mix.inputs["Fac"])
    L.new(t_front.outputs["Color"], mix.inputs["Color1"])
    L.new(t_back.outputs["Color"], mix.inputs["Color2"])
    L.new(mix.outputs["Color"], bsdf.inputs["Base Color"])

    # paper tooth
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 420.0
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.06
    L.new(noise.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def page_mat(name, image_file, flip_u=False):
    """A single printed face. flip_u compensates for geometry that has been
    turned over: the UVs come along with the flip, so without it the text
    would read backwards."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    for n in list(N):
        N.remove(n)
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.74
    L.new(bsdf.outputs[0], out.inputs[0])
    coord = N.new("ShaderNodeTexCoord")
    tex = N.new("ShaderNodeTexImage")
    tex.image = img(image_file)
    if flip_u:
        mp = N.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (-1.0, 1.0, 1.0)
        mp.inputs["Location"].default_value = (1.0, 0.0, 0.0)
        L.new(coord.outputs["UV"], mp.inputs["Vector"])
        L.new(mp.outputs["Vector"], tex.inputs["Vector"])
    else:
        L.new(coord.outputs["UV"], tex.inputs["Vector"])
    L.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return m


def plain_mat(name, color, rough=0.8):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    return m


# ------------------------------------------------------------------ geometry
def grid(name, w, h, segx, segy, x0=0.0):
    """Flat grid spanning x0..x0+w, centred on y, lying in the XY plane."""
    import bmesh
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)

    bm = bmesh.new()
    verts = {}
    for i in range(segx + 1):
        for j in range(segy + 1):
            u, v = i / segx, j / segy
            verts[(i, j)] = bm.verts.new((x0 + u * w, (v - 0.5) * h, 0.0))
    bm.verts.ensure_lookup_table()
    uv = bm.loops.layers.uv.new("UVMap")
    for i in range(segx):
        for j in range(segy):
            f = bm.faces.new([verts[(i, j)], verts[(i + 1, j)],
                              verts[(i + 1, j + 1)], verts[(i, j + 1)]])
            for lp in f.loops:
                p = lp.vert.co
                lp[uv].uv = ((p.x - x0) / w, (p.y + h / 2) / h)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    return ob


def solidify(ob, thickness):
    """A soft cover still has a slab edge; without it the silhouette reads as
    card. Added before PageTurn so the thickness bends along with the sheet."""
    m = ob.modifiers.new("Solidify", "SOLIDIFY")
    m.thickness = thickness
    m.offset = -1.0
    m.use_even_offset = True
    b = ob.modifiers.new("Bevel", "BEVEL")
    b.width = thickness * 0.30
    b.segments = 4
    b.limit_method = "ANGLE"
    b.angle_limit = radians(42)
    return m


def add_turn(ob, width, root_z):
    g = ob.modifiers.new("PageTurn", "NODES")
    g.node_group = NG
    inp = g.properties.inputs
    inp.Socket_1.value = 0.0      # Theta
    inp.Socket_2.value = 0.0      # Curl
    inp.Socket_3.value = root_z   # RootZ
    inp.Socket_4.value = width    # Width
    return g


def key(ob, socket, frame, value):
    # Subscripting inputs gives a bare IDPropertyGroup that will not take an
    # attribute assignment; the attribute form is the one that works in 5.2.
    # Interpolation is handled by the preference set below rather than by
    # walking fcurves, which slotted Actions no longer expose directly.
    name = "Socket_%d" % socket
    getattr(ob.modifiers["PageTurn"].properties.inputs, name).value = value
    path = 'modifiers["PageTurn"].properties.inputs.%s.value' % name
    ob.keyframe_insert(data_path=path, frame=frame)


# ===========================================================================
clear()
try:
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'BEZIER'
except Exception as e:
    print('could not set interpolation default:', e)
scene = bpy.context.scene
NG = page_turn_group()

M_LEATHER = leather_mat("Leather_Cover", with_logo=True, back_image="quote_1.jpg")
M_LEATHER_PLAIN = leather_mat("Leather", with_logo=False)
M_EDGE = plain_mat("PageEdge", (0.72, 0.68, 0.60), 0.85)
M_ENDPAPER = plain_mat("Endpaper", (0.60, 0.56, 0.50), 0.8)

# --- back cover (stays put) -------------------------------------------------
back = grid("BackCover", CW, CH, 8, 4, x0=-OVER)
back.data.materials.append(M_LEATHER_PLAIN)
back.location.z = 0.0
solidify(back, COVER_T)

# --- the page block, giving the stack some bulk -----------------------------
import bmesh
me = bpy.data.meshes.new("PageBlock")
block = bpy.data.objects.new("PageBlock", me)
bpy.context.collection.objects.link(block)
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
_sx, _sy, _sz = PW, PH, BLOCK_TOP
_tx, _tz = PW / 2, BLOCK_TOP / 2
for _v in bm.verts:
    _v.co.x = _v.co.x * _sx + _tx
    _v.co.y = _v.co.y * _sy
    _v.co.z = _v.co.z * _sz + _tz
bm.to_mesh(me)
bm.free()
block.data.materials.append(M_EDGE)

# --- spine ------------------------------------------------------------------
spine = grid("Spine", SPINE_W, CH, 6, 4, x0=-OVER - SPINE_W)
spine.data.materials.append(M_LEATHER_PLAIN)
spine.location.z = Z_COVER

# --- leaves -----------------------------------------------------------------
SPREADS = [
    ("photo_1.jpg", "quote_2.jpg"),
    ("photo_2.jpg", "quote_3.jpg"),
    ("photo_3.jpg", "quote_4.jpg"),
    ("photo_4.jpg", "quote_5.jpg"),
]
leaves = []
for i, (recto, verso) in enumerate(SPREADS):
    lf = grid("Leaf%d" % (i + 1), PW, PH, SEG_X, SEG_Y)
    lf.data.materials.append(leaf_mat("Leaf%d_Mat" % (i + 1), recto, verso))
    add_turn(lf, PW, z_leaf(i))
    leaves.append(lf)

# the last photo sits on the page under the final leaf
final = grid("FinalPage", PW, PH, 8, 4)
final.data.materials.append(leaf_mat("FinalPage_Mat", "photo_5.jpg", "photo_5.jpg"))
final.location.z = Z_FINAL

# --- front cover, soft ------------------------------------------------------
cover = grid("FrontCover", CW, CH, SEG_X, SEG_Y, x0=-OVER)
cover.data.materials.append(M_LEATHER)
add_turn(cover, CW, Z_COVER)

print("built geometry")

# =============================================================== animation ==
# The cover and the inside page move as one piece: the first review is printed
# on the inside of the cover, so it has to peel open with it.
cover_group = [cover]

t0 = F_HOLD_START
t1 = t0 + F_COVER                 # cover fully open
t2 = t1 + F_SETTLE                # spread 1 held

COVER_CURL = 1.15                 # soft leather: a lot of give
LEAF_CURL = 0.80

for ob in cover_group:
    key(ob, 1, 1, 0.0)
    key(ob, 1, t0, 0.0)
    key(ob, 1, t1, pi)
    key(ob, 2, 1, 0.0)
    key(ob, 2, t0, 0.0)
    key(ob, 2, t0 + F_COVER * 0.42, COVER_CURL)   # bows out mid-peel
    key(ob, 2, t1, 0.0)
    key(ob, 3, 1, Z_COVER)
    key(ob, 3, t0, Z_COVER)
    key(ob, 3, t1, Z_COVER_LEFT)                  # ends under the turned pages

turn_starts = []
f = t2
for i, lf in enumerate(leaves):
    key(lf, 1, 1, 0.0)
    key(lf, 1, f, 0.0)
    key(lf, 1, f + F_TURN, pi)
    key(lf, 2, 1, 0.0)
    key(lf, 2, f, 0.0)
    key(lf, 2, f + F_TURN * 0.45, LEAF_CURL)
    key(lf, 2, f + F_TURN, 0.0)
    key(lf, 3, 1, z_leaf(i))
    key(lf, 3, f, z_leaf(i))
    key(lf, 3, f + F_TURN, z_leaf_left(i))
    turn_starts.append(f)
    f += F_TURN + F_PAUSE

LAST = f
scene.frame_start, scene.frame_end = 1, LAST
scene.render.fps = FPS

# ---------------------------------------------------------------- camera ---
cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 80.0
cam = bpy.data.objects.new("Camera", cam_data)
bpy.context.collection.objects.link(cam)
cam.rotation_euler = (0.0, 0.0, 0.0)          # straight down, as in v1
scene.camera = cam

# The closed book sits to one side of the spine; the open spread straddles it.
# Drifting the camera across while the cover peels keeps the book centred
# without the viewer noticing a cut.
cam.location = (PW / 2, 0.0, 5.45)
cam.keyframe_insert("location", frame=1)
cam.keyframe_insert("location", frame=t0)
cam.location = (0.0, 0.0, 5.45)
cam.keyframe_insert("location", frame=t1)

# ----------------------------------------------------------------- lights --
def area(name, loc, rot, size, energy):
    d = bpy.data.lights.new(name, "AREA")
    d.energy = energy
    d.size = size
    d.use_shadow = True
    o = bpy.data.objects.new(name, d)
    o.location = loc
    o.rotation_euler = rot
    bpy.context.collection.objects.link(o)
    return o

# Key from upper-left so the curl of a turning page catches light along its
# leading edge and throws a shadow back onto the page beneath it.
area("Key", (-1.9, 1.7, 3.1), (radians(-26), radians(-26), 0), 1.15, 190.0)
area("Fill", (2.2, -1.4, 2.6), (radians(24), radians(34), 0), 4.0, 52.0)
area("Rim", (0.0, -2.6, 1.7), (radians(58), 0, 0), 2.4, 30.0)

world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.09
world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)

# ----------------------------------------------------------------- render --
r = scene.render
r.engine = "BLENDER_EEVEE"
r.resolution_x, r.resolution_y = 1400, 1050     # 4:3, the open spread's shape
r.resolution_percentage = 100
r.film_transparent = True                        # nothing under the book
r.image_settings.file_format = "PNG"
r.image_settings.color_mode = "RGBA"
r.image_settings.color_depth = "8"
r.image_settings.compression = 15
r.filepath = os.path.join(HERE, "frames_v2") + os.sep
scene.view_settings.view_transform = "Standard"

try:
    ev = scene.eevee
    ev.use_shadows = True
    ev.use_raytracing = True
    ev.taa_render_samples = 64
    ev.shadow_ray_count = 4
    ev.shadow_step_count = 12
    ev.shadow_resolution_scale = 2
except Exception as e:
    print("eevee option not available:", e)

print("v2 book built: frames 1-%d, turns start at %s" % (LAST, turn_starts))
