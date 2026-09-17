# This file is part of ncrads9.
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
The window one of DS9's Help entries opens.

One dialog for all eight documents, rather than eight dialogs: the pages
differ only in their text, and a window per page is a window per page to
keep movable, non-modal and readable under every theme.

The document is rendered in the browser's own palette colours -- see
`ncrads9/ui/help_documents.py` -- so it follows the theme, and it is
re-rendered when the theme changes under an open window.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..help_documents import HelpDocument, render


class HelpDocumentDialog(QDialog):
    """A page of NCRADS9's documentation."""

    def __init__(self, document: HelpDocument, parent: QWidget | None = None) -> None:
        """
        Args:
            document: What to show.
            parent: Owned by the main window, so it closes with it.
        """
        super().__init__(parent)
        self.document = document

        # An ordinary, movable, non-modal window: a reference page that
        # cannot be moved aside or read alongside the image is no use.
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowTitle(f"NCRADS9 -- {document.title}")
        self.resize(760, 620)

        layout = QVBoxLayout(self)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        layout.addWidget(self.browser)

        buttons = QHBoxLayout()
        buttons.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        self.refresh()

    def refresh(self) -> None:
        """Render the document in the colours currently in force."""
        self.browser.setHtml(render(self.document.title, self.document.html(), self.browser.palette()))

    def changeEvent(self, event: QEvent | None) -> None:
        """Re-render when the theme changes under an open window.

        The colours are baked into the HTML when it is rendered, so a
        palette change has to rebuild the document; the widget's own
        repaint cannot reach inside it.
        """
        super().changeEvent(event)
        if event is not None and event.type() == QEvent.Type.PaletteChange:
            self.refresh()
