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
DS9's Preferences: a list of topics, and a page of controls for each.

Laid out as DS9's is (`prefsdialog.tcl`) -- the topics down the left, the
chosen one's controls on the right -- and *generated* from
`utils/preference_defs.py` rather than written out. Twenty-nine pages of
hand-built widgets is how a preferences dialog comes to disagree with the
preferences it edits; a table and a renderer cannot.

The Bindings page is the exception, because a shortcut editor is a table of
its own rather than a row of controls.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QKeySequence
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...ui import bindings as bindings_module
from ...utils import preference_defs

#: How big the window opens.
WINDOW_SIZE = (820, 560)

#: The topic the shortcut editor lives on.
BINDINGS_TOPIC = "Bindings"


class PreferencesDialog(QDialog):
    """Every preference, by topic."""

    #: Emitted with every preference when Save or Apply is pressed.
    preferences_changed = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Args:
            parent: The main window.
        """
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(*WINDOW_SIZE)

        #: Preference key -> the widget editing it.
        self.editors: dict[str, QWidget] = {}
        #: Colour key -> the colour chosen, since a button holds no value.
        self._colors: dict[str, QColor] = {}
        #: Binding name -> its shortcut editor.
        self.shortcut_editors: dict[str, QKeySequenceEdit] = {}

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.topics = QListWidget()
        self.topics.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        splitter.addWidget(self.topics)

        self.pages = QWidget()
        self._pages_layout = QVBoxLayout(self.pages)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.pages)
        splitter.addWidget(scroll)
        splitter.setSizes([200, 620])
        layout.addWidget(splitter)

        self._build_pages()
        self.topics.currentRowChanged.connect(self.show_topic)
        self.topics.setCurrentRow(0)

        buttons = QHBoxLayout()
        #: Button name -> the button, so a test can press one.
        self.buttons: dict[str, QPushButton] = {}
        for name, label, slot in (
            ("defaults", "Restore Defaults", self.restore_defaults),
            ("apply", "Apply", self.apply),
            ("save", "Save", self.save),
            ("close", "Close", self.reject),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            buttons.addWidget(button)
            self.buttons[name] = button
        layout.addLayout(buttons)

    # -- building the pages ----------------------------------------------------

    def _build_pages(self) -> None:
        """One page per topic, from the table."""
        #: Topic -> its page.
        self._pages: dict[str, QWidget] = {}
        for topic, preferences in preference_defs.by_topic().items():
            page = self._page(preferences)
            self._pages[topic] = page
            self._pages_layout.addWidget(page)
            page.hide()
            self.topics.addItem(topic)

        bindings_page = self._bindings_page()
        self._pages[BINDINGS_TOPIC] = bindings_page
        self._pages_layout.addWidget(bindings_page)
        bindings_page.hide()
        self.topics.addItem(BINDINGS_TOPIC)
        self._pages_layout.addStretch()

    def _page(self, preferences) -> QWidget:
        """One topic's controls."""
        page = QWidget()
        form = QFormLayout(page)
        for preference in preferences:
            editor = self._editor(preference)
            self.editors[preference.key] = editor
            row = editor
            if preference.suffix:
                row = QWidget()
                inner = QHBoxLayout(row)
                inner.setContentsMargins(0, 0, 0, 0)
                inner.addWidget(editor)
                inner.addWidget(QLabel(preference.suffix))
            form.addRow(preference.label + ":", row)
            if preference.note:
                note = QLabel(preference.note)
                note.setWordWrap(True)
                note.setEnabled(False)
                form.addRow("", note)
        return page

    def _editor(self, preference) -> QWidget:
        """The control one preference needs."""
        if preference.kind == "bool":
            box = QCheckBox()
            box.setChecked(bool(preference.default))
            return box
        if preference.kind == "int":
            spin = QSpinBox()
            spin.setRange(int(preference.minimum), int(preference.maximum))
            spin.setValue(int(preference.default))
            return spin
        if preference.kind == "float":
            spin = QDoubleSpinBox()
            spin.setRange(float(preference.minimum), float(preference.maximum))
            spin.setSingleStep(float(preference.step))
            spin.setDecimals(3)
            spin.setValue(float(preference.default))
            return spin
        if preference.kind == "choice":
            combo = QComboBox()
            combo.addItems(list(preference.choices))
            combo.setCurrentText(str(preference.default))
            return combo
        if preference.kind == "color":
            button = QPushButton()
            button.setFixedSize(70, 24)
            self._colors[preference.key] = QColor(str(preference.default))
            button.clicked.connect(lambda _checked=False, key=preference.key: self._choose(key))
            self._paint(button, self._colors[preference.key])
            return button
        line = QLineEdit()
        line.setText("" if preference.default is None else str(preference.default))
        return line

    def _bindings_page(self) -> QWidget:
        """The keyboard-shortcut editor (M9-33)."""
        page = QWidget()
        column = QVBoxLayout(page)
        column.addWidget(
            QLabel(
                "Click a shortcut and type the keys you want. Clearing one leaves "
                "the command with no shortcut, which is a legitimate thing to want."
            )
        )

        table = QTableWidget(len(bindings_module.BINDINGS), 2)
        table.setHorizontalHeaderLabels(["Command", "Shortcut"])
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        for row, binding in enumerate(bindings_module.BINDINGS):
            name = QTableWidgetItem(binding.label)
            name.setFlags(Qt.ItemFlag.ItemIsEnabled)
            table.setItem(row, 0, name)
            editor = QKeySequenceEdit(QKeySequence(binding.default))
            self.shortcut_editors[binding.name] = editor
            table.setCellWidget(row, 1, editor)
        table.resizeColumnsToContents()
        column.addWidget(table)
        self.shortcut_table = table

        self._conflicts = QLabel()
        self._conflicts.setWordWrap(True)
        column.addWidget(self._conflicts)

        reset = QPushButton("Restore Default Shortcuts")
        reset.clicked.connect(self.restore_shortcuts)
        column.addWidget(reset)
        return page

    def show_topic(self, row: int) -> None:
        """Show the chosen topic's page."""
        item = self.topics.item(row)
        if item is None:
            return
        for topic, page in self._pages.items():
            page.setVisible(topic == item.text())

    # -- reading and writing ----------------------------------------------------

    def _choose(self, key: str) -> None:
        """Pick a colour."""
        chosen = QColorDialog.getColor(self._colors.get(key, QColor()), self, "Choose Color")
        if chosen.isValid():
            self._colors[key] = chosen
            editor = self.editors.get(key)
            if isinstance(editor, QPushButton):
                self._paint(editor, chosen)

    @staticmethod
    def _paint(button: QPushButton, color: QColor) -> None:
        """Show a colour on its button."""
        button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")
        button.setText(color.name())

    def load_preferences(self, prefs: dict[str, Any]) -> None:
        """Fill the dialog in.

        Args:
            prefs: The values to show. Anything the table does not know is
                ignored rather than refused, so an old preferences file
                does not stop the dialog opening.
        """
        table = preference_defs.by_key()
        for key, value in prefs.items():
            preference = table.get(key)
            editor = self.editors.get(key)
            if preference is None or editor is None:
                continue
            self._set(preference, editor, value)

        shortcuts = {name: prefs.get(bindings_module.PREFIX + name) for name in self.shortcut_editors}
        for name, editor in self.shortcut_editors.items():
            wanted = shortcuts.get(name)
            if wanted is not None:
                editor.setKeySequence(QKeySequence(str(wanted)))
        self.check_conflicts()

    def _set(self, preference, editor: QWidget, value: Any) -> None:
        """Put one value in its control."""
        if preference.kind == "bool" and isinstance(editor, QCheckBox):
            editor.setChecked(bool(value))
        elif preference.kind == "int" and isinstance(editor, QSpinBox):
            editor.setValue(int(value))
        elif preference.kind == "float" and isinstance(editor, QDoubleSpinBox):
            editor.setValue(float(value))
        elif preference.kind == "choice" and isinstance(editor, QComboBox):
            editor.setCurrentText(str(value))
        elif preference.kind == "color" and isinstance(editor, QPushButton):
            color = QColor(str(value))
            if color.isValid():
                self._colors[preference.key] = color
                self._paint(editor, color)
        elif isinstance(editor, QLineEdit):
            editor.setText("" if value is None else str(value))

    def values(self) -> dict[str, Any]:
        """Every preference as the dialog now has it."""
        found: dict[str, Any] = {}
        for preference in preference_defs.PREFERENCES:
            editor = self.editors.get(preference.key)
            if editor is None:
                continue
            if preference.kind == "bool":
                found[preference.key] = editor.isChecked()
            elif preference.kind in ("int", "float"):
                found[preference.key] = editor.value()
            elif preference.kind == "choice":
                found[preference.key] = editor.currentText()
            elif preference.kind == "color":
                found[preference.key] = self._colors[preference.key].name()
            else:
                found[preference.key] = editor.text()

        for name, editor in self.shortcut_editors.items():
            found[bindings_module.PREFIX + name] = editor.keySequence().toString()
        return found

    #: Kept under its old name, which the Edit controller and its tests use.
    def _get_settings(self) -> dict[str, Any]:
        """Every preference as the dialog now has it."""
        return self.values()

    # -- the buttons ---------------------------------------------------------------

    def check_conflicts(self) -> dict[str, list[str]]:
        """Say which shortcuts two commands are both asking for.

        Two commands on one combination means one of them never fires, and
        which one is Qt's business rather than the user's.
        """
        shortcuts = {name: editor.keySequence().toString() for name, editor in self.shortcut_editors.items()}
        clashes = bindings_module.conflicts(shortcuts)
        labels = bindings_module.by_name()
        if clashes:
            lines = [
                f"{shortcut} is wanted by "
                + " and ".join(labels[name].label for name in names if name in labels)
                for shortcut, names in clashes.items()
            ]
            self._conflicts.setText("Conflicts: " + "; ".join(lines))
        else:
            self._conflicts.setText("")
        return clashes

    def apply(self) -> None:
        """Hand the settings over without closing."""
        self.check_conflicts()
        self.preferences_changed.emit(self.values())

    def save(self) -> None:
        """Hand them over and close, as DS9's Save does."""
        self.apply()
        self.accept()

    def restore_defaults(self) -> None:
        """Put every control back to its default."""
        self.load_preferences({**preference_defs.defaults(), **bindings_module.defaults()})

    def restore_shortcuts(self) -> None:
        """Put the shortcuts back, leaving everything else alone."""
        for name, shortcut in bindings_module.defaults().items():
            editor = self.shortcut_editors.get(name.removeprefix(bindings_module.PREFIX))
            if editor is not None:
                editor.setKeySequence(QKeySequence(shortcut))
        self.check_conflicts()
