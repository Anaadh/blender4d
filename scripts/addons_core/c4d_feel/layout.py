"""Build a "C4D" workspace:

    +----------------------------+-----------------+
    |                            | Object Manager  |
    |         Viewport           |   (Outliner)    |
    |                            +-----------------+
    |                            |Attribute Manager|
    +----------------------------+   (Properties)  |
    |         Timeline           |                 |
    +----------------------------+-----------------+

Blender's area_move operator refuses to run while the mouse hovers a
region, so the layout is rebuilt by closing areas down to one viewport and
splitting it again. Area geometry only updates between event-loop ticks, so
each step runs from its own timer tick.
"""

import bpy

WORKSPACE = "C4D"
RIGHT_COLUMN = 0.27      # fraction of window width
OBJECT_MANAGER = 0.45    # fraction of right column height
BOTTOM_STRIP = 0.2       # Material + Coordinate Manager, fraction of left column
TIMELINE = 0.1           # fraction of what remains above the bottom strip


def _areas(window, kind=None):
    return [a for a in window.screen.areas if kind is None or a.type == kind]


def _override(window, area):
    return bpy.context.temp_override(window=window, screen=window.screen, area=area,
                                     region=area.regions[-1])


def _split(window, area, direction, factor):
    """Split area; return the newly created area (right/top part)."""
    before = set(window.screen.areas)
    with _override(window, area):
        bpy.ops.screen.area_split(direction=direction, factor=factor)
    new = [a for a in window.screen.areas if a not in before]
    return new[0] if new else None


def _steps(window):
    # 1. Close everything except the largest viewport, one area per tick.
    while True:
        views = _areas(window, 'VIEW_3D')
        keep = max(views, key=lambda a: a.width * a.height)
        others = [a for a in _areas(window) if a != keep]
        if not others:
            break
        with _override(window, others[0]):
            bpy.ops.screen.area_close()
        yield

    view = _areas(window, 'VIEW_3D')[0]

    # 2. Right column.
    right = _split(window, view, 'VERTICAL', 1.0 - RIGHT_COLUMN)
    yield
    right.type = 'PROPERTIES'

    # 3. Object Manager on top of the Attribute Manager.
    om = _split(window, right, 'HORIZONTAL', 1.0 - OBJECT_MANAGER)
    yield
    from .managers import native_object_manager
    # C4D Object Manager: native Outliner mode on the fork, custom list otherwise.
    om.type = 'OUTLINER' if native_object_manager() else 'PROPERTIES'

    # 4. Bottom strip under the viewport: Material Manager (Asset Browser) whose
    #    sidebar holds the Coordinate Manager.
    view = max(_areas(window, 'VIEW_3D'), key=lambda a: a.width * a.height)
    other = _split(window, view, 'HORIZONTAL', BOTTOM_STRIP)
    yield
    bottom = min((view, other), key=lambda a: a.y)
    bottom.type = 'FILE_BROWSER'
    bottom.ui_type = 'ASSETS'
    yield

    # 5. Timeline between viewport and bottom strip.
    view = max(_areas(window, 'VIEW_3D'), key=lambda a: a.width * a.height)
    other = _split(window, view, 'HORIZONTAL', TIMELINE)
    yield
    bottom = min((view, other), key=lambda a: a.y)
    bottom.type = 'DOPESHEET_EDITOR'
    bottom.ui_type = 'TIMELINE'
    yield

    _configure(window)


def _configure(window):
    # Fork: give the C4D palette its own tall top-bar row.
    if hasattr(window.screen, "show_c4d_palette"):
        window.screen.show_c4d_palette = True
    from .managers import configure_object_manager, configure_native_object_manager, native_object_manager
    for area in _areas(window, 'OUTLINER'):
        if native_object_manager():
            configure_native_object_manager(area.spaces.active)
        else:
            configure_object_manager(area.spaces.active)
    from .om import configure_space
    for area in _areas(window, 'PROPERTIES'):
        if area.y + area.height / 2 > window.height / 2:
            configure_space(area.spaces.active)   # upper: Object Manager
            continue
        try:
            area.spaces.active.context = 'OBJECT'
        except TypeError:
            pass
    for area in _areas(window, 'DOPESHEET_EDITOR'):
        area.spaces.active.show_region_channels = False
    for area in _areas(window, 'FILE_BROWSER'):
        sp = area.spaces.active
        params = sp.params
        if params is None:
            continue
        try:
            params.asset_library_reference = 'LOCAL'
        except TypeError:
            pass
        f = params.filter_asset_id
        for name in dir(f):
            if name.startswith("filter_"):
                try:
                    setattr(f, name, name == "filter_material")
                except (AttributeError, TypeError):
                    pass
        params.use_filter = True
        sp.show_region_toolbar = False     # catalog tree
        sp.show_region_tool_props = True   # sidebar -> Coordinate Manager
        for size in (64, 'SMALL'):
            try:
                params.display_size = size
                break
            except (TypeError, AttributeError, ValueError):
                pass
    for area in _areas(window, 'VIEW_3D'):
        s = area.spaces.active
        s.show_region_toolbar = True
        s.show_region_tool_header = True  # Blender tools need their options bar
        s.show_region_ui = False


def _run_steps(window):
    gen = _steps(window)

    def tick():
        if window.workspace.name != WORKSPACE:
            return None
        try:
            next(gen)
        except StopIteration:
            return None
        return 0.05
    bpy.app.timers.register(tick, first_interval=0.3)


class C4D_OT_setup_workspace(bpy.types.Operator):
    """Create (or switch to) the C4D-style workspace"""
    bl_idname = "c4d.setup_workspace"
    bl_label = "Create C4D Workspace"
    bl_options = {'REGISTER'}

    def execute(self, context):
        # Only one workspace change per event-loop tick: Blender 5.2 crashed in
        # ED_workspace_change when window.workspace was set twice before the
        # notifiers ran. Duplicate (which activates the copy) and rearrange
        # from timers once the switch has landed.
        window = context.window
        ws = bpy.data.workspaces.get(WORKSPACE)
        if ws is not None:
            if window.workspace != ws:
                window.workspace = ws
            _run_steps(window)  # rebuild the layout
            return {'FINISHED'}

        base = bpy.data.workspaces.get("Layout")
        if base is None:
            self.report({'ERROR'}, "Needs the default 'Layout' workspace to copy")
            return {'CANCELLED'}
        before = set(bpy.data.workspaces)
        with context.temp_override(window=window, workspace=base):
            bpy.ops.workspace.duplicate()
        new = [w for w in bpy.data.workspaces if w not in before]
        if not new:
            return {'CANCELLED'}
        new[0].name = WORKSPACE
        _run_steps(window)
        return {'FINISHED'}


classes = (C4D_OT_setup_workspace,)
