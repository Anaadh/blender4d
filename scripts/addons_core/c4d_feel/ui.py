"""C4D-style UI chrome:

- Command palette in the top bar (undo, tools, render, object-creation groups),
  with the workspace tabs replaced by a "Layout" dropdown like C4D.
- Mode palette at the top of the viewport's left toolbar
  (Make Editable, Model/Points/Edges/Polygons, Enable Axis, Snap, Solo).
- Coordinate Manager panel, shown in the Material Manager (Asset Browser)
  sidebar at the bottom of the C4D workspace.
- Material Manager: materials in the current file are marked as assets so the
  Asset Browser can show them as a drag-and-drop grid.
"""

import bpy
from bpy.app.handlers import persistent


# ---------------------------------------------------------------------------
# Operators used by the palettes
# ---------------------------------------------------------------------------

class C4D_OT_component_mode(bpy.types.Operator):
    """Switch to Model, Points, Edges or Polygons mode"""
    bl_idname = "c4d.component_mode"
    bl_label = "C4D Mode"
    bl_options = {'INTERNAL', 'UNDO'}

    mode: bpy.props.EnumProperty(items=[
        ('MODEL', "Model", ""), ('VERT', "Points", ""),
        ('EDGE', "Edges", ""), ('FACE', "Polygons", ""),
    ])

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        if self.mode == 'MODEL':
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            return {'FINISHED'}
        from .primitives import primitive_name
        ob = context.active_object
        if ob.type != 'MESH' or (context.mode == 'OBJECT' and primitive_name(ob)):
            self.report({'WARNING'}, "Parametric object: make it editable first (C)")
            return {'CANCELLED'}
        if context.mode != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type=self.mode, use_extend=False, use_expand=False)
        return {'FINISHED'}


# Generators / deformers are modifiers on the selected objects in Blender.
MODIFIERS = {
    'SUBSURF': ("Subdivision Surface", 'MOD_SUBSURF', {"levels": 2, "render_levels": 2}),
    'MIRROR': ("Symmetry", 'MOD_MIRROR', {}),
    'SCREW': ("Lathe", 'MOD_SCREW', {}),
    'SOLIDIFY': ("Extrude (Solidify)", 'MOD_SOLIDIFY', {"thickness": 0.1}),
    'BOOLEAN': ("Boolean", 'MOD_BOOLEAN', {}),
    'BEVEL': ("Bevel", 'MOD_BEVEL', {}),
    'REMESH': ("Volume Mesher (Remesh)", 'MOD_REMESH', {}),
    'ARRAY': ("Array", 'MOD_ARRAY', {"count": 3}),
    'BEND': ("Bend", 'MOD_SIMPLEDEFORM', {"deform_method": 'BEND'}),
    'TWIST': ("Twist", 'MOD_SIMPLEDEFORM', {"deform_method": 'TWIST'}),
    'TAPER': ("Taper", 'MOD_SIMPLEDEFORM', {"deform_method": 'TAPER'}),
    'STRETCH': ("Squash & Stretch", 'MOD_SIMPLEDEFORM', {"deform_method": 'STRETCH'}),
    'DISPLACE': ("Displacer", 'MOD_DISPLACE', {}),
    'WAVE': ("Wave", 'MOD_WAVE', {}),
    'SMOOTH': ("Smoothing", 'MOD_SMOOTH', {}),
    'SHRINKWRAP': ("Shrink Wrap", 'MOD_SHRINKWRAP', {}),
    'LATTICE': ("FFD (Lattice)", 'MOD_LATTICE', {}),
}
_MOD_TYPE = {'BEND': 'SIMPLE_DEFORM', 'TWIST': 'SIMPLE_DEFORM', 'TAPER': 'SIMPLE_DEFORM',
             'STRETCH': 'SIMPLE_DEFORM'}


class C4D_OT_add_modifier(bpy.types.Operator):
    """Add a generator/deformer (modifier) to the selected objects"""
    bl_idname = "c4d.add_modifier"
    bl_label = "Add Generator"
    bl_options = {'REGISTER', 'UNDO'}

    kind: bpy.props.EnumProperty(items=[(k, v[0], "") for k, v in MODIFIERS.items()])

    @classmethod
    def poll(cls, context):
        return any(o.type in {'MESH', 'CURVE', 'FONT', 'SURFACE'} for o in context.selected_objects)

    def execute(self, context):
        label, _icon, props = MODIFIERS[self.kind]
        mod_type = _MOD_TYPE.get(self.kind, self.kind)
        for o in context.selected_objects:
            if o.type not in {'MESH', 'CURVE', 'FONT', 'SURFACE'}:
                continue
            try:
                m = o.modifiers.new(label, mod_type)
            except (TypeError, RuntimeError):
                continue
            if m is None:
                continue
            for k, v in props.items():
                setattr(m, k, v)
        return {'FINISHED'}


