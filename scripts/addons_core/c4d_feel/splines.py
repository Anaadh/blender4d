"""C4D spline primitives and spline generators (Extrude, Lathe, Sweep, Loft).

Spline primitives are parametric (Geometry Nodes that output a curve) and
become a normal Blender curve on Make Editable (C).

Generators work like C4D: the source splines become children of the
generator in the Object Manager, and the generator's node tree reads them
through Object Info / Collection Info. Editing a child spline updates the
generator live.
Orientation (Blender is Z-up): splines lie in the XY plane and Extrude goes
up Z; Lathe profiles are drawn in the XZ plane and spin around Z.
"""

import math

import bpy

PREFIX = "C4D "
VERSION = {"Extrude": 2, "Sweep": 3}  # bump when a node tree changes

SPLINE_SPECS = {
    "Circle": [("Radius", 'NodeSocketFloat', 1.0, 0.0, 'DISTANCE'),
               ("Points", 'NodeSocketInt', 32, 3, None)],
    "Rectangle": [("Width", 'NodeSocketFloat', 2.0, 0.0, 'DISTANCE'),
                  ("Height", 'NodeSocketFloat', 2.0, 0.0, 'DISTANCE')],
    "Star": [("Inner Radius", 'NodeSocketFloat', 0.5, 0.0, 'DISTANCE'),
             ("Outer Radius", 'NodeSocketFloat', 1.0, 0.0, 'DISTANCE'),
             ("Points", 'NodeSocketInt', 8, 3, None),
             ("Twist", 'NodeSocketFloat', 0.0, None, 'ANGLE')],
    "Arc": [("Radius", 'NodeSocketFloat', 1.0, 0.0, 'DISTANCE'),
            ("Start Angle", 'NodeSocketFloat', 0.0, None, 'ANGLE'),
            ("End Angle", 'NodeSocketFloat', math.radians(90), None, 'ANGLE'),
            ("Points", 'NodeSocketInt', 16, 2, None)],
    "Text": [("Text", 'NodeSocketString', "Text", None, None),
             ("Height", 'NodeSocketFloat', 1.0, 0.0, 'DISTANCE'),
             ("Spacing", 'NodeSocketFloat', 1.0, 0.0, None)],
    "Helix": [("Start Radius", 'NodeSocketFloat', 1.0, 0.0, 'DISTANCE'),
              ("End Radius", 'NodeSocketFloat', 1.0, 0.0, 'DISTANCE'),
              ("Turns", 'NodeSocketFloat', 2.0, 0.0, None),
              ("Height", 'NodeSocketFloat', 2.0, None, 'DISTANCE'),
              ("Points", 'NodeSocketInt', 32, 1, None)],
}

GEN_SPECS = {
    "Extrude": [("Spline", 'NodeSocketObject', None, None, None),
                ("Movement", 'NodeSocketVector', (0.0, 0.0, 0.2), None, 'TRANSLATION'),
                ("Caps", 'NodeSocketBool', True, None, None),
                ("Subdivision", 'NodeSocketInt', 1, 1, None)],
    "Lathe": [("Spline", 'NodeSocketObject', None, None, None),
              ("Angle", 'NodeSocketFloat', math.radians(360), None, 'ANGLE'),
              ("Subdivision", 'NodeSocketInt', 24, 3, None),
              ("Profile Points", 'NodeSocketInt', 24, 2, None)],
    "Sweep": [("Profile", 'NodeSocketObject', None, None, None),
              ("Path", 'NodeSocketObject', None, None, None),
              ("Caps", 'NodeSocketBool', True, None, None),
              ("Start Scale", 'NodeSocketFloat', 1.0, 0.0, 'FACTOR'),
              ("End Scale", 'NodeSocketFloat', 1.0, 0.0, 'FACTOR'),
              ("Rotation", 'NodeSocketFloat', 0.0, None, 'ANGLE')],
    "Loft": [("Splines", 'NodeSocketCollection', None, None, None),
             ("Mesh Subdivision U", 'NodeSocketInt', 32, 2, None)],
}

SPLINE_ICONS = {"Text": 'OUTLINER_OB_FONT', "Circle": 'MESH_CIRCLE', "Rectangle": 'MESH_PLANE', "Star": 'SOLO_OFF',
                "Arc": 'SPHERECURVE', "Helix": 'FORCE_VORTEX'}
