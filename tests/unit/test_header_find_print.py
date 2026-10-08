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

"""The header window's File and Edit menus, as DS9's text windows have them."""

from astropy.io import fits


def _dialog(qapp):
    from ncrads9.ui.dialogs.header_dialog import HeaderDialog

    header = fits.Header({"OBJECT": "M51", "EXPTIME": 30.0, "FILTER": "r", "OBSERVER": "M51 team"})
    return HeaderDialog(header)


def test_the_menus(qapp):
    dialog = _dialog(qapp)
    bar = dialog.layout().menuBar()
    menus = {action.text(): action.menu() for action in bar.actions()}
    assert set(menus) == {"&File", "&Edit"}
    assert [a.text() for a in menus["&File"].actions() if a.text()] == ["Save...", "Print...", "Close"]
    assert [a.text() for a in menus["&Edit"].actions() if a.text()] == ["Copy", "Find...", "Find Next"]
    dialog.close()


def test_find_and_find_next_move_through_the_matches_and_wrap(qapp):
    dialog = _dialog(qapp)
    assert dialog.find("M51")
    first = dialog._header_text.textCursor().position()
    assert dialog.find_next()
    second = dialog._header_text.textCursor().position()
    assert second > first
    # Every card is still there: Find moves, it does not filter.
    assert "EXPTIME" in dialog._header_text.toPlainText()
    while dialog._header_text.textCursor().position() >= second:
        assert dialog.find_next()
    assert dialog._header_text.textCursor().position() == first
    assert not dialog.find("NOSUCHTHING")
    dialog.close()


def test_print_writes_the_header(qapp, tmp_path):
    from PyQt6.QtPrintSupport import QPrinter

    dialog = _dialog(qapp)
    printer = QPrinter()
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    target = tmp_path / "header.pdf"
    printer.setOutputFileName(str(target))
    assert dialog.print_header(printer)
    assert target.is_file() and target.stat().st_size > 0
    dialog.close()
