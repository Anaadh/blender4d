"""C4D-style Object Manager.

Drawn as a list in a Properties editor (upper-right manager, "Objects" tab),
because Python cannot add new editor types. Each row:

  [indent][fold][type icon] Name ........ [editor dot][render dot][check] [tags]

- Dots: grey = default (visible), red = hidden. Click to toggle, like C4D's
  traffic lights (editor = Disable in Viewports, render = Disable in Renders).
- Check / X: generators on/off (all modifiers), shown only on objects that
  have modifiers.
- Tags: modifiers, constraints and materials. Clicking a tag selects the
  object and shows that tag in the Attribute Manager.
- Click a name to select; Shift/Ctrl+click to add/remove. Double-click-free
  renaming: F2 in the viewport or the Basic tab.
Blender's Outliner stays available on the "Outliner" tab for drag-and-drop
parenting.
"""

import bpy

from .icons import icon as ic

TYPE_ICONS = {
    'MESH': 'OUTLINER_OB_MESH', 'CURVE': 'OUTLINER_OB_CURVE', 'SURFACE': 'OUTLINER_OB_SURFACE',
    'META': 'OUTLINER_OB_META', 'FONT': 'OUTLINER_OB_FONT', 'ARMATURE': 'OUTLINER_OB_ARMATURE',
    'LATTICE': 'OUTLINER_OB_LATTICE', 'EMPTY': 'OUTLINER_OB_EMPTY', 'GPENCIL': 'OUTLINER_OB_GREASEPENCIL',
    'GREASEPENCIL': 'OUTLINER_OB_GREASEPENCIL', 'CAMERA': 'OUTLINER_OB_CAMERA',
    'LIGHT': 'OUTLINER_OB_LIGHT', 'SPEAKER': 'OUTLINER_OB_SPEAKER', 'LIGHT_PROBE': 'OUTLINER_OB_LIGHTPROBE',
    'VOLUME': 'OUTLINER_OB_VOLUME', 'POINTCLOUD': 'OUTLINER_OB_POINTCLOUD', 'CURVES': 'OUTLINER_OB_CURVES',
}


def _object_icon(ob):
    for m in ob.modifiers:
        if m.type == 'NODES' and m.node_group and m.node_group.name.startswith("C4D "):
            kind = m.node_group.name[4:]
            if kind.startswith("Cloner"):
                return {"icon_value": ic("array")}
            from .splines import GEN_SPECS, SPLINE_SPECS
            if kind in GEN_SPECS:
                return {"icon_value": ic("generator")}
            if kind in SPLINE_SPECS:
                return {"icon_value": ic("spline")}
            return {"icon_value": ic("cube")}
    return {"icon": TYPE_ICONS.get(ob.type, 'OBJECT_DATA')}


def _modifier_icon(m):
    try:
        return bpy.types.Modifier.bl_rna.properties['type'].enum_items[m.type].icon
    except (KeyError, AttributeError):
        return 'MODIFIER'


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

_TREE = {"depth": {}, "kids": set()}

