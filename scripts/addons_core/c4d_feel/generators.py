"""C4D mesh generators: Subdivision Surface, Symmetry, Connect, Boolean.

A generator is an object whose Geometry Nodes tree reads its children and
outputs the result, like C4D. The children live in a "<Generator> Children"
collection and are hidden (the generator shows the result); unhide one with
its editor dot, or "Show Cage" in the Attribute Manager, to edit it and watch
the generator update live. Press C on the generator to bake it.

Hierarchy is membership, as in C4D: a depsgraph handler keeps each
generator's (and Cloner's) children collection equal to its children in the
Object Manager, so dragging an object under a Subdivision Surface puts it in,
and dragging it out takes it out again.
"""

import bpy
from bpy.app.handlers import persistent

from .cloner import _T, _socket, get_input, set_input, _socket_id, GROUP as CLONER_GROUP

PREFIX = "C4D "
VERSION = {}  # name: version, bump when a node tree changes

SPECS = {
    "Subdivision Surface": [("Children", 'NodeSocketCollection', None, None, None),
                            ("Subdivision Editor", 'NodeSocketInt', 2, 0, None),
                            ("Subdivision Renderer", 'NodeSocketInt', 3, 0, None)],
    "Symmetry": [("Children", 'NodeSocketCollection', None, None, None),
                 ("Mirror Plane", 'NodeSocketMenu', None, None, None),
                 ("Weld Points", 'NodeSocketBool', True, None, None),
                 ("Tolerance", 'NodeSocketFloat', 0.01, 0.0, 'DISTANCE')],
    "Connect": [("Children", 'NodeSocketCollection', None, None, None),
                ("Weld", 'NodeSocketBool', True, None, None),
                ("Tolerance", 'NodeSocketFloat', 0.001, 0.0, 'DISTANCE')],
    "Boolean": [("Children", 'NodeSocketCollection', None, None, None),
                ("Boolean Type", 'NodeSocketMenu', None, None, None)],
}
ICONS = {"Subdivision Surface": 'MOD_SUBSURF', "Symmetry": 'MOD_MIRROR',
         "Connect": 'AUTOMERGE_ON', "Boolean": 'MOD_BOOLEAN'}

# C4D's mirror planes, mapped to Blender's Z-up axes.
MIRROR_PLANES = {"ZY (mirror X)": (-1.0, 1.0, 1.0), "XZ (mirror Y)": (1.0, -1.0, 1.0),
                 "XY (mirror Z)": (1.0, 1.0, -1.0)}
BOOLEAN_TYPES = {"A subtract B": 'DIFFERENCE', "A union B": 'UNION', "A intersect B": 'INTERSECT'}

CHILD_TYPES = {'MESH', 'CURVE', 'FONT', 'SURFACE', 'META', 'EMPTY'}


# ---------------------------------------------------------------------------
# Node trees
# ---------------------------------------------------------------------------

def _children(t):
    coll = t.node('GeometryNodeCollectionInfo', transform_space='RELATIVE')
    coll.inputs["Separate Children"].default_value = True
    coll.inputs["Reset Children"].default_value = False
    t.link(t.i("Children"), coll.inputs["Collection"])
    return coll.outputs[0]


def _merge(t, geo, enabled, distance):
    merge = t.node('GeometryNodeMergeByDistance')
    t.link(geo, merge.inputs["Geometry"])
    t.link(distance, merge.inputs["Distance"])
    return t.switch('GEOMETRY', enabled, geo, merge.outputs["Geometry"])


