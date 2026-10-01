"""Parametric primitives (C4D Cube, Sphere, Cylinder, ...) on Geometry Nodes.

Each primitive is an object whose geometry comes from a "C4D <Name>" node
group, so its parameters stay editable in the Attribute Manager until the
object is made editable (C), exactly like C4D. Defaults match C4D sizes
(200 cm cube, 100 cm sphere radius, ...). All primitives get a "UVMap" and
C4D-style Phong shading (smooth, with sharp edges above ~40 degrees).
"""

import math

import bpy

PREFIX = "C4D "
VERSION = {"Cylinder": 2}  # bump when a node tree changes
SMOOTH_ANGLE = math.radians(40.0)

# name -> list of (socket name, socket type, default, min, subtype)
SPECS = {
    "Cube": [
        ("Size", 'NodeSocketVector', (2.0, 2.0, 2.0), None, 'XYZ'),
        ("Segments X", 'NodeSocketInt', 1, 1, None),
        ("Segments Y", 'NodeSocketInt', 1, 1, None),
        ("Segments Z", 'NodeSocketInt', 1, 1, None),
    ],
    "Sphere": [
        ("Radius", 'NodeSocketFloat', 1.0, 0.0, 'DISTANCE'),
        ("Segments", 'NodeSocketInt', 24, 3, None),
    ],
    "Cylinder": [
        ("Radius", 'NodeSocketFloat', 0.5, 0.0, 'DISTANCE'),
        ("Height", 'NodeSocketFloat', 2.0, 0.0, 'DISTANCE'),
        ("Height Segments", 'NodeSocketInt', 4, 1, None),
        ("Rotation Segments", 'NodeSocketInt', 36, 3, None),
        ("Caps", 'NodeSocketBool', True, None, None),
    ],
    "Cone": [
        ("Top Radius", 'NodeSocketFloat', 0.0, 0.0, 'DISTANCE'),
        ("Bottom Radius", 'NodeSocketFloat', 1.0, 0.0, 'DISTANCE'),
        ("Height", 'NodeSocketFloat', 2.0, 0.0, 'DISTANCE'),
        ("Height Segments", 'NodeSocketInt', 8, 1, None),
        ("Rotation Segments", 'NodeSocketInt', 36, 3, None),
    ],
    "Plane": [
        ("Width", 'NodeSocketFloat', 4.0, 0.0, 'DISTANCE'),
        ("Height", 'NodeSocketFloat', 4.0, 0.0, 'DISTANCE'),
        ("Width Segments", 'NodeSocketInt', 20, 1, None),
        ("Height Segments", 'NodeSocketInt', 20, 1, None),
    ],
    "Torus": [
        ("Ring Radius", 'NodeSocketFloat', 2.0, 0.0, 'DISTANCE'),
        ("Ring Segments", 'NodeSocketInt', 36, 3, None),
        ("Pipe Radius", 'NodeSocketFloat', 0.5, 0.0, 'DISTANCE'),
        ("Pipe Segments", 'NodeSocketInt', 18, 3, None),
    ],
    "Pyramid": [
        ("Size", 'NodeSocketFloat', 2.0, 0.0, 'DISTANCE'),
        ("Height", 'NodeSocketFloat', 2.0, 0.0, 'DISTANCE'),
        ("Segments", 'NodeSocketInt', 1, 1, None),
    ],
}

ICONS = {
    "Cube": 'MESH_CUBE', "Sphere": 'MESH_UVSPHERE', "Cylinder": 'MESH_CYLINDER',
    "Cone": 'MESH_CONE', "Plane": 'MESH_PLANE', "Torus": 'MESH_TORUS', "Pyramid": 'MESH_CONE',
}
FLAT = {"Cube", "Plane", "Pyramid"}  # C4D gives these no smoothing


class _Builder:
    def __init__(self, ng):
        self.ng = ng
        self.N, self.L = ng.nodes, ng.links
        self.gin = self.N.new('NodeGroupInput')
        self.gin.location = (-900, 0)
        self.x = -600

    def node(self, kind, **props):
        n = self.N.new(kind)
        n.location = (self.x, 0)
        self.x += 200
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def inp(self, name):
        return self.gin.outputs[name]

    def link(self, a, b):
        self.L.new(a, b)

    def plus_one(self, sock):
        n = self.node('ShaderNodeMath', operation='ADD')
        n.inputs[1].default_value = 1.0
        self.link(sock, n.inputs[0])
        return n.outputs[0]

    def mul(self, sock, value):
        n = self.node('ShaderNodeMath', operation='MULTIPLY')
        n.inputs[1].default_value = value
        self.link(sock, n.inputs[0])
        return n.outputs[0]


