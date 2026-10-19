"""General C4D-style operators: tools, grouping, views, display modes."""

import bpy
from mathutils import Vector


# ---------------------------------------------------------------------------
# Tool switching with "Space = last tool" memory
# ---------------------------------------------------------------------------

_last_tool = {}  # mode -> previous tool idname


def _active_tool_id(context):
    tool = context.workspace.tools.from_space_view3d_mode(context.mode, create=False)
    return tool.idname if tool else None


class C4D_OT_tool_set(bpy.types.Operator):
    """Activate a tool and remember the previous one (C4D E/R/T, 8/9/0)"""
    bl_idname = "c4d.tool_set"
    bl_label = "C4D Set Tool"
    bl_options = {'INTERNAL'}

    name: bpy.props.StringProperty()

    def execute(self, context):
        # Also called from the top bar command palette, so name the space explicitly.
        current = _active_tool_id(context)
        if current and current != self.name:
            _last_tool[context.mode] = current
        bpy.ops.wm.tool_set_by_id(name=self.name, space_type='VIEW_3D')
        return {'FINISHED'}


class C4D_OT_tool_toggle_last(bpy.types.Operator):
    """Swap back to the previously used tool (C4D Space)"""
    bl_idname = "c4d.tool_toggle_last"
    bl_label = "C4D Toggle Last Tool"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'VIEW_3D'

    def execute(self, context):
        prev = _last_tool.get(context.mode)
        if not prev:
            return {'CANCELLED'}
        _last_tool[context.mode] = _active_tool_id(context)
        bpy.ops.wm.tool_set_by_id(name=prev)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Objects
# ---------------------------------------------------------------------------

class C4D_OT_make_editable(bpy.types.Operator):
    """Convert to an editable mesh, baking modifiers (C4D C)"""
    bl_idname = "c4d.make_editable"
    bl_label = "Make Editable"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.selected_objects

    def execute(self, context):
        from .splines import kind_of
        from .cloner import cloner_modifier
        from .generators import consumed_children
        selected = list(context.selected_objects)
        # C4D folds a generator's children into the result.
        doomed = consumed_children(selected)
        splines = [o for o in selected if (kind_of(o) or ("", ""))[0] == 'spline']
        cloners = [o for o in selected if cloner_modifier(o) is not None]
        others = [o for o in selected if o not in splines and o not in cloners]
        # Parametric splines become editable curves, everything else a mesh.
        for target, objs in (('CURVE', splines), ('MESH', others)):
            if not objs:
                continue
            for o in context.selected_objects:
                o.select_set(o in objs)
            context.view_layer.objects.active = objs[0]
            bpy.ops.object.convert(target=target)
        # A Cloner becomes a Null with the clones as real children, like C4D.
        for c in cloners:
            for o in context.selected_objects:
                o.select_set(o is c)
            context.view_layer.objects.active = c
            bpy.ops.object.duplicates_make_real(use_base_parent=True, use_hierarchy=True)
            # The real clones are copies of the templates: visible again, and baked
            # now so clones of generators don't lose their inputs when those go.
            clones = [o for o in context.selected_objects if o is not c]
            for o in clones:
                o.hide_render = False
            if clones:
                _select_only(context, clones)
                bpy.ops.object.convert(target='MESH')
            c.modifiers.remove(cloner_modifier(c))
        for o in doomed:
            colls = list(o.users_collection)
            bpy.data.objects.remove(o)
            for coll in colls:
                if not coll.objects and not coll.children and coll != context.scene.collection:
                    bpy.data.collections.remove(coll)
        for o in selected:
            try:
                o.select_set(True)
            except ReferenceError:
                pass
        return {'FINISHED'}


def _select_only(context, objs):
    for o in context.selected_objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    context.view_layer.objects.active = objs[0] if objs else None


