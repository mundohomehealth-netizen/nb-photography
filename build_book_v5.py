"""
v5: the pages are simulated instead of drawn.

Everything up to v4 bent each leaf as a circular arc of constant curvature,
uniform along its height. That is a cylinder, and it is the thing that reads as
fake: a real turning page is conical, not cylindrical. Its free corners fall
under their own weight, the curl bunches near the spine and flattens toward the
fore-edge, and at the end it drops rather than arriving.

So this build keeps the v4 case exactly as it is - boards, blocks, round back,
materials - and replaces only the leaves.

How the turn is driven:

  The existing PageTurn modifier still runs, but now it is only a KINEMATIC
  GUIDE. Cloth sits after it and pins just two regions to that guide - the
  spine edge, which stays put, and a patch at the fore-edge, which is the
  "hand" carrying the page over. Everything between those two is solved. That
  is also how a page really works: two constraints and a sheet that does as
  gravity and its own stiffness dictate.

  Pinning both ends to a path the rig already computes avoids hooks, armatures
  and a second animation to keep in sync.

Leaves go back to single-surface sheets, because cloth on a closed slab behaves
like a pressure vessel rather than paper. The page rim is lost, but from
straight overhead a 0.9mm edge was never visible anyway - the stacks get their
edges from the blocks, which are unchanged.

Scale note: the scene is built at roughly 1 unit = 200mm, so a page is about
1.0 x 1.5 units. To a solver that is a sheet one and a half metres tall, which
would drape like a bedsheet. BEND is therefore set far above any real-paper
figure to compensate; it is a stiffness in scene units, not a claim about paper.
"""

import bpy
import bmesh
import os
from math import pi, exp

HERE = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else \
    r"C:\Users\Muhundan\Documents\NB Album Animation"

# ---- cloth tuning, all in scene units ------------------------------------
QUALITY = 14
MASS = 0.30
BEND = 450.0            # see the scale note above
TENSION = 120.0         # paper does not stretch
SHEAR = 90.0
AIR_DAMP = 1.6
COLL_DIST = 0.0012      # leaves sit 0.0045 apart; the default would shove them
SELF_DIST = 0.0010

PIN_SPINE = 0.045       # share of the page width pinned at the hinge
PIN_HAND_X = 0.040      # ... and at the fore-edge, where the turn is led from
PIN_HAND_Y = 0.34       # how much of the height the "hand" holds


def run_v4():
    path = os.path.join(HERE, "build_book_v4.py")
    g = {"__name__": "__main__"}
    exec(compile(open(path, encoding="utf-8").read(), path, "exec"), g)
    return g


def leaf_surface(name, w, h, segx, segy, dip, dip_falloff):
    """Single-surface sheet. Cloth wants a surface, not a solid."""
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    v = {}
    for i in range(segx + 1):
        for j in range(segy + 1):
            x = w * i / segx
            y = (j / segy - 0.5) * h
            v[(i, j)] = bm.verts.new((x, y, -dip * exp(-x / dip_falloff)))
    bm.verts.ensure_lookup_table()
    for i in range(segx):
        for j in range(segy):
            f = bm.faces.new([v[(i, j)], v[(i + 1, j)],
                              v[(i + 1, j + 1)], v[(i, j + 1)]])
            for lp in f.loops:
                p = lp.vert.co
                lp[uv].uv = (p.x / w, (p.y + h / 2) / h)
    # No recalc here: the winding above already faces +Z, and recalc on an
    # open sheet is ambiguous - it picked -Z, which made every leaf render its
    # own backface and show the verso, mirrored.
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    return ob


