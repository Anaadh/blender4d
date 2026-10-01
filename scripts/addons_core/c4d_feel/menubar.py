"""C4D R24 main menu bar (replaces Blender's top menus in the C4D workspace)."""

import bpy


def _cmd(layout, prefix, key, text):
    op = layout.operator("c4d.chord_cmd", text=f"{text}\t{prefix}~{key}")
    op.prefix = prefix
    op.key = key


class C4D_MT_main_create(bpy.types.Menu):
    bl_idname = "C4D_MT_main_create"
    bl_label = "Create"

    def draw(self, context):
        l = self.layout
        l.menu("C4D_MT_primitives", text="Mesh (Primitives)", icon='MESH_CUBE')
        l.menu("C4D_MT_splines", text="Spline", icon='CURVE_BEZCURVE')
        l.menu("C4D_MT_generators", text="Generators", icon='MOD_SUBSURF')
        l.menu("C4D_MT_array", text="Array / Instances", icon='MOD_ARRAY')
        l.menu("C4D_MT_deformers", text="Deformers", icon='MOD_SIMPLEDEFORM')
        l.separator()
        l.operator("object.empty_add", text="Null", icon='EMPTY_AXIS').type = 'PLAIN_AXES'
        l.operator("object.text_add", text="Text", icon='OUTLINER_OB_FONT')
        l.menu("C4D_MT_environment", text="Environment", icon='WORLD')
        l.operator("object.camera_add", text="Camera", icon='CAMERA_DATA')
        l.menu("VIEW3D_MT_light_add", text="Light", icon='LIGHT')
        l.separator()
        l.operator("material.new", text="New Material", icon='MATERIAL')


class C4D_MT_main_modes(bpy.types.Menu):
    bl_idname = "C4D_MT_main_modes"
    bl_label = "Modes"

    def draw(self, context):
        l = self.layout
        for mode, label, icon in (('MODEL', "Model", 'OBJECT_DATAMODE'), ('VERT', "Points", 'VERTEXSEL'),
                                  ('EDGE', "Edges", 'EDGESEL'), ('FACE', "Polygons", 'FACESEL')):
            l.operator("c4d.component_mode", text=label, icon=icon).mode = mode
        l.operator("c4d.set_workspace", text="UV Mode", icon='UV').name = "UV Editing"
        l.separator()
        l.prop(context.tool_settings, "use_transform_data_origin", text="Enable Axis")
        l.operator("object.origin_set", text="Center Axis to Geometry").type = 'ORIGIN_GEOMETRY'
        l.separator()
        l.operator_menu_enum("object.mode_set", "mode", text="Blender Mode")


class C4D_MT_main_select(bpy.types.Menu):
    bl_idname = "C4D_MT_main_select"
    bl_label = "Select"

    def draw(self, context):
        l = self.layout
        edit = context.mode == 'EDIT_MESH'
        l.operator("c4d.tool_set", text="Live Selection\t9").name = "builtin.select_circle"
        l.operator("c4d.tool_set", text="Rectangle Selection\t0").name = "builtin.select_box"
        l.operator("c4d.tool_set", text="Lasso Selection\t8").name = "builtin.select_lasso"
        l.separator()
        if edit:
            l.operator("mesh.select_all", text="Select All\tCtrl+A").action = 'SELECT'
            l.operator("mesh.select_all", text="Deselect All\tCtrl+Shift+A").action = 'DESELECT'
            for key, text in (('I', "Invert"), ('W', "Select Connected"), ('Y', "Grow Selection"),
                              ('K', "Shrink Selection"), ('L', "Loop Selection"), ('B', "Ring Selection"),
                              ('F', "Fill Selection"), ('Q', "Outline Selection")):
                _cmd(l, 'U', key, text)
            l.separator()
            l.operator("mesh.select_random", text="Random")
            l.operator("mesh.select_similar", text="Select Similar")
        else:
            l.operator("object.select_all", text="Select All\tCtrl+A").action = 'SELECT'
            l.operator("object.select_all", text="Deselect All\tCtrl+Shift+A").action = 'DESELECT'
            l.operator("object.select_all", text="Invert").action = 'INVERT'
            l.separator()
            l.operator_menu_enum("object.select_by_type", "type", text="Select by Type")
            l.operator("object.select_hierarchy", text="Select Children").direction = 'CHILD'
            l.operator("object.select_hierarchy", text="Select Parent").direction = 'PARENT'


