"""C4D-style tags.

Most C4D tags map onto Blender data that already shows as a tag in the
Object Manager (modifier, constraint, material). Tags with no Blender
counterpart (Protection, Display, Compositing) are stored in the object's
"c4d_tags" property (comma separated) so both Object Managers can draw them;
their settings live on the object itself.
"""

import bpy

PROP = "c4d_tags"

# key: (label, icon, kind) where kind is 'MODIFIER', 'CONSTRAINT', 'MATERIAL' or 'CUSTOM'
TAGS = {
    'PHONG': ("Phong", 'MOD_SMOOTH', 'MODIFIER'),
    'MATERIAL': ("Material", 'MATERIAL', 'MATERIAL'),
    'TARGET': ("Target", 'CON_TRACKTO', 'CONSTRAINT'),
    'LOOK_AT_CAMERA': ("Look at Camera", 'CON_TRACKTO', 'CONSTRAINT'),
    'ALIGN_SPLINE': ("Align to Spline", 'CON_FOLLOWPATH', 'CONSTRAINT'),
    'PROTECTION': ("Protection", 'LOCKED', 'CUSTOM'),
    'DISPLAY': ("Display", 'SHADING_TEXTURE', 'CUSTOM'),
    'COMPOSITING': ("Compositing", 'RENDERLAYERS', 'CUSTOM'),
}
CUSTOM = [k for k, v in TAGS.items() if v[2] == 'CUSTOM']


def custom_tags(ob):
    raw = ob.get(PROP, "") if ob is not None else ""
    return [t for t in str(raw).split(",") if t in TAGS]


def _set_custom(ob, tags):
    if tags:
        ob[PROP] = ",".join(tags)
    elif PROP in ob:
        del ob[PROP]


def _add(context, ob, key):
    label, _icon, kind = TAGS[key]
    if kind == 'CUSTOM':
        tags = custom_tags(ob)
        if key not in tags:
            tags.append(key)
            _set_custom(ob, tags)
        if key == 'PROTECTION':
            ob.lock_location = ob.lock_rotation = ob.lock_scale = (True, True, True)
        return
    if key == 'PHONG':
        if ob.type == 'MESH':
            with context.temp_override(object=ob, active_object=ob, selected_objects=[ob],
                                       selected_editable_objects=[ob]):
                try:
                    bpy.ops.object.shade_auto_smooth()
                except (RuntimeError, AttributeError):
                    bpy.ops.object.shade_smooth()
        return
    if key == 'MATERIAL':
        if hasattr(ob.data, "materials"):
            mat = context.object.active_material if context.object else None
            if mat is None:
                mat = bpy.data.materials.new("Mat")
            ob.data.materials.append(mat)
        return
    if key == 'TARGET':
        c = ob.constraints.new('TRACK_TO')
        c.name = "Target"
        c.track_axis = 'TRACK_NEGATIVE_Z' if ob.type in {'CAMERA', 'LIGHT'} else 'TRACK_Y'
        c.up_axis = 'UP_Y' if ob.type in {'CAMERA', 'LIGHT'} else 'UP_Z'
        others = [o for o in context.selected_objects if o is not ob]
        c.target = others[0] if others else None
        return
    if key == 'LOOK_AT_CAMERA':
        c = ob.constraints.new('DAMPED_TRACK')
        c.name = "Look at Camera"
        c.track_axis = 'TRACK_Z'
        c.target = context.scene.camera
        return
    if key == 'ALIGN_SPLINE':
        c = ob.constraints.new('FOLLOW_PATH')
        c.name = "Align to Spline"
        c.use_curve_follow = True
        curves = [o for o in context.selected_objects if o.type == 'CURVE' and o is not ob]
        c.target = curves[0] if curves else None


class C4D_OT_add_tag(bpy.types.Operator):
    """Add a C4D tag to the selected objects"""
    bl_idname = "c4d.add_tag"
    bl_label = "Add Tag"
    bl_options = {'REGISTER', 'UNDO'}

    key: bpy.props.EnumProperty(items=[(k, v[0], "", v[1], i) for i, (k, v) in enumerate(TAGS.items())])

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.selected_objects

    def execute(self, context):
        # For Target / Align to Spline, the active object gets the tag and the
        # other selected object is the target (like dropping onto the field).
        if self.key in {'TARGET', 'ALIGN_SPLINE'} and context.active_object:
            _add(context, context.active_object, self.key)
        else:
            for ob in list(context.selected_objects):
                _add(context, ob, self.key)
        return {'FINISHED'}


