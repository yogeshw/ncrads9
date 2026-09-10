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

"""DS9's 3D frame: the ray trace, the dialog and the lock (M9-21..M9-23)."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.frames import frame_3d
from ncrads9.frames.frame_3d import View3D, corners, extent, render, slice_outline

DEPTH, HEIGHT, WIDTH = 8, 32, 40


def _cube() -> np.ndarray:
    """A cube with one bright voxel in the middle of one slice."""
    cube = np.zeros((DEPTH, HEIGHT, WIDTH), dtype=np.float32)
    cube[DEPTH // 2, HEIGHT // 2, WIDTH // 2] = 100.0
    return cube


# -- the view ---------------------------------------------------------------------


def test_a_new_view_is_face_on():
    assert View3D().is_face_on() is True
    assert View3D(azimuth=1.0).is_face_on() is False


def test_the_rotation_is_the_identity_face_on():
    assert np.allclose(View3D().matrix, np.eye(3))


def test_the_rotation_is_ds9s_composition():
    """Azimuth about the screen's vertical axis, elevation about its
    horizontal one (`frame3dbase.C:394`)."""
    view = View3D(azimuth=90.0)
    # The data's x axis turns into the screen.
    turned = view.matrix @ np.array([1.0, 0.0, 0.0])
    assert np.allclose(turned, [0.0, 0.0, -1.0], atol=1e-9)

    view = View3D(elevation=90.0)
    turned = view.matrix @ np.array([0.0, 1.0, 0.0])
    assert np.allclose(turned, [0.0, 0.0, 1.0], atol=1e-9)


def test_the_rotation_keeps_lengths():
    view = View3D(azimuth=37.0, elevation=-19.0)
    assert np.allclose(view.matrix @ view.matrix.T, np.eye(3))


# -- the cube's extent -------------------------------------------------------------


def test_face_on_the_image_is_the_cubes_own_size():
    assert extent(_cube().shape, View3D()) == (HEIGHT, WIDTH)


def test_turned_the_image_grows():
    turned = extent(_cube().shape, View3D(azimuth=30.0, elevation=20.0))
    assert turned[0] >= HEIGHT
    assert turned[1] >= WIDTH


def test_seen_side_on_the_image_is_as_wide_as_the_cube_is_deep():
    """Which is the whole point of a 3D frame: the third axis becomes
    something you can see."""
    height, width = extent(_cube().shape, View3D(azimuth=90.0))
    assert height == HEIGHT
    assert width == pytest.approx(DEPTH, abs=1)


def test_the_z_scale_stretches_the_third_axis():
    _height, width = extent(_cube().shape, View3D(azimuth=90.0, scale=4.0))
    assert width == pytest.approx(DEPTH * 4, abs=1)


def test_a_badly_scaled_axis_cannot_ask_for_an_endless_image():
    height, width = extent(_cube().shape, View3D(azimuth=90.0, scale=1e9))
    assert max(height, width) <= frame_3d.MAX_EXTENT


def test_there_are_eight_corners_and_twelve_edges():
    assert corners(_cube().shape, View3D()).shape == (8, 3)
    assert len(frame_3d.edges()) == 12
    # Every edge joins two corners that exist.
    for first, second in frame_3d.edges():
        assert 0 <= first < 8 and 0 <= second < 8


# -- the ray trace ------------------------------------------------------------------


def test_face_on_mip_is_the_cubes_own_maximum_per_pixel():
    cube = np.random.default_rng(0).normal(size=(4, 8, 8)).astype(np.float32)
    assert np.allclose(render(cube, View3D(), "mip"), cube.max(axis=0))


def test_face_on_aip_is_the_average_through_the_cube():
    cube = np.random.default_rng(1).normal(size=(4, 8, 8)).astype(np.float32)
    assert np.allclose(render(cube, View3D(), "aip"), cube.mean(axis=0), atol=1e-5)


def test_mip_finds_the_brightest_voxel_from_any_angle():
    """A ray through it must return it, which is what MIP means."""
    cube = _cube()
    for azimuth, elevation in ((0, 0), (30, 20), (-45, -30), (90, 0), (180, 45)):
        image = render(cube, View3D(azimuth, elevation), "mip")
        assert np.nanmax(image) == pytest.approx(100.0), (azimuth, elevation)


def test_aip_averages_rather_than_picking_the_peak():
    cube = _cube()
    view = View3D(azimuth=30.0, elevation=20.0)
    assert np.nanmax(render(cube, view, "aip")) < np.nanmax(render(cube, view, "mip"))


def test_the_rays_that_miss_the_cube_are_blank():
    """Not zero: zero is a value, and it would stretch the scale over an
    empty corner of the view."""
    image = render(_cube(), View3D(azimuth=45.0, elevation=45.0), "mip")
    assert np.isnan(image).any()
    # And the corners of the view are the ones that miss.
    assert np.isnan(image[0, 0])


def test_the_inside_of_the_cube_is_never_blank():
    image = render(np.ones((4, 16, 16), np.float32), View3D(azimuth=20.0), "mip")
    middle = image[image.shape[0] // 2, image.shape[1] // 2]
    assert middle == pytest.approx(1.0)


def test_a_blank_voxel_is_not_counted():
    """A cube with a NaN in it has a hole, not a bright spot."""
    cube = np.ones((4, 8, 8), np.float32)
    cube[1, 4, 4] = np.nan
    image = render(cube, View3D(azimuth=15.0), "aip")
    assert np.isfinite(image[image.shape[0] // 2, image.shape[1] // 2])


def test_turning_the_cube_moves_what_is_seen():
    cube = np.zeros((8, 16, 16), np.float32)
    cube[0] = 1.0  # the first slice only
    side = render(cube, View3D(azimuth=90.0), "mip")
    columns = np.where(np.nan_to_num(side).max(axis=0) > 0.5)[0]
    # Seen side-on, one slice is a narrow band at one edge.
    assert columns.max() - columns.min() <= 2


def test_something_that_is_not_a_cube_is_refused():
    with pytest.raises(ValueError, match="data cube"):
        render(np.zeros((4, 4), np.float32))


def test_a_method_ds9_does_not_have_is_refused():
    with pytest.raises(ValueError, match="rendering method"):
        render(_cube(), View3D(), "average")


# -- the background and the decorations ----------------------------------------------


def test_no_background_is_no_gradient():
    assert frame_3d.background((4, 4), View3D(), "none") is None


def test_the_azimuth_background_runs_across_and_elevation_up():
    across = frame_3d.background((4, 6), View3D(), "azimuth")
    assert across.shape == (4, 6)
    assert across[0, 0] < across[0, -1]

    up = frame_3d.background((4, 6), View3D(), "elevation")
    assert up[0, 0] < up[-1, 0]


def test_a_background_ds9_does_not_have_is_refused():
    with pytest.raises(ValueError, match="background"):
        frame_3d.background((4, 4), View3D(), "radial")


def test_the_slice_outline_is_four_corners_at_that_slices_depth():
    face_on = slice_outline(_cube().shape, View3D(), 0)
    assert face_on.shape == (4, 3)
    # Face-on, the first slice is at the front of the cube.
    assert face_on[0][2] == pytest.approx(-(DEPTH - 1) / 2.0)
    last = slice_outline(_cube().shape, View3D(), DEPTH - 1)
    assert last[0][2] > face_on[0][2]


def test_a_slice_outside_the_cube_is_clamped():
    outline = slice_outline(_cube().shape, View3D(), 9999)
    assert np.isfinite(outline).all()


# -- the frame ------------------------------------------------------------------------


@pytest.fixture
def cube_file(tmp_path):
    path = tmp_path / "cube.fits"
    fits.PrimaryHDU(data=_cube()).writeto(path)
    return path


@pytest.fixture
def main_window(qapp, monkeypatch, tmp_path, cube_file):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.frame_controller.new_frame_of_type("3d")
    window.display.load_fits(str(cube_file))
    yield window
    window.close()


def _go_to(main_window, frame) -> None:
    """Make one frame current, whatever position it is in."""
    main_window.frame_controller.goto_index(main_window.frame_manager.frames.index(frame))


def test_a_3d_frame_knows_it_is_one(main_window):
    assert main_window.frame_manager.current_frame.frame_type == "3d"
    assert main_window.frame_3d.is_three_d() is True


def test_a_plain_frame_is_not_a_3d_frame(main_window, cube_file):
    main_window.frame_controller.new_frame()
    main_window.display.load_fits(str(cube_file))
    assert main_window.frame_3d.is_three_d() is False


def test_a_3d_frame_displays_the_whole_cube_not_a_slice(main_window):
    """Which is what DS9 v7 added the module for: the old frames stepped
    through slices."""
    frame = main_window.frame_manager.current_frame
    displayed = main_window.display.display_image_data(frame)
    # Every slice's contribution: the bright voxel shows without stepping
    # to its slice.
    assert np.nanmax(displayed) == pytest.approx(100.0)
    assert frame.slice_index == 0


def test_turning_the_frame_changes_what_is_displayed(main_window):
    frame = main_window.frame_manager.current_frame
    before = main_window.display.display_image_data(frame).shape
    main_window.frame_3d.set_view(azimuth=40.0, elevation=25.0)
    assert main_window.display.display_image_data(frame).shape != before


def test_the_view_is_per_frame(main_window, cube_file):
    first = main_window.frame_manager.current_frame
    main_window.frame_3d.set_view(azimuth=40.0)

    main_window.frame_controller.new_frame_of_type("3d")
    main_window.display.load_fits(str(cube_file))
    assert main_window.frame_3d.view().azimuth == 0.0

    _go_to(main_window, first)
    assert main_window.frame_3d.view().azimuth == 40.0


def test_the_angles_are_kept_in_ds9s_range(main_window):
    assert main_window.frame_3d.set_view(elevation=200.0).elevation == 90.0
    assert main_window.frame_3d.set_view(elevation=-200.0).elevation == -90.0
    # Azimuth wraps rather than clamping: turning past the back is fine.
    assert main_window.frame_3d.set_view(azimuth=190.0).azimuth == pytest.approx(-170.0)
    assert main_window.frame_3d.set_view(azimuth=-190.0).azimuth == pytest.approx(170.0)


def test_the_z_scale_cannot_be_zero(main_window):
    assert main_window.frame_3d.set_view(scale=0.0).scale > 0.0


def test_reset_puts_it_back_face_on(main_window):
    main_window.frame_3d.set_view(azimuth=40.0, elevation=25.0, scale=4.0)
    assert main_window.frame_3d.reset() == View3D(0.0, 0.0, 1.0)


def test_the_pointer_mode_turns_the_cube(main_window):
    main_window.menu_bar.edit_mode_actions["3d"].trigger()
    handler = main_window.pointer.handler
    assert handler is not None and handler.name == "3d"

    handler.press(10.0, 10.0)
    handler.move(40.0, 10.0)
    assert main_window.frame_3d.view().azimuth == pytest.approx(30.0)
    handler.move(40.0, 30.0)
    # Up on the screen is up in elevation, which is what makes it feel like
    # an object rather than a dial.
    assert main_window.frame_3d.view().elevation == pytest.approx(-20.0)


def test_the_3d_mode_no_longer_says_it_is_coming(main_window):
    main_window.menu_bar.edit_mode_actions["3d"].trigger()
    assert "arrives in" not in main_window.status_bar.currentMessage()


# -- the decorations -------------------------------------------------------------------


def test_the_border_and_the_highlighted_slice_are_drawn(main_window):
    lines = main_window.frame_3d.decorations()
    # Twelve edges and the slice outline.
    assert len(lines) == 13
    colours = {colour for _points, colour, _width in lines}
    assert colours == {"blue", "cyan"}


def test_the_compass_is_off_until_asked_for(main_window):
    assert main_window.frame_3d.setting("compass") is False
    main_window.frame_3d.set_setting("compass", True)
    assert len(main_window.frame_3d.decorations()) == 16


def test_turning_off_the_border_stops_drawing_it(main_window):
    main_window.frame_3d.set_setting("border", False)
    assert len(main_window.frame_3d.decorations()) == 1


def test_the_decorations_reach_the_overlay(main_window):
    main_window.frame_3d.refresh()
    assert len(main_window.image_viewer.contour_overlay._cube_lines) == 13


def test_a_plain_frame_has_no_decorations(main_window, cube_file):
    main_window.frame_controller.new_frame()
    main_window.display.load_fits(str(cube_file))
    assert main_window.frame_3d.decorations() == []


def test_the_decorations_are_inside_the_rendered_image(main_window):
    """They are drawn in the rendered image's own pixels, so they have to
    land on it."""
    main_window.frame_3d.set_view(azimuth=30.0, elevation=20.0)
    height, width = main_window.display.display_image_data(main_window.frame_manager.current_frame).shape
    for points, _colour, _width in main_window.frame_3d.decorations():
        for x, y in points:
            assert -1.0 <= x <= width
            assert -1.0 <= y <= height


# -- the dialog -------------------------------------------------------------------------


@pytest.fixture
def dialog(main_window):
    made = main_window.frame_3d.show_dialog()
    yield made
    made.close()


def test_the_dialog_shows_the_cube(dialog):
    assert f"{WIDTH} x {HEIGHT} x {DEPTH}" in dialog._what.text()


def test_the_dialog_says_when_the_frame_is_not_3d(main_window, cube_file):
    main_window.frame_controller.new_frame()
    main_window.display.load_fits(str(cube_file))
    made = main_window.frame_3d.show_dialog()
    made.reload()
    assert "not a 3D frame" in made._what.text()
    made.close()


def test_the_sliders_turn_the_cube(dialog, main_window):
    dialog._azimuth.setValue(45)
    dialog._elevation.setValue(-30)
    assert main_window.frame_3d.view().azimuth == pytest.approx(45.0)
    assert main_window.frame_3d.view().elevation == pytest.approx(-30.0)


def test_the_sliders_cover_ds9s_ranges(dialog):
    assert (dialog._azimuth.minimum(), dialog._azimuth.maximum()) == (-180, 180)
    assert (dialog._elevation.minimum(), dialog._elevation.maximum()) == (-90, 90)


def test_the_z_scale_box_stretches_the_cube(dialog, main_window):
    dialog._scale.setValue(3.0)
    assert main_window.frame_3d.view().scale == pytest.approx(3.0)


def test_reloading_does_not_turn_the_cube(dialog, main_window):
    """setValue emits, and a reload that emitted would round the angles
    every time the dialog refreshed."""
    main_window.frame_3d.set_view(azimuth=45.0, elevation=-30.0, scale=2.5)
    dialog.reload()
    dialog.reload()
    view = main_window.frame_3d.view()
    assert (view.azimuth, view.elevation, view.scale) == (45.0, -30.0, 2.5)


def test_the_render_menu_chooses_the_method(dialog, main_window):
    dialog.actions_by_name["method_aip"].trigger()
    assert main_window.frame_3d.setting("method") == "aip"
    dialog.actions_by_name["method_mip"].trigger()
    assert main_window.frame_3d.setting("method") == "mip"


def test_the_render_menu_chooses_the_background(dialog, main_window):
    dialog.actions_by_name["background_azimuth"].trigger()
    assert main_window.frame_3d.setting("background") == "azimuth"


def test_the_decoration_menus_toggle_and_recolour(dialog, main_window):
    # trigger() toggles a checkable action, so it goes on from off.
    dialog.actions_by_name["compass_show"].trigger()
    assert main_window.frame_3d.setting("compass") is True

    dialog.actions_by_name["border_red"].trigger()
    assert main_window.frame_3d.setting("border_color") == "red"


def test_the_dialogs_reset_button(dialog, main_window):
    main_window.frame_3d.set_view(azimuth=45.0)
    dialog.buttons["reset"].click()
    assert main_window.frame_3d.view() == View3D()


def test_asking_for_the_dialog_twice_reuses_it(main_window):
    first = main_window.frame_3d.show_dialog()
    assert main_window.frame_3d.show_dialog() is first
    first.close()


def test_the_frame_menu_opens_it(main_window):
    main_window.menu_bar.action_frame_3d_dialog.trigger()
    assert main_window.frame_3d._dialog is not None
    main_window.frame_3d._dialog.close()


# -- match and lock (M9-23) --------------------------------------------------------------


def test_match_3d_copies_the_view_to_the_other_3d_frames(main_window, cube_file):
    first = main_window.frame_manager.current_frame
    main_window.frame_controller.new_frame_of_type("3d")
    main_window.display.load_fits(str(cube_file))
    other = main_window.frame_manager.current_frame
    _go_to(main_window, first)
    main_window.frame_3d.set_view(azimuth=40.0, elevation=25.0)

    main_window.menu_bar.action_match_3d.trigger()
    assert main_window.frame_3d.view(other) == View3D(40.0, 25.0, 1.0)


def test_match_3d_leaves_plain_frames_alone(main_window, cube_file):
    first = main_window.frame_manager.current_frame
    main_window.frame_controller.new_frame()
    main_window.display.load_fits(str(cube_file))
    plain = main_window.frame_manager.current_frame
    _go_to(main_window, first)
    main_window.frame_3d.set_view(azimuth=40.0)

    main_window.menu_bar.action_match_3d.trigger()
    assert plain.frame_id not in main_window.frame_3d.views


def test_match_3d_from_a_plain_frame_says_so(main_window, cube_file):
    main_window.frame_controller.new_frame()
    main_window.display.load_fits(str(cube_file))
    main_window.menu_bar.action_match_3d.trigger()
    assert "not a 3D frame" in main_window.status_bar.currentMessage()


def test_the_lock_turns_the_other_frames_as_you_drag(main_window, cube_file):
    first = main_window.frame_manager.current_frame
    main_window.frame_controller.new_frame_of_type("3d")
    main_window.display.load_fits(str(cube_file))
    other = main_window.frame_manager.current_frame
    _go_to(main_window, first)

    main_window.menu_bar.action_lock_3d.setChecked(True)
    main_window.frame_controller.set_lock_flag("3d", True)
    main_window.frame_3d.set_view(azimuth=15.0)
    assert main_window.frame_3d.view(other).azimuth == pytest.approx(15.0)


def test_the_lock_can_be_turned_off(main_window, cube_file):
    first = main_window.frame_manager.current_frame
    main_window.frame_controller.new_frame_of_type("3d")
    main_window.display.load_fits(str(cube_file))
    other = main_window.frame_manager.current_frame
    _go_to(main_window, first)

    main_window.frame_3d.set_locked(True)
    main_window.frame_3d.set_locked(False)
    main_window.frame_3d.set_view(azimuth=15.0)
    assert main_window.frame_3d.view(other).azimuth == 0.0


# -- the 3d XPA point (M9-23) -------------------------------------------------------------


@pytest.fixture
def xpa(main_window):
    from ncrads9.communication.xpa.xpa_commands import XPACommands

    return XPACommands(main_window)


def _set(xpa, *args):
    return xpa.handle("3d", {"args": list(args)})


def test_xpaget_3d_reports_the_view(xpa, main_window):
    main_window.frame_3d.set_view(azimuth=30.0, elevation=20.0, scale=2.0)
    result = xpa.handle("3d", {"get": True})["result"]
    assert "view 30 20" in result
    assert "scale 2" in result
    assert "method mip" in result


def test_a_bare_3d_makes_a_3d_frame(xpa, main_window):
    before = main_window.frame_manager.num_frames
    assert _set(xpa)["status"] == "ok"
    assert main_window.frame_manager.num_frames == before + 1
    assert main_window.frame_manager.current_frame.frame_type == "3d"


def test_3d_vp_turns_the_cube(xpa, main_window):
    assert _set(xpa, "vp", "45", "30")["status"] == "ok"
    assert main_window.frame_3d.view() == View3D(45.0, 30.0, 1.0)
    assert _set(xpa, "vp", "45")["status"] == "error"


def test_3d_az_el_and_scale(xpa, main_window):
    _set(xpa, "az", "20")
    _set(xpa, "el", "10")
    _set(xpa, "scale", "3")
    assert main_window.frame_3d.view() == View3D(20.0, 10.0, 3.0)
    for command in ("az", "el", "scale"):
        assert _set(xpa, command)["status"] == "error"


def test_3d_method_and_background(xpa, main_window):
    assert _set(xpa, "method", "aip")["status"] == "ok"
    assert main_window.frame_3d.setting("method") == "aip"
    assert _set(xpa, "method", "average")["status"] == "error"

    assert _set(xpa, "background", "elevation")["status"] == "ok"
    assert main_window.frame_3d.setting("background") == "elevation"
    assert _set(xpa, "background", "radial")["status"] == "error"


def test_3d_decorations_over_xpa(xpa, main_window):
    assert _set(xpa, "compass", "yes")["status"] == "ok"
    assert main_window.frame_3d.setting("compass") is True
    assert _set(xpa, "border", "red")["status"] == "ok"
    assert main_window.frame_3d.setting("border_color") == "red"
    assert _set(xpa, "highlite")["result"] == "True"


def test_3d_match_lock_and_reset_over_xpa(xpa, main_window):
    main_window.frame_3d.set_view(azimuth=40.0)
    assert _set(xpa, "lock", "yes")["status"] == "ok"
    assert main_window.frame_3d.locked is True
    assert _set(xpa, "match")["status"] == "ok"
    assert _set(xpa, "reset")["status"] == "ok"
    assert main_window.frame_3d.view() == View3D()


def test_3d_opens_and_closes_the_dialog_over_xpa(xpa, main_window):
    assert _set(xpa, "open")["status"] == "ok"
    assert main_window.frame_3d._dialog is not None
    assert _set(xpa, "close")["status"] == "ok"


def test_an_unknown_3d_command_is_reported(xpa):
    assert "Unknown 3d command" in _set(xpa, "wibble")["message"]


# -- the backup ---------------------------------------------------------------------------


def test_the_3d_view_goes_into_the_backup(main_window, tmp_path):
    main_window.frame_3d.set_view(azimuth=40.0, elevation=25.0, scale=2.0)
    main_window.frame_3d.set_setting("method", "aip")
    path = tmp_path / "s.bck"
    main_window.session.backup(str(path))

    main_window.frame_3d.reset()
    main_window.frame_3d.set_setting("method", "mip")
    main_window.session.restore(str(path))

    assert main_window.frame_3d.view() == View3D(40.0, 25.0, 2.0)
    assert main_window.frame_3d.setting("method") == "aip"
