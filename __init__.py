bl_info = {
    "name": "Silhouette Dual View (Front+Right)",
    "author": "Florian \"Wespenwald\" Wurster",
    "version": (1, 0, 0),
    "blender": (4, 5, 0),
    "location": "3D View > View",
    "description": "Open a new window split into FRONT and RIGHT orthographic silhouette views of the selection",
    "category": "3D View",
    "doc_url": "https://wespenwald.neocities.org/",
}

import bpy
from bpy.types import Operator

# ---- helpers ----

def _find_window_view3d_area(win: bpy.types.Window):
    area_view3d = None
    region_window = None
    try:
        for area in win.screen.areas:
            if area.type == 'VIEW_3D':
                area_view3d = area
                break
        if area_view3d:
            for region in area_view3d.regions:
                if region.type == 'WINDOW':
                    region_window = region
                    break
    except Exception:
        pass
    return area_view3d, region_window


def _override(win=None, area=None, region=None):
    # Safe override: DO NOT dereference win.screen (can crash in timers)
    ov = {}
    if win is not None:
        ov['window'] = win
    if area is not None:
        ov['area'] = area
    if region is not None:
        ov['region'] = region
    return ov


def _apply_view_axis(win, area, region, axis: str):
    """Use the same operator as numpad: view3d.viewnumpad, enforce ORTHO, then lock the resulting rotation."""
    # Force ORTHO first
    try:
        area.spaces.active.region_3d.view_perspective = 'ORTHO'
    except Exception:
        pass
    try:
        screen = getattr(win, 'screen', None)
        with bpy.context.temp_override(window=win, screen=screen, area=area, region=region):
            try:
                bpy.ops.view3d.viewnumpad(type=axis, align_active=False)
            except Exception:
                try:
                    bpy.ops.view3d.view_axis(type=axis, align_active=False)
                except Exception:
                    bpy.ops.view3d.view_axis(type=axis)
    except Exception:
        # Last resort: try legacy override
        ov = _override(None, area, region)
        try:
            bpy.ops.view3d.viewnumpad(ov, type=axis, align_active=False)
        except Exception:
            try:
                bpy.ops.view3d.view_axis(ov, type=axis, align_active=False)
            except Exception:
                try:
                    bpy.ops.view3d.view_axis(ov, type=axis)
                except Exception:
                    pass
    # Lock in the resulting quaternion so Blender won't drift
    try:
        q = area.spaces.active.region_3d.view_rotation.copy()
        area.spaces.active.region_3d.view_rotation = q
    except Exception:
        pass


def _configure_silhouette_area(context, win, area, region, axis: str):
    """Configure the given VIEW_3D area to silhouette style and axis."""
    # Ensure editor type is VIEW_3D
    try:
        area.type = 'VIEW_3D'
    except Exception:
        pass
    # Ensure correct UI type
    try:
        area.ui_type = 'VIEW_3D'
    except Exception:
        pass
    space = area.spaces.active
    # Silhouette styling
    try:
        sh = space.shading
        sh.type = 'SOLID'
        sh.light = 'FLAT'
        sh.color_type = 'SINGLE'
        sh.single_color = (0.0, 0.0, 0.0)
        sh.background_type = 'VIEWPORT'
        sh.background_color = (1.0, 1.0, 1.0)
    except Exception:
        pass

    # Hide UI & overlays/gizmos
    try:
        space.show_region_header = False
        space.show_region_tool_header = False
        space.show_region_toolbar = False
        space.show_region_ui = False
        try:
            # Hide HUD if Blender exposes it
            space.show_region_hud = False
        except Exception:
            pass
        space.show_gizmo = False
        space.show_gizmo_navigate = False
        space.overlay.show_overlays = False
    except Exception:
        pass

    # Apply axis, frame selection, then re-apply axis to keep it distinct
    _apply_view_axis(win, area, region, axis)
    try:
        screen = getattr(win, 'screen', None)
        with bpy.context.temp_override(window=win, screen=screen, area=area, region=region):
            bpy.ops.view3d.view_selected(use_all_regions=False)
    except Exception:
        pass
    _apply_view_axis(win, area, region, axis)
    # Re-hide UI to ensure nothing pops back
    try:
        space.show_region_header = False
        space.show_region_tool_header = False
        space.show_region_toolbar = False
        space.show_region_ui = False
        space.show_gizmo = False
        space.show_gizmo_navigate = False
        space.overlay.show_overlays = False
        try:
            area.tag_redraw()
        except Exception:
            pass
    except Exception:
        pass


