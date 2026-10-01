"""C4D manager chrome, active only in the "C4D" workspace:

- Viewport header with C4D menus (View, Cameras, Display, Options, Filter, Panel).
- Left toolbar replaced by the C4D mode palette.
- Object Manager (Outliner) header: File, Edit, View, Objects, Tags + search.
- Attribute Manager (Properties) header: Mode, Edit, User Data, and
  Basic / Coord. / Object tabs on the Object tab, hiding Blender's panels.

Blender's own headers/panels are wrapped, not replaced, so every other
workspace keeps the stock UI.
"""

import bpy

WORKSPACE = "C4D"


def c4d_active(context):
    ws = getattr(context, "workspace", None)
    return ws is not None and ws.name == WORKSPACE


# ---------------------------------------------------------------------------
# Viewport header menus
# ---------------------------------------------------------------------------

class C4D_MT_vp_view(bpy.types.Menu):
    bl_idname = "C4D_MT_vp_view"
    bl_label = "View"

    def draw(self, context):
        l = self.layout
        l.operator("view3d.view_all", text="Frame All").center = False
        l.operator("view3d.view_selected", text="Frame Selected Elements")
        l.operator("view3d.view_all", text="Frame Default").center = True
        l.separator()
        l.operator("view3d.view_center_cursor", text="Center on Cursor")
        l.operator("view3d.localview", text="Solo (Local View)")
        l.separator()
        l.operator("screen.screen_full_area", text="Maximize Panel")
        l.operator("view3d.toggle_xray", text="X-Ray")
        l.separator()
        l.prop(context.space_data, "show_region_ui", text="Sidebar")
        l.prop(context.space_data, "show_region_toolbar", text="Mode Palette")


class C4D_MT_vp_cameras(bpy.types.Menu):
    bl_idname = "C4D_MT_vp_cameras"
    bl_label = "Cameras"

    def draw(self, context):
        from .camera import looking_through
        l = self.layout
        l.operator("c4d.editor_camera", text="Editor Camera", icon='VIEW_PERSPECTIVE')
        cams = [o for o in context.scene.objects if o.type == 'CAMERA']
        if cams:
            col = l.column()
            for cam in cams:
                on = looking_through(context, cam)
                op = col.operator("c4d.look_through", text=cam.name,
                                  icon='VIEW_CAMERA' if on else 'VIEW_CAMERA_UNSELECTED')
                op.name = cam.name
        l.prop(context.window_manager, "c4d_camera_nav", text="Navigate Moves Camera")
        l.operator("view3d.camera_to_view", text="Align Camera to View")
        l.separator()
        l.operator("c4d.view_panel", text="Perspective").view = 'PERSP'
        l.operator("view3d.view_persportho", text="Parallel / Perspective")
        l.separator()
        for label, axis in (("Left", 'LEFT'), ("Right", 'RIGHT'), ("Front", 'FRONT'),
                            ("Back", 'BACK'), ("Top", 'TOP'), ("Bottom", 'BOTTOM')):
            l.operator("view3d.view_axis", text=label).type = axis


class C4D_MT_vp_display(bpy.types.Menu):
    bl_idname = "C4D_MT_vp_display"
    bl_label = "Display"

    def draw(self, context):
        l = self.layout
        sh = context.space_data.shading
        for mode, label in (('GOURAUD', "Gouraud Shading"), ('GOURAUD_LINES', "Gouraud Shading (Lines)"),
                            ('CONSTANT', "Constant Shading"), ('LINES', "Lines"),
                            ('TEXTURES', "Textures (Material Preview)")):
            l.operator("c4d.display_mode", text=label).mode = mode
        l.operator("c4d.interactive_render", text="Rendered")
        l.separator()
        l.prop(sh, "show_backface_culling", text="Backface Culling")
        l.prop(sh, "show_xray", text="X-Ray")
        l.prop(context.space_data.overlay, "show_wireframes", text="Show Lines")


