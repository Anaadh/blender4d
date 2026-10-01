"""C4D-style camera use: look through a camera and reframe it by navigating.

Blender can already do this (Numpad 0 + View > Lock > Camera to View), but in
C4D it is one click and navigating in camera view always moves the camera.
Looking through a camera here switches "Camera to View" on for that viewport;
going back to the editor camera switches it off again.
"""

import bpy


def _main_view3d(context):
    """(area, space, region_3d) of the active or largest 3D viewport."""
    area = context.area if context.area and context.area.type == 'VIEW_3D' else None
    if area is None and context.window:
        views = [a for a in context.window.screen.areas if a.type == 'VIEW_3D']
        area = max(views, key=lambda a: a.width * a.height) if views else None
    if area is None:
        return None, None, None
    space = area.spaces.active
    return area, space, space.region_3d


def looking_through(context, cam):
    _area, space, r3d = _main_view3d(context)
    return bool(r3d and r3d.view_perspective == 'CAMERA' and context.scene.camera == cam)


def enter_camera(context, cam):
    area, space, r3d = _main_view3d(context)
    if r3d is None or cam is None:
        return False
    context.scene.camera = cam
    r3d.view_perspective = 'CAMERA'
    space.lock_camera = context.window_manager.c4d_camera_nav
    area.tag_redraw()
    return True


def leave_camera(context):
    area, space, r3d = _main_view3d(context)
    if r3d is None:
        return False
    if r3d.view_perspective == 'CAMERA':
        r3d.view_perspective = 'PERSP'
    space.lock_camera = False
    area.tag_redraw()
    return True


class C4D_OT_look_through(bpy.types.Operator):
    """Look through this camera; navigating then moves the camera (click again: editor camera)"""
    bl_idname = "c4d.look_through"
    bl_label = "Look Through Camera"
    bl_options = {'INTERNAL'}

    name: bpy.props.StringProperty(description="Camera name; empty = scene camera")

    def execute(self, context):
        cam = context.scene.objects.get(self.name) if self.name else context.scene.camera
        if cam is None:
            cams = [o for o in context.scene.objects if o.type == 'CAMERA']
            cam = cams[0] if cams else None
        if cam is None or cam.type != 'CAMERA':
            self.report({'INFO'}, "No camera in the scene")
            return {'CANCELLED'}
        if looking_through(context, cam):
            leave_camera(context)
        else:
            enter_camera(context, cam)
        return {'FINISHED'}


class C4D_OT_editor_camera(bpy.types.Operator):
    """Back to the editor (perspective) camera"""
    bl_idname = "c4d.editor_camera"
    bl_label = "Editor Camera"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        leave_camera(context)
        return {'FINISHED'}


def _sync_lock(self, context):
    _area, space, r3d = _main_view3d(context)
    if space and r3d and r3d.view_perspective == 'CAMERA':
        space.lock_camera = self.c4d_camera_nav


classes = (C4D_OT_look_through, C4D_OT_editor_camera)


def register():
    bpy.types.WindowManager.c4d_camera_nav = bpy.props.BoolProperty(
        name="Navigate Camera", default=True, update=_sync_lock,
        description="In camera view, viewport navigation moves the camera (C4D behavior)")


def unregister():
    del bpy.types.WindowManager.c4d_camera_nav
