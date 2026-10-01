"""C4D R24 hotkeys as add-on keymap items.

Add-on keymap items take priority over Blender's defaults for the same
keymap, so each binding is added to every keymap whose default would
otherwise swallow the key (e.g. "Mesh" owns E for extrude).
"""

import bpy

_items = []  # (keymap, keymap_item) for unregister

# Keymaps that are active in the 3D viewport, in object and mesh edit mode.
VIEW = ("3D View", "Object Mode", "Mesh")
OBJ = ("Object Mode",)
MESH = ("Mesh",)


def _keymap(kc, name):
    default = bpy.context.window_manager.keyconfigs.default.keymaps[name]
    return kc.keymaps.new(name=name, space_type=default.space_type, region_type=default.region_type)


def _bind(kc, keymaps, idname, key, value='PRESS', props=None, **mods):
    for name in keymaps:
        km = _keymap(kc, name)
        kmi = km.keymap_items.new(idname, key, value, **mods)
        for k, v in (props or {}).items():
            setattr(kmi.properties, k, v)
        _items.append((km, kmi))


def register():
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:  # background mode
        return
    b = lambda *a, **kw: _bind(kc, *a, **kw)

    # --- Navigation ------------------------------------------------------
    # Alt + LMB/MMB/RMB = orbit / pan / zoom
    b(VIEW, "view3d.rotate", 'LEFTMOUSE', alt=True)
    b(VIEW, "view3d.move", 'MIDDLEMOUSE', alt=True)
    b(VIEW, "view3d.zoom", 'RIGHTMOUSE', alt=True)
    # Hold 1/2/3 + drag = move / zoom / rotate camera
    b(VIEW, "view3d.move", 'LEFTMOUSE', key_modifier='ONE')
    b(VIEW, "view3d.zoom", 'LEFTMOUSE', key_modifier='TWO')
    b(VIEW, "view3d.rotate", 'LEFTMOUSE', key_modifier='THREE')
    # Hold 4/5/6 + drag = move / scale / rotate selection
    b(VIEW, "c4d.transform_drag", 'LEFTMOUSE', 'CLICK_DRAG', key_modifier='FOUR', props={"mode": 'MOVE'})
    b(VIEW, "c4d.transform_drag", 'LEFTMOUSE', 'CLICK_DRAG', key_modifier='FIVE', props={"mode": 'SCALE'})
    b(VIEW, "c4d.transform_drag", 'LEFTMOUSE', 'CLICK_DRAG', key_modifier='SIX', props={"mode": 'ROTATE'})
    # X/Y/Z toggle the axis locks like C4D.
    for axis in "XYZ":
        b(VIEW, "wm.context_toggle", axis, props={"data_path": f"window_manager.c4d_lock_{axis.lower()}"})
    # Swallow the bare number presses so Blender's collection / select-mode
    # toggles don't fire while the key is held for navigation.
    for key in ('ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN'):
        b(VIEW, "c4d.noop", key)

    # --- Views -----------------------------------------------------------
    for key, view in (('F1', 'PERSP'), ('F2', 'TOP'), ('F3', 'RIGHT'), ('F4', 'FRONT'), ('F5', 'ALL')):
        b(VIEW, "c4d.view_panel", key, props={"view": view})
    b(VIEW, "view3d.view_all", 'H', props={"center": False})
    b(VIEW, "view3d.view_selected", 'S')
    b(VIEW, "view3d.view_selected", 'O')
    b(VIEW, "wm.call_panel", 'V', shift=True, props={"name": "VIEW3D_PT_overlay", "keep_open": True})
    b(VIEW, "c4d.chord", 'N', props={"prefix": 'N'})

    # --- Tools -----------------------------------------------------------
    for key, tool in (('E', "builtin.move"), ('R', "builtin.rotate"), ('T', "builtin.scale"),
                      ('EIGHT', "builtin.select_lasso"), ('NINE', "builtin.select_circle"),
                      ('ZERO', "builtin.select_box")):
        b(VIEW, "c4d.tool_set", key, props={"name": tool})
    b(VIEW, "c4d.tool_toggle_last", 'SPACE')
    b(VIEW, "c4d.coord_toggle", 'W')
    b(VIEW, "wm.call_panel", 'P', props={"name": "VIEW3D_PT_snapping", "keep_open": True})

    # --- Selection -------------------------------------------------------
    b(OBJ, "object.select_all", 'A', ctrl=True, props={"action": 'SELECT'})
    b(OBJ, "object.select_all", 'A', ctrl=True, shift=True, props={"action": 'DESELECT'})
    b(MESH, "mesh.select_all", 'A', ctrl=True, props={"action": 'SELECT'})
    b(MESH, "mesh.select_all", 'A', ctrl=True, shift=True, props={"action": 'DESELECT'})

    # --- Objects / modes -------------------------------------------------
    b(OBJ, "c4d.make_editable", 'C')
    b(OBJ, "object.delete", 'BACK_SPACE', props={"confirm": False})
    b(OBJ, "c4d.group", 'G', alt=True)
    b(OBJ, "c4d.ungroup", 'G', shift=True)
    b(VIEW, "c4d.toggle_generators", 'Q')
    b(VIEW, "c4d.edit_toggle", 'RET')
    # Numpad 0: look through the scene camera, navigation reframes it (toggle).
    b(VIEW, "c4d.look_through", 'NUMPAD_0')
    b(VIEW, "wm.call_menu_pie", 'V', props={"name": "C4D_MT_v_pie"})

    # --- Modeling chords -------------------------------------------------
    for prefix in ('M', 'U', 'K'):
        b(MESH, "c4d.chord", prefix, props={"prefix": prefix})

    # --- Render ----------------------------------------------------------
    b(VIEW + ("Window",), "render.render", 'R', ctrl=True, props={"use_viewport": True})
    b(("Window",), "render.render", 'R', shift=True, props={"use_viewport": True})
    b(VIEW, "c4d.interactive_render", 'R', alt=True)
    b(("Window",), "screen.userpref_show", 'E', ctrl=True)
    b(("Window",), "wm.search_menu", 'C', shift=True)  # Commander

    # --- Animation -------------------------------------------------------
    anim = VIEW + ("Frames",)
    b(anim, "screen.animation_play", 'F8')
    b(anim, "screen.animation_play", 'F6', props={"reverse": True})
    b(anim, "screen.animation_cancel", 'F7', props={"restore_frame": False})
    b(anim, "screen.frame_offset", 'F', props={"delta": -1})
    b(anim, "screen.frame_offset", 'G', props={"delta": 1})
    b(anim, "screen.keyframe_jump", 'F', ctrl=True, props={"next": False})
    b(anim, "screen.keyframe_jump", 'G', ctrl=True, props={"next": True})
    b(anim, "screen.frame_jump", 'F', shift=True, props={"end": False})
    b(anim, "screen.frame_jump", 'G', shift=True, props={"end": True})
    b(VIEW, "anim.keyframe_insert", 'F9')
    b(anim, "wm.context_toggle", 'F9', ctrl=True,
      props={"data_path": "scene.tool_settings.use_keyframe_insert_auto"})

    # --- Object Manager (Outliner) ---------------------------------------
    b(("Outliner",), "c4d.group", 'G', alt=True)
    b(("Outliner",), "c4d.ungroup", 'G', shift=True)
    b(("Outliner",), "c4d.make_editable", 'C')
    b(("Outliner",), "outliner.show_active", 'S')


def unregister():
    for km, kmi in _items:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _items.clear()