GEN_ICONS = {"Extrude": 'MOD_SOLIDIFY', "Lathe": 'MOD_SCREW', "Sweep": 'CURVE_PATH', "Loft": 'MOD_SKIN'}


class _B:
    def __init__(self, ng, specs):
        self.ng, self.N, self.L = ng, ng.nodes, ng.links
        it = ng.interface
        it.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
        it.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
        for name, stype, default, min_value, subtype in specs:
            s = it.new_socket(name=name, in_out='INPUT', socket_type=stype)
            if subtype and hasattr(s, "subtype"):
                s.subtype = subtype
            if default is not None:
                s.default_value = default
            if min_value is not None and hasattr(s, "min_value"):
                s.min_value = min_value
        self.gin = self.N.new('NodeGroupInput')
        self.gin.location = (-1000, 0)
        self.x = -700

    def node(self, kind, **props):
        n = self.N.new(kind)
        n.location = (self.x, 0)
        self.x += 180
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def i(self, name):
        return self.gin.outputs[name]

    def link(self, a, b):
        self.L.new(a, b)

    def math(self, op, a, b=None, **kw):
        n = self.node('ShaderNodeMath', operation=op, **kw)
        for idx, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[idx].default_value = v
            else:
                self.link(v, n.inputs[idx])
        return n.outputs[0]

    def finish(self, geo):
        out = self.node('NodeGroupOutput')
        self.link(geo, out.inputs[0])


def _grid_uv(b, verts_x, verts_y):
    """Unit grid; returns (grid geometry, u field, v field) with u, v in [0, 1]."""
    grid = b.node('GeometryNodeMeshGrid')
    grid.inputs["Size X"].default_value = 1.0
    grid.inputs["Size Y"].default_value = 1.0
    b.link(verts_x, grid.inputs["Vertices X"])
    b.link(verts_y, grid.inputs["Vertices Y"])
    pos = b.node('GeometryNodeInputPosition')
    sep = b.node('ShaderNodeSeparateXYZ')
    b.link(pos.outputs[0], sep.inputs[0])
    u = b.math('ADD', sep.outputs["X"], 0.5)
    v = b.math('ADD', sep.outputs["Y"], 0.5)
    return grid.outputs["Mesh"], u, v


def _object_curve(b, sock):
    info = b.node('GeometryNodeObjectInfo', transform_space='RELATIVE')
    b.link(b.i(sock), info.inputs["Object"])
    return info.outputs["Geometry"]


def _build_spline(name, b):
    if name == "Circle":
        n = b.node('GeometryNodeCurvePrimitiveCircle')
        b.link(b.i("Radius"), n.inputs["Radius"])
        b.link(b.i("Points"), n.inputs["Resolution"])
        return n.outputs["Curve"]
    if name == "Rectangle":
        n = b.node('GeometryNodeCurvePrimitiveQuadrilateral')
        b.link(b.i("Width"), n.inputs["Width"])
        b.link(b.i("Height"), n.inputs["Height"])
        return n.outputs["Curve"]
    if name == "Star":
        n = b.node('GeometryNodeCurveStar')
        for s in ("Inner Radius", "Outer Radius", "Points", "Twist"):
            b.link(b.i(s), n.inputs[s])
        return n.outputs["Curve"]
    if name == "Arc":
        n = b.node('GeometryNodeCurveArc')
        b.link(b.i("Radius"), n.inputs["Radius"])
        b.link(b.i("Points"), n.inputs["Resolution"])
        b.link(b.i("Start Angle"), n.inputs["Start Angle"])
        b.link(b.math('SUBTRACT', b.i("End Angle"), b.i("Start Angle")), n.inputs["Sweep Angle"])
        return n.outputs["Curve"]
    if name == "Text":
        n = b.node('GeometryNodeStringToCurves')
        b.link(b.i("Text"), n.inputs["String"])
        b.link(b.i("Height"), n.inputs["Size"])
        b.link(b.i("Spacing"), n.inputs["Character Spacing"])
        real = b.node('GeometryNodeRealizeInstances')
        b.link(n.outputs["Curve Instances"], real.inputs[0])
        return real.outputs[0]
    if name == "Helix":
        n = b.node('GeometryNodeCurveSpiral')
        b.link(b.i("Start Radius"), n.inputs["Start Radius"])
        b.link(b.i("End Radius"), n.inputs["End Radius"])
        b.link(b.i("Turns"), n.inputs["Rotations"])
        b.link(b.i("Height"), n.inputs["Height"])
        b.link(b.i("Points"), n.inputs["Resolution"])
        return n.outputs["Curve"]
    raise KeyError(name)


