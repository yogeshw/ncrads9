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
What a parameters window has to be, to be usable at all.

Every one of DS9's Parameters windows changes something drawn on the image:
the contour levels, the graticule, the smoothing radius, the mask, the
colormap. Judging any of them means looking at the picture while the window
is open, so such a window must be three things, and each of them is a
separate mistake to make:

* **Modeless.** Shown with `exec()` a dialog is application-modal whatever
  modality it asked for, and Apply then changes something the reader cannot
  look at until they close the window.
* **An ordinary window.** Left as a plain `Qt.Dialog`, a window manager is
  free to treat it as a fixed utility panel -- no minimise, no sending it
  behind, and on some desktops nothing to take hold of. Naming the flags
  explicitly asks for a title bar and the minimise and maximise buttons; the
  close button has to be named too, because naming any flag replaces the
  whole default set rather than adding to it.
* **Held.** A modeless window nothing holds a reference to is collected the
  instant it is shown. `ControllerBase.show_window` does that part, and also
  raises the one already up rather than stacking a second.

`WindowStaysOnTopHint` is deliberately absent. It was tried, and it is what
made the older windows impossible to get out of the way: they floated over
the image whatever the reader did, and on a small screen there was nowhere
to put them.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

#: An ordinary, movable, minimisable top-level window.
WINDOW_FLAGS = (
    Qt.WindowType.Window
    | Qt.WindowType.WindowTitleHint
    | Qt.WindowType.WindowSystemMenuHint
    | Qt.WindowType.WindowMinMaxButtonsHint
    | Qt.WindowType.WindowCloseButtonHint
)


def make_modeless(dialog: QWidget) -> QWidget:
    """Turn one dialog into a parameters window. Call it from `__init__`.

    Keeps whatever parent it was given -- that is what closes it with the
    main window and stops it outliving the frame it edits -- while making it
    a top-level window in its own right rather than a panel pinned over the
    image.

    Returns:
        The same dialog, so a constructor can say what it is in one line.
    """
    dialog.setWindowFlags(WINDOW_FLAGS)
    dialog.setWindowModality(Qt.WindowModality.NonModal)
    return dialog
