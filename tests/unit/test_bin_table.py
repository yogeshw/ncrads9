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


"""DS9's Bin: turning a FITS table into an image.

Worked against `ncrads9/sampleimages/synthetic_events.fits`, a fixed-seed
synthetic event list with a bright point source, a faint extended one and a
flat background -- so a filter, a factor and a function each have a visible
effect rather than only a plausible one.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.core.bin_table import (
    BIN_FACTORS,
    BUFFER_SIZES,
    DEFAULT_BUFFER_SIZE,
    EXTENT_CARDS,
    BinFunction,
    BinSettings,
    BinTableError,
    apply_filter,
    bin_edges,
    bin_table,
    column_extent,
    column_index,
    column_names,
)
from ncrads9.core.file_spec import BinSpec
from ncrads9.core.fits_handler import FITSHandler
from ncrads9.core.wcs_handler import WCSHandler

#: The bundled synthetic event list.
EVENTS = Path(__file__).resolve().parents[2] / "ncrads9" / "sampleimages" / "synthetic_events.fits"

#: Its detector extent, from the file's own TLMIN/TLMAX.
DETECTOR = 512


@pytest.fixture
def events():
    """The synthetic event list's table HDU."""
    with fits.open(EVENTS) as hdus:
        yield hdus[1]


@pytest.fixture
def rows(events):
    """Its row count."""
    return len(events.data)


# -- the sample file itself (M5-21) ------------------------------------------


def test_the_sample_event_list_is_bundled():
    assert EVENTS.exists()


def test_it_has_the_columns_the_tests_rely_on(events):
    assert column_names(events) == ("TIME", "X", "Y", "PHA", "ENERGY", "CCD_ID")


def test_it_carries_both_extent_card_pairs(events):
    """So `column_extent`'s order of preference is exercised for real."""
    assert events.header["TLMIN2"] == 1
    assert events.header["TDMAX3"] == DETECTOR


def test_it_carries_per_column_wcs_cards(events):
    assert events.header["TCTYP2"] == "RA---TAN"
    assert events.header["TCTYP3"] == "DEC--TAN"


def test_it_is_recognised_as_an_events_table():
    with FITSHandler(str(EVENTS)) as handler:
        info = handler.default_extension()
    assert info.name == "EVENTS"
    assert info.displayable


# -- extents (M5-17) ---------------------------------------------------------


def test_ds9s_four_card_pairs_are_searched_in_order():
    assert [pair[0] for pair in EXTENT_CARDS] == ["TDMIN", "TLMIN", "TALEN", "AXLEN"]


def test_the_extent_comes_from_the_cards(events):
    assert column_extent(events, "X") == (1.0, float(DETECTOR))


def test_tdmin_wins_over_tlmin():
    table = _table(x=np.array([1.0, 2.0]), y=np.array([1.0, 2.0]))
    table.header["TLMIN1"], table.header["TLMAX1"] = 1, 100
    table.header["TDMIN1"], table.header["TDMAX1"] = 10, 20
    assert column_extent(table, "X") == (10.0, 20.0)


def test_talen_gives_a_range_from_one():
    table = _table(x=np.array([1.0]), y=np.array([1.0]))
    table.header["TALEN1"] = 64
    assert column_extent(table, "X") == (1.0, 64.0)


def test_axlen_is_the_last_resort_card():
    table = _table(x=np.array([1.0]), y=np.array([1.0]))
    table.header["AXLEN1"] = 32
    assert column_extent(table, "X") == (1.0, 32.0)


def test_without_cards_the_data_range_is_used():
    values = np.array([5.2, 9.8], dtype=np.float64)
    table = _table(x=values, y=values)
    assert column_extent(table, "X", values) == (5.0, 10.0)


def test_a_degenerate_extent_is_widened():
    values = np.array([7.0, 7.0], dtype=np.float64)
    table = _table(x=values, y=values)
    low, high = column_extent(table, "X", values)
    assert high > low


def test_column_index_is_one_based_and_case_insensitive(events):
    assert column_index(events, "X") == 2
    assert column_index(events, "x") == 2
    assert column_index(events, "nope") is None


def _table(x, y, extra=None):
    """A minimal two-column table for the edge cases."""
    columns = [
        fits.Column("X", "D", array=np.asarray(x)),
        fits.Column("Y", "D", array=np.asarray(y)),
    ]
    if extra is not None:
        columns.append(fits.Column("W", "D", array=np.asarray(extra)))
    return fits.BinTableHDU.from_columns(columns, name="EVENTS")


