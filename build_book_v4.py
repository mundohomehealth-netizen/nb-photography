"""
v4 album. Built like a case-bound book rather than a stack of planes.

What a real leather case does, and what v3 got wrong:

  * Boards are BOARDS. Roughly 3mm of greyboard under the leather, so when the
    front cover swings over you see its edge as a slab, and the turn-in on the
    inside is a different surface from the grain outside. v3's cover was one
    zero-thickness sheet, so it had no edge at all.

  * The spine is rounded, and it is a shell of leather spanning the full
    thickness of the case - from the bottom of the back board, out and around,
    to the top of the front board. Its top edge has to land exactly on the
    front board's top surface or you see a seam, which is what the gap was.

  * Opening a book flat FLATTENS the round. The spine does not stay proud while
    the covers go flat - it collapses toward the table. v3 left it standing at
    full height, so once the pages came over it showed through them. Here its
    height is driven down as the cover peels, and by the time the first page
    turns it is tucked under the boards.

  * Leaves are slabs too: top face, bottom face and a rim of page edge. A page
    seen edge-on mid-turn should have thickness, and the piles on either side
    should show their edges.

  * The square (the board's overhang past the text block) is the same on both
    sides, because it is the same board geometry mirrored. v3 had the left pile
    resting straight on the cover, so almost none of it showed.

Pages come from textures_v2/, the deboss from textures_v3/logo.png.
"""

import bpy
import bmesh
import os
from math import pi, sin, cos, radians, exp

HERE = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else \
    r"C:\Users\Muhundan\Documents\NB Album Animation"
TEX = os.path.join(HERE, "textures_v2")
LOGO = os.path.join(HERE, "textures_v3", "logo.png")

# -------------------------------------------------------------- dimensions
# 1 blender unit is about 200mm, so these read as real millimetres.
PW, PH = 1.0, 1.491           # text block page
SQUARE = 0.022                # board overhang: fore-edge, head, tail (~4.4mm)
BOARD_T = 0.016               # board thickness (~3.2mm)
LEAF_T = 0.0045               # album card (~0.9mm)
BLOCK_H = 0.055               # the pages that never turn
CW, CH = PW + SQUARE, PH + 2 * SQUARE

N_LEAVES = 4
SEG_X, SEG_Y = 76, 24        # the cone needs resolution across the height

# How much more the corners curl than the middle, and how far the unsupported
# area sags. A board is stiff and barely does either; a page does both.
# cone: how much more the corners curl than the middle
# droop: how far unsupported area sags
# twist: how far the head of the sheet leads its tail through the turn
# skew:  how much the curl favours the corner the page is lifted by
LEAF_CONE, LEAF_DROOP, LEAF_TWIST, LEAF_SKEW = 1.15, 0.075, 0.62, 0.45
COVER_CONE, COVER_DROOP, COVER_TWIST, COVER_SKEW = 0.22, 0.012, 0.16, 0.10
GUTTER_DIP = 0.0050
DIP_FALLOFF = 0.090

# --- the z ladder, built bottom-up so nothing has to be guessed -------------
Z_BACK_BOT = 0.0
Z_BACK_TOP = Z_BACK_BOT + BOARD_T
Z_BLOCK_TOP = Z_BACK_TOP + BLOCK_H
Z_FINAL_C = Z_BLOCK_TOP + LEAF_T / 2
def z_leaf(i):                                   # i=0 is the topmost leaf
    return Z_BLOCK_TOP + LEAF_T * (N_LEAVES - i + 0.5)
Z_FRONT_C = z_leaf(0) + LEAF_T / 2 + BOARD_T / 2
Z_TOP = Z_FRONT_C + BOARD_T / 2                  # outer face of the closed case
SPINE_R = Z_TOP / 2                              # a round back, so R is half the case

