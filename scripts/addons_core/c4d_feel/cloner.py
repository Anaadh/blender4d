"""MoGraph Cloner and effectors built on Geometry Nodes.

Create > MoGraph > Cloner puts the selected objects under a new "Cloner"
object. The children go into a collection that the cloner's node tree
instances, like C4D where a Cloner clones its children. Modes: Linear,
Radial, Grid, Object (clone onto an object's vertices, polygon centers,
surface or spline).

Effectors are objects, like in C4D. Each one carries a "C4D Effector" node
tree whose parameters (strength, position / rotation / scale, falloff) are
written as named attributes onto four frame points (origin + X / Y / Z).
The Cloner reads its "Effectors" collection and, in a repeat zone, applies
every effector in turn, so any number of them stack: Plain, Random, Step.
Falloff shapes: Infinite, Spherical, Box, Linear, each with an inner offset,
and the effector's own transform moves, rotates and scales the falloff.
"""

import math

import bpy

GROUP = "C4D Cloner"
EFFECTOR_GROUP = "C4D Effector"
VERSION = {GROUP: 2, EFFECTOR_GROUP: 1}  # bump when a node tree changes

MODES = ("Linear", "Radial", "Grid", "Honeycomb", "Object")
DISTRIBUTIONS = ("Vertex", "Polygon Center", "Surface", "Spline")
EFFECTOR_KINDS = ("Plain", "Random", "Step")
FALLOFFS = ("Infinite", "Spherical", "Box", "Linear")
EFFECTOR_ICONS = {"Plain": 'SPHERE', "Random": 'RNDCURVE', "Step": 'IPO_LINEAR'}
ATTR = "c4d_eff_"  # attribute prefix on the effector frame points

# Inputs shown only in some modes (C4D hides the others).
MODE_ONLY = {
    "Count": ("Linear", "Radial", "Object"),
    "Offset": ("Linear",),
    "Radius": ("Radial",),
    "Grid Count X": ("Grid", "Honeycomb"),
    "Grid Count Y": ("Grid", "Honeycomb"),
    "Grid Count Z": ("Grid",),
    "Grid Size": ("Grid", "Honeycomb"),
    "Object": ("Object",),
    "Distribution": ("Object",),
    "Align Clone": ("Object", "Radial"),
    "Seed": ("Object",),
}


# ---------------------------------------------------------------------------
# Node tree builder
# ---------------------------------------------------------------------------

def _socket(iface, name, stype, default=None, min_value=None, subtype=None, max_value=None):
    s = iface.new_socket(name=name, in_out='INPUT', socket_type=stype)
    if subtype is not None and hasattr(s, "subtype"):
        s.subtype = subtype
    if default is not None:
        s.default_value = default
    if min_value is not None and hasattr(s, "min_value"):
        s.min_value = min_value
    if max_value is not None and hasattr(s, "max_value"):
        s.max_value = max_value
    return s


def _group(name):
    """(tree, is_new). Older trees are kept as "<name> (old)" so saved files work."""
    want = VERSION[name]
    ng = bpy.data.node_groups.get(name)
    if ng is not None:
        if ng.get("c4d_version", 1) >= want:
            return ng, False
        ng.name = name + " (old)"
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng["c4d_version"] = want
    it = ng.interface
    it.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    it.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    return ng, True