# -- the grid ----------------------------------------------------------------


def test_a_unit_factor_gives_one_pixel_per_unit():
    edges = bin_edges((1.0, 64.0), BinSettings(factor=1))
    assert len(edges) - 1 == 64
    assert edges[0] == pytest.approx(0.5)
    assert edges[-1] == pytest.approx(64.5)


@pytest.mark.parametrize("factor", BIN_FACTORS)
def test_no_event_falls_off_an_edge(events, rows, factor):
    """A coarse factor used to lose everything above the last bin centre."""
    image = bin_table(events, settings=BinSettings(factor=factor))
    assert image.data.sum() == pytest.approx(rows)


@pytest.mark.parametrize(("factor", "expected"), [(1, 512), (2, 256), (4, 128), (16, 32)])
def test_the_factor_sets_the_image_size(events, factor, expected):
    image = bin_table(events, settings=BinSettings(factor=factor))
    assert image.data.shape == (expected, expected)


def test_the_buffer_size_caps_the_image(events, rows):
    image = bin_table(events, settings=BinSettings(factor=1, buffer_size=128))
    assert image.data.shape == (128, 128)
    # Capping regroups rather than discarding.
    assert image.data.sum() == pytest.approx(rows)


def test_the_buffer_sizes_are_ds9s():
    assert BUFFER_SIZES == (128, 256, 512, 1024, 2048, 4096, 8192)
    assert DEFAULT_BUFFER_SIZE == 1024


def test_a_grid_always_has_at_least_one_bin():
    assert len(bin_edges((0.0, 1.0), BinSettings(factor=1e9))) >= 2


# -- functions ---------------------------------------------------------------


def test_the_default_function_counts_rows(events, rows):
    assert bin_table(events).data.sum() == pytest.approx(rows)


def test_summing_a_depth_column_totals_it(events):
    image = bin_table(events, spec=BinSpec(("X", "Y", "PHA")))
    assert image.data.sum() == pytest.approx(float(np.sum(events.data["PHA"])))


def test_averaging_a_depth_column_stays_within_its_range(events):
    image = bin_table(
        events,
        spec=BinSpec(("X", "Y", "PHA")),
        settings=BinSettings(function=BinFunction.AVERAGE),
    )
    assert image.data.max() <= float(np.max(events.data["PHA"]))