class C4D_MT_vp_options(bpy.types.Menu):
    bl_idname = "C4D_MT_vp_options"
    bl_label = "Options"

    def draw(self, context):
        l = self.layout
        ov = context.space_data.overlay
        l.prop(ov, "show_overlays", text="Overlays")
        l.prop(ov, "show_stats", text="Statistics")
        l.prop(ov, "show_face_orientation", text="Normals")
        l.prop(ov, "show_bones", text="Bones")
        l.separator()
        l.popover("VIEW3D_PT_shading", text="Shading / Default Light")
        l.popover("VIEW3D_PT_overlay", text="Configure...")
        l.operator("wm.call_panel", text="Snap Settings...").name = "VIEW3D_PT_snapping"


class C4D_MT_vp_filter(bpy.types.Menu):
    bl_idname = "C4D_MT_vp_filter"
    bl_label = "Filter"

    def draw(self, context):
        l = self.layout
        sp = context.space_data
        ov = sp.overlay
        for prop, label in (("show_object_viewport_mesh", "Polygon Objects"),
                            ("show_object_viewport_curve", "Splines"),
                            ("show_object_viewport_empty", "Null"),
                            ("show_object_viewport_camera", "Camera"),
                            ("show_object_viewport_light", "Light"),
                            ("show_object_viewport_armature", "Joint"),
                            ("show_object_viewport_font", "Text")):
            if hasattr(sp, prop):
                l.prop(sp, prop, text=label)
        l.separator()
        l.prop(ov, "show_floor", text="Grid")
        l.prop(ov, "show_axis_x", text="World Axis X")
        l.prop(ov, "show_text", text="HUD")
        l.prop(sp, "show_gizmo", text="Gizmos")
        l.prop(ov, "show_outline_selected", text="Selection Outline")


class C4D_MT_vp_panel(bpy.types.Menu):
    bl_idname = "C4D_MT_vp_panel"
    bl_label = "Panel"

    def draw(self, context):
        l = self.layout
        l.operator("c4d.view_panel", text="Single View").view = 'PERSP'
        l.operator("c4d.view_panel", text="4 Views").view = 'ALL'
        l.separator()
        l.operator("screen.area_dupli", text="New View Panel...")


class C4D_OT_set_camera(bpy.types.Operator):
    """Look through this camera"""
    bl_idname = "c4d.set_camera"
    bl_label = "Use Camera"
    bl_options = {'INTERNAL'}

    name: bpy.props.StringProperty()

    def execute(self, context):
        from .camera import enter_camera
        cam = context.scene.objects.get(self.name)
        if cam is None:
            return {'CANCELLED'}
        enter_camera(context, cam)
        return {'FINISHED'}


def draw_viewport_header(self, context):
    layout = self.layout
    layout.template_header()
    row = layout.row(align=True)
    for m in ("C4D_MT_vp_view", "C4D_MT_vp_cameras", "C4D_MT_vp_display",
              "C4D_MT_vp_options", "C4D_MT_vp_filter", "C4D_MT_vp_panel"):
        row.menu(m)
    layout.separator_spacer()
    # Keep Blender's object-interaction mode visible (sculpt, paint, ...), compact.
    obj = context.active_object
    if obj is not None:
        layout.operator_menu_enum("object.mode_set", "mode", text="",
                                  icon='OBJECT_DATAMODE' if obj.mode == 'OBJECT' else 'EDITMODE_HLT')


# ---------------------------------------------------------------------------
# Left mode palette (replaces Blender's toolbar in the C4D workspace)
# ---------------------------------------------------------------------------

def draw_mode_palette(layout, context):
    from .icons import icon as ic
    col = layout.column(align=True)
    col.scale_y = 1.35
    mode = context.mode
    ts = context.tool_settings
    sel = ts.mesh_select_mode if mode == 'EDIT_MESH' else (False, False, False)

    col.operator("c4d.make_editable", text="", icon_value=ic("make_editable"))
    col.separator(factor=1.5)
    col.operator("c4d.component_mode", text="", icon_value=ic("mode_model"), depress=(mode == 'OBJECT')).mode = 'MODEL'
    col.operator("c4d.set_workspace", text="", icon_value=ic("mode_uv")).name = "UV Editing"
    col.operator("c4d.component_mode", text="", icon_value=ic("mode_points"), depress=sel[0]).mode = 'VERT'
    col.operator("c4d.component_mode", text="", icon_value=ic("mode_edges"), depress=sel[1]).mode = 'EDGE'
    col.operator("c4d.component_mode", text="", icon_value=ic("mode_polygons"), depress=sel[2]).mode = 'FACE'
    col.separator(factor=1.5)
    col.prop(ts, "use_transform_data_origin", text="", icon_value=ic("axis_mode"))  # Enable Axis
    col.separator(factor=1.5)
    sp = context.space_data
    local = sp is not None and getattr(sp, "local_view", None) is not None
    col.operator("view3d.localview", text="", icon_value=ic("solo_on" if local else "solo_off"), depress=local)
    col.separator(factor=1.5)
    col.prop(ts, "use_snap", text="", icon_value=ic("snap_on" if ts.use_snap else "snap_off"))
    col.separator(factor=1.5)
    if sp is not None and sp.type == 'VIEW_3D':
        col.prop(sp.overlay, "show_floor", text="", icon_value=ic("workplane"))  # Workplane


