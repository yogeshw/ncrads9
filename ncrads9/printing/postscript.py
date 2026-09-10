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
A PostScript driver: the image, at a chosen resolution, on a chosen page.

"This is not a screen capture method, but a full level 1/2/3 postscript
driver" (`ds9/doc/ref/print.html`), and this is that driver. What each level
means is DS9's own description:

  Level 1  the image as ASCIIHEX, no filters -- Level 1 has none.
  Level 2  run-length compressed and ASCII85 encoded.
  Level 3  Flate (gzip) compressed and ASCII85 encoded.

and the colour model is RGB, CMYK or greyscale, as DS9's Print dialog
offers for Levels 2 and 3.

The resolution is in pixels per inch and is independent of the screen: 96
is screen resolution, more oversamples, less undersamples. The image is
resampled to it, which is what stops a 4096-pixel mosaic becoming a
100-megabyte file at a resolution nobody can print.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import zlib
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from .page_setup import PageSetup

#: The PostScript levels DS9 writes.
LEVELS: tuple[int, ...] = (1, 2, 3)

#: The colour models it offers.
COLOR_MODELS: tuple[str, ...] = ("rgb", "cmyk", "gray")

#: The resolutions DS9's DPI menu offers.
RESOLUTIONS: tuple[int, ...] = (53, 72, 75, 86, 96, 150, 300, 600)

#: What DS9 calls screen resolution (`print.html`).
SCREEN_RESOLUTION = 96

#: How many components each colour model has, and what PostScript calls it.
COMPONENTS: dict[str, tuple[int, str]] = {
    "rgb": (3, "DeviceRGB"),
    "cmyk": (4, "DeviceCMYK"),
    "gray": (1, "DeviceGray"),
}


class PostScriptError(ValueError):
    """A print that cannot be made, for the reason given."""


def to_components(rgb: NDArray[np.uint8], color_model: str) -> NDArray[np.uint8]:
    """Turn a rendered RGB image into one colour model's components.

    Args:
        rgb: (height, width, 3) of bytes.
        color_model: One of `COLOR_MODELS`.

    Returns:
        (height, width, n) of bytes, n being that model's component count.

    Raises:
        PostScriptError: If the model is not one DS9 offers.
    """
    if color_model not in COMPONENTS:
        raise PostScriptError(f"{color_model} is not a colour model DS9 prints")

    array = np.asarray(rgb, dtype=np.uint8)
    if array.ndim == 2:
        array = np.repeat(array[:, :, None], 3, axis=2)

    if color_model == "rgb":
        return np.ascontiguousarray(array[:, :, :3])

    if color_model == "gray":
        # Rec. 601 luma, which is what a greyscale print of a colour image
        # should look like.
        luma = 0.299 * array[:, :, 0] + 0.587 * array[:, :, 1] + 0.114 * array[:, :, 2]
        return np.ascontiguousarray(np.round(luma).astype(np.uint8)[:, :, None])

    # CMYK, with the black separated out: the alternative is four inks
    # laid over each other everywhere, which prints grey as mud.
    scaled = array[:, :, :3].astype(np.float32) / 255.0
    black = 1.0 - scaled.max(axis=2)
    remaining = np.clip(1.0 - black, 1e-6, None)
    cyan = (1.0 - scaled[:, :, 0] - black) / remaining
    magenta = (1.0 - scaled[:, :, 1] - black) / remaining
    yellow = (1.0 - scaled[:, :, 2] - black) / remaining
    stacked = np.stack([cyan, magenta, yellow, black], axis=2)
    return np.ascontiguousarray(np.round(np.clip(stacked, 0.0, 1.0) * 255.0).astype(np.uint8))


def resample(image: NDArray[np.uint8], factor: float) -> NDArray[np.uint8]:
    """Sample an image up or down by a factor, by nearest neighbour.

    Nearest neighbour on purpose: a printed image of data should show the
    pixels the data has, not an interpolation invented on the way to the
    printer.

    Args:
        image: (height, width, n).
        factor: How much bigger to make it. 1 returns the image itself.

    Returns:
        The sampled image, at least one pixel each way.
    """
    if factor == 1.0 or image.size == 0:
        return image
    height, width = image.shape[:2]
    new_height = max(1, int(round(height * factor)))
    new_width = max(1, int(round(width * factor)))
    rows = (np.arange(new_height) / factor).astype(int).clip(0, height - 1)
    columns = (np.arange(new_width) / factor).astype(int).clip(0, width - 1)
    return np.ascontiguousarray(image[rows][:, columns])