def test_averaging_finds_the_hard_core(events):
    """The synthetic source's core has harder photons than its surroundings."""
    image = bin_table(
        events,
        spec=BinSpec(("X", "Y", "PHA")),
        settings=BinSettings(function=BinFunction.AVERAGE, factor=8),
    )
    centre = image.data[image.data.shape[0] // 2, image.data.shape[1] // 2]
    edge = image.data[2, 2]
    assert centre > edge


def test_ds9s_default_function_is_sum():
    assert BinSettings().function is BinFunction.SUM


def test_an_unknown_axis_column_says_which_exist(events):
    with pytest.raises(BinTableError, match="TIME, X, Y, PHA"):
        bin_table(events, spec=BinSpec(("nope", "Y")))


def test_an_unknown_depth_column_is_reported(events):
    with pytest.raises(BinTableError, match="bin the values of"):
        bin_table(events, spec=BinSpec(("X", "Y", "nope")))


def test_a_negative_factor_is_refused():
    with pytest.raises(BinTableError, match="must be positive"):
        BinSettings().with_factor(0)


# -- filters -----------------------------------------------------------------


def test_a_filter_keeps_only_matching_rows(events):
    kept = int(np.sum(events.data["PHA"] > 500))
    image = bin_table(events, settings=BinSettings(filter="pha>500"))
    assert image.data.sum() == pytest.approx(kept)
    assert 0 < kept < len(events.data)


def test_conjunctions_respect_ds9s_precedence(events):
    """Python binds `&` tighter than `>`, so `a>1&&b<2` needs parentheses.

    A bare substitution makes it `a > (1 & b) < 2`, which asks a different
    question and usually raises a type error.
    """
    data = events.data
    expected = int(np.sum((data["PHA"] > 500) & (data["CCD_ID"] == 7)))
    image = bin_table(events, settings=BinSettings(filter="pha>500&&ccd_id==7"))
    assert image.data.sum() == pytest.approx(expected)
    assert expected > 0


def test_disjunctions_work_too(events):
    data = events.data
    expected = int(np.sum((data["PHA"] > 1000) | (data["PHA"] < 30)))
    image = bin_table(events, settings=BinSettings(filter="pha>1000||pha<30"))
    assert image.data.sum() == pytest.approx(expected)


def test_a_filter_is_case_insensitive(events):
    lower = bin_table(events, settings=BinSettings(filter="pha>500")).data.sum()
    upper = bin_table(events, settings=BinSettings(filter="PHA>500")).data.sum()
    assert lower == upper


def test_a_filter_from_the_specification_is_honoured(events):
    kept = int(np.sum(events.data["PHA"] > 500))
    image = bin_table(events, spec=BinSpec(("X", "Y"), filter="pha>500"))
    assert image.data.sum() == pytest.approx(kept)


def test_an_empty_filter_keeps_everything(events, rows):
    assert apply_filter(events, "") is None
    assert bin_table(events, settings=BinSettings(filter="")).data.sum() == pytest.approx(rows)


def test_a_filter_cannot_reach_outside_the_columns(events):
    """It comes from a file name, so it must not be a way into the process."""
    with pytest.raises(BinTableError):
        apply_filter(events, "__import__('os').system('true')==0")
    with pytest.raises(BinTableError):
        apply_filter(events, "open('/etc/passwd')")


def test_a_nonsense_filter_is_reported_not_raised_raw(events):
    with pytest.raises(BinTableError, match="cannot apply filter"):
        apply_filter(events, "pha >>> 5")


def test_a_filter_that_is_not_a_row_condition_is_refused(events):
    with pytest.raises(BinTableError, match="row-by-row"):
        apply_filter(events, "1+1")


# -- the WCS a binned image inherits ----------------------------------------


def test_the_binned_image_has_a_valid_wcs(events):
    image = bin_table(events)
    assert WCSHandler(image.header).is_valid


def test_the_reference_pixel_maps_to_the_reference_sky(events):
    image = bin_table(events)
    handler = WCSHandler(image.header)
    sky = handler.pixel_to_world(image.header["CRPIX1"] - 1, image.header["CRPIX2"] - 1)
    assert sky[0] == pytest.approx(events.header["TCRVL2"], abs=1e-6)
    assert sky[1] == pytest.approx(events.header["TCRVL3"], abs=1e-6)


@pytest.mark.parametrize("factor", [1, 2, 4, 8])
def test_the_sky_scale_follows_the_bin_factor(events, factor):
    """A bin four column units wide covers four times as much sky."""
    image = bin_table(events, settings=BinSettings(factor=factor))
    assert abs(image.header["CDELT1"]) == pytest.approx(abs(events.header["TCDLT2"]) * factor, rel=1e-6)


def test_the_reference_sky_does_not_move_with_the_factor(events):
    positions = []
    for factor in (1, 2, 4, 8):
        image = bin_table(events, settings=BinSettings(factor=factor))
        handler = WCSHandler(image.header)
        positions.append(handler.pixel_to_world(image.header["CRPIX1"] - 1, image.header["CRPIX2"] - 1))
    for sky in positions[1:]:
        assert sky[0] == pytest.approx(positions[0][0], abs=1e-6)
        assert sky[1] == pytest.approx(positions[0][1], abs=1e-6)


def test_a_table_without_wcs_cards_yields_no_wcs():
    table = _table(x=np.array([1.0, 2.0]), y=np.array([1.0, 2.0]))
    image = bin_table(table)
    assert "CTYPE1" not in image.header


# -- through the loader ------------------------------------------------------


def test_the_loader_bins_with_the_settings_it_is_given():
    from ncrads9.core.file_spec import parse

    with FITSHandler(str(EVENTS)) as handler:
        coarse = handler.load_spec_with_bin(parse(str(EVENTS)), BinSettings(factor=8))
    assert coarse.data.shape == (64, 64)


def test_the_loader_reports_a_bad_column_as_a_load_error():
    from ncrads9.core.file_spec import parse
    from ncrads9.core.fits_handler import FITSLoadError

    with FITSHandler(str(EVENTS)) as handler, pytest.raises(FITSLoadError, match="no column"):
        handler.load_spec(parse(f"{EVENTS}[bin=nope,y]"))


def test_describe_names_the_settings():
    assert "sum" in BinSettings().describe()
    assert "bin 4" in BinSettings(factor=4).describe()


# -- the Bin menu, in a window (M5-16, M5-18, M5-19) -------------------------


@pytest.fixture
def main_window(qapp, monkeypatch):
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    window = MainWindow()
    window._rebuild_image_viewer(False)
    window.resize(600, 500)
    window.display.load_fits(str(EVENTS))
    yield window
    window.close()


def test_loading_the_event_list_bins_it(main_window):
    frame = main_window.frame_manager.current_frame
    assert frame.image_data.shape == (DETECTOR, DETECTOR)
    assert frame.wcs_handler.is_valid


def test_the_frame_is_recognised_as_a_binned_table(main_window):
    assert main_window.bin.table_hdu() is not None
    assert main_window.bin.available_columns() == (
        "TIME",
        "X",
        "Y",
        "PHA",
        "ENERGY",
        "CCD_ID",
    )


def test_an_image_frame_is_not_a_binned_table(main_window):
    main_window.display.load_fits("ncrads9/sampleimages/SDSS9_M51_r.fits")
    assert main_window.bin.table_hdu() is None
    assert main_window.bin.available_columns() == ()


def test_changing_the_factor_rebins_the_frame(main_window):
    main_window.bin.set_factor(4)
    frame = main_window.frame_manager.current_frame
    assert frame.image_data.shape == (128, 128)
    assert main_window.bin_settings.factor == 4


def test_every_factor_is_reachable_and_ticks(main_window):
    for factor in BIN_FACTORS:
        main_window.menu_bar.bin_factor_actions[factor].trigger()
        assert main_window.bin_settings.factor == factor
        assert main_window.menu_bar.bin_factor_actions[factor].isChecked()


def test_rebinning_keeps_every_event(main_window):
    with fits.open(EVENTS) as hdus:
        rows = len(hdus[1].data)
    for factor in (1, 2, 8, 32):
        main_window.bin.set_factor(factor)
        assert main_window.frame_manager.current_frame.image_data.sum() == pytest.approx(rows)


def test_bin_in_and_out_step_through_the_presets(main_window):
    main_window.bin.set_factor(8)
    main_window.bin.bin_out()
    assert main_window.bin_settings.factor == 16
    main_window.bin.bin_in()
    assert main_window.bin_settings.factor == 8


def test_stepping_stops_at_the_ends(main_window):
    main_window.bin.set_factor(BIN_FACTORS[0])
    main_window.bin.bin_in()
    assert main_window.bin_settings.factor == BIN_FACTORS[0]
    main_window.bin.set_factor(BIN_FACTORS[-1])
    main_window.bin.bin_out()
    assert main_window.bin_settings.factor == BIN_FACTORS[-1]


def test_bin_fit_gives_an_image_that_fits(main_window):
    main_window.bin.bin_fit()
    frame = main_window.frame_manager.current_frame
    viewport = main_window._effective_viewport_size()
    assert max(frame.image_data.shape) <= max(viewport.width(), viewport.height())


def test_bin_fit_on_an_image_frame_is_reported(main_window):
    main_window.display.load_fits("ncrads9/sampleimages/SDSS9_M51_r.fits")
    main_window.bin.bin_fit()
    assert "not a binned table" in main_window.status_bar.currentMessage()


def test_the_function_actions_reach_the_settings(main_window):
    main_window.menu_bar.bin_function_actions["average"].trigger()
    assert main_window.bin_settings.function is BinFunction.AVERAGE
    main_window.menu_bar.bin_function_actions["sum"].trigger()
    assert main_window.bin_settings.function is BinFunction.SUM


def test_the_buffer_actions_reach_the_settings(main_window):
    main_window.menu_bar.bin_buffer_actions[256].trigger()
    assert main_window.bin_settings.buffer_size == 256
    assert main_window.frame_manager.current_frame.image_data.shape == (256, 256)


def test_an_unknown_function_or_buffer_is_reported(main_window):
    main_window.bin.set_function("median")
    assert "Unknown bin function" in main_window.status_bar.currentMessage()
    main_window.bin.set_buffer_size(999)
    assert "Buffer size must be" in main_window.status_bar.currentMessage()


def test_sync_ticks_the_menu_from_the_settings(main_window):
    main_window.bin.update(factor=16.0, buffer_size=2048, function=BinFunction.AVERAGE)
    main_window.bin.sync()
    assert main_window.menu_bar.bin_factor_actions[16].isChecked()
    assert main_window.menu_bar.bin_buffer_actions[2048].isChecked()
    assert main_window.menu_bar.bin_function_actions["average"].isChecked()


def test_a_setting_change_on_an_image_frame_is_remembered_not_refused(main_window):
    """DS9's Bin settings are global; an image frame simply ignores them."""
    main_window.display.load_fits("ncrads9/sampleimages/SDSS9_M51_r.fits")
    shape = main_window.frame_manager.current_frame.image_data.shape
    main_window.bin.set_factor(8)
    assert main_window.bin_settings.factor == 8
    assert main_window.frame_manager.current_frame.image_data.shape == shape


def test_a_specification_filter_reaches_the_binning(main_window):
    with fits.open(EVENTS) as hdus:
        kept = int(np.sum(hdus[1].data["PHA"] > 500))
    main_window.display.load_fits(f"{EVENTS}[bin=x,y][PHA>500]")
    assert main_window.frame_manager.current_frame.image_data.sum() == pytest.approx(kept)


def test_a_specification_names_the_bin_columns(main_window):
    main_window.display.load_fits(f"{EVENTS}[bin=x,y,pha]")
    assert main_window.bin_spec.columns == ("x", "y", "pha")
    with fits.open(EVENTS) as hdus:
        total = float(np.sum(hdus[1].data["PHA"]))
    assert main_window.frame_manager.current_frame.image_data.sum() == pytest.approx(total)


def test_rebinning_rescales(main_window):
    """A different grid is a different distribution."""
    main_window.bin.set_factor(1)
    fine = main_window.z2
    main_window.bin.set_factor(16)
    assert main_window.z2 != fine


def test_the_parameters_dialog_round_trips(qapp):
    from ncrads9.ui.controllers.bin import BinDialog

    dialog = BinDialog(
        ("TIME", "X", "Y", "PHA"),
        BinSpec(("X", "Y", "PHA")),
        BinSettings(function=BinFunction.AVERAGE, factor=4, buffer_size=512, depth=3, filter="pha>5"),
    )
    assert dialog.bin_spec().columns == ("X", "Y", "PHA")
    settings = dialog.settings()
    assert settings.function is BinFunction.AVERAGE
    assert settings.factor == 4
    assert settings.buffer_size == 512
    assert settings.depth == 3
    assert settings.filter == "pha>5"


def test_the_parameters_dialog_can_drop_the_depth_column(qapp):
    from ncrads9.ui.controllers.bin import BinDialog

    dialog = BinDialog(("X", "Y", "PHA"), BinSpec(("X", "Y", "PHA")), BinSettings())
    dialog._depth_column.setCurrentText(BinDialog.NO_DEPTH_COLUMN)
    assert dialog.bin_spec().columns == ("X", "Y")


def test_the_parameters_dialog_needs_a_table(main_window):
    main_window.display.load_fits("ncrads9/sampleimages/SDSS9_M51_r.fits")
    main_window.bin.show_dialog()
    assert "not a binned table" in main_window.status_bar.currentMessage()


def test_the_bin_menu_no_longer_block_averages(main_window):
    """It used to be four entries doing Block's job under Bin's name."""
    frame = main_window.frame_manager.current_frame
    main_window.menu_bar.bin_factor_actions[4].trigger()
    assert frame.block_factor == 1


def test_a_specification_filter_survives_a_rebin(main_window):
    """The filter goes onto the window, not just into one load.

    It used to be folded in inside the loader, so the next change from the
    Bin menu re-binned the whole table and silently dropped it.
    """
    with fits.open(EVENTS) as hdus:
        kept = int(np.sum(hdus[1].data["PHA"] > 500))

    main_window.display.load_fits(f"{EVENTS}[PHA>500]")
    assert main_window.bin_settings.filter == "PHA>500"

    for factor in (2, 8):
        main_window.bin.set_factor(factor)
        assert main_window.frame_manager.current_frame.image_data.sum() == pytest.approx(kept)


def test_the_bin_function_is_about_the_values_in_a_bin(events):
    """DS9's wording: values that fall into one bin are summed or averaged.

    With no third column every row contributes one, so Sum is the count and
    Average is one wherever anything landed.
    """
    average = bin_table(events, settings=BinSettings(function=BinFunction.AVERAGE))
    occupied = average.data[average.data > 0]
    assert occupied.size > 0
    assert occupied.tolist() == pytest.approx([1.0] * occupied.size)


def test_the_depth_setting_is_recorded_but_not_yet_a_third_axis(events):
    """DS9 can bin into a cube; this cannot, and says so rather than lying."""
    image = bin_table(events, spec=BinSpec(("X", "Y", "PHA")), settings=BinSettings(depth=8))
    assert image.data.ndim == 2
