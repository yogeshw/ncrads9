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
The File menu: opening, saving, exporting and printing.

This is the emptiest menu relative to DS9 (PLAN.md §5.1 -- 6 entries against
59). Missing here and arriving later: the fifteen Open as / Save as loaders
(slice, RGB/HSV/HLS image and cube, multi-extension, four mosaic flavours,
URL) in M4; Import/Export for ten formats and Save Image for six in M9-13 and
M9-14; Prism in M9-9; Create Movie in M9-15; Backup/Restore in M9-11; Notes in
M9-16; Preserve During Load in M9-17; the XPA and SAMP submenus in M9-26 to
M9-28; and Page Setup with a real PostScript driver in M9-18 to M9-20.

`save_file` and `save_file_as` still do nothing but report their own name --
M4-10 implements them. They are wired rather than dead so the menu behaves
predictably, but nothing here pretends the data was written.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox

from ...colormaps.colormap import Colormap
from ...rendering.scale_algorithms import apply_scale, compute_zscale_limits
from ..dialogs.export_dialog import ExportDialog
from .base import Controller

#: Filter for the Open dialog. gzip variants are handled by astropy.
FITS_FILTER = "FITS Files (*.fits *.fit *.fts *.fits.gz *.fit.gz);;All Files (*)"

#: Filter for Save as. No gzip: nothing writes compressed FITS yet.
FITS_SAVE_FILTER = "FITS Files (*.fits *.fit *.fts);;All Files (*)"


class FileController(Controller):
    """Owns the File menu."""

    def connect(self) -> None:
        """Wire the File menu."""
        self.menu.action_open.triggered.connect(self.open_file)
        self.menu.action_save.triggered.connect(self.save_file)
        self.menu.action_save_as.triggered.connect(self.save_file_as)
        self.menu.action_export.triggered.connect(self.export_image)
        self.menu.action_print.triggered.connect(self.print_image)
        self.menu.action_exit.triggered.connect(self.window.close)

    # -- opening -------------------------------------------------------------

    def open_file(self, checked: bool = False, filepath: str | None = None) -> None:
        """Open a FITS file.

        Args:
            checked: Ignored; present because Qt passes it to triggered slots.
            filepath: The file to open. Prompts when omitted.
        """
        # Callers that pass a path positionally land it in `checked`.
        if isinstance(checked, str):
            filepath = checked

        if filepath is None or filepath is False:
            filepath, _ = QFileDialog.getOpenFileName(self.window, "Open FITS File", "", FITS_FILTER)
        if not filepath:
            return

        try:
            self.window.display.load_fits(filepath)
            self.status(f"Opened: {filepath}", 3000)
        except Exception as exc:
            self.status(f"Error loading file: {exc}", 5000)
            QMessageBox.critical(
                self.window,
                "Error Loading File",
                f"Could not load FITS file:\n{filepath}\n\nError: {exc}",
            )

    # -- saving --------------------------------------------------------------

    def save_file(self) -> None:
        """Save the current frame. Implemented by M4-10."""
        self.status("Save not yet implemented", 3000)

    def save_file_as(self) -> None:
        """Save the current frame under a new name. Implemented by M4-10."""
        filepath, _ = QFileDialog.getSaveFileName(self.window, "Save FITS File", "", FITS_SAVE_FILTER)
        if filepath:
            self.status(f"Save as: {filepath}", 3000)

    # -- rendering for export and print --------------------------------------

    def current_pixmap(self) -> QPixmap | None:
        """Render the current view to a pixmap.

        Applies the same pipeline the display uses -- clip limits, the
        viewer's contrast and bias, the scale algorithm, then the colormap --
        so what is exported or printed matches what is on screen.
        """
        image_data = self.window.image_data
        if image_data is None:
            return None

        if self.window.z1 is None or self.window.z2 is None:
            self.window.z1, self.window.z2 = compute_zscale_limits(image_data)

        contrast, brightness = self.viewer.get_contrast_brightness()
        span = self.window.z2 - self.window.z1
        center = (self.window.z1 + self.window.z2) / 2
        half = span / contrast / 2
        vmin = center - half + brightness * span
        vmax = center + half + brightness * span

        scaled = apply_scale(image_data, self.window.current_scale, vmin=vmin, vmax=vmax)

        try:
            cmap = self.window.color.colormap(self.window.current_colormap)
        except ValueError:
            cmap = self.window.color.colormap("grey")
        if self.window.invert_colormap:
            cmap = Colormap(f"{self.window.current_colormap}_inverted", cmap.colors[::-1].copy())

        rgb = cmap.apply_normalized(scaled)
        height, width = rgb.shape[:2]
        qimage = QImage(rgb.data, width, height, 3 * width, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimage)

    def export_image(self) -> None:
        """Export the current view as a raster image."""
        pixmap = self.current_pixmap()
        if pixmap is None:
            self.status("No image to export")
            return

        dialog = ExportDialog(pixmap, self.window)
        if dialog.exec():
            self.status(f"Exported to {dialog.export_path}", 3000)

    def print_image(self) -> None:
        """Print the current view.

        A pixmap scaled to the page, not the full PostScript driver DS9 has;
        M9-18 replaces this.
        """
        pixmap = self.current_pixmap()
        if pixmap is None:
            self.status("No image to print")
            return

        from PyQt6.QtGui import QPainter
        from PyQt6.QtPrintSupport import QPrintDialog, QPrinter

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        if QPrintDialog(printer, self.window).exec() != QDialog.DialogCode.Accepted:
            return

        painter = QPainter(printer)
        rect = painter.viewport()
        size = pixmap.size()
        size.scale(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
        painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
        painter.setWindow(pixmap.rect())
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        self.status("Print completed")

    # -- header --------------------------------------------------------------

    def show_header(self) -> None:
        """Show the FITS header of the current frame."""
        if self.window.fits_handler is None:
            self.status("No FITS file loaded")
            return

        from ..dialogs.header_dialog import HeaderDialog

        HeaderDialog(self.window.fits_handler.get_header(), self.window).exec()
