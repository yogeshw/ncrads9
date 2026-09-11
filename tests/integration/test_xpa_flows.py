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
End-to-end flows driven through XPA (C-7).

The other integration file drives the application by calling its
controllers. This one drives it the way a script does -- `xpaset`,
`xpaget`, one command at a time -- because that is a different path
through the same code and the interesting bugs live in the difference: a
setter the menu calls with a bool and XPA calls with the string "yes", a
getter that reads a widget the script never made visible.

Each flow is a plausible script. If one of these breaks, someone's
pipeline breaks.
"""

from __future__ import annotations

import numpy as np
from astropy.io import fits


def _set(xpa, command: str):
    """`xpaset -p ds9 <command>`, and it must succeed."""
    words = command.split()
    reply = xpa.handle(words[0], {"args": words[1:]})
    assert reply["status"] == "ok", f"xpaset {command} -> {reply.get('message')}"
    return reply


def _get(xpa, command: str) -> str:
    """`xpaget ds9 <command>`, and it must answer."""
    words = command.split()
    reply = xpa.handle(words[0], {"get": True, "args": words[1:]})
    assert reply["status"] == "ok", f"xpaget {command} -> {reply.get('message')}"
    return reply["result"]


def test_a_script_loads_scales_and_reads_back(xpa, window, image):
    """The commonest script there is: load a file, set it up, check it."""
    _set(xpa, f"file {image}")
    assert _get(xpa, "frame") == "1"
    assert "galaxy" in _get(xpa, "file")

    _set(xpa, "scale log")
    assert _get(xpa, "scale") == "log"
    _set(xpa, "scale mode minmax")
    _set(xpa, "cmap heat")
    assert _get(xpa, "cmap") == "heat"
    _set(xpa, "zoom 4")
    assert float(_get(xpa, "zoom")) == 4.0

    # And the data behind it all is still the file's.
    # The fixture's value is `row + 2 * column`, and DS9 counts from one.
    values = _get(xpa, "data image 5 5 2 2 yes").split("\n")
    assert values == ["12", "14", "13", "15"]


def test_a_script_makes_frames_and_moves_between_them(xpa, window, image, cube):
    _set(xpa, f"file {image}")
    _set(xpa, "frame new")
    _set(xpa, f"file {cube}")
    assert _get(xpa, "frame all") == "1 2"
    assert _get(xpa, "frame") == "2"

    _set(xpa, "frame first")
    assert _get(xpa, "frame") == "1"
    _set(xpa, "frame next")
    assert _get(xpa, "frame") == "2"

    # DS9's capability questions, which a script branches on.
    assert _get(xpa, "frame has fits") == "yes"
    assert _get(xpa, "frame has fits cube") == "yes"
    _set(xpa, "frame first")
    assert _get(xpa, "frame has fits cube") == "no"
    assert _get(xpa, "frame has wcs") == "yes"

    _set(xpa, "tile yes")
    assert _get(xpa, "tile") == "yes"
    _set(xpa, "single")
    assert _get(xpa, "tile") == "no"


def test_a_script_writes_and_reads_regions(xpa, window, image, tmp_path):
    """A pipeline that marks sources and hands the file to the next step."""
    _set(xpa, f"file {image}")
    _set(xpa, "region command circle 20 20 5")
    _set(xpa, "region command circle 40 40 8")
    listing = _get(xpa, "region")
    assert listing.count("circle") == 2

    target = tmp_path / "sources.reg"
    _set(xpa, f"region save {target}")
    assert target.is_file()

    _set(xpa, "region delete")
    assert _get(xpa, "region").count("circle") == 0
    _set(xpa, f"region load {target}")
    assert _get(xpa, "region").count("circle") == 2


def test_a_script_reads_a_pixel_in_every_coordinate_system(xpa, window, image):
    """What an examine script does, without the click."""
    _set(xpa, f"file {image}")
    _set(xpa, "crosshair 32 32")

    image_position = _get(xpa, "crosshair image").split()
    assert [float(word) for word in image_position] == [32.0, 32.0]

    world = _get(xpa, "crosshair wcs fk5 degrees").split()
    assert abs(float(world[0]) - 202.48) < 0.1
    assert abs(float(world[1]) - 47.21) < 0.1


def test_a_script_sets_up_a_display_and_saves_a_picture(xpa, window, image, tmp_path):
    """The other common script: render something and write a PNG for a
    web page, with nobody watching."""
    _set(xpa, f"file {image}")
    _set(xpa, "scale zscale")
    _set(xpa, "cmap viridis")
    _set(xpa, "colorbar no")
    assert _get(xpa, "colorbar") == "no"
    _set(xpa, "zoom to fit")

    picture = tmp_path / "shot.png"
    _set(xpa, f"saveimage png {picture}")
    assert picture.is_file() and picture.stat().st_size > 0


def test_a_script_blocks_and_puts_it_back(xpa, window, image):
    """Blocking is a *display* operation here, as it is in DS9: the frame
    keeps the file's data and the analysis tools see the blocked version,
    so a measurement matches what is on screen."""
    _set(xpa, f"file {image}")
    frame = window.frame_manager.current_frame
    original = frame.image_data.shape
    assert window.analysis.analysis_image_data(frame).shape == original

    _set(xpa, "block 2")
    assert _get(xpa, "block") == "2"
    assert frame.image_data.shape == original, "the file's data is untouched"
    assert window.analysis.analysis_image_data(frame).shape == (32, 32)

    _set(xpa, "block 1")
    assert _get(xpa, "block") == "1"
    assert window.analysis.analysis_image_data(frame).shape == original


def test_a_script_crops_and_uncrops(xpa, window, image):
    _set(xpa, f"file {image}")
    _set(xpa, "crop 32 32 10 10")
    cropped = _get(xpa, "crop").split()
    assert [float(word) for word in cropped[:4]] == [32.0, 32.0, 10.0, 10.0]

    # Outside the crop is blank, which is what a crop *is* here. Like
    # blocking, it is applied to what is shown and measured rather than to
    # the frame's copy of the file.
    frame = window.frame_manager.current_frame
    shown = window.analysis.analysis_image_data(frame)
    assert np.isnan(shown[0, 0]), "outside the crop is blank"
    assert not np.isnan(shown[32, 32]), "inside it is not"
    assert not np.isnan(frame.image_data[0, 0]), "the file's data is untouched"

    _set(xpa, "crop reset")
    assert not np.isnan(window.analysis.analysis_image_data(frame)[0, 0])


def test_a_script_contours_and_saves_them(xpa, window, image, tmp_path):
    _set(xpa, f"file {image}")
    _set(xpa, "contour yes")
    _set(xpa, "contour nlevels 5")
    _set(xpa, "contour color yellow")
    assert _get(xpa, "contour") == "yes"
    assert _get(xpa, "contour color") == "yellow"
    assert _get(xpa, "contour nlevels") == "5"

    target = tmp_path / "levels.ctr"
    _set(xpa, f"contour save {target}")
    assert target.is_file()

    _set(xpa, "contour no")
    assert _get(xpa, "contour") == "no"
    _set(xpa, f"contour load {target}")
    assert _get(xpa, "contour") == "yes", "loading contours shows them"


def test_reading_never_changes_anything(xpa, window, image):
    """Every `xpaget` in DS9's reference, run against a set-up window, and
    nothing may move.

    This is the regression test for the worst bug the conformance suite
    found: a read with arguments fell through to the *setter*, so `xpaget
    ds9 contour clear` cleared the contours and `xpaget ds9 crop reset`
    reset the crop -- a question that answered by changing the answer.
    """
    _set(xpa, f"file {image}")
    _set(xpa, "scale log")
    _set(xpa, "cmap heat")
    _set(xpa, "zoom 3")
    _set(xpa, "crop 30 30 12 12")
    _set(xpa, "contour yes")
    _set(xpa, "region command circle 20 20 5")

    def snapshot():
        frame = window.frame_manager.current_frame
        return {
            "scale": str(window.current_scale),
            "cmap": window.current_colormap,
            "zoom": window.image_viewer.get_zoom(),
            "crop": _get(xpa, "crop"),
            "contours": window.menu_bar.action_contours.isChecked(),
            "regions": len(frame.regions),
            "frames": len(window.frame_manager.frames),
            "data": float(np.nansum(window.analysis.analysis_image_data(frame))),
        }

    before = snapshot()
    dangerous = [
        "contour clear",
        "contour levels",
        "crop reset",
        "region delete",
        "frame delete",
        "frame new",
        "block 4",
        "smooth no",
        "zoom 1",
        "cmap grey",
    ]
    for command in dangerous:
        words = command.split()
        xpa.handle(words[0], {"get": True, "args": words[1:]})
    assert snapshot() == before, "an xpaget changed something"


def test_a_script_that_asks_for_nonsense_is_told_so(xpa, window, image):
    """A pipeline needs a diagnosable failure, not a silent success."""
    _set(xpa, f"file {image}")
    for command in (
        "wibble on",
        "scale sideways",
        "frame 99",
        "region load /nonesuch/x.reg",
        "contour nlevels lots",
        "savefits",
    ):
        words = command.split()
        reply = xpa.handle(words[0], {"args": words[1:]})
        assert reply["status"] == "error", f"{command} was accepted"
        assert reply["message"].strip(), f"{command} was refused without saying why"


def test_the_file_a_script_saved_is_a_fits_file(xpa, window, image, tmp_path):
    _set(xpa, f"file {image}")
    _set(xpa, "block 2")
    target = tmp_path / "blocked.fits"
    _set(xpa, f"savefits {target}")

    with fits.open(target) as handle:
        assert handle[0].data is not None
        assert handle[0].data.shape == window.frame_manager.current_frame.image_data.shape