class _T:
    """Small helper around a node tree: nodes get laid out left to right."""

    def __init__(self, ng):
        self.ng, self.N, self.L = ng, ng.nodes, ng.links
        self.gin = self.N.new('NodeGroupInput')
        self.gin.location = (-1400, 0)
        self.x, self.y = -1100, 0

    def node(self, kind, **props):
        n = self.N.new(kind)
        n.location = (self.x, self.y)
        self.x += 170
        if self.x > 3000:
            self.x, self.y = -1100, self.y - 500
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def i(self, name):
        return self.gin.outputs[name]

    def link(self, a, b):
        self.L.new(a, b)

    def set(self, sock, v):
        """Link a socket or set a constant."""
        if v is None:
            return
        if isinstance(v, bpy.types.NodeSocket):
            self.L.new(v, sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=None, c=None, **kw):
        n = self.node('ShaderNodeMath', operation=op, **kw)
        for idx, v in enumerate((a, b, c)):
            self.set(n.inputs[idx], v)
        return n.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        n = self.node('ShaderNodeVectorMath', operation=op)
        self.set(n.inputs[0], a)
        self.set(n.inputs[1], b)
        self.set(n.inputs["Scale"], scale)
        return n.outputs["Value"] if op in {'DOT_PRODUCT', 'LENGTH', 'DISTANCE'} else n.outputs["Vector"]

    def xyz(self, x, y, z):
        n = self.node('ShaderNodeCombineXYZ')
        for sock, v in zip(("X", "Y", "Z"), (x, y, z)):
            self.set(n.inputs[sock], v)
        return n.outputs[0]

    def eq(self, a, b):
        n = self.node('FunctionNodeCompare', data_type='FLOAT', operation='EQUAL')
        self.set(n.inputs["A"], a)
        self.set(n.inputs["B"], b)
        return n.outputs["Result"]

    def switch(self, stype, cond, false, true):
        n = self.node('GeometryNodeSwitch', input_type=stype)
        self.set(n.inputs["Switch"], cond)
        self.set(n.inputs["False"], false)
        self.set(n.inputs["True"], true)
        return n.outputs[0]

    def menu_switch(self, dtype, menu, items):
        """items: {name: socket or constant}. Linked to `menu` (a group input)."""
        sw = self.node('GeometryNodeMenuSwitch')
        sw.data_type = dtype
        sw.enum_items.clear()
        for name in items:
            sw.enum_items.new(name)
        self.link(menu, sw.inputs["Menu"])
        for name, v in items.items():
            self.set(sw.inputs[name], v)
        return sw.outputs[0]

    def named(self, name, dtype):
        n = self.node('GeometryNodeInputNamedAttribute', data_type=dtype)
        n.inputs["Name"].default_value = name
        return n.outputs[0]

    def store(self, geo, name, dtype, value, domain='POINT'):
        n = self.node('GeometryNodeStoreNamedAttribute', data_type=dtype, domain=domain)
        n.inputs["Name"].default_value = name
        self.link(geo, n.inputs["Geometry"])
        self.set(n.inputs["Value"], value)
        return n.outputs[0]

    def join(self, *geos):
        n = self.node('GeometryNodeJoinGeometry')
        for g in geos:
            self.link(g, n.inputs[0])
        return n.outputs[0]

    def realize(self, geo):
        n = self.node('GeometryNodeRealizeInstances')
        self.link(geo, n.inputs[0])
        return n.outputs[0]

    def sample(self, geo, value, dtype, index=0):
        n = self.node('GeometryNodeSampleIndex', data_type=dtype, domain='POINT')
        self.link(geo, n.inputs["Geometry"])
        self.set(n.inputs["Value"], value)
        self.set(n.inputs["Index"], index)
        return n.outputs["Value"]

    def finish(self, geo):
        out = self.node('NodeGroupOutput')
        self.link(geo, out.inputs[0])


# ---------------------------------------------------------------------------
# Effector node tree
# ---------------------------------------------------------------------------

def build_effector_group():
    ng, new = _group(EFFECTOR_GROUP)
    if not new:
        return ng
    it = ng.interface
    _socket(it, "Kind", 'NodeSocketMenu')
    _socket(it, "Strength", 'NodeSocketFloat', 1.0, subtype='FACTOR')
    _socket(it, "Position", 'NodeSocketVector', (0.0, 0.0, 0.0), subtype='TRANSLATION')
    _socket(it, "Rotation", 'NodeSocketVector', (0.0, 0.0, 0.0), subtype='EULER')
    _socket(it, "Scale", 'NodeSocketFloat', 0.0)
    _socket(it, "Seed", 'NodeSocketInt', 0)
    _socket(it, "Falloff", 'NodeSocketMenu')
    _socket(it, "Radius", 'NodeSocketFloat', 2.0, 0.0, subtype='DISTANCE')
    _socket(it, "Inner Offset", 'NodeSocketFloat', 0.0, 0.0, subtype='FACTOR', max_value=0.99)

    t = _T(ng)
    kind = t.menu_switch('INT', t.i("Kind"), {k: i for i, k in enumerate(EFFECTOR_KINDS)})
    falloff = t.menu_switch('INT', t.i("Falloff"), {k: i for i, k in enumerate(FALLOFFS)})

    # Frame: point 0 = origin, 1 / 2 / 3 = unit X / Y / Z. After the Cloner's
    # Collection Info they carry the effector's transform relative to the cloner.
    pts = t.node('GeometryNodePoints')
    pts.inputs["Count"].default_value = 4
    pts.inputs["Radius"].default_value = 0.0
    index = t.node('GeometryNodeInputIndex').outputs[0]
    t.link(t.xyz(t.eq(index, 1.0), t.eq(index, 2.0), t.eq(index, 3.0)), pts.inputs["Position"])
    geo = pts.outputs[0]
    for name, dtype, value in (("strength", 'FLOAT', t.i("Strength")),
                               ("pos", 'FLOAT_VECTOR', t.i("Position")),
                               ("rot", 'FLOAT_VECTOR', t.i("Rotation")),
                               ("scale", 'FLOAT', t.i("Scale")),
                               ("seed", 'INT', t.i("Seed")),
                               ("kind", 'INT', kind),
                               ("falloff", 'INT', falloff),
                               ("radius", 'FLOAT', t.i("Radius")),
                               ("inner", 'FLOAT', t.i("Inner Offset"))):
        geo = t.store(geo, ATTR + name, dtype, value)

    # Viewport gizmo for the falloff (curves draw as wires).
    def line(start, end):
        n = t.node('GeometryNodeCurvePrimitiveLine', mode='POINTS')
        t.set(n.inputs["Start"], start)
        t.set(n.inputs["End"], end)
        return n.outputs["Curve"]

    cross = t.join(line((-0.25, 0.0, 0.0), (0.25, 0.0, 0.0)),
                   line((0.0, -0.25, 0.0), (0.0, 0.25, 0.0)),
                   line((0.0, 0.0, -0.25), (0.0, 0.0, 0.25)))
    rings = []
    for rot in ((0.0, 0.0, 0.0), (math.pi / 2, 0.0, 0.0), (0.0, math.pi / 2, 0.0)):
        c = t.node('GeometryNodeCurvePrimitiveCircle', mode='RADIUS')
        c.inputs["Resolution"].default_value = 48
        t.link(t.i("Radius"), c.inputs["Radius"])
        tr = t.node('GeometryNodeTransform')
        t.link(c.outputs["Curve"], tr.inputs["Geometry"])
        tr.inputs["Rotation"].default_value = rot
        rings.append(tr.outputs["Geometry"])
    sphere = t.join(*rings)
    size = t.math('MULTIPLY', t.i("Radius"), 2.0)
    cube = t.node('GeometryNodeMeshCube')
    t.link(t.xyz(size, size, size), cube.inputs["Size"])
    m2c = t.node('GeometryNodeMeshToCurve')
    t.link(cube.outputs["Mesh"], m2c.inputs["Mesh"])
    box = m2c.outputs["Curve"]
    linear = t.join(cross, line((0.0, 0.0, 0.0), t.xyz(t.i("Radius"), 0.0, 0.0)))
    # A group menu input may feed only one Menu Switch, so pick the gizmo by the int.
    gizmo = t.switch('GEOMETRY', t.eq(falloff, 1.0),
                     t.switch('GEOMETRY', t.eq(falloff, 2.0),
                              t.switch('GEOMETRY', t.eq(falloff, 3.0), cross, linear), box),
                     sphere)
    t.finish(t.join(geo, gizmo))
    return ng


