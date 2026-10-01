"""Material Manager menus (Create / Edit / Material) for the bottom asset strip."""

import bpy


def _active_material(context):
    asset = getattr(context, "asset", None)
    mat = getattr(asset, "local_id", None) if asset else None
    return mat if isinstance(mat, bpy.types.Material) else None


class C4D_OT_new_material(bpy.types.Operator):
    """Create a new default material (C4D Create > New Default Material)"""
    bl_idname = "c4d.new_material"
    bl_label = "New Default Material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mat = bpy.data.materials.new("Mat")
        mat.use_nodes = True
        mat.use_fake_user = True  # keep it in the manager until used, like C4D
        mat.asset_mark()
        try:
            mat.asset_generate_preview()
        except (AttributeError, RuntimeError):
            pass
        return {'FINISHED'}


class C4D_OT_apply_material(bpy.types.Operator):
    """Apply the active material to the selected objects"""
    bl_idname = "c4d.apply_material"
    bl_label = "Apply"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _active_material(context) is not None

    def execute(self, context):
        mat = _active_material(context)
        objs = [o for o in context.selected_objects if hasattr(o.data, "materials")]
        if not objs:
            self.report({'INFO'}, "Select objects first (or drag the material onto an object)")
            return {'CANCELLED'}
        for o in objs:
            if o.data.materials:
                o.data.materials[0] = mat
            else:
                o.data.materials.append(mat)
        return {'FINISHED'}


class C4D_OT_duplicate_material(bpy.types.Operator):
    """Duplicate the active material"""
    bl_idname = "c4d.duplicate_material"
    bl_label = "Duplicate"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _active_material(context) is not None

    def execute(self, context):
        new = _active_material(context).copy()
        new.use_fake_user = True
        if new.asset_data is None:
            new.asset_mark()
        return {'FINISHED'}


class C4D_OT_edit_material(bpy.types.Operator):
    """Show the active material in the Attribute Manager"""
    bl_idname = "c4d.edit_material"
    bl_label = "Edit Material"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return _active_material(context) is not None

    def execute(self, context):
        mat = _active_material(context)
        ob = context.active_object
        if ob is not None and hasattr(ob.data, "materials"):
            for i, slot in enumerate(ob.material_slots):
                if slot.material == mat:
                    ob.active_material_index = i
        for area in context.screen.areas:
            if area.type == 'PROPERTIES':
                try:
                    area.spaces.active.context = 'MATERIAL'
                except TypeError:
                    pass
        return {'FINISHED'}


class C4D_OT_remove_unused_materials(bpy.types.Operator):
    """Delete materials that no object uses"""
    bl_idname = "c4d.remove_unused_materials"
    bl_label = "Remove Unused Materials"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        used = set()
        for o in bpy.data.objects:
            for s in getattr(o, "material_slots", ()):
                if s.material:
                    used.add(s.material)
        removed = 0
        for m in list(bpy.data.materials):
            if m not in used and not m.library and not getattr(m, "is_grease_pencil", False):
                bpy.data.materials.remove(m)
                removed += 1
        self.report({'INFO'}, f"Removed {removed} material(s)")
        return {'FINISHED'}


class C4D_MT_mm_create(bpy.types.Menu):
    bl_idname = "C4D_MT_mm_create"
    bl_label = "Create"

    def draw(self, context):
        l = self.layout
        l.operator("c4d.new_material", icon='MATERIAL')
        l.separator()
        l.operator("wm.append", text="Load Materials...", icon='APPEND_BLEND')


class C4D_MT_mm_edit(bpy.types.Menu):
    bl_idname = "C4D_MT_mm_edit"
    bl_label = "Edit"

    def draw(self, context):
        l = self.layout
        l.operator("ed.undo")
        l.operator("ed.redo")
        l.separator()
        l.operator("c4d.duplicate_material")
        l.operator("c4d.remove_unused_materials")


class C4D_MT_mm_material(bpy.types.Menu):
    bl_idname = "C4D_MT_mm_material"
    bl_label = "Material"

    def draw(self, context):
        l = self.layout
        l.operator("c4d.edit_material_nodes", text="Edit Nodes (double-click)", icon='NODETREE')
        l.operator("c4d.apply_material")
        l.operator("c4d.edit_material", text="Edit (Attribute Manager)")
        l.operator("c4d.set_workspace", text="Material Editor (Shading)").name = "Shading"


def draw_header(layout, context):
    layout.template_header()
    row = layout.row(align=True)
    for m in ("C4D_MT_mm_create", "C4D_MT_mm_edit", "C4D_MT_mm_material"):
        row.menu(m)
    layout.separator_spacer()
    params = context.space_data.params
    if params is not None:
        layout.prop(params, "filter_search", text="", icon='VIEWZOOM')
    layout.prop(context.space_data, "show_region_tool_props", text="", icon='OBJECT_ORIGIN')


classes = (
    C4D_OT_new_material, C4D_OT_apply_material, C4D_OT_duplicate_material,
    C4D_OT_edit_material, C4D_OT_remove_unused_materials,
    C4D_MT_mm_create, C4D_MT_mm_edit, C4D_MT_mm_material,
)
