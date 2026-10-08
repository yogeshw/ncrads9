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

"""Prism's Plot asks for error columns and the curve's look, as DS9's does."""

from ncrads9.ui.dialogs.prism_dialog import NO_COLUMN, ColumnChooser


def test_the_chooser_offers_error_columns_and_properties(qapp, monkeypatch):
    from PyQt6.QtWidgets import QDialog

    chooser = ColumnChooser(["T", "FLUX", "ERR"])
    chooser._x.setCurrentText("T")
    chooser._y.setCurrentText("FLUX")
    chooser._y_error.setCurrentText("ERR")
    chooser._colour.setCurrentText("red")
    chooser._shape.setCurrentText("square")
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    chosen = chooser.choose()
    assert chosen["x_error"] is None
    assert chosen["y_error"] == "ERR"
    assert chosen["style"]["color"] == "red" and chosen["style"]["shape"] == "square"
    assert chooser._x_error.itemText(0) == NO_COLUMN


def test_a_histogram_asks_for_bins_only(qapp):
    chooser = ColumnChooser(["T", "FLUX"], histogram=True)
    assert not hasattr(chooser, "_y_error")
