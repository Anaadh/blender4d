"""Redshift-style material node editing.

Double-clicking a material in the Material Manager opens a floating node
editor window pinned to that material (like C4D + Redshift's Shader Graph),
with the sidebar open for node attributes. The node editor theme is set to
a Redshift-like look in theme.py.
"""

import bpy


def _material_from_context(context, name=""):
    if name:
        return bpy.data.materials.get(name)
    asset = getattr(context, "asset", None)
    mat = getattr(asset, "local_id", None) if asset else None
    if isinstance(mat, bpy.types.Material):
        return mat
    ob = context.active_object
    return ob.active_material if ob else None


def _configure_node_window(window, mat):
    area = window.screen.areas[0]
    area.type = 'NODE_EDITOR'
    area.ui_type = 'ShaderNodeTree'
    space = area.spaces.active
    if not mat.use_nodes:
        mat.use_nodes = True
    space.pin = True
    space.node_tree = mat.node_tree
    space.show_region_ui = True       # attributes, like Redshift's node panel
    space.show_region_toolbar = False

    # Frame all nodes once the new window has its final size.
    def frame():
        try:
            for region in area.regions:
                if region.type == 'WINDOW':
                    with bpy.context.temp_override(window=window, area=area, region=region):
                        bpy.ops.node.view_all()
                    break
        except (ReferenceError, RuntimeError):
            pass
        return None
    bpy.app.timers.register(frame, first_interval=0.4)


class C4D_OT_edit_material_nodes(bpy.types.Operator):
    """Open the material in its own node editor window (Redshift Shader Graph style)"""
    bl_idname = "c4d.edit_material_nodes"
    bl_label = "Edit Material Nodes"
    bl_options = {'INTERNAL'}

    name: bpy.props.StringProperty(description="Material name; empty = active asset or object material")

    @classmethod
    def poll(cls, context):
        if context.area and context.area.type == 'FILE_BROWSER':
            # Only material assets: normal file browsing keeps its double-click.
            asset = getattr(context, "asset", None)
            return isinstance(getattr(asset, "local_id", None), bpy.types.Material)
        return _material_from_context(context) is not None

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        mat = _material_from_context(context, self.name)
        if mat is None:
            self.report({'INFO'}, "Select a material first")
            return {'CANCELLED'}
        # Reuse an open graph window for this material.
        for win in context.window_manager.windows:
            for area in win.screen.areas:
                sp = area.spaces.active
                if area.type == 'NODE_EDITOR' and getattr(sp, "pin", False) and sp.node_tree == mat.node_tree:
                    return {'FINISHED'}
        area = context.area
        if area is None:
            area = max(context.window.screen.areas, key=lambda a: a.width * a.height)
        from .winplace import blender_windows, center_new_window
        before = set(context.window_manager.windows[:])
        os_before = blender_windows()
        with context.temp_override(window=context.window, screen=context.window.screen, area=area):
            bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
        new = [w for w in context.window_manager.windows if w not in before]
        if not new:
            return {'CANCELLED'}
        window = new[0]

        def later():
            try:
                # Independent window in the middle of the screen, not where the
                # Material Manager strip happens to be.
                center_new_window(os_before)
                _configure_node_window(window, mat)
            except (ReferenceError, AttributeError, RuntimeError, OSError):
                pass
            return None
        bpy.app.timers.register(later, first_interval=0.05)
        return {'FINISHED'}


classes = (C4D_OT_edit_material_nodes,)

_keymaps = []


def register():
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return
    # Double-click a material in the Material Manager (asset browser).
    km = kc.keymaps.new(name="File Browser Main", space_type='FILE_BROWSER')
    kmi = km.keymap_items.new("c4d.edit_material_nodes", 'LEFTMOUSE', 'DOUBLE_CLICK')
    _keymaps.append((km, kmi))


def unregister():
    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _keymaps.clear()
