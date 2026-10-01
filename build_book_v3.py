"""
v3 album. A rebuild of v2 against specific faults in that render:

  * The spine was a separate strip floating at cover height and punched through
    the pages. There is no spine object now - the back board simply extends
    past the hinge, so the gutter is real geometry that nothing can intersect.
  * Every page was a different size from the cover's lining, so the right-hand
    page sat on visible leather while the left-hand one ran edge to edge. The
    cover now overhangs at the fore-edge, head and tail only (flush at the
    hinge, as a real case does) and its lining is inset to exactly one page,
    so both sides of an open spread match.
  * The leather was too busy. Mottling and grain are both pulled well back and
    the sheen does more of the work.
  * Pages were flat planes meeting in a hard seam. They now dip into the gutter
    and the block carries real page striation at the fore-edge.

The logo is optional: drop a file at textures_v3/logo.png (white mark on black,
or anything with an alpha channel) and it is debossed into the cover. Without
it the cover renders blank rather than guessing at the artwork.
"""

import bpy
import bmesh
import os
from math import pi, radians, exp

HERE = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else \
    r"C:\Users\Muhundan\Documents\NB Album Animation"
TEX = os.path.join(HERE, "textures_v2")        # pages are unchanged from v2
LOGO = os.path.join(HERE, "textures_v3", "logo.png")

# ------------------------------------------------------------------ anatomy
PW, PH = 1.0, 1.491           # a page
OVER = 0.018                  # cover overhang: fore-edge, head and tail only
CW, CH = PW + OVER, PH + 2 * OVER
SPINE_W = 0.055               # how far the back board runs past the hinge
BLOCK_H = 0.030               # the text block is thick; this is an album
LEAF_GAP = 0.0040
GUTTER_DIP = 0.0075           # how far a page sags toward the hinge
DIP_FALLOFF = 0.085

N_LEAVES = 4
SEG_X, SEG_Y = 72, 8

FPS = 24
F_HOLD_START = 14
F_COVER = 52
F_SETTLE = 16
F_TURN = 36
F_PAUSE = 14

# z ladder, bottom up
Z_BLOCK_TOP = BLOCK_H
Z_FINAL = Z_BLOCK_TOP + 0.0008
def z_leaf(i):
    return Z_FINAL + 0.0022 + (N_LEAVES - 1 - i) * LEAF_GAP
Z_COVER = z_leaf(0) + 0.0035
Z_LEFT_BASE = Z_FINAL + 0.0022
def z_leaf_left(i):
    return Z_LEFT_BASE + i * LEAF_GAP
Z_COVER_LEFT = Z_LEFT_BASE - LEAF_GAP


def clear():
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials,
                 bpy.data.images, bpy.data.node_groups, bpy.data.lights,
                 bpy.data.cameras, bpy.data.worlds):
        for item in list(coll):
            coll.remove(item)


def page_turn_group():
    """Circular-arc bend rooted at the hinge. Theta swings the sheet, Curl adds
    progressive bend along it - the difference between a page and a board."""
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
    a = M("MULTIPLY_ADD", sgn, 2e-4, a)
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


def img(name, folder=None):
    return bpy.data.images.load(os.path.join(folder or TEX, name), check_existing=True)


