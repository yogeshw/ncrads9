# NCRADS9 - NCRA DS9-like FITS Viewer
# Copyright (C) 2026 Yogesh Wadadekar
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Edit -> Undo and Redo (M9-24)."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.utils.undo import Command, UndoStack

SIZE = 32


# -- the stack ------------------------------------------------------------------


def _recorder():
    """A command that writes down when it is undone and redone."""
    done: list[str] = []
    command = Command(
        label="Thing",
        undo=lambda: done.append("undo"),
        redo=lambda: done.append("redo"),
    )
    return command, done


def test_a_new_stack_has_nothing_to_undo():
    stack = UndoStack()
    assert stack.can_undo is False
    assert stack.can_redo is False
    assert stack.undo() is None
    assert stack.redo() is None


def test_undo_and_redo_call_the_commands():
    stack = UndoStack()
    command, done = _recorder()
    stack.push(command)

    assert stack.undo() == "Thing"
    assert done == ["undo"]
    assert stack.redo() == "Thing"
    assert done == ["undo", "redo"]


def test_the_labels_say_what_would_happen():
    stack = UndoStack()
    stack.record("Delete Regions", undo=lambda: None, redo=lambda: None)
    assert stack.undo_label == "Delete Regions"
    assert stack.redo_label == ""
    stack.undo()
    assert stack.undo_label == ""
    assert stack.redo_label == "Delete Regions"


def test_doing_something_new_forgets_what_was_undone():
    """As every editor does: once you do something new, the branch you had
    undone is not coming back."""
    stack = UndoStack()
    stack.record("First", undo=lambda: None, redo=lambda: None)
    stack.undo()
    assert stack.can_redo is True

    stack.record("Second", undo=lambda: None, redo=lambda: None)
    assert stack.can_redo is False
    assert stack.labels() == ["Second"]


def test_the_stack_has_a_depth_and_drops_the_oldest():
    stack = UndoStack(depth=3)
    for number in range(5):
        stack.record(str(number), undo=lambda: None, redo=lambda: None)
    assert stack.labels() == ["2", "3", "4"]


def test_a_depth_of_nothing_is_still_a_depth_of_one():
    stack = UndoStack(depth=0)
    stack.record("One", undo=lambda: None, redo=lambda: None)
    assert len(stack) == 1


def test_nothing_is_recorded_while_undoing():
    """An undo puts state back, and recording that would make the undo
    itself undoable -- which is how an undo stack starts oscillating."""
    stack = UndoStack()
    inner: list = []

    def undo() -> None:
        inner.append(stack.record("Inner", undo=lambda: None, redo=lambda: None))

    stack.push(Command("Outer", undo=undo, redo=lambda: None))
    stack.undo()
    assert inner == [None]
    assert stack.labels() == []


def test_the_applying_flag_is_cleared_even_if_a_command_raises():
    stack = UndoStack()

    def boom() -> None:
        raise RuntimeError("no")

    stack.push(Command("Bad", undo=boom, redo=lambda: None))
    with pytest.raises(RuntimeError):
        stack.undo()
    assert stack.applying is False


def test_clearing_forgets_everything():
    stack = UndoStack()
    stack.record("One", undo=lambda: None, redo=lambda: None)
    stack.undo()
    stack.clear()
    assert stack.can_undo is False
    assert stack.can_redo is False


def test_a_long_walk_back_and_forth():
    stack = UndoStack()
    trail: list[str] = []
    for number in range(4):
        stack.record(
            str(number),
            undo=lambda n=number: trail.append(f"-{n}"),
            redo=lambda n=number: trail.append(f"+{n}"),
        )
    for _ in range(4):
        stack.undo()
    for _ in range(4):
        stack.redo()
    assert trail == ["-3", "-2", "-1", "-0", "+0", "+1", "+2", "+3"]


# -- the controller over it ------------------------------------------------------


