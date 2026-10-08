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

"""The Plot Tool's Canvas menu: several graphs, their layout, fonts and colours."""

import pytest

from ncrads9.ui.dialogs.plot_window import PlotStyle, PlotWindow


@pytest.fixture
def plot(qapp):
    window = PlotWindow()
    window.add_dataset_from("1 2\n2 4\n3 9\n", name="first")
    yield window
    window.close()


def test_the_menus_are_ds9s(plot):
    titles = [action.text() for action in plot.layout().menuBar().actions()]
    assert titles == ["&File", "&Edit", "&Canvas", "&Graph", "&Data"]
    labels = [action.text() for action in plot.canvas_menu.actions() if action.text()]
    for wanted in ("&Select Graph", "&Add Graph", "&Delete Graph", "La&yout", "Use &Theme Colors", "&Background"):
        assert wanted in labels


def test_adding_selecting_and_deleting_graphs(plot):
    second = plot.add_graph(PlotStyle.BAR)
    assert len(plot.graphs) == 2 and plot.state is second
    assert len(plot._graph_axes) == 2
    plot.add_dataset_from("1 1\n2 1\n", name="second")
    assert [d.name for d in plot.graphs[1].datasets] == ["second"]
    assert [d.name for d in plot.graphs[0].datasets] == ["first"]
    plot.select_graph(0)
    assert plot.state is plot.graphs[0]
    assert plot.actions_by_name["style_line"].isChecked()
    plot.select_graph(1)
    assert plot.actions_by_name["style_bar"].isChecked()
    assert plot.delete_graph()
    assert len(plot.graphs) == 1
    assert not plot.delete_graph(), "the last graph stays"


@pytest.mark.parametrize(("layout", "shape"), [("row", (1, 3)), ("column", (3, 1)), ("grid", (2, 2)), ("strip", (3, 1))])
def test_the_layouts(plot, layout, shape):
    plot.add_graph()
    plot.add_graph()
    plot.set_layout(layout)
    boxes = [axes.get_position() for axes in plot._graph_axes]
    columns = len({round(box.x0, 3) for box in boxes})
    rows = len({round(box.y0, 3) for box in boxes})
    assert (rows, columns) == shape or (layout == "grid" and (rows, columns) == (2, 2))
    if layout == "strip":
        # Touching, sharing the x axis.
        assert boxes[0].y0 == pytest.approx(boxes[1].y1, abs=1e-6)


def test_fonts_and_colours(plot):
    plot.set_font("title", family="courier", size=18, weight="bold", slant="italic")
    title = plot._graph_axes[0].title
    assert title.get_size() == 18 and title.get_weight() == "bold" and title.get_style() == "italic"
    plot.set_canvas_colour(theme_colors=False, background="black", foreground="yellow")
    axes = plot._graph_axes[0]
    assert axes.get_facecolor()[:3] == pytest.approx((0, 0, 0))
    assert plot.figure.get_facecolor()[:3] == pytest.approx((0, 0, 0))


def test_clicking_a_graph_selects_it(plot, qapp):
    plot.add_graph()
    plot.select_graph(0)

    class Event:
        inaxes = plot._graph_axes[1]

    plot._on_click(Event())
    assert plot.current_graph == 1


def test_the_canvas_through_xpa(qapp, tmp_path, monkeypatch):
    from ncrads9.communication.xpa.xpa_commands import XPACommands
    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow

    monkeypatch.setattr(EditController, "preferences_path", staticmethod(lambda: tmp_path / "prefs.json"))
    window = MainWindow()
    xpa = XPACommands(window)

    def run(line, get=False):
        words = line.split()
        return xpa.handle(words[0], {"args": words[1:], **({"get": True} if get else {})})

    assert run("plot line")["status"] == "ok"
    assert run("plot add graph bar")["status"] == "ok"
    assert run("plot current graph", get=True)["result"] == "2"
    assert run("plot layout strip")["status"] == "ok"
    assert run("plot layout strip scale 30")["status"] == "ok"
    assert run("plot layout", get=True)["result"] == "strip"
    assert run("plot layout strip scale", get=True)["result"] == "30"
    assert run("plot current graph 1")["status"] == "ok"
    assert run("plot font numbers size 14")["status"] == "ok"
    assert run("plot font numbers size", get=True)["result"] == "14"
    assert run("plot background black")["status"] == "ok"
    assert run("plot background", get=True)["result"] == "black"
    assert run("plot delete graph")["status"] == "ok"
    assert run("plot delete graph")["status"] == "error"
    window.close()


def test_ds9s_strip_heights():
    from ncrads9.ui.dialogs.plot_window import CanvasSettings

    settings = CanvasSettings()
    # scale 50 with three graphs: 1/(2 + 2) each below, the rest on top.
    assert settings.strip_heights(3) == [0.5, 0.25, 0.25]