# where things come to rest once turned to the left
Z_FRONT_LEFT = BOARD_T / 2                       # the board lies level with its twin
def z_leaf_left(i):
    # Turned pages land on the left block, not straight on the board. Without
    # it the left half sat a whole text block lower than the right, and under
    # perspective that reads as the two sides being different sizes.
    return Z_BLOCK_TOP + LEAF_T * (i + 0.5)

FPS = 24
F_HOLD = 14
F_COVER = 54
F_SETTLE = 16
F_TURN = 38
F_PAUSE = 14


def clear():
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials,
                 bpy.data.images, bpy.data.node_groups, bpy.data.lights,
                 bpy.data.cameras, bpy.data.worlds):
        for item in list(coll):
            coll.remove(item)


# ----------------------------------------------------------------- the bend
def page_turn_group():
    ng = bpy.data.node_groups.new("PageTurn", "GeometryNodeTree")
    try:
        ng.is_modifier = True
    except Exception:
        pass
    I = ng.interface
    I.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    for nm in ("Theta", "Curl", "RootZ", "Width", "Cone", "Droop", "Height",
               "Twist", "Skew"):
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

    # A real page turns CONICALLY, not cylindrically: its free corners fall
    # further than its middle, so curvature grows toward head and tail. With
    # one curvature for the whole sheet - which is what every version up to
    # here had - the page is a perfect cylinder, and that is the single thing
    # that read as fake.
    yn = M("DIVIDE", sep.outputs["Y"], M("DIVIDE", gi.outputs["Height"], 2.0))
    yn2 = M("MULTIPLY", yn, yn)
    # Skew tips the cone toward the head, because a page is picked up by one
    # corner: the curl starts there and is always tighter at that end.
    cone = M("ADD", M("MULTIPLY_ADD", yn2, gi.outputs["Cone"], 1.0),
             M("MULTIPLY", gi.outputs["Skew"], yn))
    a = M("MULTIPLY", M("DIVIDE", gi.outputs["Curl"], gi.outputs["Width"]), cone)
    ge = M("GREATER_THAN", a, -1e-9)
    sgn = M("MULTIPLY_ADD", ge, 2.0, -1.0)
    a = M("MULTIPLY_ADD", sgn, 2e-4, a)

    # The real motion is not a rotation about the spine with every horizontal
    # slice moving together - it is a TWIST. The head of the page leads and
    # the tail trails, all the way through: the top is already standing while
    # the bottom corner still lies on the page beneath, and on the way down
    # the bottom lands first. Scaling by sin(theta) holds the sheet untwisted
    # where it starts and where it finishes, and peaks the lean mid-turn.
    th0 = gi.outputs["Theta"]
    th = M("ADD", th0,
           M("MULTIPLY", M("MULTIPLY", gi.outputs["Twist"], yn), M("SINE", th0)))
    ang = M("MULTIPLY_ADD", a, s, th)

    # Centreline of the bent sheet.
    cx = M("DIVIDE", M("SUBTRACT", M("SINE", ang), M("SINE", th)), a)
    cz = M("DIVIDE", M("SUBTRACT", M("COSINE", th), M("COSINE", ang)), a)

    # Thickness has to ride the sheet's normal, not just get added to z.
    # Adding it leaves a slab's top face on top through a half turn, so the
    # board never actually turns over - which is invisible on a plane and
    # glaring the moment the geometry is solid.
    zl = sep.outputs["Z"]
    x = M("SUBTRACT", cx, M("MULTIPLY", zl, M("SINE", ang)))
    z = M("ADD", cz, M("MULTIPLY", zl, M("COSINE", ang)))

    # Weight. Strongest where the sheet is least supported - far from the
    # hinge and out at the corners - and only while it is actually lifted,
    # so it vanishes as the page lies down at either end of the turn.
    xn = M("DIVIDE", s, gi.outputs["Width"])
    droop = M("MULTIPLY",
              M("MULTIPLY", gi.outputs["Droop"], M("MULTIPLY", xn, xn)),
              M("MULTIPLY", M("ADD", yn2, 0.30), M("SINE", th0)))
    z = M("SUBTRACT", z, droop)
    z = M("ADD", z, gi.outputs["RootZ"])

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
def _leather_core(nt, coord):
    N, L = nt.nodes, nt.links
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 7.5
    noise.inputs["Detail"].default_value = 5.0
    noise.inputs["Roughness"].default_value = 0.45
    L.new(coord.outputs["Object"], noise.inputs["Vector"])

    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.36
    ramp.color_ramp.elements[0].color = (0.0430, 0.0163, 0.0084, 1)
    ramp.color_ramp.elements[1].position = 0.68
    ramp.color_ramp.elements[1].color = (0.0800, 0.0330, 0.0178, 1)
    L.new(noise.outputs["Fac"], ramp.inputs["Fac"])

    grain = N.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 330.0
    grain.inputs["Detail"].default_value = 3.0
    L.new(coord.outputs["Object"], grain.inputs["Vector"])
    vor = N.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 105.0
    L.new(coord.outputs["Object"], vor.inputs["Vector"])

    b1 = N.new("ShaderNodeBump")
    b1.inputs["Strength"].default_value = 0.15
    b1.inputs["Distance"].default_value = 0.006
    L.new(grain.outputs["Fac"], b1.inputs["Height"])
    b2 = N.new("ShaderNodeBump")
    b2.inputs["Strength"].default_value = 0.11
    b2.inputs["Distance"].default_value = 0.008
    L.new(vor.outputs["Distance"], b2.inputs["Height"])
    L.new(b1.outputs["Normal"], b2.inputs["Normal"])

    rn = N.new("ShaderNodeTexNoise")
    rn.inputs["Scale"].default_value = 22.0
    L.new(coord.outputs["Object"], rn.inputs["Vector"])
    rr = N.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.34
    rr.inputs["To Max"].default_value = 0.52
    L.new(rn.outputs["Fac"], rr.inputs["Value"])
    return ramp, b2, rr