class C4D_MT_main_tools(bpy.types.Menu):
    bl_idname = "C4D_MT_main_tools"
    bl_label = "Tools"

    def draw(self, context):
        l = self.layout
        for idname, text in (("builtin.move", "Move\tE"), ("builtin.scale", "Scale\tT"),
                             ("builtin.rotate", "Rotate\tR"), ("builtin.transform", "Transform")):
            l.operator("c4d.tool_set", text=text).name = idname
        l.separator()
        l.operator("wm.call_panel", text="Snap Settings\tP").name = "VIEW3D_PT_snapping"
        l.operator("c4d.coord_toggle", text="World / Object Coordinates\tW")
        l.separator()
        l.operator("c4d.tool_set", text="Measure").name = "builtin.measure"
        l.operator("c4d.tool_set", text="Annotate (Doodle)").name = "builtin.annotate"
        l.separator()
        l.menu("VIEW3D_MT_object_apply", text="Arrange / Apply")
        l.menu("VIEW3D_MT_snap", text="Snap To")


class C4D_MT_main_mesh(bpy.types.Menu):
    bl_idname = "C4D_MT_main_mesh"
    bl_label = "Mesh"

    def draw(self, context):
        l = self.layout
        l.operator("c4d.make_editable", text="Make Editable\tC")
        l.operator("object.convert", text="Current State to Object").target = 'MESH'
        l.operator("object.join", text="Connect Objects + Delete")
        l.separator()
        l.label(text="Create Tools")
        for key, text in (('E', "Polygon Pen"), ('K', "Line Cut"), ('L', "Loop/Path Cut"),
                          ('J', "Plane Cut"), ('B', "Bridge"), ('D', "Close Polygon Hole"),
                          ('A', "Create Point"), ('S', "Bevel"), ('T', "Extrude"),
                          ('W', "Extrude Inner"), ('X', "Matrix Extrude"), ('Y', "Smooth Shift"),
                          ('Q', "Weld")):
            _cmd(l, 'M', key, text)
        l.separator()
        l.label(text="Transform Tools")
        for key, text in (('O', "Slide"), ('G', "Iron"), ('Z', "Normal Move"), ('I', "Magnet"),
                          ('R', "Weight Subdivision Surface")):
            _cmd(l, 'M', key, text)
        l.separator()
        l.label(text="Commands")
        for key, text in (('S', "Subdivide"), ('Z', "Melt"), ('C', "Collapse"), ('D', "Disconnect"),
                          ('P', "Split"), ('O', "Optimize"), ('R', "Reverse Normals"),
                          ('A', "Align Normals"), ('T', "Triangulate"), ('U', "Untriangulate")):
            _cmd(l, 'U', key, text)


class C4D_MT_main_mograph(bpy.types.Menu):
    bl_idname = "C4D_MT_main_mograph"
    bl_label = "MoGraph"

    def draw(self, context):
        l = self.layout
        for mode in ("Linear", "Radial", "Grid"):
            l.operator("c4d.add_cloner", text=f"Cloner ({mode})", icon='MOD_ARRAY').mode = mode
        l.separator()
        l.operator("c4d.add_plain_effector", text="Plain Effector (link to selected Cloner)", icon='SPHERE')
        l.separator()
        l.operator("c4d.add_modifier", text="Array (Modifier)", icon='MOD_ARRAY').kind = 'ARRAY'
        l.operator("object.duplicates_make_real", text="Make Clones Editable")
        l.separator()
        l.label(text="Random effector: Cloner > Random Position / Rotation / Scale", icon='INFO')