# --------------------------------------------------------------- materials
def leather_nodes(nt, coord, busy=1.0):
    """Shared leather surface. `busy` scales how much the hide shows; v2 was
    far too loud, so this now sits low by default and the sheen carries it."""
    N, L = nt.nodes, nt.links

    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 9.0
    noise.inputs["Detail"].default_value = 4.0
    noise.inputs["Roughness"].default_value = 0.42
    L.new(coord.outputs["Object"], noise.inputs["Vector"])

    ramp = N.new("ShaderNodeValToRGB")
    # a much tighter range than v2: the hide reads as one colour that merely
    # breathes, rather than as clouds
    ramp.color_ramp.elements[0].position = 0.38
    ramp.color_ramp.elements[0].color = (0.0430, 0.0163, 0.0084, 1)
    ramp.color_ramp.elements[1].position = 0.66
    ramp.color_ramp.elements[1].color = (0.0800, 0.0330, 0.0178, 1)
    L.new(noise.outputs["Fac"], ramp.inputs["Fac"])

    # fine pebble, kept shallow
    grain = N.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 340.0
    grain.inputs["Detail"].default_value = 3.0
    L.new(coord.outputs["Object"], grain.inputs["Vector"])

    vor = N.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 110.0
    L.new(coord.outputs["Object"], vor.inputs["Vector"])

    b1 = N.new("ShaderNodeBump")
    b1.inputs["Strength"].default_value = 0.16 * busy
    b1.inputs["Distance"].default_value = 0.006
    L.new(grain.outputs["Fac"], b1.inputs["Height"])

    b2 = N.new("ShaderNodeBump")
    b2.inputs["Strength"].default_value = 0.12 * busy
    b2.inputs["Distance"].default_value = 0.008
    L.new(vor.outputs["Distance"], b2.inputs["Height"])
    L.new(b1.outputs["Normal"], b2.inputs["Normal"])

    # roughness breakup is what makes leather look like leather under a light
    rnoise = N.new("ShaderNodeTexNoise")
    rnoise.inputs["Scale"].default_value = 24.0
    L.new(coord.outputs["Object"], rnoise.inputs["Vector"])
    rr = N.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.34
    rr.inputs["To Max"].default_value = 0.52
    L.new(rnoise.outputs["Fac"], rr.inputs["Value"])

    return ramp, b2, rr


def cover_material(name, lining_image=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    for n in list(N):
        N.remove(n)

    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    coord = N.new("ShaderNodeTexCoord")
    ramp, bump, rough = leather_nodes(nt, coord)
    L.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    L.new(rough.outputs[0], bsdf.inputs["Roughness"])
    try:
        bsdf.inputs["Specular IOR Level"].default_value = 0.40
        bsdf.inputs["Coat Weight"].default_value = 0.08
        bsdf.inputs["Coat Roughness"].default_value = 0.34
    except KeyError:
        pass

    surface = bsdf
    base_colour = ramp.outputs["Color"]

    if os.path.exists(LOGO):
        tex = N.new("ShaderNodeTexImage")
        tex.image = img("logo.png", os.path.join(HERE, "textures_v3"))
        tex.extension = "CLIP"
        tex.interpolation = "Cubic"
        w, h = tex.image.size
        aspect = (w / h) if h else 2.0
        LOGO_U = 0.46
        LOGO_V = (LOGO_U * CW / aspect) / CH
        mp = N.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1 / LOGO_U, 1 / LOGO_V, 1)
        mp.inputs["Location"].default_value = (0.5 - 0.5 / LOGO_U, 0.5 - 0.5 / LOGO_V, 0)
        L.new(coord.outputs["UV"], mp.inputs["Vector"])
        L.new(mp.outputs["Vector"], tex.inputs["Vector"])

        inv = N.new("ShaderNodeMath")
        inv.operation = "MULTIPLY"
        inv.inputs[1].default_value = -1.0
        L.new(tex.outputs["Color"], inv.inputs[0])
        b3 = N.new("ShaderNodeBump")
        b3.inputs["Strength"].default_value = 0.9
        b3.inputs["Distance"].default_value = 0.045
        L.new(inv.outputs[0], b3.inputs["Height"])
        L.new(bump.outputs["Normal"], b3.inputs["Normal"])
        bump = b3

        # pressed leather sits darker and slightly glossier
        dk = N.new("ShaderNodeMixRGB")
        dk.blend_type = "MULTIPLY"
        dk.inputs["Fac"].default_value = 0.45
        dk.inputs["Color2"].default_value = (0.6, 0.57, 0.55, 1)
        L.new(ramp.outputs["Color"], dk.inputs["Color1"])
        mc = N.new("ShaderNodeMixRGB")
        L.new(tex.outputs["Color"], mc.inputs["Fac"])
        L.new(ramp.outputs["Color"], mc.inputs["Color1"])
        L.new(dk.outputs["Color"], mc.inputs["Color2"])
        base_colour = mc.outputs["Color"]
        L.new(base_colour, bsdf.inputs["Base Color"])

    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    if lining_image:
        # The lining is inset to exactly one page, so an open spread shows the
        # same leather border on the left as the board shows on the right.
        pg = N.new("ShaderNodeBsdfPrincipled")
        pg.inputs["Roughness"].default_value = 0.76
        tex = N.new("ShaderNodeTexImage")
        tex.image = img(lining_image)
        tex.extension = "CLIP"          # alpha falls to 0 outside the page
        mp = N.new("ShaderNodeMapping")
        # mirrored, because the board turns over; then scaled so the page lands
        # flush at the hinge and inset by OVER at head, tail and fore-edge
        mp.inputs["Scale"].default_value = (-CW / PW, CH / PH, 1)
        mp.inputs["Location"].default_value = (CW / PW, -OVER / PH, 0)
        L.new(coord.outputs["UV"], mp.inputs["Vector"])
        L.new(mp.outputs["Vector"], tex.inputs["Vector"])
        L.new(tex.outputs["Color"], pg.inputs["Base Color"])

        inner = N.new("ShaderNodeMixShader")
        L.new(tex.outputs["Alpha"], inner.inputs["Fac"])
        L.new(bsdf.outputs[0], inner.inputs[1])     # leather turn-in
        L.new(pg.outputs[0], inner.inputs[2])       # pasted-down page
        surface = inner

        geo = N.new("ShaderNodeNewGeometry")
        side = N.new("ShaderNodeMixShader")
        L.new(geo.outputs["Backfacing"], side.inputs["Fac"])
        L.new(bsdf.outputs[0], side.inputs[1])
        L.new(inner.outputs[0], side.inputs[2])
        surface = side

    L.new(surface.outputs[0], out.inputs[0])
    return m