def _build_generator(name, b):
    if name == "Extrude":
        curve = _object_curve(b, "Spline")
        edges = b.node('GeometryNodeCurveToMesh')
        b.link(curve, edges.inputs["Curve"])
        step = b.node('ShaderNodeVectorMath', operation='DIVIDE')
        b.link(b.i("Movement"), step.inputs[0])
        b.link(b.i("Subdivision"), step.inputs[1])

        # Extrude the top edges once per subdivision step.
        rin = b.node('GeometryNodeRepeatInput')
        rout = b.node('GeometryNodeRepeatOutput')
        rin.pair_with_output(rout)
        b.link(b.i("Subdivision"), rin.inputs["Iterations"])
        mark = b.node('GeometryNodeStoreNamedAttribute', data_type='BOOLEAN', domain='EDGE')
        mark.inputs["Name"].default_value = "c4d_top"
        mark.inputs["Value"].default_value = True
        b.link(edges.outputs["Mesh"], mark.inputs["Geometry"])
        b.link(mark.outputs[0], rin.inputs["Geometry"])
        top = b.node('GeometryNodeInputNamedAttribute', data_type='BOOLEAN')
        top.inputs["Name"].default_value = "c4d_top"
        ext = b.node('GeometryNodeExtrudeMesh', mode='EDGES')
        b.link(rin.outputs["Geometry"], ext.inputs["Mesh"])
        b.link(top.outputs[0], ext.inputs["Selection"])
        b.link(step.outputs[0], ext.inputs["Offset"])
        remark = b.node('GeometryNodeStoreNamedAttribute', data_type='BOOLEAN', domain='EDGE')
        remark.inputs["Name"].default_value = "c4d_top"
        b.link(ext.outputs["Mesh"], remark.inputs["Geometry"])
        b.link(ext.outputs["Top"], remark.inputs["Value"])
        b.link(remark.outputs[0], rout.inputs["Geometry"])
        sides = rout.outputs["Geometry"]

        fill = b.node('GeometryNodeFillCurve')
        b.link(curve, fill.inputs["Curve"])
        cap_top = b.node('GeometryNodeTransform')
        b.link(fill.outputs["Mesh"], cap_top.inputs["Geometry"])
        b.link(b.i("Movement"), cap_top.inputs["Translation"])
        flip = b.node('GeometryNodeFlipFaces')
        b.link(fill.outputs["Mesh"], flip.inputs["Mesh"])
        caps = b.node('GeometryNodeJoinGeometry')
        b.link(cap_top.outputs["Geometry"], caps.inputs[0])
        b.link(flip.outputs["Mesh"], caps.inputs[0])
        sw = b.node('GeometryNodeSwitch', input_type='GEOMETRY')
        b.link(b.i("Caps"), sw.inputs["Switch"])
        b.link(caps.outputs[0], sw.inputs["True"])
        join = b.node('GeometryNodeJoinGeometry')
        b.link(sides, join.inputs[0])
        b.link(sw.outputs[0], join.inputs[0])
        merge = b.node('GeometryNodeMergeByDistance')
        b.link(join.outputs[0], merge.inputs["Geometry"])

        # Cap rims get bevel weight 1 so the "Cap Fillet" bevel rounds only them.
        # d = position . direction; rim edge = both ends at the lowest or highest d.
        norm = b.node('ShaderNodeVectorMath', operation='NORMALIZE')
        b.link(b.i("Movement"), norm.inputs[0])
        ev = b.node('GeometryNodeInputMeshEdgeVertices')

        def dot(pos_sock):
            d = b.node('ShaderNodeVectorMath', operation='DOT_PRODUCT')
            b.link(pos_sock, d.inputs[0])
            b.link(norm.outputs[0], d.inputs[1])
            return d.outputs["Value"]
        d1, d2 = dot(ev.outputs["Position 1"]), dot(ev.outputs["Position 2"])
        ppos = b.node('GeometryNodeInputPosition')
        stat = b.node('GeometryNodeAttributeStatistic', data_type='FLOAT', domain='POINT')
        b.link(merge.outputs["Geometry"], stat.inputs["Geometry"])
        b.link(dot(ppos.outputs[0]), stat.inputs["Attribute"])

        def near(a, target):
            c = b.node('FunctionNodeCompare', data_type='FLOAT', operation='EQUAL')
            c.inputs["Epsilon"].default_value = 1e-4
            b.link(a, c.inputs["A"])
            b.link(target, c.inputs["B"])
            return c.outputs["Result"]

        def both(x, y):
            n = b.node('FunctionNodeBooleanMath', operation='AND')
            b.link(x, n.inputs[0])
            b.link(y, n.inputs[1])
            return n.outputs[0]
        lo = both(near(d1, stat.outputs["Min"]), near(d2, stat.outputs["Min"]))
        hi = both(near(d1, stat.outputs["Max"]), near(d2, stat.outputs["Max"]))
        rim = b.node('FunctionNodeBooleanMath', operation='OR')
        b.link(lo, rim.inputs[0])
        b.link(hi, rim.inputs[1])
        bw = b.node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='EDGE')
        bw.inputs["Name"].default_value = "bevel_weight_edge"
        b.link(merge.outputs["Geometry"], bw.inputs["Geometry"])
        b.link(rim.outputs[0], bw.inputs["Value"])
        clean = b.node('GeometryNodeRemoveAttribute')
        clean.inputs["Name"].default_value = "c4d_top"
        b.link(bw.outputs[0], clean.inputs["Geometry"])
        return clean.outputs["Geometry"]

    if name == "Lathe":
        curve = _object_curve(b, "Spline")
        cols = b.math('ADD', b.i("Subdivision"), 1.0)
        grid, u, v = _grid_uv(b, cols, b.i("Profile Points"))
        sample = b.node('GeometryNodeSampleCurve', mode='FACTOR')
        b.link(curve, sample.inputs["Curves"])
        b.link(v, sample.inputs["Factor"])
        rot = b.node('ShaderNodeVectorRotate', rotation_type='Z_AXIS')
        b.link(sample.outputs["Position"], rot.inputs["Vector"])
        b.link(b.math('MULTIPLY', u, b.i("Angle")), rot.inputs["Angle"])
        setp = b.node('GeometryNodeSetPosition')
        b.link(grid, setp.inputs["Geometry"])
        b.link(rot.outputs[0], setp.inputs["Position"])
        merge = b.node('GeometryNodeMergeByDistance')
        b.link(setp.outputs[0], merge.inputs["Geometry"])
        return merge.outputs["Geometry"]

    if name == "Sweep":
        param = b.node('GeometryNodeSplineParameter')
        radius = b.node('ShaderNodeMix', data_type='FLOAT')
        b.link(param.outputs["Factor"], radius.inputs["Factor"])
        b.link(b.i("Start Scale"), radius.inputs["A"])
        b.link(b.i("End Scale"), radius.inputs["B"])
        set_r = b.node('GeometryNodeSetCurveRadius')
        b.link(_object_curve(b, "Path"), set_r.inputs["Curve"])
        b.link(radius.outputs["Result"], set_r.inputs["Radius"])
        set_t = b.node('GeometryNodeSetCurveTilt')
        b.link(set_r.outputs[0], set_t.inputs["Curve"])
        b.link(b.math('MULTIPLY', param.outputs["Factor"], b.i("Rotation")), set_t.inputs["Tilt"])
        c2m = b.node('GeometryNodeCurveToMesh')
        b.link(set_t.outputs[0], c2m.inputs["Curve"])
        b.link(radius.outputs["Result"], c2m.inputs["Scale"])  # 5.x: scale is an input
        b.link(_object_curve(b, "Profile"), c2m.inputs["Profile Curve"])
        b.link(b.i("Caps"), c2m.inputs["Fill Caps"])
        return c2m.outputs["Mesh"]

    if name == "Loft":
        coll = b.node('GeometryNodeCollectionInfo', transform_space='RELATIVE')
        coll.inputs["Separate Children"].default_value = True
        coll.inputs["Reset Children"].default_value = False
        b.link(b.i("Splines"), coll.inputs["Collection"])
        real = b.node('GeometryNodeRealizeInstances')
        b.link(coll.outputs[0], real.inputs[0])
        size = b.node('GeometryNodeAttributeDomainSize', component='CURVE')
        b.link(real.outputs[0], size.inputs[0])
        count = size.outputs["Spline Count"]
        grid, u, v = _grid_uv(b, b.i("Mesh Subdivision U"), count)
        last = b.math('SUBTRACT', count, 1.0)
        k = b.math('ROUND', b.math('MULTIPLY', v, last))
        sample = b.node('GeometryNodeSampleCurve', mode='FACTOR', use_all_curves=False)
        b.link(real.outputs[0], sample.inputs["Curves"])
        b.link(u, sample.inputs["Factor"])
        b.link(k, sample.inputs["Curve Index"])
        setp = b.node('GeometryNodeSetPosition')
        b.link(grid, setp.inputs["Geometry"])
        b.link(sample.outputs["Position"], setp.inputs["Position"])
        merge = b.node('GeometryNodeMergeByDistance')
        b.link(setp.outputs[0], merge.inputs["Geometry"])
        return merge.outputs["Geometry"]
    raise KeyError(name)


