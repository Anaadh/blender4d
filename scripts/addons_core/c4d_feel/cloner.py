"""MoGraph Cloner built on Geometry Nodes.

Create > MoGraph > Cloner puts the selected objects under a new "Cloner"
object. The children go into a collection that the cloner's node tree
instances, like C4D where a Cloner clones its children. Modes: Linear,
Radial, Grid. A built-in Random effector jitters position/rotation/scale.
"""

import math

import bpy

GROUP = "C4D Cloner"

# Inputs shown only in some modes (C4D hides the others).
MODE_ONLY = {
    "Count": ("Linear", "Radial"),
    "Offset": ("Linear",),
    "Radius": ("Radial",),
    "Grid Count X": ("Grid",),
    "Grid Count Y": ("Grid",),
    "Grid Count Z": ("Grid",),
    "Grid Size": ("Grid",),
}


def _socket(iface, name, stype, default=None, min_value=None, subtype=None):
    s = iface.new_socket(name=name, in_out='INPUT', socket_type=stype)
    if subtype is not None and hasattr(s, "subtype"):
        s.subtype = subtype
    if default is not None:
        s.default_value = default
    if min_value is not None and hasattr(s, "min_value"):
        s.min_value = min_value
    return s


def build_group():
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None:
        if any(getattr(i, "name", "") == "Effector" for i in ng.interface.items_tree):
            return ng
        ng.name = GROUP + " (old)"  # older file: keep existing cloners working
    ng = bpy.data.node_groups.new(GROUP, 'GeometryNodeTree')
    it = ng.interface
    it.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    it.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    _socket(it, "Children", 'NodeSocketCollection')
    _socket(it, "Mode", 'NodeSocketMenu')
    _socket(it, "Count", 'NodeSocketInt', 3, 1)
    _socket(it, "Offset", 'NodeSocketVector', (0.0, 0.0, 1.0), subtype='TRANSLATION')
    _socket(it, "Radius", 'NodeSocketFloat', 2.0, 0.0, subtype='DISTANCE')
    _socket(it, "Grid Count X", 'NodeSocketInt', 3, 1)
    _socket(it, "Grid Count Y", 'NodeSocketInt', 3, 1)
    _socket(it, "Grid Count Z", 'NodeSocketInt', 1, 1)
    _socket(it, "Grid Size", 'NodeSocketVector', (4.0, 4.0, 0.0), subtype='TRANSLATION')
    _socket(it, "Random Position", 'NodeSocketVector', (0.0, 0.0, 0.0), subtype='TRANSLATION')
    _socket(it, "Random Rotation", 'NodeSocketVector', (0.0, 0.0, 0.0), subtype='EULER')
    _socket(it, "Random Scale", 'NodeSocketFloat', 0.0, 0.0)
    _socket(it, "Seed", 'NodeSocketInt', 0)
    _socket(it, "Effector", 'NodeSocketObject')
    _socket(it, "Falloff Radius", 'NodeSocketFloat', 1.0, 0.0, subtype='DISTANCE')
    _socket(it, "Plain Position", 'NodeSocketVector', (0.0, 0.0, 0.0), subtype='TRANSLATION')
    _socket(it, "Plain Rotation", 'NodeSocketVector', (0.0, 0.0, 0.0), subtype='EULER')
    _socket(it, "Plain Scale", 'NodeSocketFloat', 0.0)

    N, L = ng.nodes, ng.links
    gin = N.new('NodeGroupInput')
    gout = N.new('NodeGroupOutput')
    gin.location, gout.location = (-1200, 0), (1400, 0)

    def new(kind, x, y, **props):
        n = N.new(kind)
        n.location = (x, y)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    # --- point distributions --------------------------------------------
    line = new('GeometryNodeMeshLine', -800, 300, mode='OFFSET')
    L.new(gin.outputs["Count"], line.inputs["Count"])
    L.new(gin.outputs["Offset"], line.inputs["Offset"])

    circle = new('GeometryNodeMeshCircle', -800, 100)
    L.new(gin.outputs["Count"], circle.inputs["Vertices"])
    L.new(gin.outputs["Radius"], circle.inputs["Radius"])

    sep = new('ShaderNodeSeparateXYZ', -1000, -300)
    L.new(gin.outputs["Grid Size"], sep.inputs[0])
    grid = new('GeometryNodeMeshGrid', -800, -150)
    L.new(sep.outputs["X"], grid.inputs["Size X"])
    L.new(sep.outputs["Y"], grid.inputs["Size Y"])
    L.new(gin.outputs["Grid Count X"], grid.inputs["Vertices X"])
    L.new(gin.outputs["Grid Count Y"], grid.inputs["Vertices Y"])
    half = new('ShaderNodeMath', -1000, -450, operation='MULTIPLY')
    half.inputs[1].default_value = 0.5
    L.new(sep.outputs["Z"], half.inputs[0])
    neg = new('ShaderNodeMath', -900, -550, operation='MULTIPLY')
    neg.inputs[1].default_value = -1.0
    L.new(half.outputs[0], neg.inputs[0])
    zlo = new('ShaderNodeCombineXYZ', -800, -450)
    zhi = new('ShaderNodeCombineXYZ', -800, -600)
    L.new(neg.outputs[0], zlo.inputs["Z"])
    L.new(half.outputs[0], zhi.inputs["Z"])
    zline = new('GeometryNodeMeshLine', -600, -450, mode='END_POINTS')
    L.new(gin.outputs["Grid Count Z"], zline.inputs["Count"])
    L.new(zlo.outputs[0], zline.inputs["Start Location"])
    L.new(zhi.outputs[0], zline.inputs["Offset"])
    stack = new('GeometryNodeInstanceOnPoints', -400, -300)
    L.new(zline.outputs[0], stack.inputs["Points"])
    L.new(grid.outputs[0], stack.inputs["Instance"])
    real = new('GeometryNodeRealizeInstances', -200, -300)
    L.new(stack.outputs[0], real.inputs[0])

    # --- mode switch -----------------------------------------------------
    def menu_switch(data_type, x, y):
        sw = new('GeometryNodeMenuSwitch', x, y)
        sw.data_type = data_type
        sw.enum_items.clear()
        for name in ("Linear", "Radial", "Grid"):
            sw.enum_items.new(name)
        L.new(gin.outputs["Mode"], sw.inputs["Menu"])
        return sw

    # Radial clones face outward, like C4D's aligned radial cloner. The
    # rotation is stored on the circle points so one menu switch suffices.
    pos = new('GeometryNodeInputPosition', -800, -50)
    align = new('FunctionNodeAlignRotationToVector', -600, -50, axis='X')
    L.new(pos.outputs[0], align.inputs["Vector"])
    store = new('GeometryNodeStoreNamedAttribute', -400, 100, data_type='QUATERNION')
    store.inputs["Name"].default_value = "c4d_rot"
    L.new(circle.outputs[0], store.inputs["Geometry"])
    L.new(align.outputs[0], store.inputs["Value"])

    pts = menu_switch('GEOMETRY', 0, 200)
    L.new(line.outputs[0], pts.inputs["Linear"])
    L.new(store.outputs[0], pts.inputs["Radial"])
    L.new(real.outputs[0], pts.inputs["Grid"])

    rot = new('GeometryNodeInputNamedAttribute', 400, -100, data_type='QUATERNION')
    rot.inputs["Name"].default_value = "c4d_rot"

    # --- clone the children ---------------------------------------------
    coll = new('GeometryNodeCollectionInfo', 200, 400)
    coll.inputs["Separate Children"].default_value = True
    coll.inputs["Reset Children"].default_value = True
    L.new(gin.outputs["Children"], coll.inputs["Collection"])
    index = new('GeometryNodeInputIndex', 200, 150)
    iop = new('GeometryNodeInstanceOnPoints', 600, 200)
    iop.inputs["Pick Instance"].default_value = True
    L.new(pts.outputs[0], iop.inputs["Points"])
    L.new(coll.outputs[0], iop.inputs["Instance"])
    L.new(index.outputs[0], iop.inputs["Instance Index"])
    L.new(rot.outputs[0], iop.inputs["Rotation"])

    # --- Random effector -------------------------------------------------
    def rand_vec(sock, x, y):
        negv = new('ShaderNodeVectorMath', x - 200, y - 80, operation='SCALE')
        negv.inputs["Scale"].default_value = -1.0
        L.new(gin.outputs[sock], negv.inputs[0])
        r = new('FunctionNodeRandomValue', x, y, data_type='FLOAT_VECTOR')
        L.new(negv.outputs[0], r.inputs["Min"])
        L.new(gin.outputs[sock], r.inputs["Max"])
        L.new(gin.outputs["Seed"], r.inputs["Seed"])
        return r

    rp = rand_vec("Random Position", 800, -200)
    tr = new('GeometryNodeTranslateInstances', 900, 200)
    L.new(iop.outputs[0], tr.inputs["Instances"])
    L.new(rp.outputs[0], tr.inputs["Translation"])

    rr = rand_vec("Random Rotation", 1000, -350)
    ro = new('GeometryNodeRotateInstances', 1100, 200)
    L.new(tr.outputs[0], ro.inputs["Instances"])
    L.new(rr.outputs[0], ro.inputs["Rotation"])

    sneg = new('ShaderNodeMath', 900, -500, operation='MULTIPLY')
    sneg.inputs[1].default_value = -1.0
    L.new(gin.outputs["Random Scale"], sneg.inputs[0])
    rs = new('FunctionNodeRandomValue', 1050, -500, data_type='FLOAT')
    L.new(sneg.outputs[0], rs.inputs["Min"])
    L.new(gin.outputs["Random Scale"], rs.inputs["Max"])
    L.new(gin.outputs["Seed"], rs.inputs["Seed"])
    one = new('ShaderNodeMath', 1150, -500, operation='ADD')
    one.inputs[1].default_value = 1.0
    L.new(rs.outputs[0], one.inputs[0])
    sc = new('GeometryNodeScaleInstances', 1250, 200)
    L.new(ro.outputs[0], sc.inputs["Instances"])
    L.new(one.outputs[0], sc.inputs["Scale"])

    # --- Plain effector with spherical falloff ---------------------------
    # weight = clamp(1 - distance / (radius * effector scale)); radius 0 = infinite.
    ipos = new('GeometryNodeInputPosition', 1300, -700)
    info = new('GeometryNodeObjectInfo', 1300, -850, transform_space='RELATIVE')
    L.new(gin.outputs["Effector"], info.inputs["Object"])
    dist = new('ShaderNodeVectorMath', 1500, -700, operation='DISTANCE')
    L.new(ipos.outputs[0], dist.inputs[0])
    L.new(info.outputs["Location"], dist.inputs[1])
    escale = new('ShaderNodeSeparateXYZ', 1500, -900)
    L.new(info.outputs["Scale"], escale.inputs[0])
    rad = new('ShaderNodeMath', 1650, -900, operation='MULTIPLY')
    L.new(gin.outputs["Falloff Radius"], rad.inputs[0])
    L.new(escale.outputs["X"], rad.inputs[1])
    ratio = new('ShaderNodeMath', 1800, -750, operation='DIVIDE')
    L.new(dist.outputs["Value"], ratio.inputs[0])
    L.new(rad.outputs[0], ratio.inputs[1])
    weight = new('ShaderNodeMath', 1950, -750, operation='SUBTRACT', use_clamp=True)
    weight.inputs[0].default_value = 1.0
    L.new(ratio.outputs[0], weight.inputs[1])

    def weighted_vec(sock, x, y):
        v = new('ShaderNodeVectorMath', x, y, operation='SCALE')
        L.new(gin.outputs[sock], v.inputs[0])
        L.new(weight.outputs[0], v.inputs["Scale"])
        return v

    ptr = new('GeometryNodeTranslateInstances', 2150, 200)
    L.new(sc.outputs[0], ptr.inputs["Instances"])
    L.new(weighted_vec("Plain Position", 2100, -500).outputs[0], ptr.inputs["Translation"])
    pro = new('GeometryNodeRotateInstances', 2350, 200)
    L.new(ptr.outputs[0], pro.inputs["Instances"])
    L.new(weighted_vec("Plain Rotation", 2300, -650).outputs[0], pro.inputs["Rotation"])
    ws = new('ShaderNodeMath', 2400, -800, operation='MULTIPLY')
    L.new(gin.outputs["Plain Scale"], ws.inputs[0])
    L.new(weight.outputs[0], ws.inputs[1])
    ws1 = new('ShaderNodeMath', 2500, -800, operation='ADD')
    ws1.inputs[1].default_value = 1.0
    L.new(ws.outputs[0], ws1.inputs[0])
    psc = new('GeometryNodeScaleInstances', 2550, 200)
    L.new(pro.outputs[0], psc.inputs["Instances"])
    L.new(ws1.outputs[0], psc.inputs["Scale"])

    gout.location = (2800, 0)
    L.new(psc.outputs[0], gout.inputs[0])
    return ng