def leaf_material(name, recto, verso):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    for n in list(N):
        N.remove(n)
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.78
    try:
        bsdf.inputs["Specular IOR Level"].default_value = 0.26
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

    tf = N.new("ShaderNodeTexImage")
    tf.image = img(recto)
    L.new(coord.outputs["UV"], tf.inputs["Vector"])
    tb = N.new("ShaderNodeTexImage")
    tb.image = img(verso)
    L.new(comb.outputs[0], tb.inputs["Vector"])

    geo = N.new("ShaderNodeNewGeometry")
    mix = N.new("ShaderNodeMixRGB")
    L.new(geo.outputs["Backfacing"], mix.inputs["Fac"])
    L.new(tf.outputs["Color"], mix.inputs["Color1"])
    L.new(tb.outputs["Color"], mix.inputs["Color2"])
    L.new(mix.outputs["Color"], bsdf.inputs["Base Color"])

    tooth = N.new("ShaderNodeTexNoise")
    tooth.inputs["Scale"].default_value = 520.0
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.045
    L.new(tooth.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def block_material():
    """The fore-edge of a text block is hundreds of sheet edges, not a slab."""
    m = bpy.data.materials.new("PageBlock")
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    for n in list(N):
        N.remove(n)
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.88
    L.new(bsdf.outputs[0], out.inputs[0])

    coord = N.new("ShaderNodeTexCoord")
    wave = N.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Z"
    wave.inputs["Scale"].default_value = 330.0
    wave.inputs["Distortion"].default_value = 1.4
    wave.inputs["Detail"].default_value = 2.0
    L.new(coord.outputs["Object"], wave.inputs["Vector"])

    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.50, 0.455, 0.385, 1)
    ramp.color_ramp.elements[1].color = (0.80, 0.765, 0.690, 1)
    L.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    L.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.30
    bump.inputs["Distance"].default_value = 0.004
    L.new(wave.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


# ---------------------------------------------------------------- geometry
def sheet(name, w, h, segx, segy, x0=0.0, dip=True):
    """A page. Sheets sag toward the hinge rather than lying dead flat, which
    is most of what stops an open spread looking like two rectangles."""
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)

    bm = bmesh.new()
    verts = {}
    for i in range(segx + 1):
        for j in range(segy + 1):
            u, v = i / segx, j / segy
            x = x0 + u * w
            z = -GUTTER_DIP * exp(-max(x, 0.0) / DIP_FALLOFF) if dip else 0.0
            verts[(i, j)] = bm.verts.new((x, (v - 0.5) * h, z))
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