# ---------------------------------------------------------------------------
# Cloner node tree
# ---------------------------------------------------------------------------

def build_group():
    ng, new = _group(GROUP)
    if not new:
        return ng
    it = ng.interface
    _socket(it, "Children", 'NodeSocketCollection')
    _socket(it, "Mode", 'NodeSocketMenu')
    _socket(it, "Count", 'NodeSocketInt', 3, 1)
    _socket(it, "Offset", 'NodeSocketVector', (0.0, 0.0, 1.0), subtype='TRANSLATION')
    _socket(it, "Radius", 'NodeSocketFloat', 2.0, 0.0, subtype='DISTANCE')
    _socket(it, "Grid Count X", 'NodeSocketInt', 3, 1)
    _socket(it, "Grid Count Y", 'NodeSocketInt', 3, 1)
    _socket(it, "Grid Count Z", 'NodeSocketInt', 1, 1)
    _socket(it, "Grid Size", 'NodeSocketVector', (4.0, 4.0, 0.0), subtype='TRANSLATION')
    _socket(it, "Object", 'NodeSocketObject')
    _socket(it, "Distribution", 'NodeSocketMenu')
    _socket(it, "Align Clone", 'NodeSocketBool', True)
    _socket(it, "Seed", 'NodeSocketInt', 0)
    _socket(it, "Effectors", 'NodeSocketCollection')

    t = _T(ng)

    # --- point distributions --------------------------------------------
    line = t.node('GeometryNodeMeshLine', mode='OFFSET')
    t.link(t.i("Count"), line.inputs["Count"])
    t.link(t.i("Offset"), line.inputs["Offset"])

    circle = t.node('GeometryNodeMeshCircle')
    t.link(t.i("Count"), circle.inputs["Vertices"])
    t.link(t.i("Radius"), circle.inputs["Radius"])
    # Radial clones face outward, like C4D's aligned radial cloner.
    pos = t.node('GeometryNodeInputPosition').outputs[0]
    align_x = t.node('FunctionNodeAlignRotationToVector', axis='X')
    t.link(pos, align_x.inputs["Vector"])
    radial = t.store(circle.outputs[0], "c4d_rot", 'QUATERNION', align_x.outputs[0])

    sep = t.node('ShaderNodeSeparateXYZ')
    t.link(t.i("Grid Size"), sep.inputs[0])
    grid = t.node('GeometryNodeMeshGrid')
    t.link(sep.outputs["X"], grid.inputs["Size X"])
    t.link(sep.outputs["Y"], grid.inputs["Size Y"])
    t.link(t.i("Grid Count X"), grid.inputs["Vertices X"])
    t.link(t.i("Grid Count Y"), grid.inputs["Vertices Y"])
    half = t.math('MULTIPLY', sep.outputs["Z"], 0.5)
    zline = t.node('GeometryNodeMeshLine', mode='END_POINTS')
    t.link(t.i("Grid Count Z"), zline.inputs["Count"])
    # One layer sits at the start point, so start at 0 then (centred otherwise).
    layers = t.math('MINIMUM', t.math('SUBTRACT', t.i("Grid Count Z"), 1.0), 1.0)
    t.link(t.xyz(0.0, 0.0, t.math('MULTIPLY', t.math('MULTIPLY', half, -1.0), layers)), zline.inputs["Start Location"])
    t.link(t.xyz(0.0, 0.0, half), zline.inputs["Offset"])
    stack = t.node('GeometryNodeInstanceOnPoints')
    t.link(zline.outputs[0], stack.inputs["Points"])
    t.link(grid.outputs[0], stack.inputs["Instance"])
    grid_pts = t.realize(stack.outputs[0])

    # Honeycomb: the XY grid with every other row shifted by half a cell.
    gindex = t.node('GeometryNodeInputIndex').outputs[0]
    # Grid vertex order is x-major (index = x * count_y + y), so the row is index mod count_y.
    odd = t.math('FLOORED_MODULO', t.math('FLOORED_MODULO', gindex, t.i("Grid Count Y")), 2.0)
    cell = t.math('DIVIDE', sep.outputs["X"], t.math('MAXIMUM', t.math('SUBTRACT', t.i("Grid Count X"), 1.0), 1.0))
    honey = t.node('GeometryNodeSetPosition')
    t.link(grid.outputs[0], honey.inputs["Geometry"])
    t.link(t.xyz(t.math('MULTIPLY', odd, t.math('MULTIPLY', cell, 0.5)), 0.0, 0.0), honey.inputs["Offset"])

    # Object mode: clone onto another object's vertices / polygons / surface / spline.
    info = t.node('GeometryNodeObjectInfo', transform_space='RELATIVE')
    t.link(t.i("Object"), info.inputs["Object"])
    ogeo = info.outputs["Geometry"]
    normal = t.node('GeometryNodeInputNormal').outputs["Normal"]
    align_z = t.node('FunctionNodeAlignRotationToVector', axis='Z')
    t.link(normal, align_z.inputs["Vector"])
    v2p = t.node('GeometryNodeMeshToPoints', mode='VERTICES')
    t.link(t.store(ogeo, "c4d_rot", 'QUATERNION', align_z.outputs[0], 'POINT'), v2p.inputs["Mesh"])
    f2p = t.node('GeometryNodeMeshToPoints', mode='FACES')
    t.link(t.store(ogeo, "c4d_rot", 'QUATERNION', align_z.outputs[0], 'FACE'), f2p.inputs["Mesh"])
    area = t.node('GeometryNodeInputMeshFaceArea').outputs["Area"]
    stat = t.node('GeometryNodeAttributeStatistic', data_type='FLOAT', domain='FACE')
    t.link(ogeo, stat.inputs["Geometry"])
    t.link(area, stat.inputs["Attribute"])
    density = t.math('DIVIDE', t.i("Count"), t.math('MAXIMUM', stat.outputs["Sum"], 1e-6))
    dist = t.node('GeometryNodeDistributePointsOnFaces', distribute_method='RANDOM')
    t.link(ogeo, dist.inputs["Mesh"])
    t.link(density, dist.inputs["Density"])
    t.link(t.i("Seed"), dist.inputs["Seed"])
    surface = t.store(dist.outputs["Points"], "c4d_rot", 'QUATERNION', dist.outputs["Rotation"])
    c2p = t.node('GeometryNodeCurveToPoints', mode='COUNT')
    t.link(ogeo, c2p.inputs["Curve"])
    t.link(t.i("Count"), c2p.inputs["Count"])
    spline = t.store(c2p.outputs["Points"], "c4d_rot", 'QUATERNION', c2p.outputs["Rotation"])
    obj_pts = t.menu_switch('GEOMETRY', t.i("Distribution"),
                            {"Vertex": v2p.outputs["Points"], "Polygon Center": f2p.outputs["Points"],
                             "Surface": surface, "Spline": spline})

    points = t.menu_switch('GEOMETRY', t.i("Mode"),
                           {"Linear": line.outputs[0], "Radial": radial, "Grid": grid_pts,
                            "Honeycomb": honey.outputs[0], "Object": obj_pts})

    # --- clone the children ---------------------------------------------
    coll = t.node('GeometryNodeCollectionInfo')
    coll.inputs["Separate Children"].default_value = True
    coll.inputs["Reset Children"].default_value = True
    t.link(t.i("Children"), coll.inputs["Collection"])
    index = t.node('GeometryNodeInputIndex').outputs[0]
    iop = t.node('GeometryNodeInstanceOnPoints')
    iop.inputs["Pick Instance"].default_value = True
    t.link(points, iop.inputs["Points"])
    t.link(coll.outputs[0], iop.inputs["Instance"])
    t.link(index, iop.inputs["Instance Index"])
    rot = t.named("c4d_rot", 'QUATERNION')
    t.link(t.switch('ROTATION', t.i("Align Clone"), None, rot), iop.inputs["Rotation"])
    clones = iop.outputs[0]

    # --- effector stack ----------------------------------------------------
    # One repeat iteration per object in the Effectors collection.
    effs = t.node('GeometryNodeCollectionInfo', transform_space='RELATIVE')
    effs.inputs["Separate Children"].default_value = True
    effs.inputs["Reset Children"].default_value = False
    t.link(t.i("Effectors"), effs.inputs["Collection"])
    ecount = t.node('GeometryNodeAttributeDomainSize', component='INSTANCES')
    t.link(effs.outputs[0], ecount.inputs["Geometry"])

    rin = t.node('GeometryNodeRepeatInput')
    rout = t.node('GeometryNodeRepeatOutput')
    rin.pair_with_output(rout)
    t.link(ecount.outputs["Instance Count"], rin.inputs["Iterations"])
    t.link(clones, rin.inputs["Geometry"])
    iteration = rin.outputs["Iteration"]
    geo = rin.outputs["Geometry"]

    # This iteration's effector: its realized frame points + attributes.
    pick = t.node('GeometryNodeSeparateGeometry', domain='INSTANCE')
    t.link(effs.outputs[0], pick.inputs["Geometry"])
    t.link(t.eq(t.node('GeometryNodeInputIndex').outputs[0], iteration), pick.inputs["Selection"])
    comps = t.node('GeometryNodeSeparateComponents')
    t.link(t.realize(pick.outputs["Selection"]), comps.inputs["Geometry"])
    frame = comps.outputs["Point Cloud"]
    epos = t.node('GeometryNodeInputPosition').outputs[0]
    origin = t.sample(frame, epos, 'FLOAT_VECTOR', 0)
    axes = [t.vmath('SUBTRACT', t.sample(frame, epos, 'FLOAT_VECTOR', i), origin) for i in (1, 2, 3)]

    def param(name, dtype):
        return t.sample(frame, t.named(ATTR + name, dtype), dtype)

    strength, kind, falloff = param("strength", 'FLOAT'), param("kind", 'INT'), param("falloff", 'INT')
    radius, inner, seed = param("radius", 'FLOAT'), param("inner", 'FLOAT'), param("seed", 'INT')
    epos_v, erot_v, escale = param("pos", 'FLOAT_VECTOR'), param("rot", 'FLOAT_VECTOR'), param("scale", 'FLOAT')

    # Clone position in the effector's local frame (its scale sizes the falloff).
    cpos = t.node('GeometryNodeInputPosition').outputs[0]
    rel = t.vmath('SUBTRACT', cpos, origin)
    local = [t.math('DIVIDE', t.vmath('DOT_PRODUCT', rel, ax), t.vmath('DOT_PRODUCT', ax, ax)) for ax in axes]
    d_sphere = t.vmath('LENGTH', t.xyz(*local))
    d_box = t.math('MAXIMUM', t.math('MAXIMUM', t.math('ABSOLUTE', local[0]), t.math('ABSOLUTE', local[1])),
                   t.math('ABSOLUTE', local[2]))
    d_linear = local[0]
    d = t.switch('FLOAT', t.eq(falloff, 1.0), t.switch('FLOAT', t.eq(falloff, 2.0), d_linear, d_box), d_sphere)
    ramp = t.node('ShaderNodeMapRange', data_type='FLOAT', interpolation_type='SMOOTHSTEP', clamp=True)
    t.link(d, ramp.inputs["Value"])
    t.link(t.math('MULTIPLY', inner, radius), ramp.inputs["From Min"])
    t.link(radius, ramp.inputs["From Max"])
    ramp.inputs["To Min"].default_value = 1.0
    ramp.inputs["To Max"].default_value = 0.0
    weight = t.math('MULTIPLY', t.switch('FLOAT', t.eq(falloff, 0.0), ramp.outputs["Result"], 1.0), strength)

    # Kind: Random jitters per clone, Step ramps along the clone index.
    cindex = t.node('GeometryNodeInputIndex').outputs[0]
    is_random, is_step = t.eq(kind, 1.0), t.eq(kind, 2.0)

    def rnd(dtype, seed_offset):
        n = t.node('FunctionNodeRandomValue', data_type=dtype)
        n.inputs["Min"].default_value = (-1.0, -1.0, -1.0) if dtype == 'FLOAT_VECTOR' else -1.0
        n.inputs["Max"].default_value = (1.0, 1.0, 1.0) if dtype == 'FLOAT_VECTOR' else 1.0
        t.link(cindex, n.inputs["ID"])
        t.link(t.math('ADD', seed, seed_offset), n.inputs["Seed"])
        return n.outputs[0]

    f_pos = t.switch('VECTOR', is_random, (1.0, 1.0, 1.0), rnd('FLOAT_VECTOR', 0.0))
    f_rot = t.switch('VECTOR', is_random, (1.0, 1.0, 1.0), rnd('FLOAT_VECTOR', 1.0))
    f_scale = t.switch('FLOAT', is_random, 1.0, rnd('FLOAT', 2.0))
    ccount = t.node('GeometryNodeAttributeDomainSize', component='INSTANCES')
    t.link(geo, ccount.inputs["Geometry"])
    step = t.math('DIVIDE', cindex, t.math('MAXIMUM', t.math('SUBTRACT', ccount.outputs["Instance Count"], 1.0), 1.0))
    w = t.math('MULTIPLY', weight, t.switch('FLOAT', is_step, 1.0, step))

    tr = t.node('GeometryNodeTranslateInstances')
    t.link(geo, tr.inputs["Instances"])
    t.link(t.vmath('SCALE', t.vmath('MULTIPLY', epos_v, f_pos), scale=w), tr.inputs["Translation"])
    ro = t.node('GeometryNodeRotateInstances')
    t.link(tr.outputs[0], ro.inputs["Instances"])
    t.link(t.vmath('SCALE', t.vmath('MULTIPLY', erot_v, f_rot), scale=w), ro.inputs["Rotation"])
    sc = t.node('GeometryNodeScaleInstances')
    t.link(ro.outputs[0], sc.inputs["Instances"])
    t.link(t.math('ADD', t.math('MULTIPLY', t.math('MULTIPLY', escale, f_scale), w), 1.0), sc.inputs["Scale"])
    t.link(sc.outputs[0], rout.inputs["Geometry"])

    t.finish(rout.outputs["Geometry"])
    return ng


