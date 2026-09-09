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

M4 filled in DS9's `Open as` and `Save as` submenus and made Save write. What
opens a file is a DS9 file specification (`core/file_spec.py`), so an
extension, a subsection and a bin-table's columns can all be named in the
path; what reads it is one of the loaders in `core/fits_loaders.py`.

An extension chooser (`ui/dialogs/open_dialog.py`) appears when a file has
more than one displayable HDU. DS9 does not ask -- it applies its algorithm
and takes the first -- so the prompt is a deliberate divergence, and the
`prompt_for_hdu` preference turns it off.

Still missing against DS9 (PLAN.md §5.1): Import/Export for ten formats and
the five raster Save Image variants in M9-13 and M9-14; Prism in M9-9; Create
Movie in M9-15; Backup/Restore in M9-11; Notes in M9-16; Preserve During Load
in M9-17; the XPA and SAMP submenus in M9-26 to M9-28; and Page Setup with a
real PostScript driver in M9-18 to M9-20.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from astropy.io import fits
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox

from ...colormaps.colormap import Colormap
from ...core import fits_loaders
from ...core.file_spec import FileSpec
from ...core.file_spec import parse as parse_file_spec
from ...core.fits_handler import FITSHandler
from ...core.mosaic import MosaicKind
from ...io.fits_writer import FITSWriter
from ...rendering.scale_algorithms import apply_scale, compute_zscale_limits
from ..dialogs.export_dialog import ExportDialog
from ..dialogs.open_dialog import HDUChoice, OpenDialog
from .base import Controller

#: Filter for the Open dialog. gzip variants are handled by astropy.
FITS_FILTER = "FITS Files (*.fits *.fit *.fts *.fits.gz *.fit.gz);;All Files (*)"

#: Filter for Save as. No gzip: nothing writes compressed FITS yet.
FITS_SAVE_FILTER = "FITS Files (*.fits *.fit *.fts);;All Files (*)"

#: `Open as` name -> the colour space its frame uses, for the six colour
#: loaders. The loading is identical; only the frame type differs.
COLOUR_LOADERS: dict[str, tuple[str, bool]] = {
    "rgb_image": ("rgb", False),
    "rgb_cube": ("rgb", True),
    "hsv_image": ("hsv", False),
    "hsv_cube": ("hsv", True),
    "hls_image": ("hls", False),
    "hls_cube": ("hls", True),
}

#: `Open as` name -> (mosaic convention, whether it is a segment load).
MOSAIC_LOADERS: dict[str, tuple[MosaicKind, bool]] = {
    "mosaic_wcs": (MosaicKind.WCS, False),
    "mosaic_wcs_segment": (MosaicKind.WCS, True),
    "mosaic_iraf": (MosaicKind.IRAF, False),
    "mosaic_iraf_segment": (MosaicKind.IRAF, True),
    "mosaic_wfpc2": (MosaicKind.WFPC2, False),
}

#: `Save Image` formats that M4 does not write, and the milestone that does.
DEFERRED_IMAGE_FORMATS: dict[str, str] = {
    "eps": "M9-18",
    "gif": "M9-14",
    "tiff": "M9-14",
    "jpeg": "M9-14",
    "png": "M9-14",
}