def box(name, x0, x1, y0, y1, z0, z1):
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 + (v.co.x + 0.5) * (x1 - x0)
        v.co.y = y0 + (v.co.y + 0.5) * (y1 - y0)
        v.co.z = z0 + (v.co.z + 0.5) * (z1 - z0)
    bm.to_mesh(me)
    bm.free()
    return ob


def add_turn(ob, width, root_z):
    g = ob.modifiers.new("PageTurn", "NODES")
    g.node_group = NG
    inp = g.properties.inputs
    inp.Socket_1.value = 0.0
    inp.Socket_2.value = 0.0
    inp.Socket_3.value = root_z
    inp.Socket_4.value = width
    return g


def key(ob, socket, frame, value):
    name = "Socket_%d" % socket
    getattr(ob.modifiers["PageTurn"].properties.inputs, name).value = value
    ob.keyframe_insert(
        data_path='modifiers["PageTurn"].properties.inputs.%s.value' % name,
        frame=frame)


# ===========================================================================
clear()
try:
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "BEZIER"
except Exception as e:
    print("interpolation default:", e)

scene = bpy.context.scene
NG = page_turn_group()

M_COVER = cover_material("Leather_Cover", lining_image="quote_1.jpg")
M_BOARD = cover_material("Leather_Board")
M_BLOCK = block_material()

# --- back board. It runs past the hinge, so the gutter is this surface and
#     there is no separate spine strip to intersect anything. ---------------
back = sheet("BackBoard", CW + SPINE_W, CH, 14, 6, x0=-SPINE_W, dip=False)
back.data.materials.append(M_BOARD)
back.location.z = 0.0

# --- text block ------------------------------------------------------------
block = box("PageBlock", 0.0, PW, -PH / 2, PH / 2, 0.0005, Z_BLOCK_TOP)
block.data.materials.append(M_BLOCK)

# --- leaves ----------------------------------------------------------------
SPREADS = [("photo_1.jpg", "quote_2.jpg"),
           ("photo_2.jpg", "quote_3.jpg"),
           ("photo_3.jpg", "quote_4.jpg"),
           ("photo_4.jpg", "quote_5.jpg")]
leaves = []
for i, (recto, verso) in enumerate(SPREADS):
    lf = sheet("Leaf%d" % (i + 1), PW, PH, SEG_X, SEG_Y)
    lf.data.materials.append(leaf_material("Leaf%d_Mat" % (i + 1), recto, verso))
    add_turn(lf, PW, z_leaf(i))
    leaves.append(lf)

final = sheet("FinalPage", PW, PH, 24, 8)
final.data.materials.append(leaf_material("FinalPage_Mat", "photo_5.jpg", "photo_5.jpg"))
final.location.z = Z_FINAL

# --- front board, soft -----------------------------------------------------
cover = sheet("FrontCover", CW, CH, SEG_X, SEG_Y, x0=0.0, dip=False)
cover.data.materials.append(M_COVER)
add_turn(cover, CW, Z_COVER)