def _socket_id(ng, name):
    for item in ng.interface.items_tree:
        if getattr(item, "in_out", None) == 'INPUT' and item.name == name:
            return item.identifier
    return None


class C4D_OT_add_cloner(bpy.types.Operator):
    """Create a Cloner and move the selected objects in as its children (C4D MoGraph > Cloner)"""
    bl_idname = "c4d.add_cloner"
    bl_label = "Cloner"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(items=[('Linear', "Linear", ""), ('Radial', "Radial", ""), ('Grid', "Grid", "")],
                                 default='Linear')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        sources = [o for o in context.selected_objects if o.type in {'MESH', 'CURVE', 'FONT', 'EMPTY', 'SURFACE', 'META'}]
        if not sources:
            bpy.ops.mesh.primitive_cube_add(size=0.5)
            sources = [context.active_object]

        ng = build_group()
        me = bpy.data.meshes.new("Cloner")
        cloner = bpy.data.objects.new("Cloner", me)
        context.collection.objects.link(cloner)
        cloner.location = context.scene.cursor.location

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

        for o in context.selected_objects:
            o.select_set(False)
        cloner.select_set(True)
        context.view_layer.objects.active = cloner
        return {'FINISHED'}


def _input_slot(mod, name):
    """Blender 5.2 stores node-modifier inputs as mod.properties.inputs.<Socket_N>.value."""
    key = _socket_id(mod.node_group, name)
    if key is None:
        return None
    return getattr(mod.properties.inputs, key, None)