def _build(name, t):
    instances = _children(t)
    if name == "Boolean":
        # First child (by name) is A, everything else is B.
        pick = t.node('GeometryNodeSeparateGeometry', domain='INSTANCE')
        t.link(instances, pick.inputs["Geometry"])
        t.link(t.eq(t.node('GeometryNodeInputIndex').outputs[0], 0.0), pick.inputs["Selection"])
        a, b = t.realize(pick.outputs["Selection"]), t.realize(pick.outputs["Inverted"])
        results = {}
        for label, op in BOOLEAN_TYPES.items():
            n = t.node('GeometryNodeMeshBoolean', operation=op)
            # The operand socket is "Mesh 2" by identifier whatever the operation calls it.
            operands = next(s for s in n.inputs if s.identifier == "Mesh 2")
            if op == 'DIFFERENCE':
                t.link(a, n.inputs["Mesh 1"])
            else:
                t.link(a, operands)
            t.link(b, operands)
            results[label] = n.outputs["Mesh"]
        return t.menu_switch('GEOMETRY', t.i("Boolean Type"), results)

    geo = t.realize(instances)
    if name == "Subdivision Surface":
        is_viewport = t.node('GeometryNodeIsViewport').outputs[0]
        level = t.switch('INT', is_viewport, t.i("Subdivision Renderer"), t.i("Subdivision Editor"))
        sds = t.node('GeometryNodeSubdivisionSurface')
        t.link(geo, sds.inputs["Mesh"])
        t.link(level, sds.inputs["Level"])
        smooth = t.node('GeometryNodeSetShadeSmooth', domain='FACE')
        smooth.inputs["Shade Smooth"].default_value = True
        t.link(sds.outputs["Mesh"], smooth.inputs["Geometry"])
        return smooth.outputs[0]
    if name == "Symmetry":
        scale = t.menu_switch('VECTOR', t.i("Mirror Plane"), MIRROR_PLANES)
        mirror = t.node('GeometryNodeTransform')
        t.link(geo, mirror.inputs["Geometry"])
        t.link(scale, mirror.inputs["Scale"])
        flip = t.node('GeometryNodeFlipFaces')
        t.link(mirror.outputs["Geometry"], flip.inputs["Mesh"])
        return _merge(t, t.join(geo, flip.outputs["Mesh"]), t.i("Weld Points"), t.i("Tolerance"))
    if name == "Connect":
        return _merge(t, geo, t.i("Weld"), t.i("Tolerance"))
    raise KeyError(name)


def build_group(name):
    gname = PREFIX + name
    want = VERSION.get(name, 1)
    ng = bpy.data.node_groups.get(gname)
    if ng is not None:
        if ng.get("c4d_version", 1) >= want:
            return ng
        ng.name = gname + " (old)"
    ng = bpy.data.node_groups.new(gname, 'GeometryNodeTree')
    ng["c4d_version"] = want
    it = ng.interface
    it.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    it.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    for spec in SPECS[name]:
        _socket(it, *spec)
    t = _T(ng)
    t.finish(_build(name, t))
    return ng


def is_generator_group(ng):
    return ng is not None and ng.name.startswith(PREFIX) and \
        ng.name[len(PREFIX):].split(" (old)")[0] in SPECS


def generator_modifier(ob):
    for m in getattr(ob, "modifiers", ()):
        if m.type == 'NODES' and is_generator_group(m.node_group):
            return m
    return None


def generator_name(ob):
    """'Subdivision Surface', 'Symmetry', ... for generator objects, else None."""
    m = generator_modifier(ob)
    return m.node_group.name[len(PREFIX):].split(" (old)")[0] if m else None


# ---------------------------------------------------------------------------
# Children <-> hierarchy sync
# ---------------------------------------------------------------------------

def _children_modifier(ob):
    """The generator / Cloner modifier whose "Children" collection follows the hierarchy."""
    for m in getattr(ob, "modifiers", ()):
        if m.type == 'NODES' and m.node_group and (
                is_generator_group(m.node_group) or m.node_group.name.startswith(CLONER_GROUP)):
            if _socket_id(m.node_group, "Children") is not None:
                return m
    return None


def _is_child_material(ob):
    from .cloner import effector_modifier
    from .deformers import TAG as DEFORMER_TAG
    return ob.type in CHILD_TYPES and effector_modifier(ob) is None and ob.get(DEFORMER_TAG) is None


def _sync(scene):
    """Children collection == direct children in the Object Manager, for every generator."""
    for gen in bpy.data.objects:
        m = _children_modifier(gen)
        if m is None:
            continue
        coll = get_input(m, "Children")
        if coll is None:
            continue
        wanted = [c for c in gen.children if _is_child_material(c)]
        for c in wanted:
            if c.name not in coll.objects:
                for other in list(c.users_collection):
                    other.objects.unlink(c)
                coll.objects.link(c)
                c.hide_set(True)
                c.hide_render = True
        for c in list(coll.objects):
            if c.parent != gen:
                coll.objects.unlink(c)
                if not c.users_collection:
                    home = gen.users_collection[0] if gen.users_collection else scene.collection
                    home.objects.link(c)
                c.hide_set(False)
                c.hide_render = False


_busy = False


@persistent
def _on_depsgraph(scene, depsgraph):
    global _busy
    if _busy or not any(isinstance(u.id, bpy.types.Object) for u in depsgraph.updates):
        return
    _busy = True
    try:
        _sync(scene)
    except (ReferenceError, RuntimeError):
        pass
    finally:
        _busy = False


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