@pytest.fixture
def main_window(qapp, monkeypatch, tmp_path):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    rows, columns = np.indices((SIZE, SIZE))
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32)).writeto(path)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))
    window.undo.clear()
    yield window
    window.close()


def _circle(x=10.0, y=10.0, radius=3.0):
    from ncrads9.regions.shapes.circle import Circle

    return Circle(center=(x, y), radius=radius)


def test_the_menu_says_what_would_be_undone(main_window):
    """Which is what every other application's Edit menu does."""
    assert main_window.menu_bar.action_undo.isEnabled() is False
    assert main_window.menu_bar.action_undo.text() == "&Undo"

    main_window.region.on_created(_circle())
    assert main_window.menu_bar.action_undo.isEnabled() is True
    assert "Create circle" in main_window.menu_bar.action_undo.text()


def test_undoing_a_created_region_removes_it(main_window):
    frame = main_window.frame_manager.current_frame
    main_window.region.on_created(_circle())
    assert len(frame.regions) == 1

    main_window.menu_bar.action_undo.trigger()
    assert main_window.frame_manager.current_frame.regions == []
    assert "Undid Create circle" in main_window.status_bar.currentMessage()


def test_redoing_puts_it_back(main_window):
    main_window.region.on_created(_circle())
    main_window.undo.undo()
    main_window.menu_bar.action_redo.trigger()
    assert len(main_window.frame_manager.current_frame.regions) == 1


def test_undoing_a_delete_brings_the_regions_back(main_window):
    frame = main_window.frame_manager.current_frame
    frame.regions = [_circle(), _circle(20.0, 20.0)]
    for region in frame.regions:
        region.selected = True
    main_window.region.show_frame_regions(frame)

    main_window.region.delete_selection()
    assert main_window.frame_manager.current_frame.regions == []

    main_window.undo.undo()
    restored = main_window.frame_manager.current_frame.regions
    assert len(restored) == 2
    assert restored[0].center == (10.0, 10.0)


def test_undoing_delete_all(main_window):
    frame = main_window.frame_manager.current_frame
    frame.regions = [_circle(), _circle(20.0, 20.0)]
    main_window.region.clear_regions()
    assert main_window.frame_manager.current_frame.regions == []

    main_window.undo.undo()
    assert len(main_window.frame_manager.current_frame.regions) == 2


def test_undoing_a_reorder(main_window):
    frame = main_window.frame_manager.current_frame
    first, second = _circle(), _circle(20.0, 20.0)
    frame.regions = [first, second]
    first.selected = True
    main_window.region.show_frame_regions(frame)

    main_window.region.move_front()
    assert main_window.undo.stack.undo_label == "Reorder Regions"
    main_window.undo.undo()
    assert main_window.frame_manager.current_frame.regions[0].center == first.center


def test_a_region_drag_is_one_command(main_window):
    """A drag spans a press and a release, which no single signal covers."""
    frame = main_window.frame_manager.current_frame
    region = _circle()
    frame.regions = [region]
    main_window.region.show_frame_regions(frame)

    main_window.region.on_edit("begin")
    region.center = (25.0, 25.0)
    main_window.region.on_edit("finish")

    assert main_window.undo.stack.labels() == ["Move Region"]
    main_window.undo.undo()
    assert main_window.frame_manager.current_frame.regions[0].center == (10.0, 10.0)


def test_a_drag_that_moved_nothing_records_nothing(main_window):
    """A click on a region is a press and a release too."""
    frame = main_window.frame_manager.current_frame
    frame.regions = [_circle()]
    main_window.region.show_frame_regions(frame)

    main_window.region.on_edit("begin")
    main_window.region.on_edit("finish")
    assert main_window.undo.stack.labels() == []


def test_undoing_a_zoom_puts_the_view_back_on_the_screen(main_window):
    """Not just on the frame: the viewer holds the zoom, and a frame whose
    zoom disagrees with the screen has the screen's value written back over
    it by the next thing that persists the view."""
    frame = main_window.frame_manager.current_frame
    before = frame.zoom
    main_window.zoom.set_zoom(4.0)
    assert main_window.image_viewer.get_zoom() == pytest.approx(4.0)

    main_window.undo.undo()
    assert main_window.frame_manager.current_frame.zoom == pytest.approx(before)
    assert main_window.image_viewer.get_zoom() == pytest.approx(before)