def run_length_encode(data: bytes) -> bytes:
    """PostScript's RunLengthDecode format, which Level 2 uses.

    A run of 2 to 128 equal bytes becomes the length byte `257 - n` and the
    byte; anything else becomes a length byte `n - 1` and `n` literals. The
    stream ends with 128.
    """
    out = bytearray()
    index = 0
    length = len(data)
    while index < length:
        run = 1
        while run < 128 and index + run < length and data[index + run] == data[index]:
            run += 1
        if run > 1:
            out.append(257 - run)
            out.append(data[index])
            index += run
            continue
        # A literal run, up to 128 bytes, stopping before a repeat worth
        # encoding as a run.
        start = index
        while (
            index - start < 128
            and index < length
            and not (index + 1 < length and data[index] == data[index + 1])
        ):
            index += 1
        if index == start:
            index += 1
        chunk = data[start:index]
        out.append(len(chunk) - 1)
        out.extend(chunk)
    out.append(128)
    return bytes(out)


def ascii85_encode(data: bytes, width: int = 76) -> str:
    """ASCII85 as PostScript's ASCII85Decode wants it, `~>` and all."""
    import base64

    text = base64.a85encode(data).decode("ascii")
    lines = [text[start : start + width] for start in range(0, len(text), width)] or [""]
    return "\n".join(lines) + "~>\n"


def ascii_hex_encode(data: bytes, width: int = 78) -> str:
    """ASCIIHEX, which is all a Level 1 print can use."""
    text = data.hex()
    lines = [text[start : start + width] for start in range(0, len(text), width)] or [""]
    return "\n".join(lines) + "\n"