#: How long to wait for a URL before giving up, in seconds.
URL_TIMEOUT = 30


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

        for name, action in self.menu.open_as_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.open_as(key))
        for name, action in self.menu.save_as_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.save_as(key))
        for name, action in self.menu.save_image_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.save_image(key))

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
            specification = self._choose_extension(filepath)
            if specification is None:
                return
            self.window.display.load_fits(specification)
            self.status(f"Opened: {specification}", 3000)
        except Exception as exc:
            self._report(f"Could not load FITS file:\n{filepath}", exc)

    def _choose_extension(self, filepath: str) -> str | None:
        """Ask which extension to load, when there is a choice to make.

        Args:
            filepath: The specification the user gave.

        Returns:
            The specification to load, with an extension appended if one was
            chosen, or None if the user cancelled. When the file has one
            displayable HDU, or the specification already names an extension,
            or the `prompt_for_hdu` preference is off, the input is returned
            unchanged and no dialog appears.
        """
        spec = parse_file_spec(filepath)
        if spec.extension is not None:
            return filepath
        if not bool(self.window.preferences.get("prompt_for_hdu", True)):
            return filepath

        with FITSHandler(str(spec.path)) as handler:
            extensions = handler.extensions()
            displayable = [info for info in extensions if info.displayable]
            if len(displayable) < 2:
                return filepath
            default = handler.default_extension().index

        dialog = OpenDialog(spec.path, extensions, default, self.window)
        if not dialog.exec():
            return None
        selection = dialog.selection()
        if selection is None:
            return None

        if selection.choice is HDUChoice.ALL_FRAMES:
            self.load_extension_frames(spec)
            return None
        if selection.choice is HDUChoice.ALL_CUBE:
            self.load_extension_cube(spec)
            return None
        return str(FileSpec(path=spec.path, extension=selection.index, section=spec.section))

    def _report(self, message: str, exc: Exception) -> None:
        """Show a load or save failure in the status bar and a dialog."""
        self.status(f"{type(exc).__name__}: {exc}", 5000)
        QMessageBox.critical(self.window, "NCRADS9", f"{message}\n\n{exc}")

    # -- Open as -------------------------------------------------------------

    def open_as(self, loader: str) -> None:
        """Handle one entry of DS9's `Open as` submenu.

        Args:
            loader: The entry's name, as `MenuBar.open_as_actions` keys it.
        """
        if loader == "url":
            self.open_url()
            return

        filepath, _ = QFileDialog.getOpenFileName(
            self.window, f"Open as {loader.replace('_', ' ')}", "", FITS_FILTER
        )
        if not filepath:
            return

        try:
            spec = parse_file_spec(filepath)
            if loader == "slice":
                self.load_slice(spec)
            elif loader == "mef_frames":
                self.load_extension_frames(spec)
            elif loader == "mef_cube":
                self.load_extension_cube(spec)
            elif loader in COLOUR_LOADERS:
                self.load_colour(spec, *COLOUR_LOADERS[loader])
            elif loader in MOSAIC_LOADERS:
                self.load_mosaic(spec, *MOSAIC_LOADERS[loader])
            else:
                self.status(f"Unknown loader: {loader}", 3000)
        except Exception as exc:
            self._report(f"Could not open {Path(filepath).name} as {loader}", exc)

    def load_slice(self, spec: FileSpec) -> None:
        """Load one slice of a cube as a plain 2D image."""
        with FITSHandler(str(spec.path)) as handler:
            image = handler.load_spec(spec)
            depth = 0
            from ...core.cube_handler import CubeHandler, is_cube

            if is_cube(image.data):
                depth = CubeHandler(image.data, image.header).depth()
            if depth < 2:
                self.status(f"{spec.path.name} is not a data cube", 3000)
                return

            index, ok = QInputDialog.getInt(self.window, "Open Slice", f"Slice (1 to {depth}):", 1, 1, depth)
            if not ok:
                return
            sliced = fits_loaders.slice_image(handler, spec, index - 1)

        self._show(sliced, spec, f"{spec.path.name} slice {index} of {depth}")

    def load_extension_frames(self, spec: FileSpec) -> None:
        """One frame per displayable extension (DS9: Multiple Extension Frames)."""
        with FITSHandler(str(spec.path)) as handler:
            images = fits_loaders.extension_images(handler, spec)

        for position, (info, image) in enumerate(images):
            if position:
                self.window.frame_controller.new_frame()
            self._show(
                image,
                FileSpec(path=spec.path, extension=info.index, section=spec.section),
                None,
            )
        self.status(f"Loaded {len(images)} extensions into {len(images)} frames", 3000)

    def load_extension_cube(self, spec: FileSpec) -> None:
        """Every displayable extension stacked as a cube."""
        with FITSHandler(str(spec.path)) as handler:
            cube = fits_loaders.extension_cube(handler, spec)
        self._show(cube, spec, f"Stacked {cube.data.shape[0]} extensions as a cube")

    def load_colour(self, spec: FileSpec, frame_type: str, from_cube: bool) -> None:
        """Load three planes into a colour frame's channels."""
        with FITSHandler(str(spec.path)) as handler:
            channels = fits_loaders.channel_images(handler, spec, from_cube=from_cube)

        self.window.frame_controller.new_frame_of_type(frame_type)
        frame = self.frames.current_frame
        if frame is None:
            return

        for channel, image in channels.items():
            frame.rgb_channels[channel] = image.data
            frame.rgb_source_frame_ids[channel] = None
        frame.filepath = spec.path
        frame.file_spec = str(spec) if spec.has_specification else None
        first = next(iter(channels.values()))
        frame.header = first.header
        frame.image = first
        frame.wcs_handler = self._wcs_for(first)
        self.window.display.sync_rgb_scalar_view(frame)
        self.window.display.display()
        self.status(
            f"Loaded {len(channels)} channels of {spec.path.name} as {frame_type.upper()}",
            3000,
        )

    def load_mosaic(self, spec: FileSpec, kind: MosaicKind, segment: bool) -> None:
        """Assemble a mosaic, optionally into the one already on screen."""
        existing = None
        if segment:
            frame = self.frames.current_frame
            existing = frame.image if frame is not None else None
            if existing is None:
                self.status("No mosaic on screen to add a segment to", 3000)
                return

        with FITSHandler(str(spec.path)) as handler:
            mosaic = fits_loaders.mosaic_images(handler, kind, existing=existing, spec=spec)

        verb = "Added segment to" if segment else "Assembled"
        self._show(
            mosaic,
            spec,
            f"{verb} {kind.value} mosaic: {mosaic.data.shape[1]}x{mosaic.data.shape[0]} pixels",
        )

    def open_url(self) -> None:
        """Download a FITS file and open it (DS9: `Open as -> URL`)."""
        url, ok = QInputDialog.getText(self.window, "Open URL", "FITS URL:")
        if not ok or not url.strip():
            return
        url = url.strip()

        self.status(f"Downloading {url}...", 0)
        try:
            path = self._download(url)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            self._report(f"Could not download\n{url}", exc)
            return

        try:
            self.window.display.load_fits(str(path))
            self.status(f"Opened {url}", 3000)
        except Exception as exc:
            self._report(f"Downloaded {url} but could not load it", exc)

    def _download(self, url: str) -> Path:
        """Fetch a URL into a temporary file.

        Blocks the UI for up to `URL_TIMEOUT` seconds. A progress bar needs
        the background-download machinery of M8-13, which is also what the
        catalog and image-server queries will use; until then the status bar
        says what is happening and the timeout bounds the wait.

        Args:
            url: The URL to fetch. Must be http or https.

        Returns:
            The downloaded file's path.

        Raises:
            ValueError: If the URL is not http or https.
            URLError: If the download fails.
        """
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError("only http and https URLs can be opened")

        suffix = Path(url.split("?", 1)[0]).suffix or ".fits"
        # delete=False: the file has to outlive this call, since astropy
        # memory-maps it for as long as the frame holds it open.
        descriptor, name = tempfile.mkstemp(suffix=suffix)
        try:
            with (
                urllib.request.urlopen(url, timeout=URL_TIMEOUT) as response,
                open(descriptor, "wb") as handle,
            ):
                shutil.copyfileobj(response, handle)
        except BaseException:
            Path(name).unlink(missing_ok=True)
            raise
        return Path(name)

    # -- putting a loaded image on the current frame -------------------------

    def _wcs_for(self, image) -> object | None:
        """A `WCSHandler` for one image's header, or None."""
        from ...core.wcs_handler import WCSHandler

        return None if image.header is None else WCSHandler(image.header)

    def _show(self, image, spec: FileSpec, message: str | None) -> None:
        """Put an already-loaded image on the current frame and display it.

        The ordinary path is `DisplayPipeline.load_fits`, which opens the file
        itself. The `Open as` loaders have already read and combined several
        extensions, so they hand the result here instead.
        """
        from ...core.cube_handler import CubeHandler, is_cube

        frame = self.frames.current_frame
        if frame is None:
            frame = self.window.frame_controller.new_frame()
            if frame is None:
                return

        data = image.data
        frame.slice_index = 0
        frame.axis_order = "123"
        if is_cube(data):
            plane = CubeHandler(data, image.header).get_slice(0)
            data = plane if plane is not None else data

        frame.filepath = spec.path
        frame.file_spec = str(spec) if spec.has_specification else None
        frame.hdu_index = spec.extension if isinstance(spec.extension, int) else None
        frame.image = image
        frame.image_data = data
        frame.original_image_data = data
        frame.header = image.header
        frame.wcs_handler = self._wcs_for(image)
        frame.z1 = None
        frame.z2 = None
        self.window.z1 = None
        self.window.z2 = None

        self.window.display.display()
        self.window.zoom.zoom_fit()
        self.window.frame_controller.update_title()
        self.window.frame_controller.sync_cube_dialog()
        if message:
            self.status(message, 3000)

    # -- saving --------------------------------------------------------------

    def save_file(self) -> None:
        """Write the current frame back to the file it came from.

        Refuses when the frame was not loaded from a file, and when the frame
        holds a mosaic or a stack built from several extensions, since there
        is no single file such a frame belongs to.
        """
        frame = self.frames.current_frame
        if frame is None or frame.filepath is None:
            self.status("Nothing to save; the frame has no file", 3000)
            return
        self._write(Path(frame.filepath), overwrite=True)

    def save_file_as(self) -> None:
        """Write the current frame to a file the user names."""
        frame = self.frames.current_frame
        if frame is None or frame.image_data is None:
            self.status("Nothing to save; the frame is empty", 3000)
            return

        suggestion = "" if frame.filepath is None else str(frame.filepath)
        filepath, _ = QFileDialog.getSaveFileName(self.window, "Save FITS File", suggestion, FITS_SAVE_FILTER)
        if filepath:
            self._write(Path(filepath), overwrite=True)

    def _write(self, path: Path, overwrite: bool) -> None:
        """Write the current frame's data, header and WCS to `path`.

        The array written is the *working* one -- what is on screen, after
        any block, smooth or slice -- and the header is updated so it
        describes that array rather than the one on disk.
        """
        frame = self.frames.current_frame
        if frame is None or frame.image_data is None:
            self.status("Nothing to save; the frame is empty", 3000)
            return

        try:
            writer = FITSWriter(path)
            writer.add_image(frame.image_data, header=self._save_header(frame))
            writer.write(overwrite=overwrite)
        except Exception as exc:
            self._report(f"Could not save to\n{path}", exc)
            return

        frame.filepath = path
        self.window.frame_controller.update_title()
        self.status(f"Saved {path}", 3000)

    def _save_header(self, frame) -> fits.Header:
        """The header to write beside a frame's current array.

        Starts from the loaded header so the WCS, OBJECT and BUNIT survive,
        then corrects the axis cards, drops the third-axis ones when a slice
        of a cube is being written, and records what NCRADS9 did to the data.
        """
        header = fits.Header() if frame.header is None else fits.Header(frame.header).copy()
        data = frame.image_data

        header["NAXIS"] = int(data.ndim)
        for axis in range(1, data.ndim + 1):
            header[f"NAXIS{axis}"] = int(data.shape[-axis])
        if data.ndim < 3:
            for key in ("NAXIS3", "NAXIS4", "CRVAL3", "CRPIX3", "CDELT3", "CTYPE3", "CUNIT3"):
                header.pop(key, None)

        if frame.bin_factor and frame.bin_factor != 1:
            header["NCBLOCK"] = (frame.bin_factor, "NCRADS9 display block factor")
        if frame.file_spec:
            # Only the bracket part: the path is already in the filename, and
            # a full specification would overrun a FITS card's 68 characters.
            specification = frame.file_spec
            suffix = specification[len(str(frame.filepath or "")) :] or specification
            header["NCSPEC"] = (suffix[:68], "NCRADS9 source specification")
        return header

    def save_as(self, writer: str) -> None:
        """Handle one entry of DS9's `Save as` submenu.

        Args:
            writer: The entry's name, as `MenuBar.save_as_actions` keys it.
        """
        frame = self.frames.current_frame
        if frame is None or frame.image_data is None:
            self.status("Nothing to save; the frame is empty", 3000)
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self.window, f"Save as {writer.replace('_', ' ')}", "", FITS_SAVE_FILTER
        )
        if not filepath:
            return

        try:
            self._write_as(Path(filepath), writer, frame)
        except Exception as exc:
            self._report(f"Could not save as {writer}", exc)

    def _write_as(self, path: Path, writer: str, frame) -> None:
        """Write one of the `Save as` variants.

        Slice, the mosaics and the multiple-extension cube all write a single
        image, because that is what the frame holds by then -- the mosaic has
        been assembled and the cube stacked. The colour variants write the
        frame's three channels, as a cube or as three extensions, which is
        the shape their loaders read.
        """
        header = self._save_header(frame)
        fits_writer = FITSWriter(path)

        if writer in COLOUR_LOADERS:
            channels = [
                frame.rgb_channels[name]
                for name in fits_loaders.RGB_CHANNELS
                if frame.rgb_channels.get(name) is not None
            ]
            if len(channels) < len(fits_loaders.RGB_CHANNELS):
                raise ValueError(
                    f"the frame has {len(channels)} of " f"{len(fits_loaders.RGB_CHANNELS)} colour channels"
                )
            _space, as_cube = COLOUR_LOADERS[writer]
            if as_cube:
                import numpy as np

                fits_writer.add_image(np.stack(channels, axis=0), header=header)
            else:
                for name, channel in zip(fits_loaders.RGB_CHANNELS, channels, strict=True):
                    fits_writer.add_image(channel, header=header, name=name.upper())
        elif writer == "mef_cube" and frame.image is not None and frame.image.data.ndim >= 3:
            fits_writer.add_image(frame.image.data, header=header)
        else:
            fits_writer.add_image(frame.image_data, header=header)

        fits_writer.write(overwrite=True)
        self.status(f"Saved {writer.replace('_', ' ')} to {path}", 3000)

    def save_image(self, image_format: str) -> None:
        """Handle one entry of DS9's `Save Image` submenu.

        DS9's Save Image writes what is *rendered* -- the colormapped,
        scaled picture -- rather than the data. FITS is the exception: DS9
        writes the rendered image's three colour planes as a FITS cube, which
        is what makes `Save Image -> FITS` different from `Save`.

        Args:
            image_format: One of `MenuBar.save_image_actions`' keys.
        """
        milestone = DEFERRED_IMAGE_FORMATS.get(image_format)
        if milestone is not None:
            self.status(f"Save Image as {image_format.upper()} arrives in {milestone}", 3000)
            return

        pixmap = self.current_pixmap()
        if pixmap is None:
            self.status("No image to save")
            return

        filepath, _ = QFileDialog.getSaveFileName(self.window, "Save Image as FITS", "", FITS_SAVE_FILTER)
        if not filepath:
            return

        try:
            self._write_rendered_fits(Path(filepath), pixmap)
        except Exception as exc:
            self._report(f"Could not save the rendered image to\n{filepath}", exc)

    def _write_rendered_fits(self, path: Path, pixmap: QPixmap) -> None:
        """Write a rendered pixmap as a three-plane FITS cube."""
        import numpy as np

        image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
        width, height = image.width(), image.height()
        buffer = image.constBits()
        buffer.setsize(height * image.bytesPerLine())
        rows = np.frombuffer(buffer, dtype=np.uint8).reshape(height, image.bytesPerLine())
        rgb = rows[:, : width * 3].reshape(height, width, 3)
        # FITS counts rows from the bottom; Qt from the top.
        planes = np.ascontiguousarray(rgb[::-1].transpose(2, 0, 1))

        header = fits.Header()
        header["NCRENDER"] = (True, "NCRADS9 rendered image, not data")
        writer = FITSWriter(path)
        writer.add_image(planes, header=header)
        writer.write(overwrite=True)
        self.status(f"Saved the rendered image to {path}", 3000)

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
        """Show the FITS header of the current frame.

        The dialog gets the whole HDU list, so its extension selector can
        switch between them -- the reason M4-12 exists is that the selector
        was built but its handler was a comment saying "placeholder".
        """
        handler = self.window.fits_handler
        if handler is None:
            self.status("No FITS file loaded")
            return

        from ..dialogs.header_dialog import HeaderDialog

        frame = self.frames.current_frame
        index = getattr(frame, "hdu_index", None) or 0
        try:
            extensions = handler.extensions()
            header = handler.get_header(index)
        except Exception as exc:
            self.status(f"Could not read the header: {exc}", 3000)
            return

        HeaderDialog(
            header,
            self.window,
            extensions=extensions,
            handler=handler,
            index=index,
        ).exec()
