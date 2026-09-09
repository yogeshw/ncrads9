from pathlib import Path

from ncrads9.communication.xpa.xpa_commands import XPACommands
from ncrads9.coordinates.coord_system import CoordinateContext
from ncrads9.rendering.scale_algorithms import ScaleAlgorithm
from ncrads9.ui.layout.view_state import ViewState


class _DummyAction:
    def __init__(self, checked: bool = False) -> None:
        self._checked = checked

    def setChecked(self, checked: bool) -> None:
        self._checked = bool(checked)

    def isChecked(self) -> bool:
        return self._checked


class _DummyTimer:
    def __init__(self) -> None:
        self._active = False

    def isActive(self) -> bool:
        return self._active


class _DummyImageViewer:
    def __init__(self) -> None:
        self._zoom = 1.0

    def zoom_to(self, zoom: float) -> None:
        self._zoom = float(zoom)

    def get_zoom(self) -> float:
        return self._zoom


class _DummyStatusBar:
    def __init__(self) -> None:
        self.zoom = 1.0

    def update_zoom(self, zoom: float) -> None:
        self.zoom = zoom


class _DummyViewController:
    """Stands in for `ViewController`, which owns colorbar visibility."""

    def __init__(self, state) -> None:
        self._state = state

    def set_colorbar_visible(self, visible: bool) -> None:
        self._state.colorbar = bool(visible)


class _DummyColorbarWidget:
    def __init__(self) -> None:
        self.tick_count = 7
        self.bar_size = 40

    def set_tick_count(self, count: int) -> None:
        self.tick_count = int(count)

    def set_bar_size(self, size: int) -> None:
        self.bar_size = int(size)


class _DummyFrame:
    def __init__(self) -> None:
        self.filepath = None
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.regions = []


class _DummyFrameManager:
    def __init__(self) -> None:
        self.frames = [_DummyFrame()]
        self.current_index = 0

    @property
    def current_frame(self):
        return self.frames[self.current_index]

    def goto_frame(self, index: int):
        if 0 <= index < len(self.frames):
            self.current_index = index
            return self.current_frame
        return None


class _DummyFrameController:
    """The slice of FrameController that XPA calls."""

    def __init__(self, window):
        self.window = window

    @property
    def _frames(self):
        return self.window.frame_manager

    def new_frame(self):
        self._frames.frames.append(_DummyFrame())
        self._frames.current_index = len(self._frames.frames) - 1

    def new_frame_of_type(self, frame_type):
        self.new_frame()

    def delete_current(self):
        if len(self._frames.frames) > 1:
            self._frames.frames.pop(self._frames.current_index)
            self._frames.current_index = max(0, self._frames.current_index - 1)

    def delete_all(self):
        del self._frames.frames[1:]
        self._frames.current_index = 0

    def clear_current(self):
        return

    def reset_current(self):
        return

    def refresh_current(self):
        return

    def first(self):
        self._frames.current_index = 0

    def previous(self):
        self._frames.current_index = max(0, self._frames.current_index - 1)

    def next(self):
        self._frames.current_index = min(len(self._frames.frames) - 1, self._frames.current_index + 1)

    def last(self):
        self._frames.current_index = len(self._frames.frames) - 1

    def update_display(self):
        return

    def set_tile(self, checked: bool):
        self.window.menu_bar.action_tile_frames.setChecked(checked)

    def set_blink(self, checked: bool):
        self.window._blink_timer._active = checked

    def match_image(self):
        return

    def match_wcs(self):
        return


class _DummyRegionController:
    """The slice of RegionController that XPA calls."""

    def __init__(self, window):
        self.window = window

    def clear_regions(self):
        self.window.frame_manager.current_frame.regions.clear()


class _DummyFileController:
    """The slice of FileController that XPA calls."""

    def __init__(self, window):
        self.window = window

    def open_file(self, checked=False, filepath=None):
        self.window.frame_manager.current_frame.filepath = Path(filepath or checked)

    def current_pixmap(self):
        return None  # No XPA test exercises saveimage; the handler guards None.


class _DummyColorController:
    """The slice of ColorController that XPA calls."""

    def __init__(self, window):
        self.window = window

    def available_colormaps(self):
        return ["grey", "heat", "cool", "rainbow", "viridis", "magma"]

    def set_colormap(self, name: str):
        self.window.current_colormap = name

    def set_colorbar_orientation(self, orientation: str):
        self.window.colorbar_orientation = orientation

    def set_colorbar_numerics(self, show: bool):
        self.window.colorbar_numerics = bool(show)

    def set_colorbar_spacing(self, mode: str):
        self.window.colorbar_spacing = mode


