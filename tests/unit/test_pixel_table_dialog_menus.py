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

"""The Pixel Table's File, Edit and Size menus, as DS9's (`pixel.tcl`)."""

import numpy as np


def _dialog(qapp):
    from ncrads9.ui.dialogs.pixel_table_dialog import PixelTableDialog

    data = np.arange(100, dtype=np.float32).reshape(10, 10)
    return PixelTableDialog(data, 5, 5, size=3)


def test_the_menus_are_ds9s(qapp):
    dialog = _dialog(qapp)
    bar = dialog.layout().menuBar()
    assert [action.text() for action in bar.actions()] == ["&File", "&Edit", "Si&ze"]
    dialog.close()


def test_save_writes_the_table_and_copy_puts_it_on_the_clipboard(qapp, tmp_path):
    dialog = _dialog(qapp)
    target = tmp_path / "table.txt"
    assert dialog.save(str(target))
    text = target.read_text()
    lines = text.splitlines()
    assert len(lines) == 4
    assert lines[0].split("\t")[1:] == ["4", "5", "6"]
    dialog.copy()
    assert qapp.clipboard().text() == text
    dialog.close()


def test_the_size_menu_resizes_the_table(qapp):
    dialog = _dialog(qapp)
    size_menu = dialog.layout().menuBar().actions()[2].menu()
    next(action for action in size_menu.actions() if action.text() == "7x7").trigger()
    assert dialog.table.rowCount() == 7
    dialog.close()
