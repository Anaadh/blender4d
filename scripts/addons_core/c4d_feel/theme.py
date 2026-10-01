"""C4D-style color theme applied to the active Blender theme.

Colors approximate the Cinema 4D dark UI (neutral greys, blue accent).
Undo with Preferences > Themes > Reset to Default.
"""

import bpy


def _hex(h, a=None):
    h = h.lstrip("#")
    rgb = tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return rgb if a is None else rgb + (a,)


# Sampled from Maxon's S24/R24-era help screenshots (help.maxon.net, image 043421).
BG = "#3d3d3d"         # manager / editor background
HEADER = "#424242"     # manager menu bars
PANEL = "#3d3d3d"
WIDGET = "#595959"     # buttons, dropdowns, palette groups
WIDGET_HI = "#6a6a6a"
FIELD = "#323232"      # number / text fields
OUTLINE = "#2a2a2a"
TEXT = "#d9d9d9"
TEXT_DIM = "#9f9f9f"   # labels ("Position", "Size", ...)
ACCENT = "#84a4cd"     # active palette button blue
ACCENT_DARK = "#394659"  # selected item background (Material Manager)
VIEW_TOP = "#6b6e73"   # viewport gradient (approximation)
VIEW_BOTTOM = "#48494c"
GRID = "#7a7c80"
OBJ_ACTIVE = "#ffa42b"  # C4D draws the active object outline in orange
OBJ_SELECTED = "#e0781f"

EDITORS = (
    "view_3d", "graph_editor", "file_browser", "nla_editor", "dopesheet_editor",
    "image_editor", "sequence_editor", "properties", "text_editor", "node_editor",
    "outliner", "info", "preferences", "console", "clip_editor", "topbar",
    "statusbar", "spreadsheet",
)


def _set(obj, attr, value):
    if obj is None or not hasattr(obj, attr):
        return
    cur = getattr(obj, attr)
    try:
        if len(cur) == 4 and len(value) == 3:
            value = tuple(value) + (cur[3],)
    except TypeError:
        pass
    try:
        setattr(obj, attr, value)
    except (TypeError, AttributeError, ValueError):
        pass