def test_undoing_a_rotation(main_window):
    main_window.zoom.set_rotation(90.0)
    main_window.undo.undo()
    assert main_window.frame_manager.current_frame.rotation == pytest.approx(0.0)


def test_undoing_an_orientation(main_window):
    main_window.zoom.set_orientation("xy")
    assert main_window.frame_manager.current_frame.flip_x is True
    main_window.undo.undo()
    assert main_window.frame_manager.current_frame.flip_x is False


def test_undoing_a_colormap(main_window):
    main_window.color.set_colormap("heat")
    assert main_window.frame_manager.current_frame.colormap == "heat"
    main_window.undo.undo()
    assert main_window.frame_manager.current_frame.colormap != "heat"


def test_undoing_an_illustration_delete(main_window):
    main_window.illustrate.layer.create("circle", 20.0, 30.0, radius=5.0)
    main_window.illustrate.layer.select_all()
    main_window.illustrate.delete_selection()
    assert len(main_window.illustrate.layer) == 0

    main_window.undo.undo()
    assert len(main_window.illustrate.layer) == 1
    assert main_window.illustrate.layer.elements[0].center == (20.0, 30.0)


def test_undoing_delete_all_illustrations(main_window):
    main_window.illustrate.layer.create("box", 10.0, 10.0)
    main_window.illustrate.delete_all()
    main_window.undo.undo()
    assert len(main_window.illustrate.layer) == 1


def test_undo_and_redo_are_disabled_when_there_is_nothing_to_do(main_window):
    assert main_window.menu_bar.action_redo.isEnabled() is False
    main_window.region.on_created(_circle())
    main_window.undo.undo()
    assert main_window.menu_bar.action_undo.isEnabled() is False
    assert main_window.menu_bar.action_redo.isEnabled() is True


def test_undoing_with_nothing_to_undo_says_so(main_window):
    assert main_window.undo.undo() is None
    assert "Nothing to undo" in main_window.status_bar.currentMessage()
    assert main_window.undo.redo() is None
    assert "Nothing to redo" in main_window.status_bar.currentMessage()


def test_an_undo_does_not_record_itself(main_window):
    """The commonest way an undo stack goes wrong: putting state back looks
    like a change, so the undo becomes undoable and nothing ever settles."""
    main_window.region.on_created(_circle())
    main_window.undo.undo()
    assert main_window.undo.stack.labels() == []
    assert main_window.undo.stack.can_redo is True


def test_several_edits_undo_in_order(main_window):
    frame = main_window.frame_manager.current_frame
    main_window.region.on_created(_circle())
    main_window.region.on_created(_circle(20.0, 20.0))
    main_window.zoom.set_zoom(2.0)

    assert main_window.undo.stack.labels() == ["Create circle", "Create circle", "Zoom"]
    main_window.undo.undo()
    assert len(frame.regions) == 2
    main_window.undo.undo()
    assert len(main_window.frame_manager.current_frame.regions) == 1
    main_window.undo.undo()
    assert main_window.frame_manager.current_frame.regions == []


def test_the_stack_can_be_cleared(main_window):
    main_window.region.on_created(_circle())
    main_window.undo.clear()
    assert main_window.undo.stack.can_undo is False
    assert main_window.menu_bar.action_undo.isEnabled() is False


def test_recording_with_no_frame_does_nothing(main_window):
    """Undo has to survive being asked about a window with no image."""
    main_window.frame_controller.delete_all()
    frames = main_window.frame_manager.frames
    for frame in frames:
        frame.image_data = None
    with main_window.undo.regions("Nothing"):
        pass
    with main_window.undo.view("Nothing"):
        pass
    assert main_window.undo.stack.labels() == []
