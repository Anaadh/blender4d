"""C4D two-key chords (M~T, U~L, K~K, N~A ...).

Blender keymaps cannot express key sequences, so the prefix key starts a
modal operator that waits for the second key and runs the mapped command.
"""

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader


def _op(path, *args, **kwargs):
    """Return a callable that runs bpy.ops.<path> with the given args."""
    mod, name = path.split(".")

    def run():
        return getattr(getattr(bpy.ops, mod), name)(*args, **kwargs)
    return run


def _invoke(path, **kwargs):
    return _op(path, 'INVOKE_DEFAULT', **kwargs)


def _tool(idname):
    return _op("c4d.tool_set", name=idname)


# key -> (label, callable). Keys are Blender event types.
CHORDS = {
    'M': {
        'A': ("Create Point", _invoke("mesh.subdivide")),
        'B': ("Bridge", _invoke("mesh.bridge_edge_loops")),
        'D': ("Close Polygon Hole", _invoke("mesh.fill")),
        'E': ("Polygon Pen", _tool("builtin.poly_build")),
        'F': ("Edge Cut", _invoke("mesh.subdivide")),
        'G': ("Iron", _invoke("mesh.vertices_smooth")),
        'I': ("Magnet (Proportional)", _op("wm.context_toggle", data_path="tool_settings.use_proportional_edit")),
        'J': ("Plane Cut", _invoke("mesh.bisect")),
        'K': ("Line Cut", _invoke("mesh.knife_tool")),
        'L': ("Loop/Path Cut", _invoke("mesh.loopcut_slide")),
        'O': ("Slide", _invoke("c4d.slide")),
        'Q': ("Weld", _invoke("mesh.merge", type='CENTER')),
        'R': ("Weight SDS (Crease)", _invoke("transform.edge_crease")),
        'S': ("Bevel", _invoke("mesh.bevel")),
        'T': ("Extrude", _invoke("view3d.edit_mesh_extrude_move_normal")),
        'W': ("Extrude Inner", _invoke("mesh.inset")),
        'X': ("Matrix Extrude", _invoke("mesh.extrude_repeat")),
        'Y': ("Smooth Shift", _invoke("view3d.edit_mesh_extrude_individual_move")),
        'Z': ("Normal Move", _invoke("transform.shrink_fatten")),
    },
    'K': {
        'K': ("Line Cut", _invoke("mesh.knife_tool")),
        'L': ("Loop/Path Cut", _invoke("mesh.loopcut_slide")),
        'J': ("Plane Cut", _invoke("mesh.bisect")),
    },
    'U': {
        'L': ("Loop Selection", _invoke("mesh.loop_multi_select", ring=False)),
        'B': ("Ring Selection", _invoke("mesh.loop_multi_select", ring=True)),
        'Y': ("Grow Selection", _op("mesh.select_more")),
        'K': ("Shrink Selection", _op("mesh.select_less")),
        'W': ("Select Connected", _op("mesh.select_linked")),
        'I': ("Invert Selection", _op("mesh.select_all", action='INVERT')),
        'F': ("Fill Selection", _op("mesh.loop_to_region")),
        'Q': ("Outline Selection", _op("mesh.region_to_loop")),
        'S': ("Subdivide", _invoke("mesh.subdivide")),
        'Z': ("Melt", _op("mesh.dissolve_mode")),
        'C': ("Collapse", _op("mesh.merge", type='COLLAPSE')),
        'D': ("Disconnect", _op("mesh.split")),
        'P': ("Split", _op("c4d.split")),
        'R': ("Reverse Normals", _op("mesh.flip_normals")),
        'A': ("Align Normals", _op("mesh.normals_make_consistent", inside=False)),
        'T': ("Triangulate", _op("mesh.quads_convert_to_tris")),
        'U': ("Untriangulate", _op("mesh.tris_convert_to_quads")),
        'O': ("Optimize", _invoke("mesh.remove_doubles")),
    },
    'N': {
        'A': ("Gouraud Shading", _op("c4d.display_mode", mode='GOURAUD')),
        'B': ("Gouraud Shading (Lines)", _op("c4d.display_mode", mode='GOURAUD_LINES')),
        'E': ("Constant Shading", _op("c4d.display_mode", mode='CONSTANT')),
        'G': ("Lines", _op("c4d.display_mode", mode='LINES')),
        'H': ("Wireframe", _op("c4d.display_mode", mode='LINES')),
        'P': ("Backface Culling", _op("c4d.display_mode", mode='BACKFACE')),
        'Q': ("Textures", _op("c4d.display_mode", mode='TEXTURES')),
        'R': ("X-Ray", _op("c4d.display_mode", mode='XRAY')),
        # Blender extras, since N and T are taken over by C4D keys.
        'N': ("[Blender] Sidebar", _op("wm.context_toggle", data_path="space_data.show_region_ui")),
        'T': ("[Blender] Toolbar", _op("wm.context_toggle", data_path="space_data.show_region_toolbar")),
    },
}