def _split_area_and_get_new(win: bpy.types.Window, area: bpy.types.Area, direction='VERTICAL', factor=0.5):
    """Split the given area and return the newly created area deterministically.
    If direction='VERTICAL' -> return the area to the right. If 'HORIZONTAL' -> area above.
    """
    region_window = next((r for r in area.regions if r.type == 'WINDOW'), None)
    if not region_window:
        return None
    # Use the owning screen from the area itself to avoid referencing win.screen
    screen = getattr(area, 'id_data', None)
    if screen is None:
        return None
    # Only pass area+region to area_split
    ov = {'area': area, 'region': region_window}
    before = list(screen.areas)
    orig_x, orig_y = area.x, area.y
    ok = False
    try:
        bpy.ops.screen.area_split(ov, direction=direction, factor=factor)
        ok = True
    except Exception:
        pass
    if not ok:
        try:
            cx = area.x + max(1, int(area.width * factor))
            cy = area.y + max(1, int(area.height * factor))
            bpy.ops.screen.area_split(ov, direction=direction, cursor=(cx, cy))
            ok = True
        except Exception:
            return None

    candidates = [a for a in screen.areas if a not in before and a.type == area.type]
    if not candidates:
        candidates = [a for a in screen.areas if a not in before]
    if not candidates:
        if direction == 'VERTICAL':
            rights = [a for a in screen.areas if a.type == area.type and a.x > orig_x]
            return max(rights, key=lambda a: a.x, default=None)
        else:
            uppers = [a for a in screen.areas if a.type == area.type and a.y > orig_y]
            return max(uppers, key=lambda a: a.y, default=None)

    if direction == 'VERTICAL':
        pref = [a for a in candidates if a.x > orig_x]
        return max(pref or candidates, key=lambda a: a.x)
    else:
        pref = [a for a in candidates if a.y > orig_y]
        return max(pref or candidates, key=lambda a: a.y)


# ---- operator ----

class VIEW3D_OT_open_silhouette_view_dual(Operator):
    bl_idname = "view3d.open_silhouette_view_dual"
    bl_label = "Open Silhouette (Front+Right)"
    bl_description = "Open a new window split into FRONT and RIGHT orthographic silhouette views of the selection"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.view_layer.objects.active is not None

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        # 0) Create new window
        orig_win = context.window
        try:
            bpy.ops.wm.window_new()
        except Exception as e:
            self.report({'ERROR'}, f"Failed to open new window: {e}")
            return {'CANCELLED'}

        new_win = bpy.context.window
        # Modest size exactly 25% of the original Blender window
        try:
            ow, oh = getattr(orig_win, 'width', 1600), getattr(orig_win, 'height', 900)
            target_w = max(480, int(ow * 0.25))
            target_h = max(360, int(oh * 0.25))
            new_win.width = target_w
            new_win.height = target_h
            new_win.x = getattr(orig_win, 'x', 100) + 80
            new_win.y = getattr(orig_win, 'y', 100) - 80
            new_win.screen.show_statusbar = False
        except Exception:
            pass

        # Enforce size after creation in case Blender adjusts it post-open
        # Remove window resize enforcement to avoid size flapping; keep Blender defaults
        try:
            new_win.screen.show_statusbar = False
        except Exception:
            pass

        # Defer split and configuration to ensure the new window is fully ready
        def _deferred_setup():
            try:
                area_a, region_a = _find_window_view3d_area(new_win)
                if area_a is None or region_a is None:
                    return 0.05  # retry shortly
                # Split horizontally to create TOP/BOTTOM
                screen = getattr(new_win, 'screen', None)
                before = list(screen.areas) if screen else []
                ok = False
                try:
                    with bpy.context.temp_override(window=new_win, area=area_a, region=region_a):
                        bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.5)
                    ok = True
                except Exception:
                    try:
                        cy = area_a.y + max(1, int(area_a.height * 0.5))
                        with bpy.context.temp_override(window=new_win, area=area_a, region=region_a):
                            bpy.ops.screen.area_split(direction='HORIZONTAL', cursor=(area_a.x + 5, cy))
                        ok = True
                    except Exception:
                        return 0.05
                if not ok:
                    return 0.05
                # Identify new area and map to top/bottom
                screen = getattr(new_win, 'screen', None)
                new_candidates = [a for a in (screen.areas if screen else []) if a not in before]
                if not new_candidates:
                    return 0.05
                new_area = new_candidates[0]
                if area_a.y >= new_area.y:
                    area_top, area_bottom = area_a, new_area
                else:
                    area_top, area_bottom = new_area, area_a
                reg_top = next((r for r in area_top.regions if r.type == 'WINDOW'), None)
                reg_bottom = next((r for r in area_bottom.regions if r.type == 'WINDOW'), None)
                if not reg_top or not reg_bottom:
                    return 0.05
                # Configure both areas
                _configure_silhouette_area(context, new_win, area_top, reg_top, axis='FRONT')
                _configure_silhouette_area(context, new_win, area_bottom, reg_bottom, axis='RIGHT')
                _apply_view_axis(new_win, area_top, reg_top, 'FRONT')
                _apply_view_axis(new_win, area_bottom, reg_bottom, 'RIGHT')
                # One-time UI reassert
                for a in (area_top, area_bottom):
                    try:
                        sp = a.spaces.active
                        sp.show_region_header = False
                        sp.show_region_tool_header = False
                        sp.show_region_toolbar = False
                        sp.show_region_ui = False
                        sp.show_gizmo = False
                        sp.show_gizmo_navigate = False
                        sp.overlay.show_overlays = False
                    except Exception:
                        pass
                # One-time distance backoff
                try:
                    r3d_top = area_top.spaces.active.region_3d
                    r3d_bot = area_bottom.spaces.active.region_3d
                    dist = float(getattr(r3d_top, 'view_distance', 5.0)) or 5.0
                    dist *= 1.3
                    r3d_top.view_distance = dist
                    r3d_bot.view_distance = dist
                except Exception:
                    pass
                
                return None
            except Exception:
                return None
        try:
            bpy.app.timers.register(_deferred_setup, first_interval=0.05)
        except Exception:
            pass

        return {'FINISHED'}