# ---------------------------------------------------------------------------
# Modifier input access
# ---------------------------------------------------------------------------

def _socket_id(ng, name):
    for item in ng.interface.items_tree:
        if getattr(item, "in_out", None) == 'INPUT' and item.name == name:
            return item.identifier
    return None


def _input_slot(mod, name):
    """Blender 5.2 stores node-modifier inputs as mod.properties.inputs.<Socket_N>.value."""
    key = _socket_id(mod.node_group, name)
    if key is None:
        return None
    return getattr(mod.properties.inputs, key, None)


def get_input(mod, name, default=None):
    slot = _input_slot(mod, name)
    return getattr(slot, "value", default) if slot is not None else default


def set_input(mod, name, value):
    slot = _input_slot(mod, name)
    if slot is not None:
        try:
            slot.value = value
        except (TypeError, AttributeError):
            pass


def _nodes_modifier(ob, group):
    for m in getattr(ob, "modifiers", ()):
        if m.type == 'NODES' and m.node_group and m.node_group.name.startswith(group):
            return m
    return None


def cloner_modifier(ob):
    return _nodes_modifier(ob, GROUP)


def effector_modifier(ob):
    return _nodes_modifier(ob, EFFECTOR_GROUP)


def effector_kind(ob):
    """'Plain' / 'Random' / 'Step' for effector objects, else None."""
    m = effector_modifier(ob)
    if m is None:
        return None
    kind = get_input(m, "Kind", "Plain")
    return kind if kind in EFFECTOR_KINDS else "Plain"


