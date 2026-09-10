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

"""DS9's PostScript printing (M9-18, M9-19, M9-20)."""

from __future__ import annotations

import base64
import shutil
import subprocess
import zlib

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.printing import postscript, print_engine
from ncrads9.printing.page_setup import (
    POINTS_PER_INCH,
    Orientation,
    PageSetup,
    PaperSize,
)
from ncrads9.printing.postscript import PostScriptDocument, PostScriptError
from ncrads9.printing.print_engine import (
    Destination,
    OutputFormat,
    PrintError,
    PrintSettings,
)

SIZE = 16


#: A tiny image with a distinct corner, so an upside-down or mirrored print
#: is obvious rather than plausible.
def _image() -> np.ndarray:
    rgb = np.zeros((8, 12, 3), dtype=np.uint8)
    rgb[:4, :6] = (255, 0, 0)
    rgb[4:, 6:] = (0, 0, 255)
    return rgb


# -- the page (M9-19) -----------------------------------------------------------------


def test_ds9s_page_sizes_are_the_sizes_its_dialog_names():
    assert PageSetup(paper_size=PaperSize.LETTER).size_points == (612.0, 792.0)
    assert PageSetup(paper_size=PaperSize.LEGAL).size_points == (612.0, 1008.0)
    assert PageSetup(paper_size=PaperSize.TABLOID).size_points == (792.0, 1224.0)
    assert PageSetup(paper_size=PaperSize.POSTER).size_points == (2592.0, 3456.0)
    width, height = PageSetup(paper_size=PaperSize.A4).size_points
    assert (round(width), round(height)) == (595, 842)


def test_landscape_turns_the_page_round():
    portrait = PageSetup().size_points
    landscape = PageSetup(orientation=Orientation.LANDSCAPE).size_points
    assert landscape == (portrait[1], portrait[0])


def test_a_size_can_be_typed_in_inches_or_millimetres():
    inches = PageSetup(paper_size=PaperSize.OTHER, width=10.0, height=5.0)
    assert inches.size_points == (720.0, 360.0)

    millimetres = PageSetup(paper_size=PaperSize.OTHER_MM, width=210.0, height=297.0)
    assert [round(value) for value in millimetres.size_points] == [595, 842]


def test_the_printable_area_is_inside_the_margins():
    setup = PageSetup(margin=POINTS_PER_INCH)
    x, y, width, height = setup.printable
    assert (x, y) == (72.0, 72.0)
    assert (width, height) == (612.0 - 144.0, 792.0 - 144.0)


def test_a_margin_larger_than_the_page_is_clamped():
    """A poster margin on a letter page would otherwise leave nothing."""
    _x, _y, width, height = PageSetup(margin=10_000.0).printable
    assert width > 0 and height > 0


def test_an_image_is_fitted_and_centred():
    setup = PageSetup()
    x, y, width, height = setup.place(100, 50)
    area = setup.printable
    assert width == pytest.approx(area[2])
    assert height == pytest.approx(area[2] / 2)
    # Centred vertically in the printable area.
    assert y + height / 2 == pytest.approx(area[1] + area[3] / 2)


def test_the_shape_is_kept():
    _x, _y, width, height = PageSetup().place(50, 100)
    assert width / height == pytest.approx(0.5)


def test_the_scale_is_a_percentage_of_the_fit():
    once = PageSetup().place(100, 50)
    twice = PageSetup(scale=200).place(100, 50)
    assert twice[2] == pytest.approx(once[2] * 2)
    # And off the page is allowed, which is what a percentage is for.
    assert twice[0] < 0


def test_an_empty_image_goes_nowhere():
    assert PageSetup().place(0, 0) == (0.0, 0.0, 0.0, 0.0)


# -- the encodings (M9-18) --------------------------------------------------------------


def _run_length_decode(data: bytes) -> bytes:
    """PostScript's RunLengthDecode, so the encoder is checked against the
    format rather than against itself."""
    out = bytearray()
    index = 0
    while index < len(data):
        length = data[index]
        if length == 128:
            break
        if length < 128:
            out.extend(data[index + 1 : index + 2 + length])
            index += 2 + length
        else:
            out.extend(data[index + 1 : index + 2] * (257 - length))
            index += 2
    return bytes(out)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"a",
        b"aaaa",
        b"abcd",
        b"aaaabbbbcd",
        bytes(range(256)),
        b"\x00" * 500,
        bytes([7]) * 129,
    ],
)
def test_run_length_encoding_round_trips(payload):
    encoded = postscript.run_length_encode(payload)
    assert encoded.endswith(b"\x80")
    assert _run_length_decode(encoded) == payload