class C4D_OT_add_floor(bpy.types.Operator):
    """Add a large ground plane (C4D Floor)"""
    bl_idname = "c4d.add_floor"
    bl_label = "Floor"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.mesh.primitive_plane_add(size=100.0, location=(0, 0, 0))
        context.active_object.name = "Floor"
        return {'FINISHED'}


class C4D_OT_set_workspace(bpy.types.Operator):
    """Switch layout"""
    bl_idname = "c4d.set_workspace"
    bl_label = "Switch Layout"
    bl_options = {'INTERNAL'}

    name: bpy.props.StringProperty()

    def execute(self, context):
        ws = bpy.data.workspaces.get(self.name)
        if ws:
            context.window.workspace = ws
        return {'FINISHED'}


def _is_render_settings_window(win, main):
    return win != main and any(
        a.type == 'PROPERTIES' and getattr(a.spaces.active, "context", "") in {'RENDER', 'OUTPUT'}
        for a in win.screen.areas) and len(win.screen.areas) == 1


class C4D_OT_render_settings(bpy.types.Operator):
    """Open the Render Settings window (C4D Edit Render Settings)"""
    bl_idname = "c4d.render_settings"
    bl_label = "Edit Render Settings"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from .winplace import open_floating_window
        wm = context.window_manager
        main = wm.windows[0]
        if any(_is_render_settings_window(w, main) for w in wm.windows):
            return {'FINISHED'}  # already open

        def configure(window):
            area = window.screen.areas[0]
            area.type = 'PROPERTIES'
            space = area.spaces.active
            # Render + Output tabs, like C4D's Render Settings (Output, Save, ...).
            for prop in space.bl_rna.properties.keys():
                if prop.startswith("show_properties_"):
                    setattr(space, prop, prop in {"show_properties_render", "show_properties_output",
                                                  "show_properties_view_layer"})
            space.context = 'RENDER'

        if open_floating_window(context, configure, 0.42, 0.75) is None:
            return {'CANCELLED'}
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Menus for the command palette groups
# ---------------------------------------------------------------------------

class C4D_MT_generators(bpy.types.Menu):
    bl_idname = "C4D_MT_generators"
    bl_label = "Generators"

    def draw(self, context):
        from .splines import GEN_SPECS, GEN_ICONS
        for k in GEN_SPECS:
            self.layout.operator("c4d.add_spline_generator", text=k, icon=GEN_ICONS[k]).kind = k
        self.layout.separator()
        for k in ('SUBSURF', 'MIRROR', 'BOOLEAN', 'BEVEL', 'SOLIDIFY', 'REMESH'):
            label, icon, _ = MODIFIERS[k]
            self.layout.operator("c4d.add_modifier", text=label, icon=icon).kind = k


class C4D_MT_array(bpy.types.Menu):
    bl_idname = "C4D_MT_array"
    bl_label = "Array"

    def draw(self, context):
        for mode in ("Linear", "Radial", "Grid"):
            self.layout.operator("c4d.add_cloner", text=f"Cloner ({mode})", icon='MOD_ARRAY').mode = mode
        self.layout.separator()
        label, icon, _ = MODIFIERS['ARRAY']
        self.layout.operator("c4d.add_modifier", text=label, icon=icon).kind = 'ARRAY'
        self.layout.operator("object.duplicates_make_real", text="Make Instances Real", icon='OUTLINER_OB_GROUP_INSTANCE')