def _effectors_collection(context, cloner, mod, create=False):
    coll = get_input(mod, "Effectors")
    if coll is None and create:
        coll = bpy.data.collections.new(cloner.name + " Effectors")
        context.scene.collection.children.link(coll)
        set_input(mod, "Effectors", coll)
    return coll


def link_effector(context, cloner, eff):
    """Add `eff` to the cloner's effector list. False for old (pre-effector) cloners."""
    mod = cloner_modifier(cloner)
    if mod is None or _socket_id(mod.node_group, "Effectors") is None:
        return False
    coll = _effectors_collection(context, cloner, mod, create=True)
    if eff.name not in coll.objects:
        coll.objects.link(eff)
        # Keep the Object Manager tidy: an effector dropped loose in the scene
        # root moves into the cloner's list rather than showing twice.
        root = context.scene.collection
        if eff.name in root.objects:
            root.objects.unlink(eff)
    cloner.update_tag()
    return True


def unlink_effector(context, cloner, eff):
    mod = cloner_modifier(cloner)
    coll = _effectors_collection(context, cloner, mod) if mod else None
    if coll is not None and eff.name in coll.objects:
        coll.objects.unlink(eff)
    if not eff.users_collection:
        context.scene.collection.objects.link(eff)
    cloner.update_tag()


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

