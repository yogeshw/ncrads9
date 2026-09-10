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
The display pipeline: FITS data to pixels on screen.

Not a menu controller -- nothing in DS9's menu bar corresponds to it -- but it
had to come out of MainWindow for the same reason the controllers did, and
M2-16's size target is unreachable while 600 lines of rendering live there.

The pipeline is:

    data -> block -> mask -> smooth -> scale -> clip -> colormap -> composite
         -> display transform -> paint

with two backends. The CPU path renders a whole QPixmap and lets a QScrollArea
move it. The GPU path uploads only the tiles the viewport covers, so it
provides a tile callback instead of an image and never materialises the full
frame; that is what makes large images usable, and it is why the two paths
diverge as often as they do here.

An RGB, HSV or HLS frame runs the scale step per channel -- each channel keeps
its own algorithm, limits, contrast and bias -- and the frame's own `compose`
combines them.

Preview panels (panner, magnifier) get a strided downsample rather than the
full array, cached per frame, because they redraw on every pan.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtGui import QColor, QImage, QPixmap

from ..colormaps.colormap import Colormap
from ..core.cube_handler import CubeHandler, is_cube
from ..core.file_spec import parse as parse_file_spec
from ..core.fits_handler import FITSHandler, HDUKind
from ..core.wcs_handler import WCSHandler
from ..frames.crop import blank_outside
from ..frames.frame import Frame
from ..frames.tile_layout import TileLayout
from ..regions.fits_regions import has_region_extension, load_from_file
from ..rendering.block import block_image
from ..rendering.rgb_compositor import compose_rgb
from ..rendering.scale_algorithms import ScaleAlgorithm, apply_scale
from .view_transform import transform_image_array
from .widgets.colorbar_widget import ColorbarEntry

#: DS9's default blank/Inf/NaN colour (`pds9(nan)` in `ds9.tcl:157`).
DEFAULT_NAN_COLOR = "#ffffff"

#: The channels of a colour frame, in the order the colorbar shows them.
RGB_CHANNEL_ORDER: tuple[str, str, str] = ("red", "green", "blue")

#: A ramp per channel, so an RGB frame's three bars read as red, green and
#: blue rather than as three identical greys.
CHANNEL_RAMPS: dict[str, NDArray[np.floating]] = {
    channel: np.stack(
        [np.linspace(0.0, 1.0, 256) if index == position else np.zeros(256) for index in range(3)],
        axis=1,
    )
    for position, channel in enumerate(RGB_CHANNEL_ORDER)
}