class C4D_OT_remove_tag(bpy.types.Operator):
    """Remove this C4D tag"""
    bl_idname = "c4d.remove_tag"
    bl_label = "Remove Tag"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    name: bpy.props.StringProperty()
    key: bpy.props.StringProperty()

    def execute(self, context):
        ob = context.scene.objects.get(self.name)
        if ob is None:
            return {'CANCELLED'}
        tags = custom_tags(ob)
        if self.key in tags:
            tags.remove(self.key)
            _set_custom(ob, tags)
            if self.key == 'PROTECTION':
                ob.lock_location = ob.lock_rotation = ob.lock_scale = (False, False, False)
        return {'FINISHED'}


class C4D_OT_copy_tags(bpy.types.Operator):
    """Copy the active object's custom C4D tags to the other selected objects"""
    bl_idname = "c4d.copy_tags"
    bl_label = "Copy Tags to Selected"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and len(context.selected_objects) > 1

    def execute(self, context):
        src = context.active_object
        for ob in context.selected_objects:
            if ob is src:
                continue
            for key in custom_tags(src):
                _add(context, ob, key)
            for c in src.constraints:
                ob.constraints.copy(c)
        return {'FINISHED'}


def draw_tag_settings(layout, ob, key):
    """Attribute Manager page for a custom tag."""
    label, icon, _kind = TAGS[key]
    head = layout.row()
    head.label(text=f"{label} Tag [{ob.name}]", icon=icon)
    op = head.operator("c4d.remove_tag", text="", icon='X', emboss=False)
    op.name, op.key = ob.name, key
    col = layout.column()
    col.use_property_split = True
    if key == 'PROTECTION':
        col.prop(ob, "lock_location", text="Position")
        col.prop(ob, "lock_rotation", text="Rotation")
        col.prop(ob, "lock_scale", text="Scale")
    elif key == 'DISPLAY':
        col.prop(ob, "display_type", text="Shading Mode")
        col.prop(ob, "show_in_front", text="X-Ray")
        col.prop(ob, "show_wire", text="Show Lines")
        col.prop(ob, "color", text="Display Color")
        col.prop(ob, "hide_viewport", text="Visibility (hidden)")
    elif key == 'COMPOSITING':
        for prop, text in (("visible_camera", "Seen by Camera"), ("visible_shadow", "Cast Shadows"),
                           ("visible_glossy", "Seen by Reflection"),
                           ("visible_transmission", "Seen by Refraction"),
                           ("visible_diffuse", "Seen by GI"), ("is_holdout", "Compositing Background")):
            if hasattr(ob, prop):
                col.prop(ob, prop, text=text)


class C4D_MT_tags(bpy.types.Menu):
    bl_idname = "C4D_MT_tags"
    bl_label = "C4D Tags"

    def draw(self, context):
        l = self.layout
        for key, (label, icon, _kind) in TAGS.items():
            l.operator("c4d.add_tag", text=label, icon=icon).key = key
        l.separator()
        l.operator("c4d.copy_tags", icon='COPYDOWN')


def _context_menu(self, context):
    self.layout.separator()
    self.layout.menu("C4D_MT_tags", icon='BOOKMARKS')


classes = (C4D_OT_add_tag, C4D_OT_remove_tag, C4D_OT_copy_tags, C4D_MT_tags)


def register():
    bpy.types.WindowManager.c4d_active_tag = bpy.props.StringProperty()
    bpy.types.OUTLINER_MT_object.append(_context_menu)
    bpy.types.VIEW3D_MT_object_context_menu.append(_context_menu)


def unregister():
    bpy.types.VIEW3D_MT_object_context_menu.remove(_context_menu)
    bpy.types.OUTLINER_MT_object.remove(_context_menu)
    del bpy.types.WindowManager.c4d_active_tag