def test_a_long_run_is_shorter_encoded():
    """Which is the point of Level 2: a flat background costs nothing."""
    payload = b"\x00" * 10_000
    assert len(postscript.run_length_encode(payload)) < len(payload) / 10


def test_ascii85_is_what_postscript_expects():
    text = postscript.ascii85_encode(b"hello world, twice over")
    assert text.rstrip("\n").endswith("~>")
    body = text.rstrip("\n").removesuffix("~>").replace("\n", "")
    assert base64.a85decode(body) == b"hello world, twice over"


def test_ascii85_wraps_its_lines():
    """A PostScript line has a length limit that a long image would break."""
    text = postscript.ascii85_encode(b"x" * 4000)
    assert max(len(line) for line in text.splitlines()) <= 78


def test_ascii_hex_round_trips():
    text = postscript.ascii_hex_encode(b"\x00\xff\x10")
    assert bytes.fromhex(text.replace("\n", "")) == b"\x00\xff\x10"


# -- the colour models ------------------------------------------------------------------


def test_rgb_is_three_components_unchanged():
    rgb = _image()
    assert postscript.to_components(rgb, "rgb").shape == (8, 12, 3)
    assert np.array_equal(postscript.to_components(rgb, "rgb"), rgb)


def test_grey_is_one_component_and_keeps_the_contrast():
    grey = postscript.to_components(_image(), "gray")
    assert grey.shape == (8, 12, 1)
    # Red is brighter than blue in luma, which is why the weights matter.
    assert grey[0, 0, 0] > grey[7, 11, 0]


def test_cmyk_is_four_components_with_the_black_separated():
    """Four inks laid over each other everywhere prints grey as mud."""
    cmyk = postscript.to_components(_image(), "cmyk")
    assert cmyk.shape == (8, 12, 4)
    # Pure red is magenta plus yellow, no cyan and no black.
    assert cmyk[0, 0, 0] == 0
    assert cmyk[0, 0, 1] == 255
    assert cmyk[0, 0, 2] == 255
    assert cmyk[0, 0, 3] == 0
    # Black stays black through the K channel alone.
    black = postscript.to_components(np.zeros((1, 1, 3), np.uint8), "cmyk")
    assert list(black[0, 0]) == [0, 0, 0, 255]


def test_white_is_no_ink_at_all():
    white = postscript.to_components(np.full((1, 1, 3), 255, np.uint8), "cmyk")
    assert list(white[0, 0]) == [0, 0, 0, 0]


def test_a_colour_model_ds9_does_not_print_is_refused():
    with pytest.raises(PostScriptError, match="colour model"):
        postscript.to_components(_image(), "hsv")


def test_a_greyscale_image_is_treated_as_colour():
    assert postscript.to_components(np.zeros((4, 4), np.uint8), "rgb").shape == (4, 4, 3)


# -- resampling -------------------------------------------------------------------------


def test_resampling_up_and_down():
    image = np.arange(24, dtype=np.uint8).reshape(4, 6, 1)
    assert postscript.resample(image, 2.0).shape == (8, 12, 1)
    assert postscript.resample(image, 0.5).shape == (2, 3, 1)
    assert postscript.resample(image, 1.0) is image


def test_resampling_never_vanishes():
    image = np.zeros((4, 4, 1), np.uint8)
    assert postscript.resample(image, 0.001).shape == (1, 1, 1)


def test_resampling_is_nearest_neighbour():
    """A printed image of data should show the pixels the data has, not an
    interpolation invented on the way to the printer."""
    image = np.array([[[0], [255]]], dtype=np.uint8)
    doubled = postscript.resample(image, 2.0)
    assert set(doubled.ravel().tolist()) == {0, 255}


# -- the document ------------------------------------------------------------------------


@pytest.mark.parametrize("level", [1, 2, 3])
def test_each_level_says_which_it_is(level):
    text = PostScriptDocument(level=level).render(_image())
    assert f"%%LanguageLevel: {level}" in text