class DisplayPipeline:
    """Turns the current frame's data into what the viewer shows."""

    def __init__(self, window) -> None:
        """
        Args:
            window: The main window, for the viewer, frames and view state.
        """
        self.window = window

    # -- shared accessors, mirroring Controller ------------------------------

    @property
    def frames(self):
        """The frame collection."""
        return self.window.frame_manager

    @property
    def frame(self) -> Frame | None:
        """The current frame."""
        return self.window.frame_manager.current_frame

    @property
    def viewer(self):
        """The active image viewer."""
        return self.window.image_viewer

    @property
    def status_bar(self):
        """The status bar."""
        return self.window.status_bar

    def status(self, message: str, msecs: int = 2000) -> None:
        """Show a transient status-bar message."""
        self.window.statusBar().showMessage(message, msecs)

    @staticmethod
    def channel_names() -> tuple[str, str, str]:
        return ("red", "green", "blue")

    def active_channel_data(self, frame: Frame) -> NDArray[np.floating] | None:
        """Return currently selected RGB channel data, or first available channel."""
        channel = frame.rgb_current_channel if frame.rgb_current_channel in frame.rgb_channels else "red"
        data = frame.rgb_channels.get(channel)
        if data is not None:
            return data
        for name in self.channel_names():
            channel_data = frame.rgb_channels.get(name)
            if channel_data is not None:
                return channel_data
        return None

    def sync_rgb_scalar_view(self, frame: Frame) -> None:
        """Keep scalar frame data in sync with selected RGB channel for analysis/status."""
        active = self.active_channel_data(frame)
        frame.image_data = active
        frame.original_image_data = active

    def channel_view_settings(
        self,
        frame: Frame,
        channel: str,
    ) -> tuple[ScaleAlgorithm, float | None, float | None, float, float]:
        """Return per-channel RGB display settings."""
        scale = frame.rgb_channel_scale.get(channel, ScaleAlgorithm.LINEAR)
        z1 = frame.rgb_channel_z1.get(channel)
        z2 = frame.rgb_channel_z2.get(channel)
        contrast = max(float(frame.rgb_channel_contrast.get(channel, 1.0)), 0.1)
        brightness = max(-1.0, min(float(frame.rgb_channel_brightness.get(channel, 0.0)), 1.0))
        return scale, z1, z2, contrast, brightness

    def scale_channel(
        self,
        frame: Frame,
        channel: str,
        data: NDArray[np.floating],
    ) -> NDArray[np.float32]:
        """Apply per-channel limits/contrast/brightness/scale and return [0,1] channel."""
        scale, z1, z2, contrast, brightness = self.channel_view_settings(frame, channel)
        if z1 is None or z2 is None:
            z1, z2 = self.window.scale.compute_limits(data)
        range_val = max(float(z2 - z1), 1e-6)
        center = (z1 + z2) / 2.0
        new_range = range_val / contrast
        adjusted_z1 = center - new_range / 2.0 + brightness * range_val
        adjusted_z2 = center + new_range / 2.0 + brightness * range_val
        scaled = apply_scale(data, scale, vmin=adjusted_z1, vmax=adjusted_z2)
        return np.clip(scaled.astype(np.float32), 0.0, 1.0)

    def compose_rgb(self, frame: Frame) -> NDArray[np.uint8] | None:
        """Compose display RGB image for an RGB frame."""
        channels = {
            name: frame.rgb_channels.get(name)
            for name in self.channel_names()
            if frame.rgb_channels.get(name) is not None
        }
        if not channels:
            return None

        base_shape = next(iter(channels.values())).shape

        # Scale each channel with its own algorithm and limits, then let the
        # frame combine them: RGBFrame stacks, HSVFrame and HLSFrame convert
        # from their colour space. Frames created before the typed subclasses
        # existed, and plain Frames carrying frame_type="rgb", fall back to a
        # plain stack.
        normalized = {
            name: self.scale_channel(frame, name, data)
            for name, data in ((name, frame.rgb_channels.get(name)) for name in self.channel_names())
            if data is not None and data.shape == base_shape
        }
        compose = getattr(frame, "compose", None)
        composed = (
            compose(normalized, frame.rgb_view)
            if compose is not None
            else compose_rgb(normalized, frame.rgb_view)
        )
        if composed is None:
            return np.zeros((base_shape[0], base_shape[1], 3), dtype=np.uint8)
        return composed

    def apply_rgb_channels_from_sources(
        self,
        frame: Frame,
        channel_to_source_index: dict[str, int | None],
    ) -> None:
        """Assign RGB channels from existing mono frames."""
        for channel, source_index in channel_to_source_index.items():
            if channel not in frame.rgb_channels:
                continue
            if source_index is None:
                frame.rgb_channels[channel] = None
                frame.rgb_source_frame_ids[channel] = None
                continue
            if source_index < 0 or source_index >= len(self.frames.frames):
                continue
            source_frame = self.frames.frames[source_index]
            source_data = source_frame.image_data
            if source_data is None or source_data.ndim != 2:
                continue
            frame.rgb_channels[channel] = np.array(source_data, copy=True)
            frame.rgb_source_frame_ids[channel] = source_frame.frame_id
        self.sync_rgb_scalar_view(frame)

    def sync_view_state_from_channel(self, frame: Frame) -> None:
        """Load current window scale/limits/contrast from active RGB channel."""
        channel = frame.rgb_current_channel if frame.rgb_current_channel in frame.rgb_channels else "red"
        scale, z1, z2, contrast, brightness = self.channel_view_settings(frame, channel)
        self.window.current_scale = scale
        self.window.z1 = z1
        self.window.z2 = z2
        self.window.color.set_contrast_brightness(contrast, brightness)

    def _autoload_regions(self, frame, fits_handler) -> None:
        """Load the file's own regions, if it carries any and we are asked to.

        DS9 opens `fits[REGION]` on every file it loads
        (`ds9/library/fits.tcl:29`), controlled by its Autoload FITS Regions
        preference, which is on by default. A file with no such extension is
        the usual case and costs one name comparison.
        """
        if not bool(self.window.preferences.get("autoload_fits_regions", True)):
            return

        hdu_list = getattr(fits_handler, "hdu_list", None)
        if not has_region_extension(hdu_list):
            return

        try:
            found = load_from_file(hdu_list)
        except Exception:
            # A malformed REGION table must not stop the image loading.
            return
        if not found:
            return

        frame.regions = list(frame.regions) + found
        self.window.region.show_frame_regions(frame)
        self.status(f"Loaded {len(found)} region{'s' if len(found) != 1 else ''} from the file", 3000)

    def load_fits(self, filepath: str) -> None:
        """
        Load a FITS file, or one extension and section of one, into the
        current frame.

        Args:
            filepath: A path, or a DS9 file specification such as
                `foo.fits[SCI][100:200,*]` or `evt.fits[bin=detx,dety]`.
                See `core/file_spec.py` for the grammar.

        Raises:
            FileSpecError: If the specification cannot be parsed.
            FITSLoadError: If nothing in the file can be displayed, or the
                named extension cannot be.
        """
        # Get current frame
        frame = self.frames.current_frame
        if not frame:
            frame = self.frames.new_frame()
            self.window._active_frame_ids.add(frame.frame_id)

        old_handler = frame.fits_handler
        if old_handler is not None:
            try:
                old_handler.close()
            except Exception:
                pass

        # ImageData gathers the array, header, WCS and derived metadata
        # (BITPIX, cached min/max) in one place; the specification says which
        # extension and which subsection of it to gather.
        spec = parse_file_spec(filepath)
        fits_handler = FITSHandler()
        fits_handler.load(str(spec.path))
        info = fits_handler.resolve_extension(spec.extension)
        if info.kind is HDUKind.EVENTS:
            # A table is binned with whatever the Bin menu currently says,
            # and with the columns and filter the specification named if it
            # named any. Those go onto the window rather than being folded in
            # for this load alone, or the next re-bin from the Bin menu would
            # silently drop them.
            if spec.bin is not None:
                self.window.bin_spec = spec.bin
            if spec.filter_expression:
                self.window.bin_settings = replace(self.window.bin_settings, filter=spec.filter_expression)
            image = fits_handler.load_spec_with_bin(spec, self.window.bin_settings)
        else:
            image = fits_handler.load_spec(spec)
        image_data = image.data
        header = image.header
        wcs_handler = WCSHandler(header)

        # Update frame
        frame.filepath = spec.path
        frame.file_spec = str(spec) if spec.has_specification else None
        frame.hdu_index = info.index
        frame.fits_handler = fits_handler
        frame.image = image
        if frame.frame_type == "rgb":
            channel = frame.rgb_current_channel if frame.rgb_current_channel in frame.rgb_channels else "red"
            frame.rgb_channels[channel] = np.array(image_data, copy=True)
            frame.rgb_source_frame_ids[channel] = None
            self.sync_rgb_scalar_view(frame)
        else:
            # A cube is displayed one slice at a time; `frame.image` keeps
            # the whole thing so the Cube dialog can step through it.
            if is_cube(image_data):
                frame.slice_index = 0
                frame.axis_order = "123"
                plane = CubeHandler(image_data, header).get_slice(0)
                image_data = plane if plane is not None else image_data
            frame.image_data = image_data
            frame.original_image_data = image_data
        # A section's block factor is DS9's display blocking, which the frame
        # owns; M5 separates that from bin-table binning properly.
        frame.block_factor = spec.section.block if spec.section is not None else 1
        frame.header = header
        frame.wcs_handler = wcs_handler
        frame.colormap = self.window.current_colormap
        frame.scale = self.window.current_scale
        frame.invert_colormap = self.window.invert_colormap
        frame.z1 = None
        frame.z2 = None

        # Reset display state for new data
        self.window.z1 = None
        self.window.z2 = None
        if hasattr(self.viewer, "reset_contrast_brightness"):
            self.viewer.reset_contrast_brightness()

        # Update window title
        filename = spec.path.name
        if spec.extension is not None:
            filename += f"[{spec.extension}]"
        frame_info = f"Frame {self.frames.current_index + 1}/{self.frames.num_frames}"
        self.window.setWindowTitle(f"NCRADS9 - {filename} [{frame_info}]")

        self._autoload_regions(frame, fits_handler)

        # Display the image
        self.display()

        # Fit image to window on initial load
        self.window.zoom.zoom_fit()

        # Update status bar image info
        shape = image_data.shape
        dtype = image_data.dtype
        self.status_bar.update_image_info(shape[1], shape[0])

        # Update temporary message
        stats_msg = f"Loaded: {shape[1]}x{shape[0]} pixels, {dtype}"
        if is_cube(image.data):
            depth = CubeHandler(image.data, header).depth()
            stats_msg += f", slice 1 of {depth}"
        if info.kind is not HDUKind.IMAGE:
            stats_msg += f" from a {info.kind.value} HDU"
        if wcs_handler.is_valid:
            stats_msg += " (WCS available)"
        self.status(stats_msg, 3000)

    def push_block_factor(self, frame: Frame) -> None:
        """Tell the viewer how many image pixels one displayed pixel holds.

        The viewer works entirely in the units of the array it was handed, so
        with a block factor its widget-to-image mapping would come back in
        blocked pixels. Telling it the factor is what keeps the coordinate
        readout, the regions and the panner in image pixels whatever the
        block is.
        """
        factor = max(1, int(getattr(frame, "block_factor", 1)))
        for target in (self.viewer, getattr(self.viewer, "image_viewer", None)):
            setter = getattr(target, "set_block_factor", None)
            if setter is not None:
                setter(factor)

    @staticmethod
    def downsample_for_preview(
        image_data: NDArray[np.float32],
        max_pixels: int = 4_000_000,
    ) -> NDArray[np.float32]:
        """Return a strided preview view for large images."""
        height, width = image_data.shape[:2]
        total_pixels = int(height * width)
        if total_pixels <= max_pixels:
            return image_data
        stride = max(1, int(np.ceil(np.sqrt(total_pixels / max_pixels))))
        return image_data[::stride, ::stride]

    def render_preview_rgb(
        self,
        image_data: NDArray[np.float32],
        z1: float,
        z2: float,
        cmap: Colormap,
    ) -> NDArray[np.uint8]:
        """Render a lightweight RGB preview for panner/magnifier panels."""
        preview_data = self.downsample_for_preview(image_data)
        scaled_preview = apply_scale(
            preview_data,
            self.window.current_scale,
            vmin=z1,
            vmax=z2,
        )
        rgb_preview = cmap.apply_normalized(scaled_preview)
        return np.ascontiguousarray(np.flipud(rgb_preview))

    @staticmethod
    def extract_gpu_tile(
        data: NDArray[np.floating],
        x: int,
        y: int,
        w: int,
        h: int,
    ) -> NDArray[np.floating]:
        """Extract tile data for GPU upload."""
        return np.ascontiguousarray(data[y : y + h, x : x + w])

    def apply_view_transform(self, frame: Frame) -> None:
        """Apply per-frame orientation/rotation to the active viewer."""
        if self.window.using_gpu_rendering and (
            not np.isclose(frame.rotation, 0.0) or frame.flip_x or frame.flip_y
        ):
            self.window._rebuild_image_viewer(False)
            self.status(
                "Switched to CPU rendering for rotated/flipped display",
                2500,
            )
        if hasattr(self.viewer, "set_view_transform"):
            self.viewer.set_view_transform(frame.rotation, frame.flip_x, frame.flip_y)

    def cpu_pan_center(self) -> tuple[float, float] | None:
        """Return the current CPU-view center in source image coordinates."""
        viewer = getattr(self.viewer, "image_viewer", None)
        if viewer is None or self.window.image_data is None:
            return None
        zoom = max(self.viewer.get_zoom(), 1e-6)
        display_x = (
            self.window.scroll_area.horizontalScrollBar().value()
            + self.window.scroll_area.viewport().width() / 2
        ) / zoom
        display_y = (
            self.window.scroll_area.verticalScrollBar().value()
            + self.window.scroll_area.viewport().height() / 2
        ) / zoom
        source_x, source_top_y = viewer.get_view_transform().display_to_source(display_x, display_y)
        source_y = viewer.get_image_size()[1] - 1 - source_top_y
        return (float(source_x), float(source_y))

    def transform_preview(
        self,
        image: NDArray[np.generic],
        frame: Frame,
    ) -> NDArray[np.generic]:
        """Apply frame orientation/rotation to panner and magnifier previews."""
        return transform_image_array(image, frame.rotation, frame.flip_x, frame.flip_y)

    def cache_preview(self, frame: Frame, image: NDArray[np.uint8]) -> None:
        """Remember the latest untransformed preview RGB for fast view updates."""
        self.window._preview_rgb_cache = np.ascontiguousarray(image)
        self.window._preview_rgb_cache_frame_id = frame.frame_id

    def update_preview_panels(self, frame: Frame) -> None:
        """Refresh panner/magnifier panels from the cached preview image."""
        if (
            self.window._preview_rgb_cache is None
            or self.window._preview_rgb_cache_frame_id != frame.frame_id
        ):
            return
        transformed_preview = self.transform_preview(self.window._preview_rgb_cache, frame)
        if hasattr(self.window, "panner_panel"):
            self.window.panner_panel.set_image(
                transformed_preview,
                source_size=(transformed_preview.shape[1], transformed_preview.shape[0]),
            )
        if hasattr(self.window, "magnifier_panel"):
            self.window.magnifier_panel.set_image(
                transformed_preview,
                source_size=(transformed_preview.shape[1], transformed_preview.shape[0]),
            )

    def refresh_transformed_view(self, frame: Frame) -> None:
        """Apply a pure view transform change without re-rendering image data."""
        self.apply_view_transform(frame)
        self.update_preview_panels(frame)
        self.window.zoom.update_panner_rect()
        self.window.wcs.update_direction_arrows()
        self.window.view.refresh_info()
        if self.window._last_mouse_pos is not None:
            self.window._on_mouse_moved(*self.window._last_mouse_pos)

    def display(self) -> None:
        """Display the current frame's image data."""
        if self.window._tile_mode_enabled:
            self.display_tiled()
            return

        frame = self.frames.current_frame
        if not frame:
            return
        if frame.frame_type == "rgb":
            self.display_rgb_frame(frame)
            return
        if not frame.has_data:
            return

        image_data = self.display_image_data(frame)
        self.push_block_factor(frame)
        self.apply_view_transform(frame)

        # Compute scale limits using zscale (once, or when reset)
        if self.window.z1 is None or self.window.z2 is None:
            self.window.z1, self.window.z2 = self.window.scale.compute_limits(image_data)

        # Get contrast/brightness adjustments from viewer
        contrast, brightness = self.viewer.get_contrast_brightness()

        # Apply adjustments to scale limits
        range_val = self.window.z2 - self.window.z1
        center = (self.window.z1 + self.window.z2) / 2
        new_range = range_val / contrast
        adjusted_z1 = center - new_range / 2 + brightness * range_val
        adjusted_z2 = center + new_range / 2 + brightness * range_val

        # Apply colormap
        try:
            cmap = self.window.color.colormap(self.window.current_colormap)
        except ValueError:
            self.window.current_colormap = "grey"
            cmap = self.window.color.colormap(self.window.current_colormap)

        # Invert colormap if needed
        if self.window.invert_colormap:
            # Get colormap data and invert
            cmap_data = cmap.colors.copy()
            cmap_data = cmap_data[::-1]  # Reverse the colormap
            cmap = Colormap(f"{self.window.current_colormap}_inverted", cmap_data)

        # Colour tags paint flat ranges over whatever table is in force, so
        # they go on after inversion and before anything is drawn.
        cmap = self.window.color.apply_tags(cmap, frame)

        # Update the colorbar, which shows one bar per channel for a colour
        # frame and one per tiled frame under View -> Multiple Colorbars.
        self.update_colorbar(frame, cmap, adjusted_z1, adjusted_z2)

        if self.window.using_gpu_rendering:

            def tile_provider(x: int, y: int, w: int, h: int) -> NDArray[np.uint8]:
                tile = self.extract_gpu_tile(image_data, x, y, w, h)
                scaled = apply_scale(tile, self.window.current_scale, vmin=adjusted_z1, vmax=adjusted_z2)
                rgb = cmap.apply_normalized(scaled)
                return rgb

            self.viewer.set_tile_provider(image_data.shape[1], image_data.shape[0], tile_provider)
            self.viewer.set_value_source(image_data)
            display_rgb = self.render_preview_rgb(
                image_data,
                adjusted_z1,
                adjusted_z2,
                cmap,
            )
        else:
            scaled = apply_scale(image_data, self.window.current_scale, vmin=adjusted_z1, vmax=adjusted_z2)
            rgb_full = cmap.apply_normalized(scaled)
            rgb_full = self.apply_mask_layer(rgb_full)
            display_rgb = np.ascontiguousarray(np.flipud(rgb_full))

            # Convert to QImage
            height, width = display_rgb.shape[:2]
            bytes_per_line = 3 * width
            qimage = QImage(display_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)

            # Create pixmap and display
            pixmap = QPixmap.fromImage(qimage)
            self.viewer.set_image(pixmap)

        preview_rgb = self.render_preview_rgb(
            image_data,
            adjusted_z1,
            adjusted_z2,
            cmap,
        )
        self.cache_preview(frame, preview_rgb)
        transformed_preview = self.transform_preview(preview_rgb, frame)

        # Update panner panel with RGB data (DS9 style)
        if hasattr(self.window, "panner_panel"):
            self.window.panner_panel.set_image(
                transformed_preview,
                source_size=(transformed_preview.shape[1], transformed_preview.shape[0]),
            )
            self.window.zoom.update_panner_rect()

        # Update magnifier panel with RGB data (DS9 style)
        if hasattr(self.window, "magnifier_panel"):
            self.window.magnifier_panel.set_image(
                transformed_preview,
                source_size=(transformed_preview.shape[1], transformed_preview.shape[0]),
            )
        if hasattr(self.window, "horizontal_graph"):
            self.window.horizontal_graph.set_image(image_data)
        if hasattr(self.window, "vertical_graph"):
            self.window.vertical_graph.set_image(image_data)

        # Update zoom display
        self.status_bar.update_zoom(self.viewer.get_zoom())
        self.window.analysis.sync_bin_menu(getattr(frame, "block_factor", 1))
        self.window.region.show_frame_regions(frame)
        self.window.frame_controller.sync_view_state()
        if self.window._contour_settings is not None:
            self.window.analysis.update_contours()
        self.window.wcs.update_direction_arrows()
        self.window.view.refresh_info()
        self.window.analysis.refresh_overlays()

    def display_rgb_frame(self, frame: Frame) -> bool:
        """Display a composite RGB frame."""
        active_channel = (
            frame.rgb_current_channel if frame.rgb_current_channel in frame.rgb_channels else "red"
        )
        contrast, brightness = self.viewer.get_contrast_brightness()
        frame.rgb_channel_scale[active_channel] = self.window.current_scale
        frame.rgb_channel_z1[active_channel] = self.window.z1
        frame.rgb_channel_z2[active_channel] = self.window.z2
        frame.rgb_channel_contrast[active_channel] = contrast
        frame.rgb_channel_brightness[active_channel] = brightness
        composite = self.compose_rgb(frame)
        if composite is None:
            self.status("RGB frame has no channel data", 2000)
            return False

        active_data = self.active_channel_data(frame)
        if active_data is None:
            active_data = np.mean(composite.astype(np.float32), axis=2)

        self.sync_rgb_scalar_view(frame)
        # One bar per channel, each with that channel's own limits -- DS9's
        # RGB, HSV and HLS colorbar variants.
        self.update_colorbar(frame, self.window.color.colormap("grey"), 0.0, 255.0)
        display_rgb = np.ascontiguousarray(np.flipud(composite))
        self.apply_view_transform(frame)

        if self.window.using_gpu_rendering:

            def tile_provider(x: int, y: int, w: int, h: int) -> NDArray[np.uint8]:
                return self.extract_gpu_tile(composite, x, y, w, h)

            self.viewer.set_tile_provider(composite.shape[1], composite.shape[0], tile_provider)
            self.viewer.set_value_source(active_data.astype(np.float32))
        else:
            height, width = display_rgb.shape[:2]
            bytes_per_line = 3 * width
            qimage = QImage(display_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            self.viewer.set_image(QPixmap.fromImage(qimage))

        self.cache_preview(frame, display_rgb)
        transformed_preview = self.transform_preview(display_rgb, frame)

        if hasattr(self.window, "panner_panel"):
            self.window.panner_panel.set_image(
                transformed_preview,
                source_size=(transformed_preview.shape[1], transformed_preview.shape[0]),
            )
            self.window.zoom.update_panner_rect()
        if hasattr(self.window, "magnifier_panel"):
            self.window.magnifier_panel.set_image(
                transformed_preview,
                source_size=(transformed_preview.shape[1], transformed_preview.shape[0]),
            )
        if hasattr(self.window, "horizontal_graph"):
            self.window.horizontal_graph.set_image(active_data)
        if hasattr(self.window, "vertical_graph"):
            self.window.vertical_graph.set_image(active_data)

        self.status_bar.update_image_info(composite.shape[1], composite.shape[0])
        self.status_bar.update_zoom(self.viewer.get_zoom())
        self.window.analysis.sync_bin_menu(getattr(frame, "block_factor", 1))
        self.window.region.show_frame_regions(frame)
        self.window.frame_controller.sync_view_state()
        if self.window._contour_settings is not None:
            self.window.analysis.update_contours()
        self.window.wcs.update_direction_arrows()
        self.window.view.refresh_info()
        self.window.analysis.refresh_overlays()
        return True

    def render_frame_rgb(self, frame: Frame) -> NDArray[np.uint8] | None:
        """Render a frame to RGB using its own display settings."""
        if frame.frame_type == "rgb":
            return self.compose_rgb(frame)
        if not frame.has_data:
            return None

        image_data = self.display_image_data(frame)
        if image_data is None:
            return None

        z1 = frame.z1
        z2 = frame.z2
        if z1 is None or z2 is None:
            z1, z2 = self.window.scale.compute_limits(image_data, frame=frame)

        contrast = max(frame.contrast, 0.1)
        brightness = max(-1.0, min(frame.brightness, 1.0))
        range_val = max(float(z2 - z1), 1e-6)
        center = (z1 + z2) / 2.0
        new_range = range_val / contrast
        adjusted_z1 = center - new_range / 2.0 + brightness * range_val
        adjusted_z2 = center + new_range / 2.0 + brightness * range_val

        try:
            cmap = self.window.color.colormap(frame.colormap)
        except ValueError:
            frame.colormap = "grey"
            cmap = self.window.color.colormap("grey")
        if frame.invert_colormap:
            cmap_data = cmap.colors.copy()[::-1]
            cmap = Colormap(f"{frame.colormap}_inverted", cmap_data)
        cmap = self.window.color.apply_tags(cmap, frame)

        scaled = apply_scale(image_data, frame.scale, vmin=adjusted_z1, vmax=adjusted_z2)
        return self.paint_blanks(cmap.apply_normalized(scaled), image_data)

    def display_tiled(self) -> bool:
        """Render all loaded frames in a tiled grid."""
        rgb_frames: list[NDArray[np.uint8]] = []
        frame_indices: list[int] = []
        active_indices = self.window.frame_controller.active_indices()
        for frame_index in active_indices:
            frame = self.frames.frames[frame_index]
            rgb = self.render_frame_rgb(frame)
            if rgb is not None:
                rgb_frames.append(rgb)
                frame_indices.append(frame_index)

        if not rgb_frames:
            self.window._tile_layout = None
            self.status("No loaded frames to tile", 2000)
            return False

        layout = TileLayout.compute(
            count=len(rgb_frames),
            cell_width=max(rgb.shape[1] for rgb in rgb_frames),
            cell_height=max(rgb.shape[0] for rgb in rgb_frames),
            mode=self.window._tile_arrangement_mode,
        )
        self.window._tile_layout = layout
        self.window._tile_frame_indices = frame_indices

        cell_w, cell_h = layout.cell_width, layout.cell_height
        tiled_w, tiled_h = layout.width, layout.height
        tiled_rgb = np.zeros((tiled_h, tiled_w, 3), dtype=np.uint8)

        for placement, rgb in zip(layout.placements(), rgb_frames, strict=True):
            if rgb.shape[0] != cell_h or rgb.shape[1] != cell_w:
                y_idx = np.linspace(0, rgb.shape[0] - 1, cell_h).astype(np.int32)
                x_idx = np.linspace(0, rgb.shape[1] - 1, cell_w).astype(np.int32)
                rgb = rgb[y_idx][:, x_idx]
            # `placement` is bottom-up; `tiled_rgb` rows are top-down.
            top = tiled_h - placement.y - cell_h
            tiled_rgb[top : top + cell_h, placement.x : placement.x + cell_w] = rgb
        display_rgb = np.flipud(tiled_rgb)
        display_rgb = np.ascontiguousarray(display_rgb)

        if self.window.using_gpu_rendering:

            def tile_provider(x: int, y: int, w: int, h: int) -> NDArray[np.uint8]:
                return self.extract_gpu_tile(tiled_rgb, x, y, w, h)

            self.viewer.set_tile_provider(tiled_w, tiled_h, tile_provider)
            self.viewer.set_value_source(np.mean(tiled_rgb, axis=2).astype(np.float32))
        else:
            bytes_per_line = 3 * tiled_w
            qimage = QImage(display_rgb.data, tiled_w, tiled_h, bytes_per_line, QImage.Format.Format_RGB888)
            self.viewer.set_image(QPixmap.fromImage(qimage))

        # One bar per tiled frame under View -> Multiple Colorbars.
        current = self.frames.current_frame
        if current is not None:
            try:
                table = self.window.color.colormap(self.window.current_colormap)
            except ValueError:
                table = self.window.color.colormap("grey")
            self.update_colorbar(
                current,
                table,
                self.window.z1 if self.window.z1 is not None else 0.0,
                self.window.z2 if self.window.z2 is not None else 1.0,
            )

        if hasattr(self.viewer, "clear_regions"):
            self.viewer.clear_regions()
        if hasattr(self.viewer, "clear_contours"):
            self.viewer.clear_contours()
        if hasattr(self.viewer, "set_direction_arrows"):
            self.viewer.set_direction_arrows(None, None, False)
        if hasattr(self.window, "panner_panel"):
            self.window.panner_panel.set_image(display_rgb)
            self.window.panner_panel.set_view_rect(None)
        if hasattr(self.window, "magnifier_panel"):
            self.window.magnifier_panel.set_image(display_rgb)
        self.status_bar.update_image_info(tiled_w, tiled_h)
        self.status_bar.update_zoom(self.viewer.get_zoom())
        return True

    def colorbar_entries(
        self,
        frame: Frame,
        cmap: Colormap,
        low: float,
        high: float,
    ) -> list[ColorbarEntry]:
        """Which bars the colorbar should show.

        DS9 shows several in two cases: an RGB, HSV or HLS frame gets one bar
        per channel, and `View -> Multiple Colorbars` with frames tiled gets
        one per tiled frame. Everything else gets one.

        Args:
            frame: The frame being displayed.
            cmap: Its colour table, tags and inversion included.
            low: The low clip limit in force.
            high: The high clip limit.

        Returns:
            The bars, in the order to draw them.
        """
        if frame.frame_type in ("rgb", "hsv", "hls"):
            entries = []
            for channel in RGB_CHANNEL_ORDER:
                if frame.rgb_channels.get(channel) is None:
                    continue
                _scale, z1, z2, _contrast, _brightness = self.channel_view_settings(frame, channel)
                if z1 is None or z2 is None:
                    z1, z2 = self.window.scale.compute_limits(frame.rgb_channels[channel], frame=frame)
                entries.append(ColorbarEntry(colors=CHANNEL_RAMPS[channel], vmin=z1, vmax=z2, label=channel))
            if entries:
                return entries

        if self.window._tile_mode_enabled and self.window.view_state.multi:
            entries = []
            for other in self.frames.frames:
                if other.frame_id not in self.window._active_frame_ids:
                    continue
                try:
                    table = self.window.color.colormap(other.colormap)
                except ValueError:
                    continue
                table = self.window.color.apply_tags(table, other)
                z1 = other.z1 if other.z1 is not None else low
                z2 = other.z2 if other.z2 is not None else high
                entries.append(ColorbarEntry(colors=table.colors, vmin=z1, vmax=z2, label=other.colormap))
            if len(entries) > 1:
                return entries

        return [
            ColorbarEntry(
                colors=cmap.colors,
                vmin=low,
                vmax=high,
                label=self.window.current_colormap,
            )
        ]

    def update_colorbar(
        self,
        frame: Frame,
        cmap: Colormap,
        low: float,
        high: float,
    ) -> None:
        """Hand the colorbar its bars."""
        self.window.colorbar_widget.set_colorbars(
            self.colorbar_entries(frame, cmap, low, high),
            inverted=self.window.invert_colormap,
        )

    def apply_mask_layer(self, rgb: NDArray[np.floating]) -> NDArray[np.floating]:
        """Paint the loaded mask file over the coloured image (M7-24).

        Applied after the colormap and before the QImage: a mask is a flat
        colour laid on top, not a change to the data, so it must not go
        through the scale or the colour table.
        """
        analysis = getattr(self.window, "analysis", None)
        layer = getattr(analysis, "mask_layer", None)
        settings = getattr(analysis, "mask_settings", None)
        if layer is None or settings is None:
            return rgb

        from ..analysis import mask as mask_module

        fitted = mask_module.align(layer, (rgb.shape[0], rgb.shape[1]))
        chosen = mask_module.selected(fitted, settings)
        if not chosen.any():
            return rgb

        # The colormap gives bytes; the blend works in 0..1.
        as_float = np.asarray(rgb, dtype=np.float64)
        scale = 255.0 if as_float.max() > 1.0 else 1.0
        painted = mask_module.blend(
            as_float / scale,
            chosen,
            mask_module.rgb(settings.color),
            settings.alpha,
            settings.blend,
        )
        return (painted * scale).astype(rgb.dtype)

    def paint_blanks(
        self,
        rgb: NDArray[np.uint8],
        image_data: NDArray[np.floating],
    ) -> NDArray[np.uint8]:
        """Paint blank, infinite and NaN pixels in DS9's blank colour.

        A pixel with no value is not a pixel with the lowest value, which is
        what the colormap alone would make of it -- and cropped-out pixels
        are blank, so a crop would otherwise be invisible against dark data.
        """
        if image_data.size == 0 or rgb.ndim != 3:
            return rgb
        blank = ~np.isfinite(image_data)
        if not blank.any():
            return rgb
        color = QColor(getattr(self.window, "nan_color", DEFAULT_NAN_COLOR))
        if not color.isValid():
            color = QColor(DEFAULT_NAN_COLOR)
        painted = rgb.copy()
        painted[blank] = (color.red(), color.green(), color.blue())
        return painted

    def display_image_data(self, frame: Frame) -> NDArray[np.floating]:
        """Return frame data after the display-level transforms.

        In DS9's order: block, then smooth. Neither touches
        `frame.image_data` -- both work on a copy on its way to the screen,
        which is what makes Block a display transform rather than an edit
        (PLAN.md §3.4).
        """
        image_data = self.active_channel_data(frame) if frame.frame_type == "rgb" else frame.image_data
        if image_data is None:
            return np.array([], dtype=np.float32)
        # The crop comes first: it is expressed in the frame's own pixels, and
        # blanking before the block keeps its edge where the user drew it.
        image_data = blank_outside(image_data, getattr(frame, "crop", None))
        image_data = block_image(image_data, getattr(frame, "block_factor", 1))
        if self.window.menu_bar.action_smooth.isChecked():
            return self.window.analysis.apply_smoothing(image_data)
        return image_data