def leather_material(name, with_logo=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    for n in list(N):
        N.remove(n)
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    coord = N.new("ShaderNodeTexCoord")
    ramp, bump, rough = _leather_core(nt, coord)
    L.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    L.new(rough.outputs[0], bsdf.inputs["Roughness"])
    try:
        bsdf.inputs["Specular IOR Level"].default_value = 0.40
        bsdf.inputs["Coat Weight"].default_value = 0.07
        bsdf.inputs["Coat Roughness"].default_value = 0.33
    except KeyError:
        pass

    if with_logo and os.path.exists(LOGO):
        tex = N.new("ShaderNodeTexImage")
        tex.image = img("logo.png", os.path.join(HERE, "textures_v3"))
        tex.extension = "CLIP"
        tex.interpolation = "Cubic"
        w, h = tex.image.size
        aspect = (w / h) if h else 1.5
        LU = 0.46
        LV = (LU * CW / aspect) / CH
        mp = N.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1 / LU, 1 / LV, 1)
        mp.inputs["Location"].default_value = (0.5 - 0.5 / LU, 0.5 - 0.5 / LV, 0)
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
        dk = N.new("ShaderNodeMixRGB")
        dk.blend_type = "MULTIPLY"
        dk.inputs["Fac"].default_value = 0.45
        dk.inputs["Color2"].default_value = (0.6, 0.57, 0.55, 1)
        L.new(ramp.outputs["Color"], dk.inputs["Color1"])
        mc = N.new("ShaderNodeMixRGB")
        L.new(tex.outputs["Color"], mc.inputs["Fac"])
        L.new(ramp.outputs["Color"], mc.inputs["Color1"])
        L.new(dk.outputs["Color"], mc.inputs["Color2"])
        L.new(mc.outputs["Color"], bsdf.inputs["Base Color"])

    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    L.new(bsdf.outputs[0], out.inputs[0])
    return m