class C4D_MT_deformers(bpy.types.Menu):
    bl_idname = "C4D_MT_deformers"
    bl_label = "Deformers"

    def draw(self, context):
        from .deformers import KINDS
        layout = self.layout
        layout.label(text="Deformer objects (child of selection)")
        for k, (label, _d, _m, _s) in KINDS.items():
            layout.operator("c4d.add_deformer", text=label, icon='MOD_SIMPLEDEFORM').kind = k
        layout.separator()
        layout.label(text="As modifier on selection")
        for k in ('BEND', 'TWIST', 'TAPER', 'STRETCH', 'DISPLACE', 'WAVE', 'SMOOTH', 'SHRINKWRAP', 'LATTICE'):
            label, icon, _ = MODIFIERS[k]
            layout.operator("c4d.add_modifier", text=label, icon=icon).kind = k


class C4D_MT_environment(bpy.types.Menu):
    bl_idname = "C4D_MT_environment"
    bl_label = "Environment"

    def draw(self, context):
        layout = self.layout
        layout.operator("c4d.add_floor", icon='MESH_PLANE')
        layout.operator("object.empty_add", text="Null", icon='EMPTY_AXIS').type = 'PLAIN_AXES'
        layout.operator("object.camera_add", text="Camera", icon='CAMERA_DATA')
        layout.separator()
        layout.menu("VIEW3D_MT_light_add", icon='LIGHT')


class C4D_MT_layouts(bpy.types.Menu):
    bl_idname = "C4D_MT_layouts"
    bl_label = "Layout"

    def draw(self, context):
        for ws in bpy.data.workspaces:
            self.layout.operator("c4d.set_workspace", text=ws.name,
                                 icon='WORKSPACE' if ws == context.window.workspace else 'NONE').name = ws.name


# ---------------------------------------------------------------------------
# Top bar: menus + command palette + Layout dropdown
# ---------------------------------------------------------------------------

_orig_draw_left = None
_orig_draw_right = None


def _topbar_left(self, context):
    layout = self.layout
    from bl_ui.space_topbar import TOPBAR_MT_editor_menus
    from .managers import c4d_active
    from .menubar import draw_main_menus
    if c4d_active(context):
        draw_main_menus(layout, context)
    else:
        TOPBAR_MT_editor_menus.draw_collapsible(context, layout)
    if context.screen.show_fullscreen:
        layout.operator("screen.back_to_previous", icon='SCREEN_BACK', text="Back to Previous")
        return

    if not palette_row_active(context):
        draw_palette(layout, context)


def palette_row_active(context):
    """Fork only: the palette has its own tall top-bar row."""
    screen = context.screen
    return getattr(screen, "show_c4d_palette", False)


def draw_palette(layout, context):
    """C4D command palette (undo, tools, axis locks, render, object groups)."""
    from .icons import icon as ic
    layout.separator(type='LINE')
    row = layout.row(align=True)
    row.operator("ed.undo", text="", icon_value=ic("undo"))
    row.operator("ed.redo", text="", icon_value=ic("redo"))

    layout.separator(type='LINE')
    tool = context.workspace.tools.from_space_view3d_mode(context.mode, create=False)
    active = tool.idname if tool else ""
    row = layout.row(align=True)
    for idname, name in (("builtin.select_circle", "live_select"), ("builtin.move", "move"),
                         ("builtin.scale", "scale"), ("builtin.rotate", "rotate")):
        row.operator("c4d.tool_set", text="", icon_value=ic(name), depress=(active == idname)).name = idname

    wm = context.window_manager
    slot = context.scene.transform_orientation_slots[0]
    row = layout.row(align=True)
    row.prop(wm, "c4d_lock_x", text="", icon_value=ic("axis_x"))
    row.prop(wm, "c4d_lock_y", text="", icon_value=ic("axis_y"))
    row.prop(wm, "c4d_lock_z", text="", icon_value=ic("axis_z"))
    row.operator("c4d.coord_toggle", text="",
                 icon_value=ic("coord_object" if slot.type == 'LOCAL' else "coord_world"))

    layout.separator(type='LINE')
    row = layout.row(align=True)
    row.operator("render.render", text="", icon_value=ic("render_view")).use_viewport = True
    row.operator("render.render", text="", icon_value=ic("render_pv"))
    row.operator("c4d.render_settings", text="", icon_value=ic("render_settings"))

    layout.separator(type='LINE')
    row = layout.row(align=True)
    row.menu("C4D_MT_primitives", text="", icon_value=ic("cube"))
    row.menu("C4D_MT_splines", text="", icon_value=ic("spline"))
    row.menu("C4D_MT_generators", text="", icon_value=ic("generator"))
    row.menu("C4D_MT_array", text="", icon_value=ic("array"))
    row.menu("C4D_MT_deformers", text="", icon_value=ic("deformer"))
    row.menu("C4D_MT_environment", text="", icon_value=ic("floor"))
    row.operator("object.camera_add", text="", icon_value=ic("camera"))
    row.menu("VIEW3D_MT_light_add", text="", icon_value=ic("light"))


