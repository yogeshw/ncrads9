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
Restoring SAOImageDS9's own backup files.

The fixture is written line for line as DS9 8.x's `backup.tcl` writes one:
the version preamble and `BackupFindFile` proc of `BackupPreamble`, then
per frame `CreateNameNumberFrame`, the load (`array set loadParam [list
...]` and `ProcessLoad`), and the lines of each subsystem's `*Backup`
procedure, and finally `BackupGUI`'s arrays.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.io.session import ds9_backup
from ncrads9.rendering.scale_algorithms import ScaleAlgorithm

PREAMBLE = r"""global ds9
set vv 8.3
# this is a check for to ensure a match between the
# current ds9 version matches the prefs version
switch -- [string compare $vv [lindex $ds9(version) 0]] {
  -1 {
    if {[tk_messageBox -type yesno -icon question -message [msgcat::mc {DS9 has detected an older backup file, do you wish to continue?}]] == {no}} {
      return
    }
  }
  0 {}
  1 {
    tk_messageBox -type ok -icon warning -message [msgcat::mc {DS9 has detected a newer version of a backup file and therefore will not process this file.}]
    return
  }
}
proc BackupFindFile {varname} {
  upvar $varname var

  set id [string first "\[" $var(file,name)]
  if {$id > 0} {
    set fn [string range $var(file,name) 0 [expr $id-1]]
    set ext [string range $var(file,name) $id end]
  } else {
    set fn $var(file,name)
    set ext {}
  }
  return 1
}
panner compass 1
colorbar configure -size 20
colorbar configure -ticks 11
colorbar configure -numerics 1
colorbar configure -space value
colorbar configure -orientation vertical
colorbar configure -font helvetica
colorbar configure -fontsize 9
colorbar configure -fontweight normal
colorbar configure -fontslant roman
"""

FRAME1 = r"""CreateNameNumberFrame Frame1 base
global loadParam
array set loadParam [list load,layer {} file,name ./session.bck.dir/Frame1/sky.fits file,mode {} load,type mmapincr file,type fits]
if [BackupFindFile loadParam] {
  ProcessLoad
}
Frame1 magnifier graphics 1
Frame1 magnifier cursor 1
Frame1 magnifier zoom 8
Frame1 magnifier color red
Frame1cb colorbar 13 0.4 2.5 1
Frame1 colormap [Frame1cb get colormap]
Frame1 colorbar tag "{}"
Frame1cb tag "{}"
Frame1 cube axes 123
Frame1 colorscale sqrt
Frame1 colorscale log 1000
Frame1 datasec 1
Frame1 clip user 10 50
Frame1 clip mode user
Frame1 clip scope local
Frame1 clip minmax mode scan
Frame1 clip minmax sample 25
Frame1 clip zscale contrast 0.25
Frame1 clip zscale sample 600
Frame1 clip zscale line 120
Frame1 block to 1 1
Frame1 wcs wcs fk5 sexagesimal
update
Frame1 pan preserve 0
Frame1 pan to physical 20 25
Frame1 zoom to 4 4
Frame1 rotate to 0
Frame1 orient x
Frame1 wcs align 0
Frame1 marker load ds9 {"./session.bck.dir/Frame1/ds9.reg"}
Frame1 crosshair physical 12 13
Frame1 marker centroid radius 10
Frame1 marker centroid iteration 30
Frame1 mask transparency 0
Frame1 mask system physical
Frame1 mask color red
Frame1 mask mark nonzero
Frame1 mask range 0 0
Frame1 smooth boxcar 4 4 2 2 0
Frame1 contour create green 1 0 smooth 3 4 linear 1000 user local 10 40 {"10 20 30 40"}
Frame1 grid create wcs fk5 sexagesimal analysis {"..."} {"..."}
"""

FRAME2 = r"""CreateNameNumberFrame Frame2 rgb
Frame2 rgb channel red
global loadParam
array set loadParam [list load,layer {} file,name ./session.bck.dir/Frame2/r.fits file,mode {} load,type mmapincr file,type fits]
if [BackupFindFile loadParam] {
  ProcessLoad
}
Frame2 rgb channel green
global loadParam
array set loadParam [list load,layer {} file,name ./session.bck.dir/Frame2/g.fits file,mode {} load,type mmapincr file,type fits]
if [BackupFindFile loadParam] {
  ProcessLoad
}
Frame2 rgb channel blue
global loadParam
array set loadParam [list load,layer {} file,name ./session.bck.dir/Frame2/b.fits file,mode {} load,type mmapincr file,type fits]
if [BackupFindFile loadParam] {
  ProcessLoad
}
RGBDialog
Frame2cb colorbar rgb 0.5 0.5 0.5 1 1 1 0
Frame2 rgb channel red
Frame2 rgb view 1 0 1
Frame2 rgb system wcs
"""

GUI = r"""set ds9(seq) 3
global ds9notes
set ds9notes {observed on a cloudy night}
global current
array set current { frame Frame1 display tile mode crosshair colorbar Frame1cb rgb red }
global view
array set view { layout vertical info 1 panner 1 magnifier 1 buttons 1 colorbar 1 graph,horz 0 graph,vert 0 }
global tile
array set tile { mode column grid,row 10 grid,col 10 }
global blink
array set blink { interval 500 }
"""