_CLONEABLE = {'MESH', 'CURVE', 'FONT', 'EMPTY', 'SURFACE', 'META'}


class C4D_OT_add_cloner(bpy.types.Operator):
    """Create a Cloner and move the selected objects in as its children (C4D MoGraph > Cloner)"""
    bl_idname = "c4d.add_cloner"
    bl_label = "Cloner"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(items=[(m, m, "") for m in MODES], default='Linear')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        sources = [o for o in context.selected_objects
                   if o.type in _CLONEABLE and effector_modifier(o) is None]
        target = None
        if self.mode == 'Object':
            # Active object = the one to clone onto; the rest are the clones.
            active = context.active_object
            if active in sources:
                target = active
                sources = [o for o in sources if o is not active]
        if not sources:
            bpy.ops.mesh.primitive_cube_add(size=0.5)
            sources = [context.active_object]

        ng = build_group()
        me = bpy.data.meshes.new("Cloner")
        cloner = bpy.data.objects.new("Cloner", me)
        context.collection.objects.link(cloner)
        cloner.location = (0.0, 0.0, 0.0) if target is not None else context.scene.cursor.location

        # Children collection (instanced by the node tree).
        coll = bpy.data.collections.new("Cloner Children")
        context.scene.collection.children.link(coll)
        context.view_layer.update()
        for o in sources:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            coll.objects.link(o)
            mw = o.matrix_world.copy()
            o.parent = cloner
            o.matrix_world = mw
            o.hide_set(True)      # templates hidden, like C4D children of a cloner
            o.hide_render = True

        mod = cloner.modifiers.new("Cloner", 'NODES')
        mod.node_group = ng
        set_input(mod, "Children", coll)
        set_input(mod, "Mode", self.mode)
        if target is not None:
            set_input(mod, "Object", target)
            set_input(mod, "Distribution", "Vertex")

        for o in context.selected_objects:
            o.select_set(False)
        cloner.select_set(True)
        context.view_layer.objects.active = cloner
        return {'FINISHED'}