# ---------------------------------------------------------------------------
# Object Manager header
# ---------------------------------------------------------------------------

class C4D_MT_om_file(bpy.types.Menu):
    bl_idname = "C4D_MT_om_file"
    bl_label = "File"

    def draw(self, context):
        l = self.layout
        l.operator("wm.append", text="Merge Objects...", icon='APPEND_BLEND')
        l.operator("wm.link", text="Link Objects...")
        l.menu("TOPBAR_MT_file_import", text="Import")
        l.menu("TOPBAR_MT_file_export", text="Export")


class C4D_MT_om_edit(bpy.types.Menu):
    bl_idname = "C4D_MT_om_edit"
    bl_label = "Edit"

    def draw(self, context):
        l = self.layout
        l.operator("ed.undo")
        l.operator("ed.redo")
        l.separator()
        l.operator("outliner.id_copy", text="Copy")
        l.operator("outliner.id_paste", text="Paste")
        l.operator("outliner.delete", text="Delete")
        l.separator()
        l.operator("outliner.select_all", text="Select All").action = 'SELECT'
        l.operator("outliner.select_all", text="Deselect All").action = 'DESELECT'


class C4D_MT_om_view(bpy.types.Menu):
    bl_idname = "C4D_MT_om_view"
    bl_label = "View"

    def draw(self, context):
        l = self.layout
        l.operator("outliner.show_active", text="Scroll to Active (S)")
        l.operator("outliner.expanded_toggle", text="Fold / Unfold All")
        l.operator("outliner.show_one_level", text="Unfold One Level")
        l.operator("outliner.show_one_level", text="Fold One Level").open = False
        l.separator()
        sp = context.space_data
        l.prop(sp, "use_filter_collection", text="Show Collections (Layers)")
        l.prop(sp, "use_filter_children", text="Show Hierarchy")
        l.prop(sp, "show_restrict_column_select", text="Selectable Column")
        l.popover("OUTLINER_PT_filter", text="Filter...")


class C4D_MT_om_objects(bpy.types.Menu):
    bl_idname = "C4D_MT_om_objects"
    bl_label = "Objects"

    def draw(self, context):
        l = self.layout
        l.operator("c4d.group", text="Group Objects  Alt+G")
        l.operator("c4d.ungroup", text="Expand Object Group  Shift+G")
        l.operator("c4d.make_editable", text="Make Editable  C")
        l.operator("object.join", text="Connect Objects + Delete")
        l.separator()
        l.operator("outliner.item_rename", text="Rename")
        l.operator("object.duplicate_move", text="Duplicate")
        l.separator()
        l.operator("object.hide_view_set", text="Hide in Editor")
        l.operator("object.hide_view_clear", text="Unhide All")


class C4D_MT_om_tags(bpy.types.Menu):
    bl_idname = "C4D_MT_om_tags"
    bl_label = "Tags"

    def draw(self, context):
        l = self.layout
        l.menu("C4D_MT_tags", text="C4D Tags", icon='BOOKMARKS')
        l.separator()
        l.operator_menu_enum("object.modifier_add", "type", text="Generator / Deformer Tags")
        l.operator_menu_enum("object.constraint_add", "type", text="Constraint Tags")
        l.separator()
        l.operator("object.material_slot_add", text="Texture Tag (Material Slot)")
        l.operator("object.shade_smooth", text="Phong (Shade Smooth)")
        l.operator("object.shade_flat", text="Remove Phong (Shade Flat)")