def _body(name, b):
    """Return (geometry socket, uv socket or None)."""
    if name == "Cube":
        n = b.node('GeometryNodeMeshCube')
        b.link(b.inp("Size"), n.inputs["Size"])
        for axis in "XYZ":
            b.link(b.plus_one(b.inp(f"Segments {axis}")), n.inputs[f"Vertices {axis}"])
        return n.outputs["Mesh"], n.outputs["UV Map"]
    if name == "Sphere":
        n = b.node('GeometryNodeMeshUVSphere')
        b.link(b.inp("Radius"), n.inputs["Radius"])
        b.link(b.inp("Segments"), n.inputs["Segments"])
        b.link(b.mul(b.inp("Segments"), 0.5), n.inputs["Rings"])
        return n.outputs["Mesh"], n.outputs["UV Map"]
    if name == "Cylinder":
        # Caps on/off: fill type is a node setting, so switch between two cylinders.
        outs = []
        for fill in ('NGON', 'NONE'):
            n = b.node('GeometryNodeMeshCylinder', fill_type=fill)
            b.link(b.inp("Rotation Segments"), n.inputs["Vertices"])
            b.link(b.inp("Height Segments"), n.inputs["Side Segments"])
            b.link(b.inp("Height"), n.inputs["Depth"])
            b.link(b.inp("Radius"), n.inputs["Radius"])
            outs.append(n)
        geo = b.node('GeometryNodeSwitch', input_type='GEOMETRY')
        b.link(b.inp("Caps"), geo.inputs["Switch"])
        b.link(outs[0].outputs["Mesh"], geo.inputs["True"])
        b.link(outs[1].outputs["Mesh"], geo.inputs["False"])
        uv = b.node('GeometryNodeSwitch', input_type='VECTOR')
        b.link(b.inp("Caps"), uv.inputs["Switch"])
        b.link(outs[0].outputs["UV Map"], uv.inputs["True"])
        b.link(outs[1].outputs["UV Map"], uv.inputs["False"])
        return geo.outputs[0], uv.outputs[0]
    if name == "Cone":
        kind = 'GeometryNodeMeshCone'
        n = b.node(kind)
        b.link(b.inp("Rotation Segments"), n.inputs["Vertices"])
        b.link(b.inp("Height Segments"), n.inputs["Side Segments"])
        b.link(b.inp("Height"), n.inputs["Depth"])
        b.link(b.inp("Top Radius"), n.inputs["Radius Top"])
        b.link(b.inp("Bottom Radius"), n.inputs["Radius Bottom"])
        return n.outputs["Mesh"], n.outputs["UV Map"]
    if name == "Plane":
        n = b.node('GeometryNodeMeshGrid')
        b.link(b.inp("Width"), n.inputs["Size X"])
        b.link(b.inp("Height"), n.inputs["Size Y"])
        b.link(b.plus_one(b.inp("Width Segments")), n.inputs["Vertices X"])
        b.link(b.plus_one(b.inp("Height Segments")), n.inputs["Vertices Y"])
        return n.outputs["Mesh"], n.outputs["UV Map"]
    if name == "Torus":
        ring = b.node('GeometryNodeCurvePrimitiveCircle')
        b.link(b.inp("Ring Segments"), ring.inputs["Resolution"])
        b.link(b.inp("Ring Radius"), ring.inputs["Radius"])
        pipe = b.node('GeometryNodeCurvePrimitiveCircle')
        b.link(b.inp("Pipe Segments"), pipe.inputs["Resolution"])
        b.link(b.inp("Pipe Radius"), pipe.inputs["Radius"])
        c2m = b.node('GeometryNodeCurveToMesh')
        b.link(ring.outputs["Curve"], c2m.inputs["Curve"])
        b.link(pipe.outputs["Curve"], c2m.inputs["Profile Curve"])
        return c2m.outputs["Mesh"], None
    if name == "Pyramid":
        n = b.node('GeometryNodeMeshCone')
        n.inputs["Vertices"].default_value = 4
        n.inputs["Radius Top"].default_value = 0.0
        b.link(b.mul(b.inp("Size"), math.sqrt(0.5)), n.inputs["Radius Bottom"])
        b.link(b.inp("Height"), n.inputs["Depth"])
        b.link(b.inp("Segments"), n.inputs["Side Segments"])
        rot = b.node('GeometryNodeTransform')
        rot.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(45.0))
        b.link(n.outputs["Mesh"], rot.inputs["Geometry"])
        return rot.outputs["Geometry"], n.outputs["UV Map"]
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
    it = ng.interface
    it.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    it.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    for sname, stype, default, min_value, subtype in SPECS[name]:
        s = it.new_socket(name=sname, in_out='INPUT', socket_type=stype)
        if subtype and hasattr(s, "subtype"):
            s.subtype = subtype
        s.default_value = default
        if min_value is not None and hasattr(s, "min_value"):
            s.min_value = min_value

    b = _Builder(ng)
    geo, uv = _body(name, b)

    if uv is not None:
        store = b.node('GeometryNodeStoreNamedAttribute', data_type='FLOAT2', domain='CORNER')
        store.inputs["Name"].default_value = "UVMap"
        b.link(geo, store.inputs["Geometry"])
        b.link(uv, store.inputs["Value"])
        geo = store.outputs["Geometry"]

    # Phong: faces smooth, edges sharper than SMOOTH_ANGLE stay hard.
    if name not in FLAT:
        faces = b.node('GeometryNodeSetShadeSmooth', domain='FACE')
        faces.inputs["Shade Smooth"].default_value = True
        b.link(geo, faces.inputs["Geometry"])
        angle = b.node('GeometryNodeInputMeshEdgeAngle')
        cmp_ = b.node('FunctionNodeCompare', data_type='FLOAT', operation='LESS_THAN')
        cmp_.inputs["B"].default_value = SMOOTH_ANGLE
        b.link(angle.outputs["Unsigned Angle"], cmp_.inputs["A"])
        edges = b.node('GeometryNodeSetShadeSmooth', domain='EDGE')
        b.link(faces.outputs["Geometry"], edges.inputs["Geometry"])
        b.link(cmp_.outputs["Result"], edges.inputs["Shade Smooth"])
        geo = edges.outputs["Geometry"]

    out = b.node('NodeGroupOutput')
    b.link(geo, out.inputs[0])
    if old is not None:
        # Existing objects switch to the new tree (new sockets appended at the end).
        old.user_remap(ng)
        bpy.data.node_groups.remove(old)
    return ng