class C4D_HT_palette(bpy.types.Header):
    """Big C4D command palette in the fork's second top-bar row."""
    bl_space_type = 'TOPBAR'
    bl_region_type = 'WINDOW'

    def draw(self, context):
        from .managers import c4d_active
        if not (c4d_active(context) and palette_row_active(context)):
            return
        layout = self.layout
        layout.scale_y = 1.7
        layout.scale_x = 1.7
        draw_palette(layout, context)


def _topbar_right(self, context):
    layout = self.layout
    screen = context.screen
    if not screen.show_statusbar:
        layout.template_reports_banner()
        layout.template_running_jobs()
    layout.label(text="Layout:")
    layout.menu("C4D_MT_layouts", text=context.window.workspace.name)
    layout.template_ID(context.window, "scene", new="scene.new", unlink="scene.delete")


# ---------------------------------------------------------------------------
# Coordinate Manager
# ---------------------------------------------------------------------------

def _draw_coordinates(layout, context):
    from . import coord
    coord.draw(layout, context)


class C4D_PT_coordinates(bpy.types.Panel):
    """Coordinate Manager in the Material Manager sidebar"""
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Coordinates"
    bl_order = -1

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space and space.browse_mode == 'ASSETS'

    def draw(self, context):
        _draw_coordinates(self.layout, context)


class C4D_PT_coordinates_view3d(bpy.types.Panel):
    """Coordinate Manager in the viewport sidebar (N~N)"""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "C4D"
    bl_label = "Coordinates"

    def draw(self, context):
        _draw_coordinates(self.layout, context)


# ---------------------------------------------------------------------------
# Material Manager: keep scene materials visible in the Asset Browser
# ---------------------------------------------------------------------------

def _mark_materials():
    for mat in bpy.data.materials:
        if mat.library or mat.asset_data or getattr(mat, "is_grease_pencil", False):
            continue
        mat.asset_mark()
        try:
            mat.asset_generate_preview()
        except (AttributeError, RuntimeError):
            pass


@persistent
def _on_depsgraph(scene, depsgraph):
    if any(isinstance(u.id, bpy.types.Material) for u in depsgraph.updates):
        _mark_materials()


@persistent
def _on_load(*_args):
    _mark_materials()


classes = (
    C4D_OT_component_mode,
    C4D_OT_add_modifier,
    C4D_OT_add_floor,
    C4D_OT_set_workspace,
    C4D_OT_render_settings,
    C4D_MT_generators,
    C4D_MT_array,
    C4D_MT_deformers,
    C4D_MT_environment,
    C4D_MT_layouts,
    C4D_HT_palette,
    C4D_PT_coordinates,
    C4D_PT_coordinates_view3d,
)


def register():
    global _orig_draw_left, _orig_draw_right
    for axis in "xyz":
        setattr(bpy.types.WindowManager, f"c4d_lock_{axis}", bpy.props.BoolProperty(
            name=f"{axis.upper()}-Axis", default=True,
            description=f"Allow dragging along {axis.upper()} with the hold-4/5/6 transforms"))
    top = bpy.types.TOPBAR_HT_upper_bar
    _orig_draw_left, _orig_draw_right = top.draw_left, top.draw_right
    top.draw_left, top.draw_right = _topbar_left, _topbar_right
    bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)
    bpy.app.handlers.load_post.append(_on_load)
    # ID data can't be edited during add-on registration; defer.
    bpy.app.timers.register(lambda: _mark_materials() or None, first_interval=0.5)


def unregister():
    for axis in "xyz":
        delattr(bpy.types.WindowManager, f"c4d_lock_{axis}")
    top = bpy.types.TOPBAR_HT_upper_bar
    if _orig_draw_left:
        top.draw_left, top.draw_right = _orig_draw_left, _orig_draw_right
    for lst, fn in ((bpy.app.handlers.depsgraph_update_post, _on_depsgraph),
                    (bpy.app.handlers.load_post, _on_load)):
        if fn in lst:
            lst.remove(fn)
