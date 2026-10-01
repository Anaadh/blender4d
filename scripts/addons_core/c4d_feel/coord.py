"""C4D Coordinate Manager.

Position / Size / Rotation columns with the C4D dropdowns:
  space: Object (Rel) | Object (Abs) | World
  size:  Size | Scale
In object mode it edits the active object. In mesh edit mode it shows the
selection's center and bounding size, and editing moves / resizes / rotates
the selected elements, like C4D's point/polygon mode.

Values are live (no Apply needed); the Apply button just commits a pending
field edit, as in C4D.
"""

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

MAX_EDIT_VERTS = 200_000  # skip live readout on huge meshes


# ---------------------------------------------------------------------------
# Edit-mode helpers
# ---------------------------------------------------------------------------

def _edit_selection(ob):
    if ob is None or ob.type != 'MESH' or ob.mode != 'EDIT':
        return None, []
    me = ob.data
    if len(me.vertices) > MAX_EDIT_VERTS:
        return None, []
    bm = bmesh.from_edit_mesh(me)
    return bm, [v for v in bm.verts if v.select]


def _space_matrix(ob, space):
    return ob.matrix_world if space == 'WORLD' else Matrix.Identity(4)


def _sel_bounds(ob, verts, space):
    m = _space_matrix(ob, space)
    pts = [m @ v.co for v in verts]
    lo = Vector((min(p[i] for p in pts) for i in range(3)))
    hi = Vector((max(p[i] for p in pts) for i in range(3)))
    return lo, hi


def _apply_edit(ob, bm, verts, mat_local):
    """Apply a local-space transform matrix to the selected verts."""
    for v in verts:
        v.co = mat_local @ v.co
    bmesh.update_edit_mesh(ob.data)


# ---------------------------------------------------------------------------
# Property getters / setters
# ---------------------------------------------------------------------------

def _ob():
    return bpy.context.active_object


def _wm():
    return bpy.context.window_manager


def get_pos(self):
    ob = _ob()
    if ob is None:
        return (0.0, 0.0, 0.0)
    space = _wm().c4d_coord_space
    bm, verts = _edit_selection(ob)
    if verts:
        lo, hi = _sel_bounds(ob, verts, space)
        return tuple((lo + hi) / 2)
    if space == 'WORLD':
        return tuple(ob.matrix_world.translation)
    if space == 'OBJ_ABS':
        return tuple(ob.location + ob.delta_location)
    return tuple(ob.location)


def set_pos(self, value):
    ob = _ob()
    if ob is None:
        return
    value = Vector(value)
    space = _wm().c4d_coord_space
    bm, verts = _edit_selection(ob)
    if verts:
        lo, hi = _sel_bounds(ob, verts, space)
        delta = value - (lo + hi) / 2
        if space == 'WORLD':
            delta = ob.matrix_world.inverted().to_3x3() @ delta
        _apply_edit(ob, bm, verts, Matrix.Translation(delta))
        return
    if space == 'WORLD':
        ob.matrix_world.translation = value
    elif space == 'OBJ_ABS':
        ob.location = value - ob.delta_location
    else:
        ob.location = value


def get_size(self):
    ob = _ob()
    if ob is None:
        return (0.0, 0.0, 0.0)
    bm, verts = _edit_selection(ob)
    if verts:
        lo, hi = _sel_bounds(ob, verts, _wm().c4d_coord_space)
        return tuple(hi - lo)
    if _wm().c4d_coord_size == 'SCALE':
        return tuple(ob.scale)
    return tuple(ob.dimensions)


def set_size(self, value):
    ob = _ob()
    if ob is None:
        return
    value = Vector(value)
    bm, verts = _edit_selection(ob)
    if verts:
        lo, hi = _sel_bounds(ob, verts, 'OBJ_REL')
        cur = hi - lo
        center = (lo + hi) / 2
        f = [value[i] / cur[i] if cur[i] > 1e-9 else 1.0 for i in range(3)]
        m = Matrix.Translation(center) @ Matrix.Diagonal((*f, 1.0)) @ Matrix.Translation(-center)
        _apply_edit(ob, bm, verts, m)
        return
    if _wm().c4d_coord_size == 'SCALE':
        ob.scale = value
    else:
        ob.dimensions = value