def build_group(name):
    gname = PREFIX + name
    want = VERSION.get(name, 1)
    old = bpy.data.node_groups.get(gname)
    if old is not None and old.get("c4d_version", 1) >= want:
        return old
    if old is not None:
        old.name = gname + " (old)"
    ng = bpy.data.node_groups.new(gname, 'GeometryNodeTree')
    ng["c4d_version"] = want
    if name in SPLINE_SPECS:
        b = _B(ng, SPLINE_SPECS[name])
        b.finish(_build_spline(name, b))
    else:
        b = _B(ng, GEN_SPECS[name])
        geo = _build_generator(name, b)
        smooth = b.node('GeometryNodeSetShadeSmooth', domain='FACE')
        smooth.inputs["Shade Smooth"].default_value = name != "Extrude"
        b.link(geo, smooth.inputs["Geometry"])
        b.finish(smooth.outputs["Geometry"])
    if old is not None:
        # Existing objects switch to the new tree; new sockets are appended,
        # so their identifiers (and saved values) still match.
        old.user_remap(ng)
        bpy.data.node_groups.remove(old)
    return ng


def kind_of(ob):
    """('spline'|'generator', name) for C4D spline objects/generators, else None."""
    for m in getattr(ob, "modifiers", ()):
        if m.type == 'NODES' and m.node_group and m.node_group.name.startswith(PREFIX):
            n = m.node_group.name[len(PREFIX):]
            if n in SPLINE_SPECS:
                return 'spline', n
            if n in GEN_SPECS:
                return 'generator', n
    return None