_IGNORED = {
    'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE', 'TIMER', 'TIMER_REPORT', 'NONE',
    'LEFT_SHIFT', 'RIGHT_SHIFT', 'LEFT_CTRL', 'RIGHT_CTRL', 'LEFT_ALT', 'RIGHT_ALT', 'OSKEY',
    'WINDOW_DEACTIVATE',
}


def _draw_hud(op, context):
    table = CHORDS[op.prefix]
    font = 0
    ui = context.preferences.view.ui_scale
    size = 13 * ui
    line = int(size * 1.5)
    pad = int(10 * ui)
    rows = [f"{op.prefix}~   (Esc to cancel)"] + [f"{op.prefix}~{k}   {label}" for k, (label, _) in table.items()]
    blf.size(font, size)
    width = max(blf.dimensions(font, r)[0] for r in rows) + pad * 2
    height = line * len(rows) + pad * 2
    x = op.mouse_x + 20
    y = op.mouse_y - height + 20
    region = context.region
    x = max(0, min(x, region.width - width))
    y = max(0, min(y, region.height - height))

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    verts = ((x, y), (x + width, y), (x + width, y + height), (x, y + height))
    batch = batch_for_shader(shader, 'TRI_FAN', {"pos": verts})
    gpu.state.blend_set('ALPHA')
    shader.uniform_float("color", (0.16, 0.17, 0.18, 0.94))
    batch.draw(shader)
    gpu.state.blend_set('NONE')

    for i, r in enumerate(rows):
        ty = y + height - pad - line * (i + 1) + int(line * 0.3)
        if i == 0:
            blf.color(font, 0.18, 0.55, 1.0, 1.0)
        else:
            blf.color(font, 0.91, 0.92, 0.93, 1.0)
        blf.position(font, x + pad, ty, 0)
        blf.draw(font, r)


class C4D_OT_chord(bpy.types.Operator):
    """Wait for the second key of a C4D chord (M~, U~, K~, N~)"""
    bl_idname = "c4d.chord"
    bl_label = "C4D Chord"
    bl_options = {'INTERNAL'}

    prefix: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        if self.prefix not in CHORDS:
            return {'CANCELLED'}
        self.mouse_x = event.mouse_region_x
        self.mouse_y = event.mouse_region_y
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_hud, (self, context), 'WINDOW', 'POST_PIXEL')
        self._prefix_released = False
        context.area.tag_redraw()
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _finish(self, context):
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        context.area.tag_redraw()

    def modal(self, context, event):
        if event.type in _IGNORED:
            return {'RUNNING_MODAL'}
        if event.type in {'ESC', 'RIGHTMOUSE', 'LEFTMOUSE'} and event.value == 'PRESS':
            self._finish(context)
            return {'CANCELLED'}
        if event.value != 'PRESS':
            return {'RUNNING_MODAL'}
        # Ignore auto-repeat of the prefix key while it is still held.
        if event.type == self.prefix and event.is_repeat:
            return {'RUNNING_MODAL'}

        self._finish(context)
        entry = CHORDS[self.prefix].get(event.type)
        if entry is None:
            self.report({'INFO'}, f"No command on {self.prefix}~{event.type}")
            return {'CANCELLED'}
        label, run = entry
        try:
            run()
        except RuntimeError as ex:
            self.report({'WARNING'}, f"{label}: {str(ex).splitlines()[-1]}")
            return {'CANCELLED'}
        return {'FINISHED'}


def _view3d_override(context):
    """Context override targeting the largest 3D viewport, for menu-bar calls."""
    screen = context.window.screen
    views = [a for a in screen.areas if a.type == 'VIEW_3D']
    if not views:
        return None
    area = max(views, key=lambda a: a.width * a.height)
    region = next(r for r in area.regions if r.type == 'WINDOW')
    return context.temp_override(window=context.window, screen=screen, area=area, region=region)


class C4D_OT_chord_cmd(bpy.types.Operator):
    """Run a C4D command in the 3D viewport"""
    bl_idname = "c4d.chord_cmd"
    bl_label = "C4D Command"
    bl_options = {'INTERNAL'}

    prefix: bpy.props.StringProperty()
    key: bpy.props.StringProperty()

    @classmethod
    def description(cls, context, props):
        entry = CHORDS.get(props.prefix, {}).get(props.key)
        return f"{entry[0]}  ({props.prefix}~{props.key})" if entry else ""

    def execute(self, context):
        entry = CHORDS.get(self.prefix, {}).get(self.key)
        ov = _view3d_override(context)
        if entry is None or ov is None:
            return {'CANCELLED'}
        label, run = entry
        try:
            with ov:
                run()
        except RuntimeError as ex:
            self.report({'WARNING'}, f"{label}: {str(ex).splitlines()[-1]}")
            return {'CANCELLED'}
        return {'FINISHED'}


classes = (C4D_OT_chord, C4D_OT_chord_cmd)
