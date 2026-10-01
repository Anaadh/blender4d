"""C4D Feel: Cinema 4D R24 style hotkeys, chords, V pie, theme and layout for Blender."""

# Used when bundled as a core add-on in the C4D Blender fork
# (as an extension, blender_manifest.toml is used instead).
bl_info = {
    "name": "C4D Feel",
    "author": "Mohamed Anaadh Hussain",
    "version": (0, 3, 0),
    "blender": (5, 0, 0),
    "location": "C4D workspace",
    "description": "Cinema 4D R24 style hotkeys, managers, generators and layout",
    "category": "Interface",
}

import bpy

from . import icons, coord, ops, chords, menus, menubar, cloner, deformers, primitives, splines, tags, camera, nodes, om, matmanager, theme, layout, ui, managers, keymap

_modules = (coord, ops, chords, menus, menubar, cloner, deformers, primitives, splines, tags, camera, nodes, om, matmanager, theme, layout, ui, managers)


def _toggle_keymap(self, _context):
    keymap.unregister()
    if self.use_c4d_keymap:
        keymap.register()


def prefs():
    addon = bpy.context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


class C4D_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    use_c4d_keymap: bpy.props.BoolProperty(
        name="C4D Hotkeys", default=True, update=_toggle_keymap,
        description="Cinema 4D hotkeys and chords. Off = Blender's own keymap")

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "use_c4d_keymap")
        col.label(text="The C4D layout, menus and managers only change the 'C4D' workspace; "
                       "other workspaces keep Blender's UI.", icon='INFO')
        row = col.row()
        row.operator("c4d.apply_theme", icon='COLOR')
        row.operator("preferences.reset_default_theme", text="Reset Theme", icon='LOOP_BACK')
        col.operator("c4d.setup_workspace", icon='WORKSPACE')


def register():
    for m in _modules:
        for cls in m.classes:
            bpy.utils.register_class(cls)
    bpy.utils.register_class(C4D_AddonPreferences)
    icons.register()
    coord.register()
    om.register()
    deformers.register()
    tags.register()
    camera.register()
    nodes.register()
    ui.register()
    managers.register()
    p = prefs()
    if p is None or p.use_c4d_keymap:
        keymap.register()


def unregister():
    keymap.unregister()
    managers.unregister()
    ui.unregister()
    nodes.unregister()
    camera.unregister()
    tags.unregister()
    deformers.unregister()
    om.unregister()
    coord.unregister()
    icons.unregister()
    bpy.utils.unregister_class(C4D_AddonPreferences)
    for m in reversed(_modules):
        for cls in reversed(m.classes):
            bpy.utils.unregister_class(cls)