def get_rot(self):
    ob = _ob()
    if ob is None:
        return (0.0, 0.0, 0.0)
    bm, verts = _edit_selection(ob)
    if verts:
        return (0.0, 0.0, 0.0)  # C4D shows 0 for component rotation
    if _wm().c4d_coord_space == 'WORLD':
        return tuple(ob.matrix_world.to_euler())
    return tuple(ob.rotation_euler)


def set_rot(self, value):
    ob = _ob()
    if ob is None:
        return
    bm, verts = _edit_selection(ob)
    if verts:
        lo, hi = _sel_bounds(ob, verts, 'OBJ_REL')
        center = (lo + hi) / 2
        rot = Euler(value).to_matrix().to_4x4()
        _apply_edit(ob, bm, verts, Matrix.Translation(center) @ rot @ Matrix.Translation(-center))
        return
    if _wm().c4d_coord_space == 'WORLD':
        loc, _rot, scale = ob.matrix_world.decompose()
        ob.matrix_world = Matrix.LocRotScale(loc, Euler(value).to_quaternion(), scale)
    else:
        ob.rotation_euler = value


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def draw(layout, context):
    wm = context.window_manager
    ob = context.active_object
    if ob is None:
        layout.label(text="No object selected")
        return
    grid = layout.grid_flow(row_major=True, columns=3, even_columns=True, align=False)
    size_prop = "c4d_scale" if wm.c4d_coord_size == 'SCALE' and not _edit_selection(ob)[1] else "c4d_size"
    for title, prop in (("Position", "c4d_pos"), ("Size", size_prop), ("Rotation", "c4d_rot")):
        col = grid.column(align=True)
        col.label(text=title)
        col.prop(wm, prop, text="")
    row = layout.row(align=True)
    row.prop(wm, "c4d_coord_space", text="")
    row.prop(wm, "c4d_coord_size", text="")
    row.operator("c4d.coord_apply", text="Apply")


class C4D_OT_coord_apply(bpy.types.Operator):
    """Apply the Coordinate Manager values"""
    bl_idname = "c4d.coord_apply"
    bl_label = "Apply"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Fields are live; this records an undo step like C4D's Apply.
        return {'FINISHED'}


classes = (C4D_OT_coord_apply,)


def register():
    WM = bpy.types.WindowManager
    WM.c4d_coord_space = bpy.props.EnumProperty(
        name="Coordinate System",
        items=[('OBJ_REL', "Object (Rel)", "Local values relative to the parent"),
               ('OBJ_ABS', "Object (Abs)", "Local values including frozen (delta) transforms"),
               ('WORLD', "World", "World space values")])
    WM.c4d_coord_size = bpy.props.EnumProperty(
        name="Size Mode",
        items=[('SIZE', "Size", "Bounding box size"), ('SCALE', "Scale", "Scale factors")])
    WM.c4d_pos = bpy.props.FloatVectorProperty(name="Position", subtype='TRANSLATION', unit='LENGTH',
                                               get=get_pos, set=set_pos)
    # Same getter/setter; unitless so Scale mode doesn't show "m".
    WM.c4d_scale = bpy.props.FloatVectorProperty(name="Scale", subtype='XYZ', get=get_size, set=set_size)
    WM.c4d_size = bpy.props.FloatVectorProperty(name="Size", subtype='XYZ_LENGTH', unit='LENGTH',
                                                get=get_size, set=set_size)
    WM.c4d_rot = bpy.props.FloatVectorProperty(name="Rotation", subtype='EULER', get=get_rot, set=set_rot)


def unregister():
    WM = bpy.types.WindowManager
    for p in ("c4d_rot", "c4d_scale", "c4d_size", "c4d_pos", "c4d_coord_size", "c4d_coord_space"):
        delattr(WM, p)