def draw_outliner_header(self, context):
    layout = self.layout
    layout.template_header()
    draw_manager_tabs(layout, context)
    row = layout.row(align=True)
    for m in ("C4D_MT_om_file", "C4D_MT_om_edit", "C4D_MT_om_view", "C4D_MT_om_objects", "C4D_MT_om_tags"):
        row.menu(m)
    layout.separator_spacer()
    sp = context.space_data
    row = layout.row(align=True)
    row.prop(sp, "filter_text", icon='VIEWZOOM', text="")
    row.popover("OUTLINER_PT_filter", text="", icon='FILTER')


# ---------------------------------------------------------------------------
# Attribute Manager
# ---------------------------------------------------------------------------

class C4D_MT_am_mode(bpy.types.Menu):
    bl_idname = "C4D_MT_am_mode"
    bl_label = "Mode"

    def draw(self, context):
        l = self.layout
        sp = context.space_data
        for ctx, label in (('OBJECT', "Object"), ('MODIFIER', "Generators / Deformers"),
                           ('MATERIAL', "Material"), ('DATA', "Object Data"),
                           ('CONSTRAINT', "Constraints"), ('PHYSICS', "Simulation"),
                           ('SCENE', "Project"), ('RENDER', "Render Settings"),
                           ('OUTPUT', "Output"), ('WORLD', "World / Sky"), ('TOOL', "Tool")):
            op = l.operator("c4d.am_context", text=label,
                            icon='CHECKMARK' if sp.context == ctx else 'BLANK1')
            op.context = ctx


class C4D_OT_am_context(bpy.types.Operator):
    """Show this in the Attribute Manager"""
    bl_idname = "c4d.am_context"
    bl_label = "Attribute Manager Mode"
    bl_options = {'INTERNAL'}

    context: bpy.props.StringProperty()

    def execute(self, context):
        try:
            context.space_data.context = self.context
        except TypeError:
            self.report({'INFO'}, "Nothing to show for the current selection")
            return {'CANCELLED'}
        return {'FINISHED'}


class C4D_MT_am_userdata(bpy.types.Menu):
    bl_idname = "C4D_MT_am_userdata"
    bl_label = "User Data"

    def draw(self, context):
        l = self.layout
        op = l.operator("wm.properties_add", text="Add User Data...")
        op.data_path = "object"
        l.operator("c4d.am_tab", text="Manage User Data...").tab = 'BLENDER'


def draw_properties_header(self, context):
    layout = self.layout
    layout.template_header()
    draw_manager_tabs(layout, context)
    if _column_slot(context) == 'UPPER':  # custom Object Manager
        row = layout.row(align=True)
        for m in ("C4D_MT_om_file", "C4D_MT_om_edit", "C4D_MT_om_objects", "C4D_MT_om_tags"):
            row.menu(m)
        return
    row = layout.row(align=True)
    row.menu("C4D_MT_am_mode")
    row.menu("C4D_MT_am_userdata")
    layout.separator_spacer()
    sp = context.space_data
    layout.prop(sp, "search_filter", icon='VIEWZOOM', text="")
    layout.prop(sp, "use_pin_id", text="", icon='PINNED' if sp.use_pin_id else 'UNPINNED', emboss=False)


AM_TABS = [
    ('BASIC', "Basic", ""),
    ('COORD', "Coord.", ""),
    ('OBJECT', "Object", ""),
    ('PHONG', "Phong", ""),
    ('BLENDER', "All", "Blender's full object properties"),
]


class C4D_OT_am_tab(bpy.types.Operator):
    bl_idname = "c4d.am_tab"
    bl_label = "Attribute Tab"
    bl_options = {'INTERNAL'}

    tab: bpy.props.StringProperty()

    def execute(self, context):
        context.window_manager.c4d_am_tab = self.tab
        return {'FINISHED'}


def _am_filtering(context):
    return c4d_active(context) and context.window_manager.c4d_am_tab != 'BLENDER'