# C4D defaults per effector kind (Blender is Z-up: C4D P.Y 100 cm = Z 1 m).
_EFFECTOR_DEFAULTS = {
    "Plain": {"Position": (0.0, 0.0, 1.0)},
    "Random": {"Position": (0.5, 0.5, 0.5), "Seed": 12345},
    "Step": {"Scale": 1.0},
}


def new_effector(context, kind, location=None):
    me = bpy.data.meshes.new(kind)
    eff = bpy.data.objects.new(kind, me)
    context.collection.objects.link(eff)
    eff.location = context.scene.cursor.location if location is None else location
    eff.display_type = 'WIRE'
    mod = eff.modifiers.new("Effector", 'NODES')
    mod.node_group = build_effector_group()
    set_input(mod, "Kind", kind)
    for k, v in _EFFECTOR_DEFAULTS[kind].items():
        set_input(mod, k, v)
    return eff


def _selected_cloners(context):
    return [o for o in context.selected_objects if cloner_modifier(o) is not None]


class C4D_OT_add_effector(bpy.types.Operator):
    """Add an effector and link it to the selected Cloners (C4D MoGraph > Effector)"""
    bl_idname = "c4d.add_effector"
    bl_label = "Effector"
    bl_options = {'REGISTER', 'UNDO'}

    kind: bpy.props.EnumProperty(items=[(k, k, "") for k in EFFECTOR_KINDS], default='Plain')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        cloners = _selected_cloners(context)
        eff = new_effector(context, self.kind)
        linked = 0
        for c in cloners:
            if link_effector(context, c, eff):
                linked += 1
            else:
                self.report({'WARNING'}, f"{c.name}: old cloner, recreate it to use effectors")
        for o in context.selected_objects:
            o.select_set(False)
        eff.select_set(True)
        context.view_layer.objects.active = eff
        if not cloners:
            self.report({'INFO'}, "Select a Cloner first to link the effector, or link it from the Cloner's Effectors list")
        return {'FINISHED'}