class C4D_OT_current_state_to_object(bpy.types.Operator):
    """Bake a copy of the selection in its current state; the originals stay parametric (C4D Current State to Object)"""
    bl_idname = "c4d.current_state_to_object"
    bl_label = "Current State to Object"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.selected_objects

    def execute(self, context):
        from .generators import sync_children
        roots = list(context.selected_objects)
        # Duplicate with the children, so generators keep their inputs, then bake the copies.
        family = list(roots)
        for o in roots:
            family += [c for c in o.children_recursive if c not in family]
        hidden = [o for o in family if o.hide_get()]
        for o in hidden:
            o.hide_set(False)  # hidden objects can't be selected for duplication
        _select_only(context, family)
        bpy.ops.object.duplicate(linked=False)
        copies = list(context.selected_objects)
        for o in hidden:
            o.hide_set(True)
        sync_children(context.scene)  # copied generators get their own children collections
        copy_roots = [o for o in copies if o.parent not in copies]
        _select_only(context, copy_roots)
        bpy.ops.c4d.make_editable()
        return {'FINISHED'}


class C4D_OT_connect_objects(bpy.types.Operator):
    """Join the selected objects into one polygon object in their current state (C4D Connect Objects)"""
    bl_idname = "c4d.connect_objects"
    bl_label = "Connect Objects"
    bl_options = {'REGISTER', 'UNDO'}

    delete: bpy.props.BoolProperty(name="Delete", default=True,
                                   description="Remove the originals (C4D Connect Objects + Delete)")

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and len(context.selected_objects) >= 2

    def execute(self, context):
        if self.delete:
            bpy.ops.c4d.make_editable()
        else:
            bpy.ops.c4d.current_state_to_object()
        baked = list(context.selected_objects)
        for o in list(baked):
            baked += [c for c in o.children_recursive if c not in baked]  # a Cloner's clones
        meshes = [o for o in baked if o.type == 'MESH']
        if len(meshes) < 2:
            self.report({'WARNING'}, "Need at least two polygon objects to connect")
            return {'CANCELLED'}
        _select_only(context, meshes)
        if context.active_object not in meshes:
            context.view_layer.objects.active = meshes[0]
        bpy.ops.object.join()
        return {'FINISHED'}


class C4D_OT_group(bpy.types.Operator):
    """Parent the selection under a new Null (empty) at its center (C4D Alt+G)"""
    bl_idname = "c4d.group"
    bl_label = "Group Objects"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.selected_objects

    def execute(self, context):
        objs = list(context.selected_objects)
        center = sum((o.matrix_world.translation for o in objs), Vector()) / len(objs)
        # Keep the null under the common parent, like C4D does.
        parents = {o.parent for o in objs}
        common_parent = parents.pop() if len(parents) == 1 else None

        null = bpy.data.objects.new("Null", None)
        null.empty_display_type = 'PLAIN_AXES'
        context.collection.objects.link(null)
        null.parent = common_parent
        null.matrix_world.translation = center

        for o in objs:
            mw = o.matrix_world.copy()
            o.parent = null
            o.matrix_world = mw
            o.select_set(False)
        null.select_set(True)
        context.view_layer.objects.active = null
        return {'FINISHED'}


class C4D_OT_ungroup(bpy.types.Operator):
    """Move the children of the selected nulls up one level and delete the nulls (C4D Shift+G)"""
    bl_idname = "c4d.ungroup"
    bl_label = "Expand Object Group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(o.type == 'EMPTY' for o in context.selected_objects)

    def execute(self, context):
        for null in [o for o in context.selected_objects if o.type == 'EMPTY']:
            for child in list(null.children):
                mw = child.matrix_world.copy()
                child.parent = null.parent
                child.matrix_world = mw
                child.select_set(True)
            bpy.data.objects.remove(null)
        return {'FINISHED'}


class C4D_OT_toggle_generators(bpy.types.Operator):
    """Toggle all modifiers of the selected objects in the viewport (C4D Q)"""
    bl_idname = "c4d.toggle_generators"
    bl_label = "Enable/Disable Generators"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.selected_objects

    def execute(self, context):
        for o in context.selected_objects:
            if not o.modifiers:
                continue
            state = not any(m.show_viewport for m in o.modifiers)
            for m in o.modifiers:
                m.show_viewport = state
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Views (F1-F5)
# ---------------------------------------------------------------------------