class C4D_PT_attributes(bpy.types.Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Attributes"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        return c4d_active(context) and context.object is not None

    def draw(self, context):
        layout = self.layout
        ob = context.object
        wm = context.window_manager

        head = layout.row()
        head.label(text=f"{_type_label(ob)} Object [{ob.name}]", icon=_type_icon(ob))

        from .tags import custom_tags, draw_tag_settings
        if wm.c4d_active_tag and wm.c4d_active_tag in custom_tags(ob):
            draw_tag_settings(layout, ob, wm.c4d_active_tag)
            layout.separator()
            op = layout.operator("wm.context_set_string", text="Back to Object", icon='BACK')
            op.data_path, op.value = "window_manager.c4d_active_tag", ""
            return
        row = layout.row(align=True)
        row.scale_y = 1.1
        row.prop(wm, "c4d_am_tab", expand=True)

        tab = wm.c4d_am_tab
        if tab == 'BLENDER':
            return
        box = layout.column()
        box.use_property_split = True
        box.use_property_decorate = True
        if tab == 'BASIC':
            _draw_basic(box, ob)
        elif tab == 'COORD':
            _draw_coord(box, ob)
        elif tab == 'OBJECT':
            _draw_object(box, context, ob)
        elif tab == 'PHONG':
            _draw_phong(box, ob)


def _type_label(ob):
    from .primitives import primitive_name
    from .splines import kind_of
    from .deformers import KINDS as DEFORMERS
    prim = (primitive_name(ob) or (kind_of(ob) or (None, None))[1]
            or (DEFORMERS[ob["c4d_deformer"]][0] if ob.get("c4d_deformer") in DEFORMERS else None))
    if prim:
        return prim
    return {'MESH': "Polygon", 'EMPTY': "Null", 'CURVE': "Spline", 'LIGHT': "Light",
            'CAMERA': "Camera", 'FONT': "Text", 'ARMATURE': "Joint"}.get(ob.type, ob.type.title())


def _type_icon(ob):
    return {'MESH': 'OUTLINER_OB_MESH', 'EMPTY': 'OUTLINER_OB_EMPTY', 'CURVE': 'OUTLINER_OB_CURVE',
            'LIGHT': 'OUTLINER_OB_LIGHT', 'CAMERA': 'OUTLINER_OB_CAMERA',
            'FONT': 'OUTLINER_OB_FONT'}.get(ob.type, 'OBJECT_DATA')


def _draw_basic(col, ob):
    col.prop(ob, "name")
    col.prop(ob, "hide_viewport", text="Visible in Editor", invert_checkbox=True)
    col.prop(ob, "hide_render", text="Visible in Renderer", invert_checkbox=True)
    col.prop(ob, "color", text="Display Color")
    col.prop(ob, "display_type", text="Display")
    col.prop(ob, "show_in_front", text="X-Ray")
    col.prop(ob, "show_name", text="Show Name")
    if ob.users_collection:
        col.label(text="Layer: " + ", ".join(c.name for c in ob.users_collection), icon='OUTLINER_COLLECTION')


def _draw_coord(col, ob):
    col.prop(ob, "location", text="P")
    col.prop(ob, "scale", text="S")
    col.prop(ob, "rotation_euler", text="R")
    col.prop(ob, "rotation_mode", text="Order")
    col.separator()
    sub = col.column(heading="Freeze Transformation")
    sub.prop(ob, "delta_location", text="Frozen P")
    sub.prop(ob, "delta_scale", text="Frozen S")
    sub.prop(ob, "delta_rotation_euler", text="Frozen R")
    col.operator("object.transform_apply", text="Freeze All").properties = True


def _draw_object(col, context, ob):
    data = ob.data
    if ob.type == 'EMPTY':
        from .deformers import deformer_modifier
        dm = deformer_modifier(ob)
        if dm is not None:
            col.label(text=f"Deforming: {ob.parent.name}", icon='MOD_SIMPLEDEFORM')
            _draw_modifier_props(col, dm)
            return
        col.prop(ob, "empty_display_type", text="Display")
        col.prop(ob, "empty_display_size", text="Radius")
    elif ob.type == 'CAMERA':
        col.prop(data, "type", text="Projection")
        col.prop(data, "lens", text="Focal Length")
        col.prop(data, "sensor_width", text="Sensor Size")
        col.prop(data, "clip_start")
        col.prop(data, "clip_end")
    elif ob.type == 'LIGHT':
        col.prop(data, "type")
        col.prop(data, "color")
        col.prop(data, "energy", text="Intensity")
        if hasattr(data, "shadow_soft_size"):
            col.prop(data, "shadow_soft_size", text="Radius")
    elif ob.type == 'MESH':
        from .primitives import primitive_name, draw_attributes, PREFIX
        from .splines import kind_of
        if primitive_name(ob) or kind_of(ob):
            draw_attributes(col, ob)
            col.separator()
            col.operator("c4d.make_editable", text="Make Editable (C)", icon='MESH_DATA')
            extra = [m for m in ob.modifiers
                     if not (m.type == 'NODES' and m.node_group and m.node_group.name.startswith(PREFIX))
                     and not (m.type == 'BEVEL' and "Fillet" in m.name)]
            _draw_modifier_boxes(col, extra)
            return
        me = data
        col.label(text=f"Points {len(me.vertices)}   Polygons {len(me.polygons)}")
        if not ob.modifiers:
            col.label(text="Editable polygon object. Add generators from the palette or Tags menu.")
    elif ob.type in {'CURVE', 'FONT'}:
        col.prop(data, "dimensions", text="Type")
        col.prop(data, "resolution_u", text="Intermediate Points")
        col.prop(data, "extrude")
        col.prop(data, "bevel_depth", text="Caps Size")
    # Generators / deformers act as the object's "Object" parameters.
    _draw_modifier_boxes(col, ob.modifiers)


def _draw_modifier_boxes(col, modifiers):
    for m in modifiers:
        box = col.box()
        r = box.row()
        r.prop(m, "show_expanded", text="", emboss=False)
        r.label(text=m.name, icon='MODIFIER')
        r.prop(m, "show_viewport", text="")
        r.prop(m, "show_render", text="")
        r.operator("object.modifier_remove", text="", icon='X', emboss=False).modifier = m.name
        if m.show_expanded:
            if m.type == 'NODES':
                from .cloner import draw_nodes_modifier
                draw_nodes_modifier(box, m)
            else:
                _draw_modifier_props(box, m)


_SKIP = {"rna_type", "name", "type", "show_viewport", "show_render", "show_in_editmode",
         "show_on_cage", "show_expanded", "is_active", "is_override_data", "use_apply_on_spline",
         "persistent_uid", "execution_time", "use_pin_to_last", "is_override_data_editable"}


def _draw_modifier_props(layout, m):
    for p in m.bl_rna.properties:
        if p.identifier in _SKIP or p.is_readonly or p.identifier.startswith("open_"):
            continue
        if p.type in {'POINTER', 'COLLECTION'} and p.identifier not in {"object", "offset_object", "mirror_object", "texture"}:
            continue
        layout.prop(m, p.identifier)


def _draw_phong(col, ob):
    col.operator("object.shade_smooth", text="Phong (Smooth)")
    col.operator("object.shade_flat", text="Flat")
    if ob.type == 'MESH':
        col.operator("object.shade_auto_smooth", text="Phong Angle (Auto Smooth)")


# ---------------------------------------------------------------------------
# Manager tabs (C4D's tab strip on the right edge; Blender can't rotate text,
# so the tabs sit at the start of each right-column header)
# ---------------------------------------------------------------------------

UPPER_TABS = (
    ('OBJECTS', "Objects", 'PROPERTIES'),
    ('OUTLINER', "Outliner", 'OUTLINER'),
    ('CONTENT', "Content Browser", 'ASSETS'),
    ('STRUCTURE', "Structure", 'SPREADSHEET'),
)
LOWER_TABS = (
    ('ATTRIBUTES', "Attributes", 'PROPERTIES'),
    ('LAYERS', "Layers", 'OUTLINER'),
)


def native_object_manager():
    """True on the C4D Blender fork, whose Outliner draws C4D columns natively."""
    return "use_c4d_style" in bpy.types.SpaceOutliner.bl_rna.properties


def _upper_tabs():
    if native_object_manager():
        # Objects = native C4D Outliner (keeps drag & drop); Outliner = stock.
        return (('OBJECTS', "Objects", 'OUTLINER'),) + UPPER_TABS[1:]
    return UPPER_TABS


def _column_slot(context):
    """'UPPER' / 'LOWER' for areas in the right column, else None."""
    area, window = context.area, context.window
    if area is None or window is None:
        return None
    if area.x + area.width / 2 < window.width * 0.6:
        return None
    return 'UPPER' if area.y + area.height / 2 > window.height / 2 else 'LOWER'


def _current_tab(context, slot):
    area = context.area
    if slot == 'UPPER':
        if area.ui_type == 'OUTLINER' and getattr(area.spaces.active, "use_c4d_style", False):
            return 'OBJECTS'
        return {'PROPERTIES': 'OBJECTS', 'OUTLINER': 'OUTLINER', 'ASSETS': 'CONTENT',
                'SPREADSHEET': 'STRUCTURE'}.get(area.ui_type)
    return {'PROPERTIES': 'ATTRIBUTES', 'OUTLINER': 'LAYERS'}.get(area.ui_type)


def draw_manager_tabs(layout, context):
    if not c4d_active(context):
        return
    slot = _column_slot(context)
    if slot is None:
        return
    current = _current_tab(context, slot)
    row = layout.row(align=True)
    for key, label, _ui in (_upper_tabs() if slot == 'UPPER' else LOWER_TABS):
        row.operator("c4d.manager_tab", text=label, depress=(key == current)).tab = key
    layout.separator()


def configure_object_manager(sp):
    """Outliner as C4D Object Manager: hierarchy only, two visibility columns, tags."""
    sp.display_mode = 'VIEW_LAYER'
    sp.use_filter_collection = False
    sp.use_filter_object = True
    sp.use_filter_children = True
    if hasattr(sp, "use_c4d_style"):
        sp.use_c4d_style = False
    sp.use_filter_object_content = True   # modifiers / constraints = "tags"
    for prop, on in (("show_restrict_column_hide", True),      # editor dot
                     ("show_restrict_column_render", True),    # render dot
                     ("show_restrict_column_viewport", False),
                     ("show_restrict_column_select", False),
                     ("show_restrict_column_enable", False)):
        if hasattr(sp, prop):
            setattr(sp, prop, on)


def configure_native_object_manager(sp):
    """Fork only: Outliner with native C4D columns; tags drawn as icons, not children."""
    sp.display_mode = 'VIEW_LAYER'
    sp.use_filter_collection = False
    sp.use_filter_object = True
    sp.use_filter_children = True
    sp.use_filter_object_content = False
    sp.use_c4d_style = True


def _configure_tab(window, area, tab):
    sp = area.spaces.active
    if tab == 'OBJECTS' and area.type == 'OUTLINER':
        configure_native_object_manager(sp)
    elif tab == 'OBJECTS':
        from .om import configure_space
        configure_space(sp)
    elif tab == 'OUTLINER':
        configure_object_manager(sp)
    elif tab == 'LAYERS':
        sp.display_mode = 'VIEW_LAYER'
        sp.use_filter_collection = True
        sp.use_filter_object = False
    elif tab == 'STRUCTURE':
        sp.show_region_toolbar = False
    elif tab == 'CONTENT' and sp.params is not None:
        try:
            sp.params.asset_library_reference = 'ALL'
        except TypeError:
            pass


class C4D_OT_manager_tab(bpy.types.Operator):
    """Switch this manager"""
    bl_idname = "c4d.manager_tab"
    bl_label = "Manager Tab"
    bl_options = {'INTERNAL'}

    tab: bpy.props.StringProperty()

    def execute(self, context):
        area, window = context.area, context.window
        ui = {k: u for k, _l, u in UPPER_TABS + LOWER_TABS}.get(self.tab)
        if self.tab == 'OBJECTS' and native_object_manager():
            ui = 'OUTLINER'
        if ui is None:
            return {'CANCELLED'}
        area.ui_type = ui
        tab = self.tab

        # The new space's settings exist only after the switch lands.
        def later():
            try:
                _configure_tab(window, area, tab)
            except (ReferenceError, AttributeError):
                pass
            return None
        bpy.app.timers.register(later, first_interval=0.05)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Wrapping Blender classes (only affects the C4D workspace)
# ---------------------------------------------------------------------------

_saved = {}  # (cls, attr) -> original


def _wrap_draw(cls, replacement):
    orig = cls.draw
    _saved[(cls, "draw")] = orig

    def draw(self, context):
        if c4d_active(context):
            replacement(self, context)
        else:
            orig(self, context)
    cls.draw = draw


def _wrap_prefix(cls, prefix):
    """Draw `prefix` before the original header (C4D workspace only)."""
    orig = cls.draw
    _saved[(cls, "draw")] = orig

    def draw(self, context):
        prefix(self.layout, context)
        orig(self, context)
    cls.draw = draw


def _wrap_filebrowser_header():
    """Asset strip: Material Manager menus bottom-left, manager tabs on the right."""
    cls = bpy.types.FILEBROWSER_HT_header
    orig = cls.draw
    _saved[(cls, "draw")] = orig

    def draw(self, context):
        if c4d_active(context) and _column_slot(context) is None and context.area.ui_type == 'ASSETS':
            from .matmanager import draw_header
            draw_header(self.layout, context)
            return
        draw_manager_tabs(self.layout, context)
        orig(self, context)
    cls.draw = draw


def _toolbar_draw_factory(orig):
    # C4D mode palette on top, then every Blender tool for the current mode
    # (knife, poly build, sculpt/paint brushes...) so nothing is lost.
    def draw(self, context):
        if c4d_active(context) and context.mode in {'OBJECT', 'EDIT_MESH'}:
            draw_mode_palette(self.layout, context)
            self.layout.separator(factor=2.0)
        orig(self, context)
    return draw


_wrapped_panels = []


def _hide_scene_panels(context):
    from .om import om_area
    return om_area(context)


def _wrap_object_panels():
    """Hide Blender's Object-tab panels in the C4D workspace (except 'All' tab).

    Panel poll functions are bound at registration, so the panels are
    re-registered with a wrapped poll.
    """
    from bl_ui import properties_object, properties_scene
    obj_panels = [c for c in properties_object.classes
                  if issubclass(c, bpy.types.Panel) and getattr(c, "bl_context", "") == "object"]
    scene_panels = [c for c in properties_scene.classes
                    if issubclass(c, bpy.types.Panel) and getattr(c, "bl_context", "") == "scene"]
    _rewrap(obj_panels, _am_filtering)
    _rewrap(scene_panels, _hide_scene_panels)


def _rewrap(panels, hide):
    for c in reversed(panels):
        bpy.utils.unregister_class(c)
    for c in panels:
        had = "poll" in c.__dict__
        orig = c.__dict__.get("poll")
        _wrapped_panels.append((c, had, orig))
        base_poll = getattr(c, "poll", None)

        def make(base_poll):
            def poll(cls, context):
                if hide(context):
                    return False
                return base_poll(context) if base_poll else True
            return classmethod(poll)
        c.poll = make(base_poll)
        bpy.utils.register_class(c)


def _unwrap_object_panels():
    for c, _had, _orig in reversed(_wrapped_panels):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
    for c, had, orig in _wrapped_panels:
        if had:
            c.poll = orig
        else:
            del c.poll
        bpy.utils.register_class(c)
    _wrapped_panels.clear()


classes = (
    C4D_MT_vp_view, C4D_MT_vp_cameras, C4D_MT_vp_display, C4D_MT_vp_options,
    C4D_MT_vp_filter, C4D_MT_vp_panel, C4D_OT_set_camera,
    C4D_MT_om_file, C4D_MT_om_edit, C4D_MT_om_view, C4D_MT_om_objects, C4D_MT_om_tags,
    C4D_MT_am_mode, C4D_OT_am_context, C4D_MT_am_userdata, C4D_OT_am_tab,
    C4D_PT_attributes, C4D_OT_manager_tab,
)


def register():
    bpy.types.WindowManager.c4d_am_tab = bpy.props.EnumProperty(items=AM_TABS, default='BASIC')

    _wrap_draw(bpy.types.VIEW3D_HT_header, draw_viewport_header)
    _wrap_draw(bpy.types.OUTLINER_HT_header, draw_outliner_header)
    _wrap_draw(bpy.types.PROPERTIES_HT_header, draw_properties_header)
    _wrap_filebrowser_header()
    _wrap_prefix(bpy.types.SPREADSHEET_HT_header, draw_manager_tabs)

    tb = bpy.types.VIEW3D_PT_tools_active
    _saved[(tb, "draw")] = tb.draw
    tb.draw = _toolbar_draw_factory(tb.draw)

    _wrap_object_panels()


def unregister():
    _unwrap_object_panels()
    for (cls, attr), orig in _saved.items():
        setattr(cls, attr, orig)
    _saved.clear()
    del bpy.types.WindowManager.c4d_am_tab