class _DummyScaleController:
    """The slice of ScaleController that XPA calls."""

    def __init__(self, window):
        self.window = window

    def set_scale(self, scale: ScaleAlgorithm):
        self.window.current_scale = scale

    def reset_limits(self):
        return

    def set_minmax_limits(self):
        return


class _DummyWCSController:
    """The slice of WCSController that XPA calls."""

    def __init__(self, window):
        self.window = window

    def set_sky_frame(self, system: str):
        self.window.coord_context = self.window.coord_context.with_sky(system)


class _DummyViewer:
    def __init__(self) -> None:
        self.frame_manager = _DummyFrameManager()
        self.menu_bar = type(
            "MenuBar",
            (),
            {
                "action_tile_frames": _DummyAction(),
                "action_blink_frames": _DummyAction(),
            },
        )()
        self._blink_timer = _DummyTimer()
        self.image_viewer = _DummyImageViewer()
        self.status_bar = _DummyStatusBar()
        # Colorbar visibility became a View-menu flag in M3, so it is read
        # off the window's ViewState rather than a dock's isVisible().
        self.view_state = ViewState()
        self.view = _DummyViewController(self.view_state)
        self.colorbar_widget = _DummyColorbarWidget()
        self.current_colormap = "grey"
        self.current_scale = ScaleAlgorithm.LINEAR
        self.coord_context = CoordinateContext()
        self.colorbar_orientation = "vertical"
        self.colorbar_numerics = True
        self.colorbar_spacing = "value"
        self._last_mouse_pos = (5, 6)
        # XPA reaches scale and WCS through the controllers as of M2, so the
        # fake exposes the same surface rather than the old flat methods.
        self.frame_controller = _DummyFrameController(self)
        self.region = _DummyRegionController(self)
        self.file = _DummyFileController(self)
        self.color = _DummyColorController(self)
        self.scale = _DummyScaleController(self)
        self.wcs = _DummyWCSController(self)
        self._w = 800
        self._h = 600

    def _tile_frames(self, checked: bool):
        self.menu_bar.action_tile_frames.setChecked(checked)

    def _toggle_blink(self, checked: bool):
        self._blink_timer._active = checked

    def _zoom_fit(self):
        self.image_viewer.zoom_to(0.8)

    def _zoom_in(self):
        self.image_viewer.zoom_to(self.image_viewer.get_zoom() * 1.2)

    def _zoom_out(self):
        self.image_viewer.zoom_to(self.image_viewer.get_zoom() / 1.2)

    def _display_image(self):
        return

    def _on_panner_pan(self, x: float, y: float):
        frame = self.frame_manager.current_frame
        frame.pan_x = x
        frame.pan_y = y

    def _match_frames_image(self):
        return

    def _match_frames_wcs(self):
        return

    def resize(self, width: int, height: int):
        self._w = width
        self._h = height

    def width(self) -> int:
        return self._w

    def height(self) -> int:
        return self._h

    def close(self):
        return


def test_frame_command_set_and_get():
    viewer = _DummyViewer()
    viewer.frame_controller.new_frame()
    commands = XPACommands(viewer)
    set_response = commands.handle("frame", {"args": [2]})
    assert set_response["status"] == "ok"
    assert set_response["result"] == "2"
    get_response = commands.handle("frame", {"action": "get"})
    assert get_response["result"] == "2"


def test_zoom_tile_and_blink_commands():
    viewer = _DummyViewer()
    commands = XPACommands(viewer)
    commands.handle("zoom", {"level": 2.5})
    assert viewer.image_viewer.get_zoom() == 2.5
    commands.handle("tile", {"enabled": True})
    assert viewer.menu_bar.action_tile_frames.isChecked()
    commands.handle("blink", {"action": "start"})
    assert viewer._blink_timer.isActive()


def test_file_and_cmap_commands():
    viewer = _DummyViewer()
    commands = XPACommands(viewer)
    commands.handle("file", {"path": "/tmp/test.fits", "action": "load"})
    assert viewer.frame_manager.current_frame.filepath == Path("/tmp/test.fits")
    commands.handle("cmap", {"name": "heat"})
    assert viewer.current_colormap == "heat"


def test_colorbar_extended_commands():
    viewer = _DummyViewer()
    commands = XPACommands(viewer)
    commands.handle(
        "colorbar",
        {"visible": False, "orientation": "horizontal", "numerics": False, "ticks": 5, "size": 24},
    )
    assert viewer.view_state.colorbar is False
    assert viewer.colorbar_orientation == "horizontal"
    assert viewer.colorbar_numerics is False
    assert viewer.colorbar_widget.tick_count == 5
    assert viewer.colorbar_widget.bar_size == 24