# =============================================================== animation ==
t0 = F_HOLD_START
t1 = t0 + F_COVER
t2 = t1 + F_SETTLE
COVER_CURL, LEAF_CURL = 1.20, 0.82

key(cover, 1, 1, 0.0); key(cover, 1, t0, 0.0); key(cover, 1, t1, pi)
key(cover, 2, 1, 0.0); key(cover, 2, t0, 0.0)
key(cover, 2, t0 + F_COVER * 0.42, COVER_CURL)
key(cover, 2, t1, 0.0)
key(cover, 3, 1, Z_COVER); key(cover, 3, t0, Z_COVER); key(cover, 3, t1, Z_COVER_LEFT)

f = t2
turns = []
for i, lf in enumerate(leaves):
    key(lf, 1, 1, 0.0); key(lf, 1, f, 0.0); key(lf, 1, f + F_TURN, pi)
    key(lf, 2, 1, 0.0); key(lf, 2, f, 0.0)
    key(lf, 2, f + F_TURN * 0.45, LEAF_CURL)
    key(lf, 2, f + F_TURN, 0.0)
    key(lf, 3, 1, z_leaf(i)); key(lf, 3, f, z_leaf(i))
    key(lf, 3, f + F_TURN, z_leaf_left(i))
    turns.append(f)
    f += F_TURN + F_PAUSE

LAST = f
scene.frame_start, scene.frame_end = 1, LAST
scene.render.fps = FPS

# ------------------------------------------------------------------ camera -
cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 85.0
cam = bpy.data.objects.new("Camera", cam_data)
bpy.context.collection.objects.link(cam)
cam.rotation_euler = (0.0, 0.0, 0.0)
scene.camera = cam
cam.location = (PW / 2, 0.0, 5.6)
cam.keyframe_insert("location", frame=1)
cam.keyframe_insert("location", frame=t0)
cam.location = (0.0, 0.0, 5.6)
cam.keyframe_insert("location", frame=t1)

# ------------------------------------------------------------------ lights -
def area(name, loc, rot, size, energy, spread=None):
    d = bpy.data.lights.new(name, "AREA")
    d.energy = energy
    d.size = size
    d.use_shadow = True
    if spread is not None:
        try:
            d.spread = radians(spread)
        except Exception:
            pass
    o = bpy.data.objects.new(name, d)
    o.location = loc
    o.rotation_euler = rot
    bpy.context.collection.objects.link(o)
    return o

# A softbox close enough to throw a readable shadow off a lifted page, but not
# so hard that the grain turns into gravel.
area("Key", (-1.55, 1.45, 2.5), (radians(-28), radians(-28), 0), 1.6, 118.0)
area("Fill", (2.0, -1.25, 2.3), (radians(26), radians(36), 0), 3.2, 30.0)
area("Rim", (0.15, -2.3, 1.5), (radians(60), 0, 0), 2.0, 17.0)

world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.030
world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)

# ------------------------------------------------------------------ render -
r = scene.render
r.engine = "BLENDER_EEVEE"
r.resolution_x, r.resolution_y = 1400, 1050
r.resolution_percentage = 100
r.film_transparent = True
r.image_settings.file_format = "PNG"
r.image_settings.color_mode = "RGBA"
r.image_settings.color_depth = "8"
r.image_settings.compression = 15
r.filepath = os.path.join(HERE, "frames_v3") + os.sep
scene.view_settings.view_transform = "Standard"

try:
    ev = scene.eevee
    ev.use_shadows = True
    ev.use_raytracing = True
    ev.taa_render_samples = 96
    ev.shadow_ray_count = 4
    ev.shadow_step_count = 12
    ev.shadow_resolution_scale = 2
    ev.use_fast_gi = True          # contact darkening in the gutter
except Exception as e:
    print("eevee option:", e)

print("v3 built: 1-%d, turns at %s, logo=%s" % (LAST, turns, os.path.exists(LOGO)))