def test_level_1_uses_no_filters_because_it_has_none():
    text = PostScriptDocument(level=1).render(_image())
    assert "readhexstring" in text
    assert "filter" not in text


def test_level_2_run_length_compresses_and_ascii85_encodes():
    text = PostScriptDocument(level=2).render(_image())
    assert "/RunLengthDecode filter" in text
    assert "/ASCII85Decode filter" in text


def test_level_3_flate_compresses():
    text = PostScriptDocument(level=3).render(_image())
    assert "/FlateDecode filter" in text


def test_level_3_of_a_flat_image_is_the_smallest():
    flat = np.zeros((64, 64, 3), np.uint8)
    sizes = {level: len(PostScriptDocument(level=level).render(flat)) for level in (1, 2, 3)}
    assert sizes[3] < sizes[2] < sizes[1]


def test_the_image_data_decodes_back_to_the_pixels():
    """The whole point of the driver: what comes out is the image."""
    rgb = _image()
    text = PostScriptDocument(level=3, resolution=96).render(rgb)
    body = text.split("image\n", 1)[1].split("~>")[0].replace("\n", "")
    payload = zlib.decompress(base64.a85decode(body))
    assert np.array_equal(np.frombuffer(payload, dtype=np.uint8).reshape(rgb.shape), rgb)


def test_the_colour_space_is_named_for_the_model():
    assert "/DeviceCMYK setcolorspace" in PostScriptDocument(color_model="cmyk").render(_image())
    assert "/DeviceGray setcolorspace" in PostScriptDocument(color_model="gray").render(_image())


def test_a_level_1_print_of_cmyk_falls_back_to_rgb():
    """DS9 offers the colour models for Levels 2 and 3; Level 1 has no CMYK
    operator, and a print is better than a refusal."""
    text = PostScriptDocument(level=1, color_model="cmyk").render(_image())
    assert "colorimage" in text


def test_the_resolution_changes_how_many_pixels_are_written():
    rgb = np.zeros((32, 32, 3), np.uint8)
    coarse = PostScriptDocument(level=1, resolution=48).render(rgb)
    fine = PostScriptDocument(level=1, resolution=192).render(rgb)
    assert "16 16 8" in coarse
    assert "64 64 8" in fine


def test_the_image_matrix_flips_the_rows():
    """PostScript's image space has y upwards and the data arrives top row
    first; without the flip every print is upside down."""
    text = PostScriptDocument(resolution=96).render(_image())
    assert "[12 0 0 -8 0 8]" in text


def test_a_level_that_is_not_ds9s_is_refused():
    with pytest.raises(PostScriptError, match="level"):
        PostScriptDocument(level=4)


def test_a_document_with_no_image_is_refused():
    with pytest.raises(PostScriptError, match="no image"):
        PostScriptDocument().render(np.zeros((0, 0, 3), np.uint8))


def test_eps_is_one_figure_with_no_showpage():
    """A figure goes inside another document, which supplies the page."""
    text = PostScriptDocument(encapsulated=True).render(_image())
    assert text.startswith("%!PS-Adobe-3.0 EPSF-3.0")
    assert "showpage" not in text


def test_a_page_print_has_a_showpage_and_the_pages_bounding_box():
    text = PostScriptDocument().render(_image())
    assert "showpage" in text
    assert "%%BoundingBox: 0 0 612 792" in text


def test_an_eps_bounding_box_is_the_figure_not_the_page():
    text = PostScriptDocument(encapsulated=True).render(_image())
    box = next(line for line in text.splitlines() if line.startswith("%%BoundingBox"))
    assert box != "%%BoundingBox: 0 0 612 792"


# -- rendered by an actual PostScript interpreter ----------------------------------------

pytestmark_gs = pytest.mark.skipif(shutil.which("gs") is None, reason="ghostscript is not installed")