def primitive_name(ob):
    """'Cube', 'Sphere', ... if ob is a parametric primitive, else None."""
    for m in getattr(ob, "modifiers", ()):
        if m.type == 'NODES' and m.node_group and m.node_group.name.startswith(PREFIX):
            n = m.node_group.name[len(PREFIX):]
            if n in SPECS:
                return n
    return None


class C4D_OT_add_primitive(bpy.types.Operator):
    """Add a parametric primitive (editable parameters until Make Editable)"""
    bl_idname = "c4d.add_primitive"
    bl_label = "Add Primitive"
    bl_options = {'REGISTER', 'UNDO'}

    kind: bpy.props.EnumProperty(items=[(k, k, "") for k in SPECS])

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        ng = build_group(self.kind)
        me = bpy.data.meshes.new(self.kind)
        ob = bpy.data.objects.new(self.kind, me)
        context.collection.objects.link(ob)
        ob.location = context.scene.cursor.location
        mod = ob.modifiers.new(self.kind, 'NODES')
        mod.node_group = ng
        if self.kind == "Cube":
            # C4D Fillet: a bevel after the generator, off until enabled.
            bev = ob.modifiers.new("Fillet", 'BEVEL')
            bev.width = 0.05
            bev.segments = 5
            bev.limit_method = 'NONE'
            bev.show_viewport = bev.show_render = False
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        return {'FINISHED'}


class C4D_MT_primitives(bpy.types.Menu):
    bl_idname = "C4D_MT_primitives"
    bl_label = "Primitives"

    def draw(self, context):
        l = self.layout
        for k in SPECS:
            l.operator("c4d.add_primitive", text=k, icon=ICONS[k]).kind = k
        l.separator()
        l.menu("VIEW3D_MT_mesh_add", text="Blender Mesh Primitives", icon='BLENDER')


def draw_attributes(layout, ob):
    """Attribute Manager 'Object' tab for a parametric primitive."""
    from .cloner import draw_nodes_modifier
    for m in ob.modifiers:
        if m.type == 'NODES' and m.node_group and m.node_group.name.startswith(PREFIX):
            draw_nodes_modifier(layout, m)
        elif m.type == 'BEVEL' and "Fillet" in m.name:
            col = layout.column(align=True)
            col.use_property_split = False
            row = col.row(align=True)
            row.label(text=m.name)
            row.prop(m, "show_viewport", text="Editor", toggle=True)
            row.prop(m, "show_render", text="Render", toggle=True)
            sub = layout.column(align=True)
            sub.active = m.show_viewport or m.show_render
            sub.prop(m, "width", text="Fillet Radius")
            sub.prop(m, "segments", text="Fillet Subdivision")


classes = (C4D_OT_add_primitive, C4D_MT_primitives)