def apply(theme):
    ui = theme.user_interface

    # Widgets
    for name in ("wcol_regular", "wcol_tool", "wcol_toolbar_item", "wcol_radio", "wcol_text",
                 "wcol_option", "wcol_toggle", "wcol_num", "wcol_numslider", "wcol_box",
                 "wcol_menu", "wcol_pulldown", "wcol_menu_back", "wcol_pie_menu",
                 "wcol_tooltip", "wcol_menu_item", "wcol_list_item", "wcol_tab"):
        w = getattr(ui, name, None)
        _set(w, "outline", _hex(OUTLINE))
        _set(w, "inner", _hex(WIDGET, 1.0))
        _set(w, "inner_sel", _hex(ACCENT, 1.0))
        _set(w, "text", _hex(TEXT))
        _set(w, "text_sel", _hex("#ffffff"))
        _set(w, "item", _hex(ACCENT, 1.0))
        _set(w, "roundness", 0.15)
        _set(w, "show_shaded", False)
    for name in ("wcol_text", "wcol_num", "wcol_numslider"):
        _set(getattr(ui, name, None), "inner", _hex(FIELD, 1.0))
    for name in ("wcol_tool", "wcol_toolbar_item", "wcol_toggle", "wcol_radio",
                 "wcol_menu_item", "wcol_pulldown", "wcol_option", "wcol_regular"):
        _set(getattr(ui, name, None), "text_sel", _hex("#1a1a1a"))
    for name in ("wcol_menu_back", "wcol_pie_menu", "wcol_tooltip"):
        _set(getattr(ui, name, None), "inner", _hex(PANEL, 0.98))
    for name in ("wcol_menu_item", "wcol_pulldown", "wcol_list_item", "wcol_tab"):
        _set(getattr(ui, name, None), "inner", _hex(PANEL, 0.0))
    _set(ui.wcol_numslider, "item", _hex(ACCENT_DARK, 1.0))

    _set(ui, "panel_header", _hex(HEADER, 1.0))
    _set(ui, "panel_back", _hex(PANEL, 1.0))
    _set(ui, "panel_sub_back", _hex(BG, 1.0))
    _set(ui, "panel_title", _hex(TEXT))
    _set(ui, "panel_text", _hex(TEXT))
    _set(ui, "panel_outline", _hex(OUTLINE, 1.0))
    _set(ui, "panel_active", _hex(ACCENT, 1.0))
    _set(ui, "editor_border", _hex("#18191a"))
    _set(ui, "editor_outline", _hex(OUTLINE, 1.0))
    _set(ui, "editor_outline_active", _hex(ACCENT_DARK, 1.0))
    _set(ui, "panel_roundness", 0.1)

    # Editors
    for ed in EDITORS:
        space = getattr(getattr(theme, ed, None), "space", None)
        if space is None:
            continue
        _set(space, "back", _hex(BG))
        _set(space, "header", _hex(HEADER, 1.0))
        _set(space, "title", _hex(TEXT))
        _set(space, "text", _hex(TEXT_DIM))
        _set(space, "text_hi", _hex("#ffffff"))
        _set(space, "header_text", _hex(TEXT))
        _set(space, "header_text_hi", _hex("#ffffff"))

    # Object Manager look: selected rows in C4D blue
    ol = theme.outliner
    _set(ol, "selected_highlight", _hex(ACCENT_DARK))
    _set(ol, "active", _hex(ACCENT))
    _set(ol, "selected_object", _hex(OBJ_SELECTED))
    _set(ol, "active_object", _hex(OBJ_ACTIVE))
    _set(ol, "row_alternate", _hex("#303134", 1.0))

    # Node editor: Redshift Shader Graph look (dark bodies, muted colored headers)
    ne = theme.node_editor
    _set(ne.space, "back", _hex("#262626"))
    _set(ne, "grid", _hex("#2e2e2e"))
    _set(ne, "node_backdrop", _hex("#3a3a3a", 1.0))
    _set(ne, "node_outline", _hex("#1c1c1c", 1.0))
    _set(ne, "node_selected", _hex(OBJ_SELECTED))
    _set(ne, "node_active", _hex(OBJ_ACTIVE))
    _set(ne, "wire", _hex("#9a9a9a", 1.0))
    _set(ne, "wire_inner", _hex("#5a5a5a"))
    _set(ne, "wire_select", _hex(OBJ_ACTIVE))
    for prop, color in (("shader_node", "#7a3f3f"),      # materials / shaders
                        ("texture_node", "#8a6a2a"),     # textures
                        ("converter_node", "#3e5f8a"),   # utilities / math
                        ("color_node", "#6a4f8a"),
                        ("vector_node", "#3f7373"),
                        ("input_node", "#505050"),
                        ("output_node", "#962d2d"),
                        ("group_node", "#4a6a3a"),
                        ("frame_node", "#303030"),
                        ("attribute_node", "#3f6a5a"),
                        ("geometry_node", "#3f6a5a"),
                        ("script_node", "#555555")):
        _set(ne, prop, _hex(color))
    _set(ne, "noodle_curving", 5)

    # Viewport
    v = theme.view_3d
    grad = v.space.gradients
    _set(grad, "background_type", 'LINEAR')
    _set(grad, "high_gradient", _hex(VIEW_TOP))
    _set(grad, "gradient", _hex(VIEW_BOTTOM))
    _set(v, "grid", _hex(GRID, 0.6))
    _set(v, "object_active", _hex(OBJ_ACTIVE))
    _set(v, "object_selected", _hex(OBJ_SELECTED))
    _set(v, "vertex_select", _hex(OBJ_ACTIVE))
    _set(v, "edge_select", _hex(OBJ_ACTIVE))
    _set(v, "edge_mode_select", _hex(OBJ_ACTIVE))
    _set(v, "face_select", _hex(OBJ_ACTIVE, 0.35))
    _set(v, "face_mode_select", _hex(OBJ_ACTIVE, 0.35))
    _set(v, "editmesh_active", _hex("#ffffff", 0.5))
    _set(v, "wire", _hex("#101010"))
    _set(v, "wire_edit", _hex("#1a1a1a"))
    _set(v, "vertex", _hex("#1a1a1a"))


class C4D_OT_apply_theme(bpy.types.Operator):
    """Recolor the current theme to a Cinema 4D-like palette"""
    bl_idname = "c4d.apply_theme"
    bl_label = "Apply C4D Theme"
    bl_options = {'REGISTER'}

    def execute(self, context):
        apply(context.preferences.themes[0])
        for w in context.window_manager.windows:
            for a in w.screen.areas:
                a.tag_redraw()
        return {'FINISHED'}


classes = (C4D_OT_apply_theme,)