class C4D_MT_main_animate(bpy.types.Menu):
    bl_idname = "C4D_MT_main_animate"
    bl_label = "Animate"

    def draw(self, context):
        l = self.layout
        l.operator("anim.keyframe_insert", text="Record Active Objects\tF9")
        l.prop(context.scene.tool_settings, "use_keyframe_insert_auto", text="Autokeying\tCtrl+F9")
        l.separator()
        l.operator("screen.animation_play", text="Play Forwards\tF8")
        l.operator("screen.animation_play", text="Play Backwards\tF6").reverse = True
        l.operator("screen.animation_cancel", text="Stop\tF7").restore_frame = False
        l.separator()
        l.operator("screen.frame_jump", text="Go to Start\tShift+F").end = False
        l.operator("screen.frame_jump", text="Go to End\tShift+G").end = True
        l.operator("screen.keyframe_jump", text="Previous Key\tCtrl+F").next = False
        l.operator("screen.keyframe_jump", text="Next Key\tCtrl+G").next = True
        l.separator()
        l.operator("c4d.set_workspace", text="Timeline (Animation Layout)").name = "Animation"


class C4D_MT_main_simulate(bpy.types.Menu):
    bl_idname = "C4D_MT_main_simulate"
    bl_label = "Simulate"

    def draw(self, context):
        l = self.layout
        l.menu("VIEW3D_MT_object_quick_effects", text="Quick Effects")
        l.separator()
        for t, label in (('CLOTH', "Cloth"), ('SOFT_BODY', "Soft Body"), ('COLLISION', "Collider")):
            l.operator("object.modifier_add", text=label).type = t
        l.operator("rigidbody.object_add", text="Rigid Body")


class C4D_MT_main_render(bpy.types.Menu):
    bl_idname = "C4D_MT_main_render"
    bl_label = "Render"

    def draw(self, context):
        l = self.layout
        l.operator("render.render", text="Render View\tCtrl+R").use_viewport = True
        l.operator("render.render", text="Render to Picture Viewer\tShift+R")
        l.operator("c4d.interactive_render", text="Interactive Render Region\tAlt+R")
        l.operator("render.render", text="Render Animation").animation = True
        l.separator()
        l.operator("c4d.render_settings", text="Edit Render Settings...\tCtrl+B")
        l.operator("render.view_show", text="Picture Viewer\tShift+F6")


# Menus shown in the top bar, in C4D order.
MAIN_MENUS = (
    ("TOPBAR_MT_file", "File"),
    ("TOPBAR_MT_edit", "Edit"),
    ("C4D_MT_main_create", "Create"),
    ("C4D_MT_main_modes", "Modes"),
    ("C4D_MT_main_select", "Select"),
    ("C4D_MT_main_tools", "Tools"),
    ("C4D_MT_main_mesh", "Mesh"),
    ("C4D_MT_main_mograph", "MoGraph"),
    ("C4D_MT_main_animate", "Animate"),
    ("C4D_MT_main_simulate", "Simulate"),
    ("C4D_MT_main_render", "Render"),
    ("TOPBAR_MT_window", "Window"),
    ("TOPBAR_MT_help", "Help"),
)


def draw_main_menus(layout, context):
    row = layout.row(align=True)
    row.menu("TOPBAR_MT_blender", text="", icon='BLENDER')
    for idname, text in MAIN_MENUS:
        row.menu(idname, text=text)


classes = (
    C4D_MT_main_create, C4D_MT_main_modes, C4D_MT_main_select, C4D_MT_main_tools,
    C4D_MT_main_mesh, C4D_MT_main_mograph, C4D_MT_main_animate, C4D_MT_main_simulate,
    C4D_MT_main_render,
)