# ---------------------------------------------------------------------------
# Object creation
# ---------------------------------------------------------------------------

def _new_node_object(context, name, group, location=None):
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    context.collection.objects.link(ob)
    ob.location = context.scene.cursor.location if location is None else location
    mod = ob.modifiers.new(name, 'NODES')
    mod.node_group = group
    return ob, mod


def _new_spline(context, kind, location=(0.0, 0.0, 0.0), **values):
    from .cloner import set_input
    ob, mod = _new_node_object(context, kind, build_group(kind), location)
    for k, v in values.items():
        set_input(mod, k, v)
    return ob


def _default_profile(context):
    """A lathe profile in the XZ plane (like a vase)."""
    cu = bpy.data.curves.new("Profile", 'CURVE')
    cu.dimensions = '3D'
    sp = cu.splines.new('BEZIER')
    pts = [(0.4, 0.0, 0.0), (0.9, 0.0, 0.6), (0.5, 0.0, 1.4), (0.7, 0.0, 2.0)]
    sp.bezier_points.add(len(pts) - 1)
    for bp, co in zip(sp.bezier_points, pts):
        bp.co = co
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
    ob = bpy.data.objects.new("Spline", cu)
    context.collection.objects.link(ob)
    return ob


def _is_spline(o):
    return o.type == 'CURVE' or (kind_of(o) or ("", ""))[0] == 'spline'