def two_sided_material(name, recto, verso, tex_dir):
    """Recto and verso on one surface, chosen by Geometry > Backfacing, with
    the verso's U mirrored so it is not reversed once the page has turned."""
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
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(coord.outputs["UV"], sep.inputs[0])
    flip = N.new("ShaderNodeMath")
    flip.operation = "SUBTRACT"
    flip.inputs[0].default_value = 1.0
    L.new(sep.outputs["X"], flip.inputs[1])
    comb = N.new("ShaderNodeCombineXYZ")
    L.new(flip.outputs[0], comb.inputs["X"])
    L.new(sep.outputs["Y"], comb.inputs["Y"])

    def tex(fn, vec):
        t = N.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(os.path.join(tex_dir, fn), check_existing=True)
        L.new(vec, t.inputs["Vector"])
        return t

    tf = tex(recto, coord.outputs["UV"])
    tb = tex(verso, comb.outputs[0])
    geo = N.new("ShaderNodeNewGeometry")
    mix = N.new("ShaderNodeMixRGB")
    L.new(geo.outputs["Backfacing"], mix.inputs["Fac"])
    L.new(tf.outputs["Color"], mix.inputs["Color1"])
    L.new(tb.outputs["Color"], mix.inputs["Color2"])
    L.new(mix.outputs["Color"], bsdf.inputs["Base Color"])

    tooth = N.new("ShaderNodeTexNoise")
    tooth.inputs["Scale"].default_value = 520.0
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.04
    L.new(tooth.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def pin_group(ob, w, h):
    """Two held regions: the hinge, and the patch the turn is led from."""
    vg = ob.vertex_groups.new(name="pin")
    spine, hand = [], []
    for v in ob.data.vertices:
        if v.co.x <= w * PIN_SPINE:
            spine.append(v.index)
        elif v.co.x >= w * (1.0 - PIN_HAND_X) and abs(v.co.y) <= h * PIN_HAND_Y / 2:
            hand.append(v.index)
    vg.add(spine, 1.0, "REPLACE")
    vg.add(hand, 1.0, "REPLACE")
    return vg, len(spine), len(hand)


def add_cloth(ob, vg_name):
    md = ob.modifiers.new("Cloth", "CLOTH")
    s = md.settings
    c = md.collision_settings
    s.quality = QUALITY
    s.mass = MASS
    s.tension_stiffness = TENSION
    s.compression_stiffness = TENSION
    s.shear_stiffness = SHEAR
    s.bending_stiffness = BEND
    s.air_damping = AIR_DAMP
    try:
        s.bending_model = "ANGULAR"
    except Exception:
        pass
    s.vertex_group_mass = vg_name          # the pin group
    c.use_collision = True
    c.distance_min = COLL_DIST
    c.use_self_collision = True
    c.self_distance_min = SELF_DIST
    c.collision_quality = 4
    return md


def make_collider(ob, thickness=0.0010):
    if "Collision" in ob.modifiers:
        return
    md = ob.modifiers.new("Collision", "COLLISION")
    try:
        md.settings.thickness_outer = thickness
        md.settings.thickness_inner = thickness
        md.settings.damping = 0.4
    except Exception:
        pass


# ===========================================================================
G = run_v4()

PW, PH = G["PW"], G["PH"]
SEG_X, SEG_Y = G["SEG_X"], G["SEG_Y"]
GUTTER_DIP, DIP_FALLOFF = G["GUTTER_DIP"], G["DIP_FALLOFF"]
TEX = G["TEX"]
NG = G["NG"]
N_LEAVES = G["N_LEAVES"]
SPREADS = G["SPREADS"]
z_leaf, z_leaf_left = G["z_leaf"], G["z_leaf_left"]
t2, F_TURN, F_PAUSE = G["t2"], G["F_TURN"], G["F_PAUSE"]
LEAF_CURL = G["LEAF_CURL"]
key, add_turn = G["key"], G["add_turn"]

scene = bpy.context.scene

# --- swap each solid leaf for a simulated surface --------------------------
old = [bpy.data.objects["Leaf%d" % (i + 1)] for i in range(N_LEAVES)]
for ob in old:
    bpy.data.objects.remove(ob, do_unlink=True)

leaves = []
f = t2
report = []
for i, (recto, verso) in enumerate(SPREADS):
    lf = leaf_surface("Leaf%d" % (i + 1), PW, PH, SEG_X, SEG_Y,
                      GUTTER_DIP, DIP_FALLOFF)
    lf.data.materials.append(
        two_sided_material("Leaf%d_Mat" % (i + 1), recto, verso, TEX))

    # the same kinematic path as before, now only a guide for the pins
    add_turn(lf, PW, z_leaf(i))
    key(lf, 1, 1, 0.0); key(lf, 1, f, 0.0); key(lf, 1, f + F_TURN, pi)
    key(lf, 2, 1, 0.0)          # Curl stays flat: the guide is a rigid swing,
    key(lf, 2, f + F_TURN, 0.0) # and the solver supplies the actual curve
    key(lf, 3, 1, z_leaf(i)); key(lf, 3, f, z_leaf(i))
    key(lf, 3, f + F_TURN, z_leaf_left(i))

    vg, n_spine, n_hand = pin_group(lf, PW, PH)
    add_cloth(lf, vg.name)
    leaves.append(lf)
    report.append((lf.name, n_spine, n_hand))
    f += F_TURN + F_PAUSE

# --- everything a page can land on -----------------------------------------
for nm in ("PageBlock", "LeftBlock", "BackBoard", "FrontCover", "FinalPage"):
    ob = bpy.data.objects.get(nm)
    if ob:
        make_collider(ob)
for lf in leaves:
    make_collider(lf)

scene.frame_set(scene.frame_start)
print("v5: %d simulated leaves, pins %s" % (len(leaves), report))