class C4D_OT_view_panel(bpy.types.Operator):
    """Switch view like C4D F1-F5"""
    bl_idname = "c4d.view_panel"
    bl_label = "C4D View Panel"
    bl_options = {'INTERNAL'}

    view: bpy.props.EnumProperty(items=[
        ('PERSP', "Perspective", ""),
        ('TOP', "Top", ""),
        ('RIGHT', "Right", ""),
        ('FRONT', "Front", ""),
        ('ALL', "All Views", ""),
    ])

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'VIEW_3D'

    def execute(self, context):
        space = context.space_data
        quad = bool(space.region_quadviews)
        if self.view == 'ALL':
            bpy.ops.screen.region_quadview()
            return {'FINISHED'}
        if quad:
            bpy.ops.screen.region_quadview()
        r3d = context.space_data.region_3d
        if self.view == 'PERSP':
            if r3d.view_perspective != 'CAMERA':
                r3d.view_perspective = 'PERSP'
        else:
            bpy.ops.view3d.view_axis(type=self.view)
        return {'FINISHED'}


class C4D_OT_display_mode(bpy.types.Operator):
    """Viewport display mode (C4D N~ chords)"""
    bl_idname = "c4d.display_mode"
    bl_label = "C4D Display Mode"
    bl_options = {'INTERNAL'}

    mode: bpy.props.EnumProperty(items=[
        ('GOURAUD', "Gouraud Shading", ""),
        ('GOURAUD_LINES', "Gouraud Shading (Lines)", ""),
        ('CONSTANT', "Constant Shading", ""),
        ('LINES', "Lines", ""),
        ('TEXTURES', "Textures", ""),
        ('XRAY', "X-Ray", ""),
        ('BACKFACE', "Backface Culling", ""),
    ])

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'VIEW_3D'

    def execute(self, context):
        space = context.space_data
        sh = space.shading
        ov = space.overlay
        if self.mode in {'GOURAUD', 'GOURAUD_LINES'}:
            sh.type = 'SOLID'
            sh.light = 'STUDIO'
            ov.show_wireframes = self.mode == 'GOURAUD_LINES'
        elif self.mode == 'CONSTANT':
            sh.type = 'SOLID'
            sh.light = 'FLAT'
            ov.show_wireframes = False
        elif self.mode == 'LINES':
            sh.type = 'WIREFRAME'
        elif self.mode == 'TEXTURES':
            sh.type = 'MATERIAL'
        elif self.mode == 'XRAY':
            bpy.ops.view3d.toggle_xray()
        elif self.mode == 'BACKFACE':
            sh.show_backface_culling = not sh.show_backface_culling
        return {'FINISHED'}


_prev_shading = {}  # viewport -> shading type before Alt+R (spaces can't hold custom props)


class C4D_OT_interactive_render(bpy.types.Operator):
    """Interactive Render Region (C4D Alt+R): rendered viewport limited to a
    box in the view; Ctrl+B redraws the box, Alt+R again closes it"""
    bl_idname = "c4d.interactive_render"
    bl_label = "Interactive Render Region"
    bl_options = {'INTERNAL'}

    full_view: bpy.props.BoolProperty(name="Full View", default=False,
                                      description="Render the whole viewport instead of a region")

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'VIEW_3D'

    def execute(self, context):
        space = context.space_data
        sh = space.shading
        if sh.type == 'RENDERED':
            sh.type = _prev_shading.pop(space.as_pointer(), 'SOLID')
            space.use_render_border = False
            return {'FINISHED'}
        _prev_shading[space.as_pointer()] = sh.type
        sh.type = 'RENDERED'
        if self.full_view:
            space.use_render_border = False
            return {'FINISHED'}
        # Default region: centred box, like C4D's IRR frame (keep a user-drawn one).
        if (space.render_border_max_x - space.render_border_min_x) >= 0.999:
            space.render_border_min_x, space.render_border_max_x = 0.25, 0.75
            space.render_border_min_y, space.render_border_max_y = 0.25, 0.75
        space.use_render_border = True
        return {'FINISHED'}