def set_input(mod, name, value):
    slot = _input_slot(mod, name)
    if slot is not None:
        try:
            slot.value = value
        except (TypeError, AttributeError):
            pass


def draw_nodes_modifier(layout, m):
    """Draw a Geometry Nodes modifier's inputs (e.g. the Cloner) in the Attribute Manager."""
    ng = m.node_group
    if ng is None:
        layout.prop(m, "node_group")
        return
    inputs = m.properties.inputs
    hidden = set()
    if ng.name.startswith(GROUP):
        mode_slot = _input_slot(m, "Mode")
        mode = getattr(mode_slot, "value", "Linear")
        hidden = {n for n, modes in MODE_ONLY.items() if mode not in modes}
    for item in ng.interface.items_tree:
        if getattr(item, "in_out", None) != 'INPUT' or item.socket_type == 'NodeSocketGeometry':
            continue
        if item.name in hidden:
            continue
        if item.name == "Random Position":
            layout.label(text="Random Effector")
        elif item.name == "Effector":
            layout.label(text="Plain Effector")
        slot = getattr(inputs, item.identifier, None)
        if slot is not None:
            layout.prop(slot, "value", text=item.name)


class C4D_OT_add_plain_effector(bpy.types.Operator):
    """Add a Plain effector (sphere falloff) and link it to the selected Cloner"""
    bl_idname = "c4d.add_plain_effector"
    bl_label = "Plain Effector"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        cloners = [o for o in context.selected_objects
                   if any(m.type == 'NODES' and m.node_group and m.node_group.name.startswith(GROUP)
                          for m in o.modifiers)]
        eff = bpy.data.objects.new("Plain", None)
        eff.empty_display_type = 'SPHERE'
        eff.empty_display_size = 1.0  # scale the empty to scale the falloff
        context.collection.objects.link(eff)
        eff.location = context.scene.cursor.location
        for c in cloners:
            m = next(m for m in c.modifiers if m.type == 'NODES' and m.node_group.name.startswith(GROUP))
            if _socket_id(m.node_group, "Effector") is None:
                self.report({'WARNING'}, f"{c.name}: old cloner, recreate it to use effectors")
                continue
            set_input(m, "Effector", eff)
            set_input(m, "Plain Position", (0.0, 0.0, 1.0))  # C4D default: P.Y 100 cm
            c.update_tag()
        for o in context.selected_objects:
            o.select_set(False)
        eff.select_set(True)
        context.view_layer.objects.active = eff
        if not cloners:
            self.report({'INFO'}, "Select a Cloner first to link the effector")
        return {'FINISHED'}


classes = (C4D_OT_add_cloner, C4D_OT_add_plain_effector)
