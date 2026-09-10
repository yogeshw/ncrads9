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
from dataclasses import replace
from pathlib import Path

import numpy as np
from astropy.io import fits
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from ... import printing
from ...colormaps.colormap import Colormap
from ...core import fits_loaders
from ...core.file_spec import FileSpec
from ...core.file_spec import parse as parse_file_spec
from ...core.fits_handler import FITSHandler
from ...core.mosaic import MosaicKind
from ...io import array_reader, envi_writer, movie, nrrd_writer, raster
from ...io.envi_reader import ENVIReader
from ...io.fits_writer import FITSWriter
from ...io.nrrd_reader import NRRDReader
from ...rendering.scale_algorithms import apply_scale, compute_zscale_limits
from ..dialogs.array_dialog import ArrayDialog
from ..dialogs.movie_dialog import MovieDialog
from ..dialogs.open_dialog import HDUChoice, OpenDialog
from ..dialogs.page_setup_dialog import PageSetupDialog
from ..dialogs.print_dialog import PrintDialog
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

#: `Save Image` formats nothing writes yet, and the milestone that does.
#: Empty since M9-18 gave EPS the PostScript driver; kept because the
#: mechanism is how a format says which milestone it is waiting for.
DEFERRED_IMAGE_FORMATS: dict[str, str] = {}

#: What the Import and Export cascades' colour entries make of a frame.
COLOUR_ARRAYS: dict[str, str] = {
    "rgb_array": "rgb",
    "hsv_array": "hsv",
    "hls_array": "hls",
}

#: How long to wait for a URL before giving up, in seconds.
URL_TIMEOUT = 30