class C4D_OT_add_spline(bpy.types.Operator):
    """Add a parametric spline"""
    bl_idname = "c4d.add_spline"
    bl_label = "Add Spline"
    bl_options = {'REGISTER', 'UNDO'}

    kind: bpy.props.EnumProperty(items=[(k, k, "") for k in SPLINE_SPECS])

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        ob = _new_spline(context, self.kind, context.scene.cursor.location.copy())
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        return {'FINISHED'}


class C4D_OT_add_spline_generator(bpy.types.Operator):
    """Add a generator; selected splines become its children (C4D Extrude/Lathe/Sweep/Loft)"""
    bl_idname = "c4d.add_spline_generator"
    bl_label = "Add Spline Generator"
    bl_options = {'REGISTER', 'UNDO'}

    kind: bpy.props.EnumProperty(items=[(k, k, "") for k in GEN_SPECS])

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        from .cloner import set_input
        splines = [o for o in context.selected_objects if _is_spline(o)]
        active = context.active_object if context.active_object in splines else None
        gen, mod = _new_node_object(context, self.kind, build_group(self.kind), (0.0, 0.0, 0.0))

        if self.kind in {"Extrude", "Lathe"}:
            src = active or (splines[0] if splines else None)
            if src is None:
                src = (_new_spline(context, "Rectangle") if self.kind == "Extrude"
                       else _default_profile(context))
            children = [src]
            set_input(mod, "Spline", src)
        elif self.kind == "Sweep":
            if len(splines) >= 2:
                # C4D: first child = profile, second = path. The smaller one is the profile.
                a, b = sorted(splines[:2], key=lambda o: max(o.dimensions))
                profile, path = a, b
            else:
                path = splines[0] if splines else _new_spline(context, "Helix")
                profile = _new_spline(context, "Circle", Radius=0.1)
            children = [profile, path]
            set_input(mod, "Profile", profile)
            set_input(mod, "Path", path)
        else:  # Loft
            if len(splines) < 2:
                splines = [_new_spline(context, "Circle", (0.0, 0.0, z), Radius=r)
                           for z, r in ((0.0, 1.0), (1.0, 0.5), (2.0, 0.9))]
            coll = bpy.data.collections.new("Loft Splines")
            context.scene.collection.children.link(coll)
            for i, o in enumerate(splines):
                o.name = f"Loft {i:02d} {o.name}"  # collection order = name order
                for c in list(o.users_collection):
                    c.objects.unlink(o)
                coll.objects.link(o)
            children = splines
            set_input(mod, "Splines", coll)

        if self.kind == "Extrude":
            # C4D Cap Fillet: bevel limited to the cap-rim edges the tree weights.
            bev = gen.modifiers.new("Cap Fillet", 'BEVEL')
            bev.limit_method = 'WEIGHT'
            bev.width = 0.03
            bev.segments = 4
            bev.harden_normals = False
            bev.show_viewport = bev.show_render = False

        context.view_layer.update()  # new objects' matrix_world is stale until updated
        for c in children:
            mw = c.matrix_world.copy()
            c.parent = gen
            c.matrix_world = mw
        for o in context.selected_objects:
            o.select_set(False)
        gen.select_set(True)
        context.view_layer.objects.active = gen
        return {'FINISHED'}


class C4D_MT_splines(bpy.types.Menu):
    bl_idname = "C4D_MT_splines"
    bl_label = "Spline"

    def draw(self, context):
        l = self.layout
        l.operator("c4d.tool_set", text="Spline Pen (Draw)", icon='GREASEPENCIL').name = "builtin.draw"
        l.separator()
        for k in SPLINE_SPECS:
            l.operator("c4d.add_spline", text=k, icon=SPLINE_ICONS[k]).kind = k
        l.separator()
        l.menu("VIEW3D_MT_curve_add", text="Blender Curves", icon='BLENDER')


class C4D_MT_spline_generators(bpy.types.Menu):
    bl_idname = "C4D_MT_spline_generators"
    bl_label = "Spline Generators"

    def draw(self, context):
        l = self.layout
        for k in GEN_SPECS:
            l.operator("c4d.add_spline_generator", text=k, icon=GEN_ICONS[k]).kind = k


classes = (C4D_OT_add_spline, C4D_OT_add_spline_generator, C4D_MT_splines, C4D_MT_spline_generators)
