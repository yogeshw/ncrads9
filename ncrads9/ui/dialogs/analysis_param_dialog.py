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
The dialog a `param` block in an analysis file describes.

DS9 builds it from the rows of the block: each row names a variable, a
widget, a title, a default and a hint, and the values the user leaves are
substituted into the command line as `$<variable>`
(`ds9/library/analysisparam.tcl`). A block split into `tab`s becomes a
notebook.

Seven widgets, all DS9's: entry, text (which is static -- it displays a
value the command line will use but does not let it be edited), checkbox,
menu, combobox (editable, unlike menu), and open/save, each a path with a
browse button.

The defaults may themselves contain macros -- `{$filename}` is in DS9's own
sample -- so they are expanded before the dialog is shown rather than after,
which is why this takes an `expand` callable.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...analysis.task_file import Parameter, ParameterSet

#: The checkbox values DS9 writes into a command line.
CHECKED = "1"
UNCHECKED = "0"


class AnalysisParamDialog(QDialog):
    """One `param` block, as a dialog.

    Args:
        parameters: The block.
        expand: Called with a default value to expand any macros in it --
            DS9's own sample defaults include `$filename` and `$width`.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        parameters: ParameterSet,
        expand: Callable[[str], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(parameters.name or "Parameters")
        self.parameters = parameters
        self._expand = expand or (lambda value: value)
        self._widgets: dict[str, QWidget] = {}

        layout = QVBoxLayout(self)
        if parameters.iraf_file:
            layout.addWidget(
                QLabel(
                    f"This task's parameters come from the IRAF file "
                    f"<b>{parameters.iraf_file}</b>, which is not read yet."
                )
            )

        tabs = [tab for tab in parameters.tabs if tab.parameters]
        if len(tabs) > 1:
            notebook = QTabWidget()
            for tab in tabs:
                notebook.addTab(self._page(tab.parameters), tab.title or "Parameters")
            layout.addWidget(notebook)
        elif tabs:
            layout.addWidget(self._page(tabs[0].parameters))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _page(self, rows: tuple[Parameter, ...]) -> QWidget:
        """One tab, or the whole of an untabbed block."""
        page = QWidget()
        form = QFormLayout(page)
        for row in rows:
            widget = self._widget_for(row)
            self._widgets[row.variable] = widget
            label = row.title or row.variable
            form.addRow(f"{label}:", widget)
            if row.comment:
                hint = QLabel(f"<i>{row.comment}</i>")
                hint.setWordWrap(True)
                form.addRow("", hint)
        return page

    def _widget_for(self, row: Parameter) -> QWidget:
        """The widget one row asks for."""
        initial = self._expand(row.initial)

        if row.kind == "checkbox":
            box = QCheckBox()
            box.setChecked(str(row.default).strip() not in ("", "0", "false", "no"))
            return box

        if row.kind in ("menu", "combobox"):
            combo = QComboBox()
            combo.addItems([self._expand(choice) for choice in row.choices] or [initial])
            # A combobox is DS9's editable one; a menu is a fixed choice.
            combo.setEditable(row.kind == "combobox")
            return combo

        if row.kind in ("open", "save"):
            return _PathChooser(initial, row.kind)

        if row.kind == "text":
            # DS9's `text` displays a value without letting it be edited.
            field = QLineEdit(initial)
            field.setReadOnly(True)
            return field

        return QLineEdit(initial)

    def values(self) -> dict[str, str]:
        """What the user left in each field, keyed by variable name."""
        result: dict[str, str] = {}
        for name, widget in self._widgets.items():
            if isinstance(widget, QCheckBox):
                result[name] = CHECKED if widget.isChecked() else UNCHECKED
            elif isinstance(widget, QComboBox):
                result[name] = widget.currentText()
            elif isinstance(widget, _PathChooser):
                result[name] = widget.path()
            elif isinstance(widget, QLineEdit):
                result[name] = widget.text()
        return result


class _PathChooser(QWidget):
    """A path with a browse button, for DS9's `open` and `save` rows."""

    def __init__(self, initial: str, kind: str) -> None:
        super().__init__()
        self._kind = kind
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._field = QLineEdit(initial)
        layout.addWidget(self._field)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse)
        layout.addWidget(browse)

    def _browse(self) -> None:
        """Ask for a path, in whichever direction the row asked for."""
        if self._kind == "save":
            chosen, _filter = QFileDialog.getSaveFileName(self, "Save", self._field.text())
        else:
            chosen, _filter = QFileDialog.getOpenFileName(self, "Open", self._field.text())
        if chosen:
            self._field.setText(chosen)

    def path(self) -> str:
        """The chosen path."""
        return self._field.text()