class PostScriptDocument:
    """One page of PostScript with one image on it."""

    def __init__(
        self,
        page: PageSetup | None = None,
        level: int = 2,
        color_model: str = "rgb",
        resolution: int = 150,
        title: str = "NCRADS9",
        encapsulated: bool = False,
    ) -> None:
        """
        Args:
            page: The page to print on. A letter portrait page if omitted.
            level: 1, 2 or 3.
            color_model: `rgb`, `cmyk` or `gray`.
            resolution: Pixels per inch to sample the image at.
            title: What the document calls itself.
            encapsulated: Whether to write EPS -- one figure, no showpage,
                and a bounding box around the image rather than the page.

        Raises:
            PostScriptError: If the level or the colour model is not one of
                DS9's.
        """
        if level not in LEVELS:
            raise PostScriptError(f"PostScript level {level} is not one DS9 writes")
        if color_model not in COMPONENTS:
            raise PostScriptError(f"{color_model} is not a colour model DS9 prints")

        self.page = page or PageSetup()
        self.level = int(level)
        self.color_model = color_model
        self.resolution = max(1, int(resolution))
        self.title = title
        self.encapsulated = bool(encapsulated)

    # -- the document ------------------------------------------------------------

    def render(self, rgb: NDArray[np.uint8]) -> str:
        """The whole PostScript document for one rendered image.

        Args:
            rgb: The image as it appears on screen, (height, width, 3).

        Returns:
            The document's text.

        Raises:
            PostScriptError: If there is no image.
        """
        array = np.asarray(rgb)
        if array.size == 0:
            raise PostScriptError("there is no image to print")

        # Level 1 has no filters and no CMYK operator; DS9 offers the colour
        # models for Levels 2 and 3 only, so a Level 1 print of a colour
        # model it cannot express goes out as RGB rather than being refused.
        model = self.color_model if self.level > 1 else ("gray" if self.color_model == "gray" else "rgb")

        components = to_components(array, model)
        sampled = resample(components, self.resolution / SCREEN_RESOLUTION)
        height, width = sampled.shape[:2]

        x, y, box_width, box_height = self.page.place(width, height)
        count, space = COMPONENTS[model]

        lines = [self._header(x, y, box_width, box_height)]
        lines.append(self._page_device())
        lines.append("gsave")
        lines.append(f"{x:.2f} {y:.2f} translate")
        lines.append(f"{box_width:.2f} {box_height:.2f} scale")
        lines.append(self._image_operator(sampled, width, height, count, space, model))
        lines.append("grestore")
        if not self.encapsulated:
            lines.append("showpage")
        lines.append("%%Trailer")
        lines.append("%%EOF")
        return "\n".join(lines) + "\n"

    def write(self, path: str | Path, rgb: NDArray[np.uint8]) -> Path:
        """Write the document to a file."""
        target = Path(path)
        target.write_text(self.render(rgb), encoding="ascii")
        return target

    # -- the pieces ---------------------------------------------------------------

    def _header(self, x: float, y: float, width: float, height: float) -> str:
        """The document's comments, EPS or not."""
        page_width, page_height = self.page.size_points
        if self.encapsulated:
            box = (int(x), int(y), int(x + width) + 1, int(y + height) + 1)
            first = "%!PS-Adobe-3.0 EPSF-3.0"
        else:
            box = (0, 0, int(page_width), int(page_height))
            first = "%!PS-Adobe-3.0"

        return "\n".join(
            [
                first,
                f"%%Title: {self.title}",
                "%%Creator: NCRADS9",
                f"%%LanguageLevel: {self.level}",
                f"%%BoundingBox: {box[0]} {box[1]} {box[2]} {box[3]}",
                "%%Pages: 1",
                "%%EndComments",
                "%%BeginProlog",
                "%%EndProlog",
                "%%Page: 1 1",
            ]
        )

    def _page_device(self) -> str:
        """Ask for the page this document is laid out for.

        Without this an interpreter prints on whatever its default tray
        says, so an A4 or landscape print comes out on a letter portrait
        page with the image in the wrong place. `setpagedevice` is Level 2,
        so a Level 1 print says its size in a comment and relies on the
        printer being set up for it, as DS9's Level 1 does.
        """
        width, height = self.page.size_points
        if self.encapsulated:
            # A figure is placed by whatever includes it.
            return "% encapsulated: the page belongs to the document that includes this"
        if self.level == 1:
            return f"%%DocumentMedia: page {width:.0f} {height:.0f} 0 () ()"
        return f"<< /PageSize [{width:.0f} {height:.0f}] >> setpagedevice"

    def _image_operator(
        self,
        sampled: NDArray[np.uint8],
        width: int,
        height: int,
        count: int,
        space: str,
        model: str,
    ) -> str:
        """The image itself, encoded for the chosen level."""
        # PostScript's image space has y upwards and the data arrives top
        # row first, so the matrix flips it: [w 0 0 -h 0 h].
        matrix = f"[{width} 0 0 -{height} 0 {height}]"
        payload = sampled.tobytes()

        if self.level == 1:
            data = ascii_hex_encode(payload)
            operator = "colorimage" if count > 1 else "image"
            trailing = f" {count} {operator}" if count > 1 else f" {operator}"
            return "\n".join(
                [
                    f"/picstr {width * count} string def",
                    f"{width} {height} 8",
                    matrix,
                    "{currentfile picstr readhexstring pop}",
                    f"false{trailing}" if count > 1 else f"{trailing.strip()}",
                    data.rstrip("\n"),
                ]
            )

        if self.level == 2:
            encoded = ascii85_encode(run_length_encode(payload))
            filters = "/ASCII85Decode filter /RunLengthDecode filter"
        else:
            encoded = ascii85_encode(zlib.compress(payload, 9))
            filters = "/ASCII85Decode filter /FlateDecode filter"

        return "\n".join(
            [
                f"/{space} setcolorspace",
                "<<",
                "  /ImageType 1",
                f"  /Width {width}",
                f"  /Height {height}",
                "  /BitsPerComponent 8",
                f"  /Decode [{' '.join(['0 1'] * count)}]",
                f"  /ImageMatrix {matrix}",
                f"  /DataSource currentfile {filters}",
                ">>",
                "image",
                encoded.rstrip("\n"),
            ]
        )