# An alternative operator: split the CURRENT 3D View into Front+Right silhouettes (no new window)
class VIEW3D_OT_open_silhouette_split_current(Operator):
    bl_idname = "view3d.open_silhouette_split_current"
    bl_label = "Silhouette Split Here (Front+Right)"
    bl_description = "Split the current 3D View into FRONT and RIGHT orthographic silhouette views"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'OBJECT' and
            context.area is not None and context.area.type == 'VIEW_3D' and
            context.view_layer.objects.active is not None
        )

    def execute(self, context):
        area = context.area
        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
        if region is None:
            self.report({'ERROR'}, "No WINDOW region in current area.")
            return {'CANCELLED'}

        win = context.window
        scr = context.screen
        ov = {'area': area, 'region': region}

        # 1) Split current area vertically into LEFT and RIGHT
        before = list(scr.areas)
        orig_x = area.x
        try:
            bpy.ops.screen.area_split(direction='VERTICAL', factor=0.5)
        except Exception:
            try:
                cx = area.x + max(1, int(area.width * 0.5))
                cy = area.y + max(1, int(area.height * 0.5))
                bpy.ops.screen.area_split(direction='VERTICAL', cursor=(cx, cy))
            except Exception as e:
                self.report({'ERROR'}, f"Failed to split current area: {e}")
                return {'CANCELLED'}

        new_areas = [a for a in scr.areas if a not in before]
        # Determine LEFT and RIGHT by x
        if not new_areas:
            self.report({'ERROR'}, "Could not determine new split area.")
            return {'CANCELLED'}
        area_right = max(new_areas, key=lambda a: a.x)
        area_left = area if area.x <= area_right.x else area_right
        if area_right is area_left:
            # Fallback pick by x
            sorted_by_x = sorted([area] + new_areas, key=lambda a: a.x)
            area_left, area_right = sorted_by_x[0], sorted_by_x[-1]

        # 2) Split LEFT area horizontally into TOP/BOTTOM (or above/below)
        before2 = list(scr.areas)
        # Make LEFT area active context for split
        try:
            for r in area_left.regions:
                if r.type == 'WINDOW':
                    with context.temp_override(area=area_left, region=r):
                        try:
                            bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.5)
                        except Exception:
                            cy = area_left.y + max(1, int(area_left.height * 0.5))
                            bpy.ops.screen.area_split(direction='HORIZONTAL', cursor=(area_left.x + 5, cy))
                    break
        except Exception as e:
            self.report({'ERROR'}, f"Failed to split left area: {e}")
            return {'CANCELLED'}

        new_areas2 = [a for a in scr.areas if a not in before2]
        if not new_areas2:
            self.report({'ERROR'}, "Could not determine sub-areas of left split.")
            return {'CANCELLED'}
        # Identify the two left sub-areas by x proximity to area_left.x
        left_subs = sorted([a for a in new_areas2 + [area_left] if a.type == 'VIEW_3D'], key=lambda a: (abs(a.x - area_left.x), -a.y))[:2]
        if len(left_subs) < 2:
            self.report({'ERROR'}, "Left split did not produce two VIEW_3D areas.")
            return {'CANCELLED'}
        # top is higher y
        left_top, left_bottom = sorted(left_subs, key=lambda a: a.y, reverse=True)

        # Resolve regions
        get_win_region = lambda a: next((r for r in a.regions if r.type == 'WINDOW'), None)
        reg_top = get_win_region(left_top)
        reg_bottom = get_win_region(left_bottom)
        if not reg_top or not reg_bottom:
            self.report({'ERROR'}, "Could not get WINDOW regions for left sub-areas.")
            return {'CANCELLED'}

        # Configure silhouettes on left sub-areas only: FRONT (top), RIGHT (bottom)
        _configure_silhouette_area(context, win, left_top, reg_top, axis='FRONT')
        _configure_silhouette_area(context, win, left_bottom, reg_bottom, axis='RIGHT')
        _apply_view_axis(win, left_top, reg_top, 'FRONT')
        _apply_view_axis(win, left_bottom, reg_bottom, 'RIGHT')

        # Finalize with a tiny deferred re-apply to ensure distinct axes and hidden UI stick
        def _post_fix():
            try:
                # Re-apply axis and UI hiding in case Blender changed anything after framing
                _apply_view_axis(win, left_top, reg_top, 'FRONT')
                _apply_view_axis(win, left_bottom, reg_bottom, 'RIGHT')
                # If both ended up identical, rotate bottom by +90deg around Z to guarantee RIGHT
                try:
                    from mathutils import Quaternion
                    qt = left_top.spaces.active.region_3d.view_rotation.copy()
                    qb = left_bottom.spaces.active.region_3d.view_rotation.copy()
                    same = all(abs(a - b) < 1e-5 for a, b in zip(qt, qb))
                    if same:
                        z90 = Quaternion((0.70710678, 0.0, 0.0, 0.70710678))  # +90 deg around Z
                        left_bottom.spaces.active.region_3d.view_rotation = (z90 @ qt)
                        left_bottom.spaces.active.region_3d.view_perspective = 'ORTHO'
                except Exception:
                    pass
                # Re-hide UI explicitly
                for a in (left_top, left_bottom):
                    sp = a.spaces.active
                    sp.show_region_header = False
                    sp.show_region_tool_header = False
                    sp.show_region_toolbar = False
                    sp.show_region_ui = False
                    sp.show_gizmo = False
                    sp.show_gizmo_navigate = False
                    sp.overlay.show_overlays = False
            except Exception:
                pass
            return None
        try:
            bpy.app.timers.register(_post_fix, first_interval=0.05)
        except Exception:
            pass

        return {'FINISHED'}