def _render(path, tmp_path, resolution=72):
    """Render a PostScript file to pixels with ghostscript."""
    out = tmp_path / f"{path.stem}.png"
    result = subprocess.run(
        [
            "gs",
            "-q",
            "-dNOPAUSE",
            "-dBATCH",
            "-dSAFER",
            "-sDEVICE=png16m",
            f"-r{resolution}",
            f"-sOutputFile={out}",
            str(path),
        ],
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    from PIL import Image

    with Image.open(out) as opened:
        return np.asarray(opened.convert("RGB"))


@pytestmark_gs
@pytest.mark.parametrize("level", [1, 2, 3])
@pytest.mark.parametrize("model", ["rgb", "cmyk", "gray"])
def test_every_level_and_model_is_valid_postscript(tmp_path, level, model):
    """Ghostscript is the only witness that matters: a driver that writes
    something no interpreter accepts is not a driver."""
    path = tmp_path / f"l{level}{model}.ps"
    PostScriptDocument(level=level, color_model=model, resolution=96).write(path, _image())
    pixels = _render(path, tmp_path)
    assert pixels.shape[0] > 0


@pytestmark_gs
def test_the_print_comes_out_the_right_way_round(tmp_path):
    """Red is the top-left quarter of the image, so it must be printed
    above and left of the blue."""
    rgb = _image()
    path = tmp_path / "orient.ps"
    PostScriptDocument(resolution=96).write(path, rgb)
    pixels = _render(path, tmp_path)

    red_rows, red_columns = np.where((pixels[:, :, 0] > 180) & (pixels[:, :, 2] < 80))
    blue_rows, blue_columns = np.where((pixels[:, :, 2] > 180) & (pixels[:, :, 0] < 80))
    assert red_rows.mean() < blue_rows.mean()
    assert red_columns.mean() < blue_columns.mean()


@pytestmark_gs
def test_compressing_the_image_does_not_change_it(tmp_path):
    """Levels 2 and 3 differ only in how the pixels are packed, so their
    prints must be identical to the pixel."""
    rendered = []
    for level in (2, 3):
        path = tmp_path / f"same{level}.ps"
        PostScriptDocument(level=level, resolution=96).write(path, _image())
        rendered.append(_render(path, tmp_path))
    assert np.array_equal(rendered[0], rendered[1])


@pytestmark_gs
def test_levels_2_and_3_ask_for_the_page_and_level_1_cannot(tmp_path):
    """`setpagedevice` is Level 2. Without it an interpreter prints on
    whatever its default tray says, which is why a Level 1 print relies on
    the printer being set up for the paper -- as DS9's Level 1 does."""
    sizes = {}
    for level in (1, 2, 3):
        path = tmp_path / f"page{level}.ps"
        PostScriptDocument(level=level, resolution=96).write(path, _image())
        sizes[level] = _render(path, tmp_path).shape[:2]

    letter = (792, 612)
    assert sizes[2] == letter
    assert sizes[3] == letter
    # And Level 1 says what it wants, even though it cannot set it.
    text = (tmp_path / "page1.ps").read_text(encoding="ascii")
    assert "%%DocumentMedia: page 612 792" in text


@pytestmark_gs
def test_landscape_prints_a_wider_page_than_it_is_tall(tmp_path):
    path = tmp_path / "landscape.ps"
    PostScriptDocument(page=PageSetup(orientation=Orientation.LANDSCAPE), resolution=96).write(path, _image())
    pixels = _render(path, tmp_path)
    assert pixels.shape[1] > pixels.shape[0]


# -- where it goes (M9-20) ----------------------------------------------------------------


def test_printing_to_a_file(tmp_path):
    path = print_engine.to_file(tmp_path / "out.ps", _image(), PrintSettings())
    assert path.read_text(encoding="ascii").startswith("%!PS-Adobe-3.0")


def test_printing_a_pdf(tmp_path):
    settings = PrintSettings(output_format=OutputFormat.PDF, resolution=96)
    path = print_engine.to_file(tmp_path / "out.pdf", _image(), settings)
    assert path.read_bytes().startswith(b"%PDF")


def test_a_pdf_page_is_the_size_the_page_setup_says(tmp_path):
    """Read out of the PDF's own MediaBox, since Pillow writes PDFs but
    does not read them."""
    settings = PrintSettings(
        output_format=OutputFormat.PDF,
        resolution=72,
        page=PageSetup(orientation=Orientation.LANDSCAPE),
    )
    path = print_engine.to_file(tmp_path / "wide.pdf", _image(), settings)
    text = path.read_bytes().decode("latin-1")
    box = text.split("/MediaBox [", 1)[1].split("]", 1)[0].split()
    width, height = float(box[2]), float(box[3])
    assert width > height
    assert (round(width), round(height)) == (792, 612)


def test_printing_where_it_cannot_be_written_is_reported(tmp_path):
    blocked = tmp_path / "afile"
    blocked.write_text("in the way")
    with pytest.raises(PrintError):
        print_engine.to_file(blocked / "out.ps", _image(), PrintSettings())


def test_printing_to_a_command_pipes_the_postscript():
    sent = {}

    def runner(command, input=None, **kwargs):
        sent["command"] = command
        sent["input"] = input
        return subprocess.CompletedProcess(command, 0, b"", b"")

    print_engine.to_command(_image(), PrintSettings(command="lp -d printer"), runner=runner)
    assert sent["command"] == ["lp", "-d", "printer"]
    assert sent["input"].startswith(b"%!PS-Adobe-3.0")


def test_a_command_that_fails_is_reported():
    def runner(command, input=None, **kwargs):
        return subprocess.CompletedProcess(command, 1, b"", b"no such printer")

    with pytest.raises(PrintError, match="no such printer"):
        print_engine.to_command(_image(), PrintSettings(), runner=runner)


def test_a_command_that_is_not_there_is_reported():
    def runner(command, **kwargs):
        raise FileNotFoundError(command[0])

    with pytest.raises(PrintError, match="not on the path"):
        print_engine.to_command(_image(), PrintSettings(command="nosuchlp"), runner=runner)


def test_an_empty_command_is_refused():
    with pytest.raises(PrintError, match="no print command"):
        print_engine.to_command(_image(), PrintSettings(command="  "))


def test_the_default_command_is_ds9s():
    assert PrintSettings().command == "lp"
    assert PrintSettings().level == 2
    assert PrintSettings().resolution == 150
    assert PrintSettings().color_model == "rgb"


# -- the menus over them --------------------------------------------------------------------


@pytest.fixture
def main_window(qapp, monkeypatch, tmp_path):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    rows, columns = np.indices((SIZE, SIZE))
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32)).writeto(path)

    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.display.load_fits(str(path))
    yield window
    window.close()


