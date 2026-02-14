from pathlib import Path

from ncrads9.communication.xpa.xpa_commands import XPACommands
from ncrads9.rendering.scale_algorithms import ScaleAlgorithm


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


class _DummyDock:
    def __init__(self) -> None:
        self._visible = True

    def setVisible(self, visible: bool) -> None:
        self._visible = visible

    def isVisible(self) -> bool:
        return self._visible


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
        self.colorbar_dock = _DummyDock()
        self.current_colormap = "grey"
        self.current_scale = ScaleAlgorithm.LINEAR
        self.current_wcs_system = "fk5"
        self._last_mouse_pos = (5, 6)
        self._w = 800
        self._h = 600

    def open_file(self, filepath):
        self.frame_manager.current_frame.filepath = Path(filepath)

    def _new_frame(self):
        self.frame_manager.frames.append(_DummyFrame())
        self.frame_manager.current_index = len(self.frame_manager.frames) - 1

    def _delete_frame(self):
        if len(self.frame_manager.frames) > 1:
            self.frame_manager.frames.pop(self.frame_manager.current_index)
            self.frame_manager.current_index = max(0, self.frame_manager.current_index - 1)

    def _first_frame(self):
        self.frame_manager.current_index = 0

    def _prev_frame(self):
        self.frame_manager.current_index = max(0, self.frame_manager.current_index - 1)

    def _next_frame(self):
        self.frame_manager.current_index = min(
            len(self.frame_manager.frames) - 1, self.frame_manager.current_index + 1
        )

    def _last_frame(self):
        self.frame_manager.current_index = len(self.frame_manager.frames) - 1

    def _update_frame_display(self):
        return

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

    def _set_colormap(self, name: str):
        self.current_colormap = name

    def _set_scale(self, scale: ScaleAlgorithm):
        self.current_scale = scale

    def _reset_scale_limits(self):
        return

    def _scale_minmax(self):
        return

    def _display_image(self):
        return

    def _on_panner_pan(self, x: float, y: float):
        frame = self.frame_manager.current_frame
        frame.pan_x = x
        frame.pan_y = y

    def _clear_regions(self):
        self.frame_manager.current_frame.regions.clear()

    def _set_wcs_system(self, system: str):
        self.current_wcs_system = system

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
    viewer._new_frame()
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