def _default_children(context, kind):
    cursor = context.scene.cursor.location.copy()
    bpy.ops.c4d.add_primitive(kind='Cube')
    kids = [context.active_object]
    if kind == "Boolean":
        bpy.ops.c4d.add_primitive(kind='Sphere')
        sphere = context.active_object
        sphere.location = cursor + type(cursor)((1.0, 1.0, 1.0))
        kids.append(sphere)
    return kids


class C4D_OT_add_generator(bpy.types.Operator):
    """Add a generator; the selected objects become its children (C4D Subdivision Surface, Symmetry, Connect, Boolean)"""
    bl_idname = "c4d.add_generator"
    bl_label = "Add Generator"
    bl_options = {'REGISTER', 'UNDO'}

    kind: bpy.props.EnumProperty(items=[(k, k, "") for k in SPECS])

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        sources = [o for o in context.selected_objects if _is_child_material(o)]
        if not sources:
            sources = _default_children(context, self.kind)
        if self.kind == "Boolean" and len(sources) > 1:
            # Collection order is name order: the active object is A.
            active = context.active_object
            if active in sources:
                sources.remove(active)
                sources.insert(0, active)
            for i, o in enumerate(sources):
                o.name = ("A " if i == 0 else "B ") + o.name

        me = bpy.data.meshes.new(self.kind)
        gen = bpy.data.objects.new(self.kind, me)
        context.collection.objects.link(gen)
        mod = gen.modifiers.new(self.kind, 'NODES')
        mod.node_group = build_group(self.kind)

        coll = bpy.data.collections.new(f"{self.kind} Children")
        context.scene.collection.children.link(coll)
        context.view_layer.update()
        for o in sources:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            coll.objects.link(o)
            mw = o.matrix_world.copy()
            o.parent = gen
            o.matrix_world = mw
            o.hide_set(True)
            o.hide_render = True
        set_input(mod, "Children", coll)

        for o in context.selected_objects:
            o.select_set(False)
        gen.select_set(True)
        context.view_layer.objects.active = gen
        return {'FINISHED'}


class C4D_OT_generator_cage(bpy.types.Operator):
    """Show or hide the generator's children (the cage) to edit them"""
    bl_idname = "c4d.generator_cage"
    bl_label = "Show / Hide Cage"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    name: bpy.props.StringProperty()

    def execute(self, context):
        gen = bpy.data.objects.get(self.name)
        if gen is None:
            return {'CANCELLED'}
        kids = [c for c in gen.children if _is_child_material(c)]
        show = any(c.hide_get() for c in kids)
        for c in kids:
            c.hide_set(not show)
        return {'FINISHED'}


def consumed_children(objects):
    """Children that Make Editable (C) folds into the result, like C4D."""
    from .splines import kind_of
    from .cloner import cloner_modifier
    doomed = []
    for o in objects:
        if generator_modifier(o) or cloner_modifier(o) or (kind_of(o) or ("", ""))[0] == 'generator':
            for c in o.children_recursive:
                if c not in doomed and c not in objects:
                    doomed.append(c)
    return doomed


# ---------------------------------------------------------------------------
# Attribute Manager
# ---------------------------------------------------------------------------

def draw_generator(layout, m):
    kind = m.node_group.name[len(PREFIX):].split(" (old)")[0]
    layout.label(text=kind, icon=ICONS.get(kind, 'MODIFIER'))
    names = [spec[0] for spec in SPECS[kind] if spec[0] != "Children"]
    if kind == "Symmetry" and not get_input(m, "Weld Points", True):
        names.remove("Tolerance")
    if kind == "Connect" and not get_input(m, "Weld", True):
        names.remove("Tolerance")
    for name in names:
        slot = getattr(m.properties.inputs, _socket_id(m.node_group, name) or "", None)
        if slot is not None:
            layout.prop(slot, "value", text=name)

    layout.separator()
    layout.label(text="Children" + ("  (A, then B)" if kind == "Boolean" else ""))
    box = layout.box()
    coll = get_input(m, "Children")
    kids = list(coll.objects) if coll is not None else []
    for c in kids:
        box.label(text=c.name, icon='HIDE_ON' if c.hide_get() else 'HIDE_OFF')
    if not kids:
        box.label(text="None. Drag objects under this generator in the Object Manager.")
    else:
        layout.operator("c4d.generator_cage", icon='MESH_DATA').name = m.id_data.name


classes = (C4D_OT_add_generator, C4D_OT_generator_cage)


def register():
    bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)


def unregister():
    if _on_depsgraph in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph)