def test_the_file_menu_has_page_setup_and_print(main_window):
    labels = [
        action.text().replace("&", "")
        for action in main_window.menu_bar.file_menu.actions()
        if not action.isSeparator()
    ]
    assert "Page Setup..." in labels
    assert "Print..." in labels


def test_printing_to_a_file_from_the_controller(main_window, tmp_path):
    path = tmp_path / "printed.ps"
    settings = PrintSettings(destination=Destination.FILE, filename=str(path))
    assert main_window.file.print_image(settings) is True
    assert path.read_text(encoding="ascii").startswith("%!PS-Adobe-3.0")
    assert "Printed to printed.ps" in main_window.status_bar.currentMessage()


def test_the_settings_are_remembered_for_the_next_print(main_window, tmp_path):
    settings = PrintSettings(destination=Destination.FILE, filename=str(tmp_path / "a.ps"), level=3)
    main_window.file.print_image(settings)
    assert main_window.file.print_settings.level == 3


def test_printing_with_no_image_is_refused(main_window, tmp_path):
    main_window.frame_controller.new_frame()
    settings = PrintSettings(destination=Destination.FILE, filename=str(tmp_path / "x.ps"))
    assert main_window.file.print_image(settings) is False
    assert "No image to print" in main_window.status_bar.currentMessage()


def test_a_failed_print_is_reported_not_raised(main_window, tmp_path):
    blocked = tmp_path / "afile"
    blocked.write_text("in the way")
    settings = PrintSettings(destination=Destination.FILE, filename=str(blocked / "x.ps"))
    assert main_window.file.print_image(settings) is False
    assert "Print failed" in main_window.status_bar.currentMessage()


def test_page_setup_changes_the_page_the_print_uses(main_window, monkeypatch):
    from ncrads9.ui.dialogs import page_setup_dialog

    wanted = PageSetup(paper_size=PaperSize.A4, orientation=Orientation.LANDSCAPE, scale=50.0)
    monkeypatch.setattr(page_setup_dialog.PageSetupDialog, "choose", lambda self: wanted)

    assert main_window.file.show_page_setup() is True
    assert main_window.file.print_settings.page == wanted
    assert "a4 landscape at 50%" in main_window.status_bar.currentMessage()


