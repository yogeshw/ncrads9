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
The illustrate layer: what is drawn, in what order, and what is selected.

Kept apart from the overlay that paints it and the controller that drives
the menu, so the rules -- what a click picks, what Front means, what Invert
does -- can be tested without a display.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from .elements import DEFAULT_SIZES, ELEMENTS, Element, Style


class IllustrateLayer:
    """An ordered stack of illustrations with a selection."""

    def __init__(self) -> None:
        #: Back to front: the last element is drawn last and picked first.
        self.elements: list[Element] = []
        #: The style a new element is given, which the menu's Color and
        #: Width set.
        self.style = Style()
        #: Which shape the Shape menu has chosen.
        self.shape = "circle"
        #: Whether the layer is drawn at all, DS9's Show.
        self.visible = True
        #: What Copy and Cut left behind, for Paste.
        self.clipboard: list[Element] = []

    def __len__(self) -> int:
        """How many illustrations there are."""
        return len(self.elements)

    # -- adding and removing ----------------------------------------------------

    def add(self, element: Element) -> Element:
        """Put an element on top of the stack."""
        self.elements.append(element)
        return element

    def create(self, shape: str | None = None, x: float = 0.0, y: float = 0.0, **geometry) -> Element:
        """Make an element of one shape at a canvas position.

        Args:
            shape: Which shape, or None for the one the Shape menu has.
            x: Canvas x.
            y: Canvas y.
            geometry: Anything else that shape takes, such as a radius.

        Returns:
            The new element, already on the layer.
        """
        name = shape or self.shape
        kind = ELEMENTS[name]
        made: Element
        if name in ("polygon", "line"):
            half_w, half_h = DEFAULT_SIZES.get("polygon", (20.0, 20.0))
            points = geometry.pop(
                "points",
                (
                    [
                        (x - half_w, y - half_h),
                        (x + half_w, y - half_h),
                        (x + half_w, y + half_h),
                        (x - half_w, y + half_h),
                    ]
                    if name == "polygon"
                    else [(x - half_w, y), (x + half_w, y)]
                ),
            )
            made = kind(style=Style(**vars(self.style)), points=points, **geometry)
        else:
            made = kind(style=Style(**vars(self.style)), x=x, y=y, **geometry)
        return self.add(made)

    def delete(self, element: Element) -> None:
        """Remove one element."""
        if element in self.elements:
            self.elements.remove(element)

    def delete_selection(self) -> int:
        """Remove every selected element.

        Returns:
            How many went.
        """
        going = self.selection()
        self.elements = [element for element in self.elements if not element.selected]
        return len(going)

    def clear(self) -> int:
        """Remove everything.

        Returns:
            How many went.
        """
        count = len(self.elements)
        self.elements = []
        return count

    # -- the selection ------------------------------------------------------------

    def selection(self) -> list[Element]:
        """The selected elements, in draw order."""
        return [element for element in self.elements if element.selected]

    def select_all(self) -> int:
        """Select everything."""
        for element in self.elements:
            element.selected = True
        return len(self.elements)

    def select_none(self) -> None:
        """Select nothing."""
        for element in self.elements:
            element.selected = False

    def invert_selection(self) -> int:
        """Select what was not, and unselect what was."""
        for element in self.elements:
            element.selected = not element.selected
        return len(self.selection())

    def select_front(self) -> Element | None:
        """Select the topmost element alone, DS9's Front."""
        self.select_none()
        if not self.elements:
            return None
        self.elements[-1].selected = True
        return self.elements[-1]

    def select_back(self) -> Element | None:
        """Select the bottom element alone, DS9's Back."""
        self.select_none()
        if not self.elements:
            return None
        self.elements[0].selected = True
        return self.elements[0]

    def select_only(self, element: Element | None) -> None:
        """Select one element and nothing else, as a click does."""
        self.select_none()
        if element is not None:
            element.selected = True

    # -- the order they are drawn in ------------------------------------------------

    def move_to_front(self) -> int:
        """Put the selection on top, keeping its own order."""
        chosen = self.selection()
        if not chosen:
            return 0
        self.elements = [element for element in self.elements if not element.selected] + chosen
        return len(chosen)

    def move_to_back(self) -> int:
        """Put the selection at the bottom, keeping its own order."""
        chosen = self.selection()
        if not chosen:
            return 0
        self.elements = chosen + [element for element in self.elements if not element.selected]
        return len(chosen)

    # -- what a click finds ----------------------------------------------------------

    def at(self, x: float, y: float) -> Element | None:
        """The topmost element under a canvas position, if any.

        Front to back, because the one drawn last is the one you can see and
        so the one you meant to click.
        """
        for element in reversed(self.elements):
            if element.contains(x, y):
                return element
        return None

    def handle_at(self, x: float, y: float) -> tuple[Element, int] | None:
        """A selected element's handle under a position, if any.

        Only the selection has handles, and they win over whatever is under
        them: the handles of a small element sit inside larger ones, and
        grabbing one has to reshape rather than select what is behind.
        """
        for element in reversed(self.selection()):
            index = element.handle_at(x, y)
            if index is not None:
                return (element, index)
        return None

    # -- the clipboard -----------------------------------------------------------------

    def copy_selection(self) -> int:
        """Remember the selection, for Paste."""
        self.clipboard = [element.copy() for element in self.selection()]
        return len(self.clipboard)

    def cut_selection(self) -> int:
        """Remember the selection and remove it."""
        count = self.copy_selection()
        self.delete_selection()
        return count

    def paste(self, offset: float = 0.0) -> list[Element]:
        """Put the clipboard back, optionally shifted so it can be seen.

        Returns:
            The pasted elements, which become the selection.
        """
        pasted = []
        for element in self.clipboard:
            clone = element.copy()
            if offset:
                clone.move(offset, offset)
            pasted.append(self.add(clone))
        self.select_none()
        for element in pasted:
            element.selected = True
        return pasted

    # -- moving what is selected --------------------------------------------------------

    def move_selection(self, dx: float, dy: float) -> None:
        """Shift every selected element."""
        for element in self.selection():
            element.move(dx, dy)