class C4D_UL_objects(bpy.types.UIList):
    bl_idname = "C4D_UL_objects"

    def filter_items(self, context, data, propname):
        objs = getattr(data, propname)
        index = {ob.name: i for i, ob in enumerate(objs)}
        depth = {}
        order = []  # original indices in display order
        visible = set()

        # Parent -> children map from parent pointers (Object.children is O(n) per call).
        kids_of = {}
        for o in objs:
            if o.parent is not None and o.parent.name in index:
                kids_of.setdefault(o.parent.name, []).append(o)
        roots = sorted((o for o in objs if o.parent is None or o.parent.name not in index),
                       key=lambda o: o.name.lower())
        stack = [(o, 0, True) for o in reversed(roots)]
        while stack:
            ob, d, shown = stack.pop()
            i = index[ob.name]
            order.append(i)
            depth[ob.name] = d
            if shown:
                visible.add(i)
            kids = sorted(kids_of.get(ob.name, ()), key=lambda o: o.name.lower())
            open_ = shown and ob.c4d_om_open
            stack.extend((c, d + 1, open_) for c in reversed(kids))

        text = self.filter_name.lower()
        flags = []
        for i, ob in enumerate(objs):
            ok = i in visible and (not text or text in ob.name.lower())
            flags.append(self.bitflag_filter_item if ok else 0)
        neworder = [0] * len(objs)
        for pos, i in enumerate(order):
            neworder[i] = pos
        # filter_items and draw_item run on different UIList instances; share via module.
        _TREE["depth"] = depth
        _TREE["kids"] = set(kids_of)
        return flags, neworder

    def draw_item(self, context, layout, data, ob, icon, active_data, active_propname, index=0, flt_flag=0):
        depth = _TREE["depth"].get(ob.name, 0)
        split = layout.split(factor=0.55, align=True)

        left = split.row(align=True)
        if depth:
            left.separator(factor=depth * 1.6)
        if ob.name in _TREE["kids"]:
            left.prop(ob, "c4d_om_open", text="", emboss=False,
                      icon='DISCLOSURE_TRI_DOWN' if ob.c4d_om_open else 'DISCLOSURE_TRI_RIGHT')
        else:
            left.label(text="", icon='BLANK1')
        selected = ob.select_get()
        name_row = left.row(align=True)
        name_row.alignment = 'LEFT'
        op = name_row.operator("c4d.om_select", text=ob.name, emboss=selected, depress=selected,
                           **_object_icon(ob))
        op.name = ob.name

        right = split.row(align=True)
        right.alignment = 'RIGHT'
        # Traffic lights: editor, render
        # (operators, not props: Blender offsets custom icons on boolean toggles)
        for what, hidden in (('EDITOR', ob.hide_viewport), ('RENDER', ob.hide_render)):
            t = right.operator("c4d.om_visibility", text="", emboss=False,
                               icon_value=ic("om_dot_red" if hidden else "om_dot_grey"))
            t.name, t.what = ob.name, what
        if ob.modifiers:
            on = any(m.show_viewport for m in ob.modifiers)
            right.operator("c4d.om_toggle_generators", text="", emboss=False,
                           icon_value=ic("om_check" if on else "om_cross")).name = ob.name
        else:
            right.label(text="", icon='BLANK1')

        # Tags
        tags = right.row(align=True)
        if ob.type == 'CAMERA':
            from .camera import looking_through
            on = looking_through(context, ob)
            tags.operator("c4d.look_through", text="", emboss=False,
                          icon='VIEW_CAMERA' if on else 'VIEW_CAMERA_UNSELECTED').name = ob.name
        for i, m in enumerate(ob.modifiers):
            t = tags.operator("c4d.om_tag", text="", emboss=False, icon=_modifier_icon(m))
            t.name, t.kind, t.index = ob.name, 'MODIFIER', i
        for i, c in enumerate(ob.constraints):
            t = tags.operator("c4d.om_tag", text="", emboss=False, icon='CONSTRAINT')
            t.name, t.kind, t.index = ob.name, 'CONSTRAINT', i
        from .tags import TAGS, custom_tags
        for i, key in enumerate(custom_tags(ob)):
            t = tags.operator("c4d.om_tag", text="", emboss=False, icon=TAGS[key][1])
            t.name, t.kind, t.index = ob.name, 'CUSTOM', i
        for i, slot in enumerate(getattr(ob, "material_slots", ())):
            if slot.material is None:
                continue
            prev = slot.material.preview
            kw = {"icon_value": prev.icon_id} if prev else {"icon": 'MATERIAL'}
            t = tags.operator("c4d.om_tag", text="", emboss=False, **kw)
            t.name, t.kind, t.index = ob.name, 'MATERIAL', i


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class C4D_OT_om_select(bpy.types.Operator):
    """Select (Shift/Ctrl+click: add or remove)"""
    bl_idname = "c4d.om_select"
    bl_label = "Select Object"
    bl_options = {'INTERNAL', 'UNDO'}

    name: bpy.props.StringProperty()

    def invoke(self, context, event):
        ob = context.scene.objects.get(self.name)
        if ob is None:
            return {'CANCELLED'}
        if context.mode != 'OBJECT' and context.active_object is not ob:
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except RuntimeError:
                return {'CANCELLED'}
        vl = context.view_layer
        if event.shift or event.ctrl:
            if ob.select_get() and vl.objects.active is ob:
                ob.select_set(False)
                return {'FINISHED'}
            try:
                ob.select_set(True)
            except RuntimeError:
                pass
        else:
            for o in context.selected_objects:
                o.select_set(False)
            try:
                ob.select_set(True)
            except RuntimeError:
                pass  # hidden objects can still become active, like C4D
        vl.objects.active = ob
        context.window_manager.c4d_active_tag = ""
        return {'FINISHED'}