# ---- menu ----

def draw_in_view_menu(self, context):
    if context.mode == 'OBJECT':
        # Single dropdown entry instead of two separate items
        self.layout.menu(VIEW3D_MT_silhouette_menu.bl_idname, text="Silhouette")


class VIEW3D_MT_silhouette_menu(bpy.types.Menu):
    bl_label = "Silhouette (Front+Right)"
    bl_idname = "VIEW3D_MT_silhouette_menu"

    def draw(self, context):
        layout = self.layout
        layout.operator("view3d.open_silhouette_split_current", text="Split Here (Front+Right)")
        layout.operator("view3d.open_silhouette_view_dual", text="New Window (Front+Right)")


# ---- register ----

def register():
    bpy.utils.register_class(VIEW3D_OT_open_silhouette_split_current)
    bpy.utils.register_class(VIEW3D_OT_open_silhouette_view_dual)
    bpy.utils.register_class(VIEW3D_MT_silhouette_menu)
    bpy.types.VIEW3D_MT_view.append(draw_in_view_menu)


def unregister():
    bpy.types.VIEW3D_MT_view.remove(draw_in_view_menu)
    bpy.utils.unregister_class(VIEW3D_MT_silhouette_menu)
    bpy.utils.unregister_class(VIEW3D_OT_open_silhouette_split_current)
    bpy.utils.unregister_class(VIEW3D_OT_open_silhouette_view_dual)

if __name__ == "__main__":
    register()