def test_cancelling_page_setup_changes_nothing(main_window, monkeypatch):
    from ncrads9.ui.dialogs import page_setup_dialog

    monkeypatch.setattr(page_setup_dialog.PageSetupDialog, "choose", lambda self: None)
    before = main_window.file.print_settings.page
    assert main_window.file.show_page_setup() is False
    assert main_window.file.print_settings.page == before


def test_the_page_setup_dialog_round_trips_a_page(main_window):
    from ncrads9.ui.dialogs.page_setup_dialog import PageSetupDialog

    wanted = PageSetup(paper_size=PaperSize.TABLOID, orientation=Orientation.LANDSCAPE, scale=75.0)
    dialog = PageSetupDialog(wanted, main_window)
    got = dialog.setup()
    assert (got.paper_size, got.orientation, got.scale) == (
        PaperSize.TABLOID,
        Orientation.LANDSCAPE,
        75.0,
    )
    # The page it describes is what matters, and a named size ignores the
    # typed boxes.
    assert got.size_points == wanted.size_points
    dialog.close()


def test_a_typed_page_size_round_trips(main_window):
    from ncrads9.ui.dialogs.page_setup_dialog import PageSetupDialog

    wanted = PageSetup(paper_size=PaperSize.OTHER, width=20.0, height=30.0)
    dialog = PageSetupDialog(wanted, main_window)
    assert dialog.setup() == wanted
    dialog.close()


def test_the_typed_size_is_only_for_the_other_choices(main_window):
    from ncrads9.ui.dialogs.page_setup_dialog import PageSetupDialog

    dialog = PageSetupDialog(PageSetup(), main_window)
    assert dialog._width.isEnabled() is False
    dialog.size_buttons[PaperSize.OTHER].setChecked(True)
    assert dialog._width.isEnabled() is True
    dialog.close()


def test_choosing_a_named_size_shows_its_measurements(main_window):
    """So the boxes are never stale about what is being printed on."""
    from ncrads9.ui.dialogs.page_setup_dialog import PageSetupDialog

    dialog = PageSetupDialog(PageSetup(), main_window)
    dialog.size_buttons[PaperSize.LEGAL].setChecked(True)
    assert (dialog._width.value(), dialog._height.value()) == (8.5, 14.0)
    dialog.close()


def test_the_print_dialog_round_trips_its_settings(main_window):
    from ncrads9.ui.dialogs.print_dialog import PrintDialog

    wanted = PrintSettings(
        destination=Destination.FILE,
        filename="/tmp/x.ps",
        level=3,
        color_model="cmyk",
        resolution=300,
        output_format=OutputFormat.EPS,
    )
    dialog = PrintDialog(wanted, main_window)
    got = dialog.settings()
    assert (got.destination, got.filename, got.level) == (Destination.FILE, "/tmp/x.ps", 3)
    assert (got.color_model, got.resolution, got.output_format) == ("cmyk", 300, OutputFormat.EPS)
    dialog.close()


def test_the_print_dialog_turns_off_what_a_pdf_has_no_use_for(main_window):
    """A PDF has no PostScript level and cannot be piped to `lp` as text."""
    from ncrads9.ui.dialogs.print_dialog import PrintDialog

    dialog = PrintDialog(PrintSettings(), main_window)
    assert dialog._level.isEnabled() is True
    dialog._format.setCurrentIndex(dialog._format.findData(OutputFormat.PDF))
    assert dialog._level.isEnabled() is False
    assert dialog._color.isEnabled() is False
    assert dialog._file.isChecked() is True
    dialog.close()


def test_the_print_dialog_enables_the_destination_it_is_using(main_window):
    from ncrads9.ui.dialogs.print_dialog import PrintDialog

    dialog = PrintDialog(PrintSettings(destination=Destination.PRINTER), main_window)
    assert dialog._command.isEnabled() is True
    assert dialog._filename.isEnabled() is False
    dialog._file.setChecked(True)
    assert dialog._command.isEnabled() is False
    assert dialog._filename.isEnabled() is True
    dialog.close()
