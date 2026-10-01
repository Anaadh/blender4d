"""C4D-style deformer objects.

A deformer is an Empty placed as a child of the object it deforms, like in
Cinema 4D. Its transform drives the deformation (it is the modifier's
origin object). Moving the deformer under another parent moves the effect:
a depsgraph handler keeps one modifier on the current parent per deformer
and removes it from the old one.
"""

import math

import bpy
from bpy.app.handlers import persistent

TAG = "c4d_deformer"      # custom property on the deformer empty
MOD_PREFIX = "C4D "      # modifier name = MOD_PREFIX + deformer name

KINDS = {
    # kind: (label, empty display, modifier type, settings)
    'BEND': ("Bend", 'SINGLE_ARROW', 'SIMPLE_DEFORM', {"deform_method": 'BEND', "angle": math.radians(45)}),
    'TWIST': ("Twist", 'SINGLE_ARROW', 'SIMPLE_DEFORM', {"deform_method": 'TWIST', "angle": math.radians(90)}),
    'TAPER': ("Taper", 'SINGLE_ARROW', 'SIMPLE_DEFORM', {"deform_method": 'TAPER', "factor": 0.5}),
    'STRETCH': ("Squash & Stretch", 'SINGLE_ARROW', 'SIMPLE_DEFORM', {"deform_method": 'STRETCH', "factor": 0.3}),
    'WAVE': ("Wave", 'CIRCLE', 'WAVE', {"height": 0.2, "width": 1.0}),
}

# Modifier property holding the controlling object, per modifier type.
ORIGIN_PROP = {'SIMPLE_DEFORM': "origin", 'WAVE': "start_position_object"}


def _modifier_for(target, deformer):
    return target.modifiers.get(MOD_PREFIX + deformer.name)


def _sync():
    """Make every deformer's modifier live on its current parent only."""
    deformers = {o.name: o for o in bpy.data.objects if o.get(TAG) in KINDS}
    for ob in bpy.data.objects:
        for m in list(ob.modifiers):
            if not m.name.startswith(MOD_PREFIX) or m.type not in ORIGIN_PROP:
                continue
            origin = getattr(m, ORIGIN_PROP[m.type], None)
            if origin is None:
                ob.modifiers.remove(m)  # its deformer object was deleted
                continue
            owner_ok = origin.name in deformers and origin.parent == ob
            if origin.get(TAG) in KINDS and not owner_ok:
                ob.modifiers.remove(m)  # deformer moved to another parent
    for d in deformers.values():
        target = d.parent
        if target is None or not hasattr(target, "modifiers") or target.type not in {'MESH', 'CURVE', 'FONT', 'LATTICE'}:
            continue
        if _modifier_for(target, d) is not None:
            continue
        label, _disp, mtype, settings = KINDS[d[TAG]]
        m = target.modifiers.new(MOD_PREFIX + d.name, mtype)
        setattr(m, ORIGIN_PROP[mtype], d)
        for k, v in settings.items():
            setattr(m, k, v)
        if mtype == 'SIMPLE_DEFORM':
            m.deform_axis = 'Z'  # C4D Y-up = Blender Z-up


_busy = False


@persistent
def _on_depsgraph(scene, depsgraph):
    global _busy
    if _busy:
        return
    if not any(isinstance(u.id, bpy.types.Object) for u in depsgraph.updates):
        return
    _busy = True
    try:
        _sync()
    finally:
        _busy = False


class C4D_OT_add_deformer(bpy.types.Operator):
    """Add a deformer as a child of the selected object (C4D style)"""
    bl_idname = "c4d.add_deformer"
    bl_label = "Add Deformer"
    bl_options = {'REGISTER', 'UNDO'}

    kind: bpy.props.EnumProperty(items=[(k, v[0], "") for k, v in KINDS.items()])

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        label, display, _mtype, _settings = KINDS[self.kind]
        target = context.active_object if context.active_object in context.selected_objects else None
        d = bpy.data.objects.new(label, None)
        d.empty_display_type = display
        d.empty_display_size = 1.0
        d[TAG] = self.kind
        context.collection.objects.link(d)
        if target is not None:
            context.view_layer.update()
            d.parent = target
            d.matrix_world = target.matrix_world.normalized()  # at the target's origin
        else:
            d.location = context.scene.cursor.location
        _sync()
        for o in context.selected_objects:
            o.select_set(False)
        d.select_set(True)
        context.view_layer.objects.active = d
        return {'FINISHED'}


def deformer_modifier(ob):
    """For a deformer empty: its modifier on the parent (for the Attribute Manager)."""
    if ob is None or ob.get(TAG) not in KINDS or ob.parent is None:
        return None
    return _modifier_for(ob.parent, ob)


classes = (C4D_OT_add_deformer,)


def register():
    bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)


def unregister():
    if _on_depsgraph in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph)