def _image(path, value_offset=0.0):
    rows, columns = np.indices((64, 64))
    header = fits.Header(
        {
            "CRPIX1": 32,
            "CRPIX2": 32,
            "CRVAL1": 202.48,
            "CRVAL2": 47.21,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
        }
    )
    fits.PrimaryHDU(data=(rows + columns + value_offset).astype(np.float32), header=header).writeto(path)


@pytest.fixture
def backup_file(tmp_path):
    """A DS9 backup and its `.bck.dir`, as DS9 lays them out."""
    data = tmp_path / "session.bck.dir"
    (data / "Frame1").mkdir(parents=True)
    (data / "Frame2").mkdir(parents=True)
    _image(data / "Frame1" / "sky.fits")
    for index, name in enumerate(("r", "g", "b")):
        _image(data / "Frame2" / f"{name}.fits", value_offset=index * 10)
    (data / "Frame1" / "ds9.reg").write_text(
        "# Region file format: DS9 version 4.1\nglobal color=green\nimage\ncircle(30,30,5)\nbox(10,10,4,6,0)\n"
    )
    path = tmp_path / "session.bck"
    path.write_text(PREAMBLE + FRAME1 + FRAME2 + GUI)
    return path


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow

    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    made = MainWindow()
    made.resize(900, 800)
    made.show()
    yield made
    made.close()


# -- the reader ----------------------------------------------------------------------


def test_tcl_words():
    assert ds9_backup.words('a {b c} "d e" [x y]') == ["a", "b c", "d e", "[x y]"]
    assert ds9_backup.pairs("{ frame Frame1 display tile }") == {"frame": "Frame1", "display": "tile"}
    commands = ds9_backup.commands("proc P {v} {\n  set x 1\n}\nFrame1 zoom to 2 2\n# c\nupdate")
    assert [c[0] for c in commands] == ["proc", "Frame1", "update"]


def test_a_ds9_backup_is_recognised(backup_file, tmp_path):
    assert ds9_backup.is_ds9_backup(backup_file)
    ours = tmp_path / "ours.bck"
    ours.write_text('{"format": "ncrads9-backup"}')
    assert not ds9_backup.is_ds9_backup(ours)


def test_the_colormap_numbers_are_ds9s():
    assert ds9_backup.COLORMAP_IDS[0] == "grey"
    assert ds9_backup.COLORMAP_IDS[12] == "heat"
    assert len(ds9_backup.COLORMAP_IDS) == 180


def test_the_translation(backup_file):
    plan = ds9_backup.read(backup_file)
    frames = [(step.frame, step.words[0]) for step in plan.steps if step.kind == "frame"]
    assert frames == [(1, "base"), (2, "rgb")]
    commands = [" ".join(step.words) for step in plan.steps if step.kind == "xpa" and step.frame == 1]
    assert "cmap heat" in commands
    assert "scale limits 10 50" in commands
    assert "zoom to 4" in commands
    assert "pan to 20 25 physical" in commands
    assert plan.current_frame == 1
    assert plan.notes == "observed on a cloudy night"
    assert not [line for line in plan.skipped if "Frame" in line], plan.skipped


# -- the restore ---------------------------------------------------------------------


def test_restoring_a_ds9_backup(window, backup_file, qapp):
    assert window.session.restore(str(backup_file))
    qapp.processEvents()
    frames = window.frame_manager
    assert [frame.frame_id for frame in frames.frames] == [1, 2]
    assert frames.frames[1].frame_type == "rgb"
    assert frames.current_frame.frame_id == 1, "the frame that was current"

    first = frames.frames[0]
    assert first.filepath is not None and first.filepath.name == "sky.fits"
    assert window.current_colormap == "heat"
    assert window.invert_colormap is True
    assert window.color.contrast_bias() == pytest.approx((2.5, 0.4))
    assert window.current_scale is ScaleAlgorithm.LOG
    assert window.scale.current_limits() == pytest.approx((10, 50))
    # The session ends tiled, where the viewer shows the mosaic; the
    # frame keeps its own zoom.
    assert first.zoom == pytest.approx(4)
    assert first.flip_x and not first.flip_y
    assert len(first.regions) == 2
    assert first.crosshair == pytest.approx((12, 13))
    assert window.menu_bar.action_smooth.isChecked()
    assert window._smooth_settings["kernel_type"].lower() == "boxcar"
    assert window.menu_bar.action_contours.isChecked()
    assert list(window._contour_levels) == pytest.approx([10, 20, 30, 40])
    assert window.analysis.grid_config.visible

    second = frames.frames[1]
    assert all(second.rgb_channels[name] is not None for name in ("red", "green", "blue"))
    assert second.rgb_view == {"red": True, "green": False, "blue": True}

    assert window._frame_display_mode == "tile"
    assert "cloudy" in window.notes.text
    assert not [p for p in window.session.problems if "Frame" in p], window.session.problems


def test_a_missing_data_file_is_reported_not_fatal(window, backup_file, qapp):
    (backup_file.parent / "session.bck.dir" / "Frame2" / "g.fits").unlink()
    assert window.session.restore(str(backup_file))
    assert [frame.frame_id for frame in window.frame_manager.frames] == [1, 2]
    assert any("g.fits" in problem for problem in window.session.problems)