class C4D_OT_om_visibility(bpy.types.Operator):
    """Traffic light: toggle visibility in the editor (viewport) or renderer"""
    bl_idname = "c4d.om_visibility"
    bl_label = "Toggle Visibility"
    bl_options = {'INTERNAL', 'UNDO'}

    name: bpy.props.StringProperty()
    what: bpy.props.StringProperty()

    def execute(self, context):
        ob = context.scene.objects.get(self.name)
        if ob is None:
            return {'CANCELLED'}
        if self.what == 'EDITOR':
            ob.hide_viewport = not ob.hide_viewport
        else:
            ob.hide_render = not ob.hide_render
        return {'FINISHED'}


class C4D_OT_om_toggle_generators(bpy.types.Operator):
    """Enable / disable this object's generators and deformers"""
    bl_idname = "c4d.om_toggle_generators"
    bl_label = "Toggle Generators"
    bl_options = {'INTERNAL', 'UNDO'}

    name: bpy.props.StringProperty()

    def execute(self, context):
        ob = context.scene.objects.get(self.name)
        if ob is None or not ob.modifiers:
            return {'CANCELLED'}
        state = not any(m.show_viewport for m in ob.modifiers)
        for m in ob.modifiers:
            m.show_viewport = state
            m.show_render = state
        return {'FINISHED'}


class C4D_OT_om_tag(bpy.types.Operator):
    """Show this tag in the Attribute Manager"""
    bl_idname = "c4d.om_tag"
    bl_label = "Tag"
    bl_options = {'INTERNAL'}

    name: bpy.props.StringProperty()
    kind: bpy.props.StringProperty()
    index: bpy.props.IntProperty()

    def execute(self, context):
        ob = context.scene.objects.get(self.name)
        if ob is None:
            return {'CANCELLED'}
        for o in context.selected_objects:
            o.select_set(False)
        try:
            ob.select_set(True)
        except RuntimeError:
            pass
        context.view_layer.objects.active = ob
        if self.kind == 'MODIFIER' and self.index < len(ob.modifiers):
            ob.modifiers.active = ob.modifiers[self.index]
        elif self.kind == 'MATERIAL':
            ob.active_material_index = self.index
        wm = context.window_manager
        wm.c4d_active_tag = ""
        if self.kind == 'CUSTOM':
            from .tags import custom_tags
            tags = custom_tags(ob)
            if self.index < len(tags):
                wm.c4d_active_tag = tags[self.index]
        ctx = {'MODIFIER': 'MODIFIER', 'CONSTRAINT': 'CONSTRAINT', 'MATERIAL': 'MATERIAL',
               'CUSTOM': 'OBJECT'}[self.kind]
        for area in context.screen.areas:
            if area.type != 'PROPERTIES':
                continue
            if area.y + area.height / 2 > context.window.height / 2 and area.x > context.window.width * 0.6:
                continue  # skip the Object Manager itself
            try:
                area.spaces.active.context = ctx
            except TypeError:
                pass
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

def om_area(context):
    from .managers import c4d_active, _column_slot
    return (c4d_active(context) and context.area is not None and context.area.type == 'PROPERTIES'
            and _column_slot(context) == 'UPPER')


class C4D_PT_object_manager(bpy.types.Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"
    bl_label = "Objects"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        return om_area(context)

    def draw(self, context):
        rows = max(8, int(context.region.height / (20 * context.preferences.view.ui_scale)) - 3)
        self.layout.template_list("C4D_UL_objects", "", context.scene, "objects",
                                  context.scene, "c4d_om_index", rows=rows)


def _on_index(self, context):
    objs = self.objects
    if 0 <= self.c4d_om_index < len(objs):
        ob = objs[self.c4d_om_index]
        for o in context.selected_objects:
            o.select_set(False)
        try:
            ob.select_set(True)
        except RuntimeError:
            pass
        context.view_layer.objects.active = ob


def configure_space(sp):
    """Properties editor used as Object Manager: only the Scene tab."""
    for p in sp.bl_rna.properties.keys():
        if p.startswith("show_properties_"):
            setattr(sp, p, p == "show_properties_scene")
    try:
        sp.context = 'SCENE'
    except TypeError:
        pass


classes = (C4D_UL_objects, C4D_OT_om_select, C4D_OT_om_visibility, C4D_OT_om_toggle_generators, C4D_OT_om_tag,
           C4D_PT_object_manager)


def register():
    bpy.types.Object.c4d_om_open = bpy.props.BoolProperty(
        name="Unfolded", default=True, description="Show children in the Object Manager")
    bpy.types.Scene.c4d_om_index = bpy.props.IntProperty(default=-1, update=_on_index)


def unregister():
    del bpy.types.Scene.c4d_om_index
    del bpy.types.Object.c4d_om_open