class C4D_OT_cloner_effector(bpy.types.Operator):
    """Link the selected effectors to this Cloner, or unlink one"""
    bl_idname = "c4d.cloner_effector"
    bl_label = "Cloner Effector"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    action: bpy.props.EnumProperty(items=[('LINK', "Link Selected", ""), ('UNLINK', "Unlink", "")])
    cloner: bpy.props.StringProperty()
    effector: bpy.props.StringProperty()

    def execute(self, context):
        cloner = bpy.data.objects.get(self.cloner)
        if cloner is None or cloner_modifier(cloner) is None:
            return {'CANCELLED'}
        if self.action == 'UNLINK':
            eff = bpy.data.objects.get(self.effector)
            if eff is not None:
                unlink_effector(context, cloner, eff)
            return {'FINISHED'}
        effs = [o for o in context.selected_objects if effector_modifier(o) is not None]
        if not effs:
            self.report({'INFO'}, "Select one or more effectors first")
            return {'CANCELLED'}
        for eff in effs:
            if not link_effector(context, cloner, eff):
                self.report({'WARNING'}, f"{cloner.name}: old cloner, recreate it to use effectors")
                return {'CANCELLED'}
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Attribute Manager
# ---------------------------------------------------------------------------

def _draw_inputs(layout, m, names):
    for name in names:
        slot = _input_slot(m, name)
        if slot is not None:
            layout.prop(slot, "value", text=name)


def _input_names(ng):
    return [item.name for item in ng.interface.items_tree
            if getattr(item, "in_out", None) == 'INPUT' and item.socket_type != 'NodeSocketGeometry']


def draw_cloner(layout, m):
    mode = get_input(m, "Mode", "Linear")
    dist = get_input(m, "Distribution", "Vertex")
    hidden = {n for n, modes in MODE_ONLY.items() if mode not in modes}
    if mode == "Object":
        if dist not in {"Surface", "Spline"}:
            hidden.add("Count")
        if dist != "Surface":
            hidden.add("Seed")
    names = [n for n in _input_names(m.node_group) if n not in hidden and n not in {"Children", "Effectors"}]
    _draw_inputs(layout, m, names)

    if _socket_id(m.node_group, "Effectors") is None:
        layout.label(text="Old cloner: recreate it to use effectors", icon='INFO')
        return
    layout.separator()
    layout.label(text="Effectors")
    box = layout.box()
    coll = get_input(m, "Effectors")
    effs = list(coll.objects) if coll is not None else []
    for eff in effs:
        kind = effector_kind(eff) or "Plain"
        row = box.row(align=True)
        row.label(text=eff.name, icon=EFFECTOR_ICONS[kind])
        em = effector_modifier(eff)
        slot = _input_slot(em, "Strength") if em else None
        if slot is not None:
            row.prop(slot, "value", text="Strength")
        op = row.operator("c4d.cloner_effector", text="", icon='X', emboss=False)
        op.action, op.cloner, op.effector = 'UNLINK', m.id_data.name, eff.name
    if not effs:
        box.label(text="None. Add one below, or select effectors and link them.")
    row = layout.row(align=True)
    for kind in EFFECTOR_KINDS:
        row.operator("c4d.add_effector", text=kind, icon=EFFECTOR_ICONS[kind]).kind = kind
    op = layout.operator("c4d.cloner_effector", text="Link Selected Effectors", icon='LINKED')
    op.action, op.cloner = 'LINK', m.id_data.name


def draw_effector(layout, m):
    kind = get_input(m, "Kind", "Plain")
    layout.label(text=f"{kind} Effector", icon=EFFECTOR_ICONS.get(kind, 'SPHERE'))
    _draw_inputs(layout, m, ["Strength"])
    layout.separator()
    layout.label(text="Parameter")
    names = ["Position", "Rotation", "Scale"] + (["Seed"] if kind == "Random" else [])
    _draw_inputs(layout, m, names)
    layout.separator()
    layout.label(text="Falloff")
    falloff = get_input(m, "Falloff", "Infinite")
    _draw_inputs(layout, m, ["Falloff"] + (["Radius", "Inner Offset"] if falloff != "Infinite" else []))
    ob = m.id_data
    users = []
    for o in bpy.data.objects:
        cm = cloner_modifier(o)
        coll = get_input(cm, "Effectors") if cm is not None else None
        if coll is not None and ob.name in coll.objects:
            users.append(o.name)
    layout.separator()
    layout.label(text="Used by: " + (", ".join(users) if users else "no Cloner (select a Cloner, then Link Selected Effectors)"),
                 icon='MOD_ARRAY')


def draw_nodes_modifier(layout, m):
    """Draw a Geometry Nodes modifier's inputs (Cloner, effector, generators...) in the Attribute Manager."""
    ng = m.node_group
    if ng is None:
        layout.prop(m, "node_group")
        return
    if ng.name.startswith(GROUP):
        draw_cloner(layout, m)
        return
    if ng.name.startswith(EFFECTOR_GROUP):
        draw_effector(layout, m)
        return
    from .generators import is_generator_group, draw_generator
    if is_generator_group(ng):
        draw_generator(layout, m)
        return
    _draw_inputs(layout, m, _input_names(ng))


classes = (C4D_OT_add_cloner, C4D_OT_add_effector, C4D_OT_cloner_effector)