class FileController(Controller):
    """Owns the File menu."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, as every controller takes.
        """
        super().__init__(window)
        #: What the last print was set up as, so the next one need not be.
        self.print_settings = printing.PrintSettings()

    def connect(self) -> None:
        """Wire the File menu."""
        self.menu.action_open.triggered.connect(self.open_file)
        self.menu.action_save.triggered.connect(self.save_file)
        self.menu.action_save_as.triggered.connect(self.save_file_as)
        self.menu.action_create_movie.triggered.connect(lambda _checked=False: self.create_movie())
        self.menu.action_console.triggered.connect(lambda _checked=False: self.show_console())
        self.menu.action_run_script.triggered.connect(lambda _checked=False: self.run_script())
        for name, action in self.menu.preserve_actions.items():
            action.toggled.connect(lambda checked, key=name: self.set_preserve(key, checked))
        for name, action in self.menu.import_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.import_file(key))
        for name, action in self.menu.export_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.export_file(key))
        self.menu.action_print.triggered.connect(lambda _checked=False: self.print_image())
        self.menu.action_page_setup.triggered.connect(lambda _checked=False: self.show_page_setup())
        self.menu.action_exit.triggered.connect(self.window.close)

        for name, action in self.menu.open_as_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.open_as(key))
        for name, action in self.menu.save_as_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.save_as(key))
        for name, action in self.menu.save_image_actions.items():
            action.triggered.connect(lambda _checked=False, key=name: self.save_image(key))

    # -- the Python console (M9-34) ------------------------------------------

    def show_console(self):
        """DS9's TCL console, in the language this application is made of."""
        from ..dialogs.console_dialog import ConsoleDialog

        existing = getattr(self, "_console", None)
        if existing is not None:
            existing.raise_()
            existing.activateWindow()
            return existing

        console = ConsoleDialog(self.window, self.window)
        console.finished.connect(lambda _result: setattr(self, "_console", None))
        self._console = console
        console.show()
        return console

    def run_script(self, path: str | None = None) -> bool:
        """Run a Python script, where DS9 sources a TCL one.

        The console is opened to run it, so what it printed and anything it
        raised can be read -- a script that failed silently would be worse
        than no script at all.

        Args:
            path: The script, or None to ask.

        Returns:
            Whether a script was run.
        """
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self.window, "Run Python Script", "", "Python scripts (*.py);;All files (*)"
            )
        if not path:
            return False

        console = self.show_console()
        console.run_script(str(path))
        self.status(f"Ran {Path(path).name}", 3000)
        return True

    # -- Preserve During Load (M9-17) ----------------------------------------

    def preserving(self, what: str) -> bool:
        """Whether one thing survives a load into the same frame."""
        return bool(self.window._preserve.get(what, False))

    def set_preserve(self, what: str, enabled: bool) -> None:
        """Turn one Preserve During Load entry on or off."""
        self.window._preserve[what] = bool(enabled)
        action = self.menu.preserve_actions.get(what)
        if action is not None and action.isChecked() != bool(enabled):
            action.setChecked(bool(enabled))
        self.status(f"Preserve {what} during load: {'on' if enabled else 'off'}", 2000)

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

        if frame.block_factor and frame.block_factor != 1:
            header["NCBLOCK"] = (frame.block_factor, "NCRADS9 display block factor")
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

        if image_format in raster.FORMATS:
            self._save_image_raster(image_format, pixmap)
            return
        if image_format == "eps":
            self._save_eps(pixmap)
            return

        filepath, _ = QFileDialog.getSaveFileName(self.window, "Save Image as FITS", "", FITS_SAVE_FILTER)
        if not filepath:
            return

        try:
            self._write_rendered_fits(Path(filepath), pixmap)
        except Exception as exc:
            self._report(f"Could not save the rendered image to\n{filepath}", exc)

    def _save_image_raster(self, image_format: str, pixmap: QPixmap, path: str | None = None) -> bool:
        """Write the rendered view as one of DS9's four raster formats."""
        if path is None:
            path, _ = QFileDialog.getSaveFileName(
                self.window,
                f"Save Image as {image_format.upper()}",
                "",
                raster.file_filter(image_format),
            )
        if not path:
            return False
        try:
            raster.write(path, self._pixmap_rgb(pixmap), image_format)
        except Exception as exc:
            self._report(f"Could not save the rendered image to\n{path}", exc)
            return False
        self.status(f"Saved the rendered image to {Path(path).name}", 3000)
        return True

    @staticmethod
    def _pixmap_rgb(pixmap: QPixmap) -> np.ndarray:
        """A pixmap as a (height, width, 3) byte array, rows from the bottom.

        `constBits` borrows Qt's own memory, which goes when the QImage
        does, so the rows are copied out before that can happen.
        """
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
        width, height = image.width(), image.height()
        buffer = image.constBits()
        buffer.setsize(height * image.bytesPerLine())
        rows = np.frombuffer(buffer, dtype=np.uint8).reshape(height, image.bytesPerLine()).copy()
        return rows[:, : width * 3].reshape(height, width, 3)[::-1]

    # -- Import and Export (M9-13, M9-14) ------------------------------------------

    def import_file(self, name: str, path: str | None = None) -> bool:
        """One entry of DS9's Import cascade.

        Import reads a file *as data*: its pixels become the frame's array,
        so they can be scaled, measured and have regions drawn on them.

        Args:
            name: One of `MenuBar.import_actions`' keys.
            path: The file, or None to ask.

        Returns:
            Whether anything was loaded.
        """
        base = name.removeprefix("slice_")
        if path is None:
            path = self._ask_import(base)
        if not path:
            return False

        try:
            data, label = self._read_import(base, path)
        except Exception as exc:
            self._report(f"Could not import\n{path}", exc)
            return False
        if data is None:
            return False

        frame_type = COLOUR_ARRAYS.get(base)
        if frame_type is not None:
            self.window.frame_controller.new_frame_of_type(frame_type)
        loaded = self.window.display.load_array(data, name=label, frame_type=frame_type)
        return loaded is not None

    def _ask_import(self, base: str) -> str:
        """The Open dialog for one import format."""
        if base in raster.FORMATS:
            chosen, _ = QFileDialog.getOpenFileName(
                self.window, f"Import {base.upper()}", "", raster.file_filter(base)
            )
            return chosen
        filters = {
            "array": "Array files (*.arr *.raw *.dat *.bin);;All files (*)",
            "rgb_array": "Array files (*.arr *.raw *.dat *.bin);;All files (*)",
            "hsv_array": "Array files (*.arr *.raw *.dat *.bin);;All files (*)",
            "hls_array": "Array files (*.arr *.raw *.dat *.bin);;All files (*)",
            "nrrd": "NRRD files (*.nrrd *.nhdr);;All files (*)",
            "envi": "ENVI files (*.hdr *.img *.dat *.raw);;All files (*)",
        }
        chosen, _ = QFileDialog.getOpenFileName(
            self.window, f"Import {base}", "", filters.get(base, "All files (*)")
        )
        return chosen

    def _read_import(self, base: str, path: str) -> tuple[np.ndarray | None, str]:
        """Read one import format. Returns (data, what to call it)."""
        if base in raster.FORMATS:
            colour = False
            return (raster.read(path, colour=colour), Path(path).name)

        if base == "nrrd":
            return (NRRDReader(path).read_data(), Path(path).name)
        if base == "envi":
            return (ENVIReader(path).read_data(), Path(path).name)

        # An array of any kind: the dimensions have to come from somewhere.
        target, embedded = array_reader.split_spec(path)
        spec = None
        if embedded:
            spec = array_reader.parse_spec(embedded)
        else:
            spec = array_reader.environment_spec()
            chosen = ArrayDialog(spec, self.window).choose()
            if chosen is None:
                return (None, "")
            spec = chosen
        data = array_reader.read(target, spec)
        if base in COLOUR_ARRAYS and data.ndim == 3 and data.shape[0] != 3:
            self.status("A colour array needs three planes", 3500)
            return (None, "")
        return (data, target.name)

    def export_file(self, name: str, path: str | None = None) -> bool:
        """One entry of DS9's Export cascade.

        Export writes the frame *as* its format: the data itself for the
        array kinds, and the rendered picture for the raster kinds, because
        a GIF has no room for a stretch.

        Args:
            name: One of `MenuBar.export_actions`' keys.
            path: The file, or None to ask.

        Returns:
            Whether anything was written.
        """
        frame = self.frame
        data = getattr(frame, "image_data", None) if frame is not None else None
        if data is None:
            self.status("No image to export")
            return False

        if name in raster.FORMATS:
            pixmap = self.current_pixmap()
            if pixmap is None:
                self.status("No image to export")
                return False
            if path is None:
                path, _ = QFileDialog.getSaveFileName(
                    self.window, f"Export {name.upper()}", "", raster.file_filter(name)
                )
            if not path:
                return False
            try:
                raster.write(path, self._pixmap_rgb(pixmap), name)
            except Exception as exc:
                self._report(f"Could not export to\n{path}", exc)
                return False
            self.status(f"Exported {name.upper()} to {Path(path).name}", 3000)
            return True

        if path is None:
            path, _ = QFileDialog.getSaveFileName(
                self.window, f"Export {name.replace('_', ' ')}", "", "All files (*)"
            )
        if not path:
            return False

        big_endian = True
        if name in ("array", "nrrd", "envi") or name in COLOUR_ARRAYS:
            dialog = ArrayDialog(None, self.window, exporting=True)
            chosen = dialog.choose()
            if chosen is None:
                return False
            big_endian = chosen.big_endian

        try:
            self._write_export(name, path, data, big_endian)
        except Exception as exc:
            self._report(f"Could not export to\n{path}", exc)
            return False
        return True

    def _write_export(self, name: str, path: str, data, big_endian: bool) -> None:
        """Write one of the data export formats."""
        if name == "nrrd":
            nrrd_writer.write(path, data, big_endian=big_endian)
            self.status(f"Exported NRRD to {Path(path).name}", 3000)
            return
        if name == "envi":
            _target, header = envi_writer.write(path, data, big_endian=big_endian)
            self.status(f"Exported ENVI to {Path(path).name} and {header.name}", 4000)
            return

        if name in COLOUR_ARRAYS:
            data = self._colour_planes(data)
        spec = array_reader.write(path, data, big_endian=big_endian)
        # A raw array carries no header, so the only way the user gets the
        # numbers back is if we tell them now.
        self.status(
            f"Exported array to {Path(path).name} -- read it back with "
            f"[xdim={spec.xdim},ydim={spec.ydim},zdim={spec.zdim},bitpix={spec.bitpix}]",
            8000,
        )

    def _colour_planes(self, data):
        """The three planes a colour array export writes.

        An RGB frame has its own three channels; any other frame has one
        plane, which goes out three times so the file is still a valid
        colour array rather than a silent single-channel one.
        """
        frame = self.frame
        if frame is not None and frame.frame_type in ("rgb", "hsv", "hls"):
            channels = [frame.rgb_channels.get(channel) for channel in ("red", "green", "blue")]
            if all(channel is not None for channel in channels):
                return np.stack([np.asarray(channel) for channel in channels])
        return np.repeat(np.asarray(data)[None, :, :], 3, axis=0)

    def _write_rendered_fits(self, path: Path, pixmap: QPixmap) -> None:
        """Write a rendered pixmap as a three-plane FITS cube."""
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

    # -- Create Movie (M9-15) ------------------------------------------------------

    def create_movie(self, path: str | None = None, settings: dict | None = None) -> bool:
        """DS9's File -> Create Movie.

        Args:
            path: The file to write, or None to ask.
            settings: What to make, as `MovieDialog.settings` returns.
                None asks.

        Returns:
            Whether a movie was written.
        """
        frame = self.frame
        if frame is None or frame.image_data is None:
            self.status("No image to make a movie of")
            return False

        handler = self.window.frame_controller.cube_handler(frame)
        depth = handler.depth(frame.axis_order) if handler is not None else 1

        if settings is None:
            chosen = MovieDialog(self.window, is_cube=depth > 1).choose()
            if chosen is None:
                return False
            settings = chosen

        if settings.get("action") == "3d":
            self.status("A 3D movie needs the 3D frame of M9-21", 3500)
            return False

        images = self._slice_images(depth) if settings.get("action") == "slice" else self._frame_images()
        if not images:
            self.status("Nothing to make a movie of")
            return False

        if path is None:
            kind = settings.get("type", "gif")
            path, _ = QFileDialog.getSaveFileName(
                self.window,
                "Create Movie",
                "",
                (
                    "Animated GIF (*.gif);;All files (*)"
                    if kind == "gif"
                    else "MPEG (*.mpg *.mp4);;All files (*)"
                ),
            )
        if not path:
            return False

        try:
            movie.write(
                path,
                images,
                movie_type=settings.get("type", "gif"),
                transition=settings.get("transition", "blink"),
                delay=int(settings.get("delay", movie.DEFAULT_DELAY)),
            )
        except movie.MovieError as exc:
            self.status(f"Could not make the movie: {exc}", 5000)
            return False
        except Exception as exc:
            self._report(f"Could not write the movie to\n{path}", exc)
            return False

        self.status(f"Wrote {len(images)} frame(s) to {Path(path).name}", 4000)
        return True

    def _frame_images(self) -> list:
        """One rendered image per active frame, for a frames movie."""
        rendered = []
        for index in self.window.frame_controller.active_indices():
            frame = self.frames.frames[index]
            image = self.window.display.render_frame_rgb(frame)
            if image is not None:
                rendered.append(image)
        return movie.frames_of(rendered)

    def _slice_images(self, depth: int) -> list:
        """One rendered image per slice of the current cube.

        The slice on screen is put back afterwards: making a movie should
        not move the view.
        """
        controller = self.window.frame_controller
        frame = self.frame
        if frame is None:
            return []
        was = frame.slice_index

        rendered = []
        try:
            for index in range(max(1, depth)):
                controller.set_slice(index)
                image = self.window.display.render_frame_rgb(self.frame)
                if image is not None:
                    rendered.append(image)
        finally:
            controller.set_slice(was)
        return movie.frames_of(rendered)

    def print_image(self, settings=None) -> bool:
        """DS9's File -> Print, through the PostScript driver.

        Not a screen capture: the image is resampled to the chosen
        resolution and written as PostScript at the chosen level, with the
        graphics as PostScript elements -- which is what makes a printed
        figure sharper than the screen it came from.

        Args:
            settings: What to print, as `PrintDialog.settings` returns.
                None asks.

        Returns:
            Whether anything was printed.
        """
        pixmap = self.current_pixmap()
        if pixmap is None:
            self.status("No image to print")
            return False

        if settings is None:
            chosen = PrintDialog(self.print_settings, self.window).choose()
            if chosen is None:
                return False
            settings = chosen
        # Remembered, so the next print does not have to be set up again.
        self.print_settings = settings

        rgb = self._pixmap_rgb(pixmap)
        title = self.window.windowTitle()
        try:
            if settings.destination is printing.Destination.PRINTER:
                printing.to_command(rgb, settings, title)
                self.status(f"Sent to {settings.command}", 3000)
            else:
                written = printing.to_file(settings.filename, rgb, settings, title)
                self.status(f"Printed to {written.name}", 3000)
        except printing.PrintError as exc:
            self.status(f"Print failed: {exc}", 5000)
            return False
        return True

    def show_page_setup(self) -> bool:
        """DS9's File -> Page Setup.

        Returns:
            Whether the page was changed.
        """
        chosen = PageSetupDialog(self.print_settings.page, self.window).choose()
        if chosen is None:
            return False
        self.print_settings = replace(self.print_settings, page=chosen)
        self.status(
            f"Page: {chosen.paper_size.value} {chosen.orientation.value} at {chosen.scale:g}%",
            3000,
        )
        return True

    def _save_eps(self, pixmap: QPixmap, path: str | None = None) -> bool:
        """DS9's Save Image -> EPS: one figure, through the same driver."""
        if path is None:
            path, _ = QFileDialog.getSaveFileName(
                self.window, "Save Image as EPS", "", "EPS files (*.eps);;All files (*)"
            )
        if not path:
            return False
        settings = replace(self.print_settings, output_format=printing.OutputFormat.EPS)
        try:
            printing.to_file(path, self._pixmap_rgb(pixmap), settings, self.window.windowTitle())
        except printing.PrintError as exc:
            self.status(f"Could not write the EPS: {exc}", 5000)
            return False
        self.status(f"Saved the rendered image to {Path(path).name}", 3000)
        return True

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
