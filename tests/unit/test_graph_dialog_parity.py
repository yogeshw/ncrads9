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

"""DS9's Graph Parameters window (`graph.tcl`), and the median cut."""

import numpy as np
import pytest

from ncrads9.analysis.cut_graph import GraphSettings


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow

    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    made = MainWindow()
    yield made
    made.close()


def test_the_settings_reach_both_graphs(window, qapp):
    window.analysis.show_graph_dialog()
    qapp.processEvents()
    dialog = window._open_windows["GraphDialog"]
    dialog.grid_check.setChecked(True)
    dialog.size_entry.setText("120")
    dialog.thickness_entry.setText("5")
    dialog.apply()
    dialog.axis_actions["log"].trigger()
    dialog.method_actions["median"].trigger()
    for graph in (window.horizontal_graph, window.vertical_graph):
        assert graph.settings.grid
        assert graph.settings.size == 120
        assert graph.settings.thickness == 5
        assert graph.settings.log
        assert graph.settings.method == "median"
    titles = [action.text() for action in dialog.layout().menuBar().actions()]
    assert titles == ["&File", "&Axis", "&Method"]
    dialog.close()


def test_a_median_cut():
    from ncrads9.analysis import cut_graph

    data = np.array([[1.0, 1.0], [2.0, 2.0], [100.0, 100.0]])
    settings = GraphSettings()
    settings.method = "median"
    settings.with_thickness(3)
    assert list(cut_graph.cut(data, "horizontal", 1, settings)) == [2.0, 2.0]