def lining_material(name, page_image):
    """The inside of a board: leather turn-in around a pasted-down page. The
    page is masked to exactly the text block, so the square shows as a border
    the same width as the one the back board shows on the other side."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    for n in list(N):
        N.remove(n)
    out = N.new("ShaderNodeOutputMaterial")
    coord = N.new("ShaderNodeTexCoord")

    leather = N.new("ShaderNodeBsdfPrincipled")
    ramp, bump, rough = _leather_core(nt, coord)
    L.new(ramp.outputs["Color"], leather.inputs["Base Color"])
    L.new(rough.outputs[0], leather.inputs["Roughness"])
    L.new(bump.outputs["Normal"], leather.inputs["Normal"])

    paper = N.new("ShaderNodeBsdfPrincipled")
    paper.inputs["Roughness"].default_value = 0.76
    tex = N.new("ShaderNodeTexImage")
    tex.image = img(page_image)
    tex.extension = "CLIP"
    mp = N.new("ShaderNodeMapping")
    # The underside's UVs are already mirrored by the mesh, so the page maps
    # into the mirrored block region: u' in [1 - PW/CW, 1].
    mp.inputs["Scale"].default_value = (CW / PW, CH / PH, 1)
    mp.inputs["Location"].default_value = (1 - CW / PW, -SQUARE / PH, 0)
    L.new(coord.outputs["UV"], mp.inputs["Vector"])
    L.new(mp.outputs["Vector"], tex.inputs["Vector"])
    L.new(tex.outputs["Color"], paper.inputs["Base Color"])

    mix = N.new("ShaderNodeMixShader")
    L.new(tex.outputs["Alpha"], mix.inputs["Fac"])
    L.new(leather.outputs[0], mix.inputs[1])
    L.new(paper.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs[0])
    return m


def page_material(name, image, mirror=False):
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
        bsdf.inputs["Specular IOR Level"].default_value = 0.25
    except KeyError:
        pass
    L.new(bsdf.outputs[0], out.inputs[0])
    coord = N.new("ShaderNodeTexCoord")
    tex = N.new("ShaderNodeTexImage")
    tex.image = img(image)
    L.new(coord.outputs["UV"], tex.inputs["Vector"])
    L.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    tooth = N.new("ShaderNodeTexNoise")
    tooth.inputs["Scale"].default_value = 520.0
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.04
    L.new(tooth.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def edge_material(name, striated):
    m = bpy.data.materials.new(name)
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
    if striated:
        wave = N.new("ShaderNodeTexWave")
        wave.wave_type = "BANDS"
        wave.bands_direction = "Z"
        wave.inputs["Scale"].default_value = 300.0
        wave.inputs["Distortion"].default_value = 1.5
        wave.inputs["Detail"].default_value = 2.0
        L.new(coord.outputs["Object"], wave.inputs["Vector"])
        ramp = N.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (0.46, 0.418, 0.350, 1)
        ramp.color_ramp.elements[1].color = (0.78, 0.745, 0.670, 1)
        L.new(wave.outputs["Fac"], ramp.inputs["Fac"])
        L.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        bump = N.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.28
        bump.inputs["Distance"].default_value = 0.004
        L.new(wave.outputs["Fac"], bump.inputs["Height"])
        L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    else:
        bsdf.inputs["Base Color"].default_value = (0.70, 0.665, 0.595, 1)
    return m


# ----------------------------------------------------------------- geometry
def slab(name, w, h, segx, segy, t, x0=0.0, dip=0.0):
    """A sheet with real thickness. Face materials are explicit: 0 on top,
    1 underneath, 2 around the rim - which is what lets a board show grain on
    one side, a pasted lining on the other, and a leather edge between."""
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)

    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    top, bot = {}, {}
    for i in range(segx + 1):
        for j in range(segy + 1):
            u, v = i / segx, j / segy
            x = x0 + u * w
            y = (v - 0.5) * h
            zc = -dip * exp(-max(x, 0.0) / DIP_FALLOFF) if dip else 0.0
            top[(i, j)] = bm.verts.new((x, y, zc + t / 2))
            bot[(i, j)] = bm.verts.new((x, y, zc - t / 2))
    bm.verts.ensure_lookup_table()

    def put_uv(f, mirror):
        for lp in f.loops:
            p = lp.vert.co
            u = (p.x - x0) / w
            lp[uv].uv = (1.0 - u if mirror else u, (p.y + h / 2) / h)

    for i in range(segx):
        for j in range(segy):
            f = bm.faces.new([top[(i, j)], top[(i + 1, j)],
                              top[(i + 1, j + 1)], top[(i, j + 1)]])
            f.material_index = 0
            put_uv(f, False)
            g = bm.faces.new([bot[(i, j)], bot[(i, j + 1)],
                              bot[(i + 1, j + 1)], bot[(i + 1, j)]])
            g.material_index = 1
            put_uv(g, True)     # mirrored: this face is seen after a turn

    def rim(a, b):
        f = bm.faces.new([top[a], top[b], bot[b], bot[a]])
        f.material_index = 2
        put_uv(f, False)
    for i in range(segx):
        rim((i + 1, 0), (i, 0))
        rim((i, segy), (i + 1, segy))
    for j in range(segy):
        rim((0, j), (0, j + 1))
        rim((segx, j + 1), (segx, j))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    for p in me.polygons:               # rims read better faceted
        if p.material_index == 2:
            p.use_smooth = False
    return ob


def rounded_spine(name, R, height, h, segt=26, segy=8):
    """The round back: a leather shell from the underside of the back board,
    out and around, to the top of the front board. Its ends sit exactly on
    those two surfaces so the closed case has no seam."""
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    grid = {}
    for i in range(segt + 1):
        tt = pi * i / segt                      # 0 at the top, pi at the bottom
        x = -R * sin(tt)
        z = height * 0.5 * (1 + cos(tt))
        for j in range(segy + 1):
            grid[(i, j)] = bm.verts.new((x, (j / segy - 0.5) * h, z))
    bm.verts.ensure_lookup_table()
    for i in range(segt):
        for j in range(segy):
            f = bm.faces.new([grid[(i, j)], grid[(i + 1, j)],
                              grid[(i + 1, j + 1)], grid[(i, j + 1)]])
            for lp in f.loops:
                p = lp.vert.co
                lp[uv].uv = (0.5 + p.x / (2 * R), (p.y + h / 2) / h)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    return ob


def page_block(name, x0, x1, h, z_bot, z_top, dip, segx=40, segy=6):
    """The text block. Its top carries the same gutter curve as the pages, so
    a page resting on it cannot sink through near the hinge - which is what
    put a hard grey band down the middle of the last spread."""
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    bm = bmesh.new()
    top, bot = {}, {}
    for i in range(segx + 1):
        for j in range(segy + 1):
            x = x0 + (x1 - x0) * i / segx
            y = (j / segy - 0.5) * h
            d = dip * exp(-abs(x) / DIP_FALLOFF)
            top[(i, j)] = bm.verts.new((x, y, z_top - d))
            bot[(i, j)] = bm.verts.new((x, y, z_bot))
    bm.verts.ensure_lookup_table()
    for i in range(segx):
        for j in range(segy):
            bm.faces.new([top[(i, j)], top[(i + 1, j)],
                          top[(i + 1, j + 1)], top[(i, j + 1)]])
            bm.faces.new([bot[(i, j)], bot[(i, j + 1)],
                          bot[(i + 1, j + 1)], bot[(i + 1, j)]])
    def rim(a, b):
        bm.faces.new([top[a], top[b], bot[b], bot[a]])
    for i in range(segx):
        rim((i + 1, 0), (i, 0))
        rim((i, segy), (i + 1, segy))
    for j in range(segy):
        rim((0, j), (0, j + 1))
        rim((segx, j + 1), (segx, j))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
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


def add_turn(ob, width, root_z, cone=0.0, droop=0.0, height=1.0,
             twist=0.0, skew=0.0):
    g = ob.modifiers.new("PageTurn", "NODES")
    g.node_group = NG
    inp = g.properties.inputs
    inp.Socket_1.value = 0.0
    inp.Socket_2.value = 0.0
    inp.Socket_3.value = root_z
    inp.Socket_4.value = width
    inp.Socket_5.value = cone
    inp.Socket_6.value = droop
    inp.Socket_7.value = height
    inp.Socket_8.value = twist
    inp.Socket_9.value = skew
    return g


def key(ob, socket, frame, value):
    nm = "Socket_%d" % socket
    getattr(ob.modifiers["PageTurn"].properties.inputs, nm).value = value
    ob.keyframe_insert(
        data_path='modifiers["PageTurn"].properties.inputs.%s.value' % nm, frame=frame)


# ===========================================================================
clear()
try:
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "BEZIER"
except Exception as e:
    print("interp:", e)

scene = bpy.context.scene
NG = page_turn_group()

M_GRAIN = leather_material("Leather_Grain")
M_GRAIN_LOGO = leather_material("Leather_Cover", with_logo=True)
M_LINING = lining_material("Cover_Lining", "quote_1.jpg")
M_LINING_BACK = lining_material("BackBoard_Lining", "photo_5.jpg")
M_EDGE_PAGE = edge_material("PageEdge", True)
M_EDGE_BOARD = edge_material("BoardEdge", False)
M_BLOCK = edge_material("BlockEdge", True)

# --- back board ------------------------------------------------------------
back = slab("BackBoard", CW, CH, 18, 8, BOARD_T, x0=0.0)
for m in (M_GRAIN, M_LINING_BACK, M_GRAIN):   # under / inside / rim
    back.data.materials.append(m)
back.location.z = Z_BACK_BOT + BOARD_T / 2
# the back board's lining faces UP, so swap which face carries it
back.data.materials[0] = M_LINING_BACK
back.data.materials[1] = M_GRAIN

# --- the pages that never turn --------------------------------------------
block = page_block("PageBlock", 0.0, PW, PH, Z_BACK_TOP, Z_BLOCK_TOP, GUTTER_DIP)
block.data.materials.append(M_BLOCK)

# The mirror of it, under the turned pages. It grows over the first turn, by
# which point the board is already lying flat beneath it, so nothing is ever
# seen floating.
left_block = page_block("LeftBlock", -PW, 0.0, PH, Z_BACK_TOP, Z_BLOCK_TOP, GUTTER_DIP)
left_block.data.materials.append(M_BLOCK)

# --- leaves ----------------------------------------------------------------
SPREADS = [("photo_1.jpg", "quote_2.jpg"),
           ("photo_2.jpg", "quote_3.jpg"),
           ("photo_3.jpg", "quote_4.jpg"),
           ("photo_4.jpg", "quote_5.jpg")]
leaves = []
for i, (recto, verso) in enumerate(SPREADS):
    lf = slab("Leaf%d" % (i + 1), PW, PH, SEG_X, SEG_Y, LEAF_T, dip=GUTTER_DIP)
    lf.data.materials.append(page_material("Leaf%d_R" % (i + 1), recto))
    lf.data.materials.append(page_material("Leaf%d_V" % (i + 1), verso))
    lf.data.materials.append(M_EDGE_PAGE)
    add_turn(lf, PW, z_leaf(i), cone=LEAF_CONE, droop=LEAF_DROOP, height=PH,
             twist=LEAF_TWIST, skew=LEAF_SKEW)
    leaves.append(lf)

final = slab("FinalPage", PW, PH, 28, 8, LEAF_T, dip=GUTTER_DIP)
final.data.materials.append(page_material("Final_R", "photo_5.jpg"))
final.data.materials.append(page_material("Final_V", "photo_5.jpg"))
final.data.materials.append(M_EDGE_PAGE)
final.location.z = Z_FINAL_C

# --- front board -----------------------------------------------------------
cover = slab("FrontCover", CW, CH, SEG_X, SEG_Y, BOARD_T, x0=0.0)
cover.data.materials.append(M_GRAIN_LOGO)     # grain, debossed
cover.data.materials.append(M_LINING)         # turn-in and pasted page
cover.data.materials.append(M_EDGE_BOARD)     # the slab edge, seen when open
add_turn(cover, CW, Z_FRONT_C, cone=COVER_CONE, droop=COVER_DROOP, height=CH,
         twist=COVER_TWIST, skew=COVER_SKEW)

# --- rounded spine ---------------------------------------------------------
spine = rounded_spine("Spine", SPINE_R, Z_TOP, CH)
spine.data.materials.append(M_GRAIN)

# =============================================================== animation ==
t0 = F_HOLD
t1 = t0 + F_COVER
t2 = t1 + F_SETTLE
COVER_CURL, LEAF_CURL = 1.15, 0.80

key(cover, 1, 1, 0.0); key(cover, 1, t0, 0.0); key(cover, 1, t1, pi)
key(cover, 2, 1, 0.0); key(cover, 2, t0, 0.0)
key(cover, 2, t0 + F_COVER * 0.44, COVER_CURL)
key(cover, 2, t1, 0.0)
key(cover, 3, 1, Z_FRONT_C); key(cover, 3, t0, Z_FRONT_C)
key(cover, 3, t1, Z_FRONT_LEFT)

# Opening the case flat collapses the round back. Driving the spine's height
# down as the cover peels is what keeps it from standing proud of the pages
# once they start coming over - the fault in v3.
spine.scale.z = 1.0
spine.keyframe_insert("scale", frame=1)
spine.keyframe_insert("scale", frame=t0)
spine.scale.z = 0.13
spine.keyframe_insert("scale", frame=t1)

# It has to appear without ever being seen appearing. Flattening it in z does
# not help - from overhead a flat slab is still an opaque rectangle. Instead it
# grows out of the gutter along x, tracking the leading edge of the page that
# is turning over it: a sheet at angle theta covers back to -PW*cos(theta), so
# matching that keeps the block permanently hidden beneath it.
left_block.scale.x = 0.001
left_block.keyframe_insert("scale", frame=1)
left_block.keyframe_insert("scale", frame=t2 + F_TURN * 0.5)
left_block.scale.x = 0.707                       # theta = 135 degrees
left_block.keyframe_insert("scale", frame=t2 + F_TURN * 0.75)
left_block.scale.x = 1.0
left_block.keyframe_insert("scale", frame=t2 + F_TURN)

f = t2
turns = []
for i, lf in enumerate(leaves):
    key(lf, 1, 1, 0.0); key(lf, 1, f, 0.0); key(lf, 1, f + F_TURN, pi)
    key(lf, 2, 1, 0.0); key(lf, 2, f, 0.0)
    key(lf, 2, f + F_TURN * 0.46, LEAF_CURL)
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
cam_data.lens = 200.0
cam = bpy.data.objects.new("Camera", cam_data)
bpy.context.collection.objects.link(cam)
cam.rotation_euler = (0.0, 0.0, 0.0)
scene.camera = cam
cam.location = (PW / 2, 0.0, 12.4)
cam.keyframe_insert("location", frame=1)
cam.keyframe_insert("location", frame=t0)
cam.location = (0.0, 0.0, 12.4)
cam.keyframe_insert("location", frame=t1)

# ------------------------------------------------------------------ lights -
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
r.filepath = os.path.join(HERE, "frames_v4") + os.sep
scene.view_settings.view_transform = "Standard"

try:
    ev = scene.eevee
    ev.use_shadows = True
    ev.use_raytracing = True
    ev.taa_render_samples = 96
    ev.shadow_ray_count = 4
    ev.shadow_step_count = 12
    ev.shadow_resolution_scale = 2
    ev.use_fast_gi = True
except Exception as e:
    print("eevee:", e)

print("v4 built: 1-%d, turns %s, case %.4f thick, spine R %.4f"
      % (LAST, turns, Z_TOP, SPINE_R))
