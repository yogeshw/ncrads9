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

"""
End-to-end viewing flows (C-7).

The unit tests each check one part in isolation. These drive the whole
application the way a person does -- open a file, change the scale, draw a
region, save it, load it back -- because the interesting failures are at
the seams: a controller that changes state without telling the renderer, a
save that writes what the screen no longer shows, a reload that comes back
subtly different.

Each test is one flow, and asserts at each step rather than only at the
end, so a break says *where* it broke.
"""

from __future__ import annotations

import numpy as np
from astropy.io import fits

from ncrads9.rendering.scale_algorithms import ScaleAlgorithm


def test_open_scale_region_save_reload(window, image, tmp_path, quiet):
    """DS9's central loop: open a file, look at it, mark it, keep the mark.

    The flow C-7 names. Every step is a different subsystem, and the point
    is that the state one leaves behind is the state the next one reads.
    """
    # 1. Open.
    window.display.load_fits(str(image))
    frame = window.frame_manager.current_frame
    assert frame.image_data is not None
    assert frame.image_data.shape == (64, 64)
    assert window.wcs_handler is not None and window.wcs_handler.is_valid

    # 2. Scale. The limits must actually change what is drawn, not just
    #    what the menu says.
    window.scale.set_scale(ScaleAlgorithm.LOG)
    assert window.current_scale is ScaleAlgorithm.LOG
    window.scale.set_minmax_limits()
    low, high = window.z1, window.z2
    assert low is not None and high is not None and high > low

    # 3. Zoom and pan, and have the view survive a frame change and come
    #    back -- the bug this catches is a view state kept on the window
    #    rather than on the frame.
    window.zoom.set_zoom(2.0)
    assert window.image_viewer.get_zoom() == 2.0
    window.frame_controller.new_frame()
    window.frame_controller.first()
    assert window.image_viewer.get_zoom() == 2.0, "the view should follow the frame"

    # 4. Mark. A region drawn in image coordinates has to survive being
    #    written in world coordinates and read back.
    from ncrads9.regions.shapes.circle import Circle

    frame = window.frame_manager.current_frame
    frame.regions = [Circle(center=(32.0, 32.0), radius=6.0)]
    window.region.show_frame_regions(frame)

    # 5. Save.
    saved = tmp_path / "marks.reg"
    assert window.region.save_file(str(saved)) is None
    assert "circle" in saved.read_text()

    # 6. Reload into a clean frame, and get the same circle back.
    window.region.clear_regions()
    assert window.frame_manager.current_frame.regions == []
    assert window.region.load_file(str(saved)) is None
    reloaded = window.frame_manager.current_frame.regions
    assert len(reloaded) == 1
    assert reloaded[0].center[0] == 32.0
    assert reloaded[0].radius == 6.0


def test_a_session_survives_a_backup_and_restore(window, image, tmp_path, quiet):
    """Everything set up, written out, and read back into a fresh state.

    A backup that quietly drops the scale or the regions is worse than no
    backup: the user finds out when they need it.
    """
    from ncrads9.regions.shapes.circle import Circle

    window.display.load_fits(str(image))
    window.scale.set_scale(ScaleAlgorithm.SQRT)
    window.color.set_colormap("heat")
    window.zoom.set_zoom(3.0)
    frame = window.frame_manager.current_frame
    frame.regions = [Circle(center=(20.0, 20.0), radius=4.0)]

    backup = tmp_path / "session.bck"
    assert window.session.backup(str(backup)) is True
    assert backup.is_file()

    # Change everything, so a restore that does nothing would be obvious.
    window.scale.set_scale(ScaleAlgorithm.LINEAR)
    window.color.set_colormap("grey")
    window.frame_controller.delete_all()
    assert window.frame_manager.current_frame.image_data is None

    assert window.session.restore(str(backup)) is True
    restored = window.frame_manager.current_frame
    assert restored.image_data is not None, "the image came back"
    assert window.current_scale is ScaleAlgorithm.SQRT, "and the scale with it"
    assert window.current_colormap == "heat"
    assert len(restored.regions) == 1


def test_a_cube_steps_through_its_planes(window, cube, quiet):
    """Loading a cube, walking it, and having the display follow."""
    window.display.load_fits(str(cube))
    frame = window.frame_manager.current_frame
    assert frame.image is not None and frame.image.data.ndim == 3

    first = np.nanmean(frame.image_data)
    window.frame_controller.set_slice(1)
    assert frame.slice_index == 1
    second = np.nanmean(frame.image_data)
    assert second != first, "a different plane should hold different data"

    window.frame_controller.set_slice(2)
    assert np.nanmean(frame.image_data) not in (first, second)


def test_analysis_reads_what_the_display_shows(window, image, quiet):
    """Smoothing changes the numbers the analysis tools report.

    The seam: the renderer smooths for display, and statistics must read
    the smoothed data rather than the file's -- or the two disagree about
    what is on screen.
    """
    window.display.load_fits(str(image))
    frame = window.frame_manager.current_frame
    raw = window.analysis.analysis_image_data(frame)

    window.analysis.apply_smooth_settings({"function": "gaussian", "radius": 3, "sigma": 1.5})
    smoothed = window.analysis.analysis_image_data(frame)
    assert not np.array_equal(np.nan_to_num(raw), np.nan_to_num(smoothed))
    # A gaussian narrows the spread; that is what smoothing is.
    assert np.nanstd(smoothed) < np.nanstd(raw)


def test_a_blank_pixel_survives_the_whole_pipeline(window, image, quiet):
    """The NaN in the fixture is there to be followed.

    A blank has to stay blank from the file, through the scale, to the
    colormap -- the bug it catches is an `astype(int)` on a NaN, which
    produces a nonsense colour and a runtime warning rather than the
    Blank/NaN colour the preferences ask for.
    """
    window.display.load_fits(str(image))
    frame = window.frame_manager.current_frame
    assert np.isnan(frame.image_data[10, 10]), "the file's blank"

    with np.errstate(all="raise"):
        window.display.display()

    window.scale.set_scale(ScaleAlgorithm.LOG)
    window.display.display()
    assert np.isnan(frame.image_data[10, 10]), "and it is still blank afterwards"


def test_a_file_saved_is_the_file_reloaded(window, image, tmp_path, quiet):
    """Write the frame out and read it back: same data, same WCS."""
    window.display.load_fits(str(image))
    before = np.array(window.frame_manager.current_frame.image_data)

    target = tmp_path / "written.fits"
    assert window.file.save_fits_to(str(target)) is None

    window.frame_controller.new_frame()
    window.display.load_fits(str(target))
    after = window.frame_manager.current_frame.image_data
    np.testing.assert_array_equal(np.nan_to_num(before), np.nan_to_num(after))
    assert np.isnan(after[10, 10]), "the blank came through FITS as a blank"

    with fits.open(target) as handle:
        assert handle[0].header["CTYPE1"] == "RA---TAN", "the WCS came with it"