class C4D_OT_coord_toggle(bpy.types.Operator):
    """Toggle world/object coordinate system (C4D W)"""
    bl_idname = "c4d.coord_toggle"
    bl_label = "Toggle World/Object Coordinates"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        slot = context.scene.transform_orientation_slots[0]
        slot.type = 'LOCAL' if slot.type == 'GLOBAL' else 'GLOBAL'
        self.report({'INFO'}, "Coordinates: " + ("Object" if slot.type == 'LOCAL' else "World"))
        return {'FINISHED'}


class C4D_OT_split(bpy.types.Operator):
    """Copy the selected elements into a new object (C4D U~P Split)"""
    bl_idname = "c4d.split"
    bl_label = "Split"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        bpy.ops.mesh.duplicate()
        bpy.ops.mesh.separate(type='SELECTED')
        return {'FINISHED'}


class C4D_OT_slide(bpy.types.Operator):
    """Edge slide in edge mode, vertex slide otherwise (C4D M~O)"""
    bl_idname = "c4d.slide"
    bl_label = "Slide"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        if context.tool_settings.mesh_select_mode[1]:
            return bpy.ops.transform.edge_slide('INVOKE_DEFAULT')
        return bpy.ops.transform.vert_slide('INVOKE_DEFAULT')


class C4D_OT_transform_drag(bpy.types.Operator):
    """Move/scale/rotate while dragging, honoring the X/Y/Z axis locks (C4D hold 4/5/6)"""
    bl_idname = "c4d.transform_drag"
    bl_label = "C4D Transform Drag"
    bl_options = {'INTERNAL'}

    mode: bpy.props.EnumProperty(items=[('MOVE', "Move", ""), ('SCALE', "Scale", ""), ('ROTATE', "Rotate", "")])

    def invoke(self, context, event):
        wm = context.window_manager
        axes = (wm.c4d_lock_x, wm.c4d_lock_y, wm.c4d_lock_z)
        kw = {"release_confirm": True}
        if self.mode == 'ROTATE':
            if sum(axes) == 1:
                kw["orient_axis"] = "XYZ"[axes.index(True)]
                kw["constraint_axis"] = axes
            return bpy.ops.transform.rotate('INVOKE_DEFAULT', **kw)
        if not all(axes) and any(axes):
            kw["constraint_axis"] = axes
        op = bpy.ops.transform.translate if self.mode == 'MOVE' else bpy.ops.transform.resize
        return op('INVOKE_DEFAULT', **kw)


class C4D_OT_edit_toggle(bpy.types.Operator):
    """Toggle Model / last component mode (C4D Enter). Parametric objects need Make Editable first"""
    bl_idname = "c4d.edit_toggle"
    bl_label = "Toggle Model Mode"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from .primitives import primitive_name
        ob = context.active_object
        if ob is None:
            return {'CANCELLED'}
        if context.mode == 'OBJECT' and primitive_name(ob):
            self.report({'WARNING'}, "Parametric object: make it editable first (C)")
            return {'CANCELLED'}
        bpy.ops.object.editmode_toggle()
        return {'FINISHED'}


class C4D_OT_noop(bpy.types.Operator):
    """Consume a key press (keys used as held navigation modifiers)"""
    bl_idname = "c4d.noop"
    bl_label = "C4D No-op"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        return {'FINISHED'}


classes = (
    C4D_OT_noop,
    C4D_OT_edit_toggle,
    C4D_OT_transform_drag,
    C4D_OT_tool_set,
    C4D_OT_tool_toggle_last,
    C4D_OT_make_editable, C4D_OT_current_state_to_object, C4D_OT_connect_objects,
    C4D_OT_group,
    C4D_OT_ungroup,
    C4D_OT_toggle_generators,
    C4D_OT_view_panel,
    C4D_OT_display_mode,
    C4D_OT_interactive_render,
    C4D_OT_coord_toggle,
    C4D_OT_split,
    C4D_OT_slide,
)
