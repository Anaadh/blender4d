"""C4D V menu as a Blender pie menu."""

import bpy


class C4D_MT_mode_menu(bpy.types.Menu):
    bl_label = "Mode"
    bl_idname = "C4D_MT_mode_menu"

    def draw(self, context):
        layout = self.layout
        layout.operator("object.mode_set", text="Model", icon='OBJECT_DATAMODE').mode = 'OBJECT'
        for label, icon, mode in (("Points", 'VERTEXSEL', 'VERT'),
                                  ("Edges", 'EDGESEL', 'EDGE'),
                                  ("Polygons", 'FACESEL', 'FACE')):
            op = layout.operator("mesh.select_mode", text=label, icon=icon)
            op.type = mode
            op.use_extend = False
            op.use_expand = False


class C4D_MT_display_menu(bpy.types.Menu):
    bl_label = "Display"
    bl_idname = "C4D_MT_display_menu"

    def draw(self, context):
        layout = self.layout
        for mode, label in (('GOURAUD', "Gouraud Shading"),
                            ('GOURAUD_LINES', "Gouraud Shading (Lines)"),
                            ('CONSTANT', "Constant Shading"),
                            ('LINES', "Lines"),
                            ('TEXTURES', "Textures"),
                            ('XRAY', "X-Ray"),
                            ('BACKFACE', "Backface Culling")):
            layout.operator("c4d.display_mode", text=label).mode = mode


class C4D_MT_v_pie(bpy.types.Menu):
    bl_label = "C4D"
    bl_idname = "C4D_MT_v_pie"

    def draw(self, context):
        pie = self.layout.menu_pie()
        # Order: W, E, S, N, NW, NE, SW, SE
        pie.operator("c4d.view_panel", text="Perspective", icon='VIEW_PERSPECTIVE').view = 'PERSP'
        pie.operator("c4d.view_panel", text="All Views", icon='VIEW_CAMERA').view = 'ALL'
        if context.mode == 'OBJECT':
            pie.operator("c4d.make_editable", icon='MESH_DATA')
        else:
            pie.operator("object.editmode_toggle", text="Model Mode", icon='OBJECT_DATAMODE')
        pie.operator("view3d.view_selected", text="Frame Selected", icon='ZOOM_SELECTED')
        pie.menu("C4D_MT_mode_menu", icon='EDITMODE_HLT')
        pie.menu("C4D_MT_display_menu", icon='SHADING_SOLID')
        pie.operator("view3d.view_all", text="Frame All", icon='ZOOM_ALL').center = False
        pie.operator("c4d.interactive_render", text="Interactive Render", icon='SHADING_RENDERED')


classes = (C4D_MT_mode_menu, C4D_MT_display_menu, C4D_MT_v_pie)
