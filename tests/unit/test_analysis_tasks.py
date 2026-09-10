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

"""DS9's analysis description files: parsing, macros, running (M7-1 ... M7-9)."""

from __future__ import annotations

import pathlib

import pytest

from ncrads9.analysis.macros import MacroContext, expand
from ncrads9.analysis.task_file import (
    MenuNode,
    TaskFileError,
    TaskType,
    parse,
    parse_file,
    tcl_split,
)
from ncrads9.analysis.task_runner import TaskResult, run_sync

#: A file exercising every construct DS9's documentation describes. Kept
#: here rather than in a data file so a change to the format and a change to
#: the test that covers it are the same diff.
FIXTURE = """\
# A fixture analysis file.

param sizes
  radius entry {Radius} {10} {aperture radius}
  shape menu {Shape} {circle|box|ellipse} {which shape}
endparam

param tabbed
  tab {First}
    one entry {One} {1} {first}
  endtab
  tab {Second}
    two checkbox {Two} 1 {second}
  endtab
endparam

help Fixture Help
This help has

a blank line in it.
endhelp
---

Counts
*.fits
menu
funcnts $filename $regions | $text

hmenu Nested
  Deeper
  *
  menu
  echo deeper | $text

  hmenu Deeper still
    Bottom
    *
    menu
    echo bottom | $text
  endhmenu
endhmenu

Print coordinates
*.fits
bind x
echo "$x $y" | $text

Docs
*
web
https://example.invalid/docs

buttonbar
Hello
*.fits
button
echo hello | $text

World
*.fits
button
echo world | $text
endbuttonbar
"""


@pytest.fixture
def fixture_file():
    return parse(FIXTURE, directory="/opt/ans")


# -- the Tcl-ish word splitter ------------------------------------------------


@pytest.mark.parametrize(
    "line,expected",
    [
        ("a b c", ["a", "b", "c"]),
        (
            "var1 entry {Variable 1} {default} {a comment}",
            ["var1", "entry", "Variable 1", "default", "a comment"],
        ),
        ('x menu "a b" c', ["x", "menu", "a b", "c"]),
        ("nested {a {b} c}", ["nested", "a {b} c"]),
        ("v entry {} {}", ["v", "entry", "", ""]),
        ("   ", []),
    ],
)
def test_tcl_split(line, expected):
    assert tcl_split(line) == expected


# -- parsing ---------------------------------------------------------------------


def test_a_four_line_block_becomes_a_task(fixture_file):
    counts = next(t for t in fixture_file.tasks() if t.label == "Counts")
    assert counts.templates == ("*.fits",)
    assert counts.task_type is TaskType.MENU
    assert counts.command == "funcnts $filename $regions | $text"
    assert counts.directory == "/opt/ans"


def test_hmenus_nest(fixture_file):
    nested = next(e for e in fixture_file.menu.entries if isinstance(e, MenuNode))
    assert nested.label == "Nested"
    deeper = next(e for e in nested.entries if isinstance(e, MenuNode))
    assert deeper.label == "Deeper still"
    assert [t.label for t in deeper.tasks()] == ["Bottom"]


def test_a_separator_keeps_its_place(fixture_file):
    assert None in fixture_file.menu.entries


def test_a_bind_task_carries_its_key(fixture_file):
    (bound,) = fixture_file.binds
    assert (bound.event, bound.label) == ("x", "Print coordinates")
    # Binds are not on the menu; they answer a keystroke.
    assert bound not in fixture_file.menu.tasks()


def test_a_web_task_keeps_its_url(fixture_file):
    web = next(t for t in fixture_file.tasks() if t.task_type is TaskType.WEB)
    assert web.command == "https://example.invalid/docs"


def test_a_buttonbar_groups_its_buttons(fixture_file):
    (bar,) = fixture_file.buttonbars
    assert [t.label for t in bar] == ["Hello", "World"]


def test_help_keeps_its_blank_lines(fixture_file):
    """Blank lines are the message; stripping them would reflow the text."""
    help_task = next(t for t in fixture_file.tasks() if t.task_type is TaskType.HELP)
    assert help_task.label == "Fixture Help"
    assert help_task.command == "This help has\n\na blank line in it."


def test_parameters_are_read_as_tcl_lists(fixture_file):
    sizes = fixture_file.parameters["sizes"]
    radius, shape = sizes.parameters
    assert (radius.variable, radius.kind, radius.title, radius.default) == (
        "radius",
        "entry",
        "Radius",
        "10",
    )
    assert shape.choices == ("circle", "box", "ellipse")
    assert shape.initial == "circle"


def test_a_tabbed_parameter_set_keeps_its_tabs(fixture_file):
    tabbed = fixture_file.parameters["tabbed"]
    assert [tab.title for tab in tabbed.tabs] == ["First", "Second"]
    assert [p.variable for p in tabbed.parameters] == ["one", "two"]


def test_an_iraf_parameter_file_is_recorded():
    parsed = parse("param p\n@analysis.par\nendparam\n")
    assert parsed.parameters["p"].iraf_file == "analysis.par"


def test_a_trailing_comment_is_stripped_from_a_label():
    """DS9's own sample writes `Test escape char # this is a comment`."""
    parsed = parse("Label # a comment\n*\nmenu\necho hi | $text\n")
    assert parsed.tasks()[0].label == "Label"


def test_a_full_line_comment_is_not_a_label():
    parsed = parse("# not a task\nReal\n*\nmenu\necho hi | $text\n")
    assert [t.label for t in parsed.tasks()] == ["Real"]


def test_end_closes_any_block():
    """DS9 accepts a bare `end` for hmenu, param and help alike."""
    parsed = parse("hmenu One\n  A\n  *\n  menu\n  echo a | $text\nend\nB\n*\nmenu\necho b | $text\n")
    assert isinstance(parsed.menu.entries[0], MenuNode)
    assert parsed.menu.entries[1].label == "B"


def test_an_unknown_command_type_is_refused():
    """DS9 abandons the file; half-loading it puts tasks under wrong menus."""
    with pytest.raises(TaskFileError, match="unknown analysis command type"):
        parse("Task\n*\nmangle\necho hi\n")


def test_an_unfinished_block_is_dropped_not_fatal():
    parsed = parse("Good\n*\nmenu\necho ok | $text\n\nTruncated\n*.fits\n")
    assert [t.label for t in parsed.tasks()] == ["Good"]


def test_a_block_with_an_empty_line_is_not_registered():
    assert parse("Label\n*\nmenu\n").tasks() == []


@pytest.mark.parametrize(
    "templates,filename,expected",
    [
        (("*.fits",), "m51.fits", True),
        (("*.fits",), "table.tab", False),
        (("*.fits",), None, False),
        (("*",), None, True),
        (("*.fits", "*.fits.gz"), "m51.fits.gz", True),
    ],
)
def test_a_task_knows_which_files_it_is_for(templates, filename, expected):
    from ncrads9.analysis.task_file import Task

    task = Task("t", templates, TaskType.MENU, "echo")
    assert task.applies_to(filename) is expected


def test_a_file_is_read_from_disk(tmp_path):
    path = tmp_path / "ds9.ans"
    path.write_text(FIXTURE)
    parsed = parse_file(path)
    assert parsed.directory == str(tmp_path)
    assert parsed.tasks()[0].directory == str(tmp_path)


# -- DS9's own sample ---------------------------------------------------------------


def test_ds9s_documented_sample_parses(tmp_path):
    """The sample in `ds9/doc/ref/analysis.html`, which uses every feature."""
    import html
    import pathlib
    import re

    reference = pathlib.Path(".tmp_sao_ds9/ds9/doc/ref/analysis.html")
    if not reference.exists():
        pytest.skip("the DS9 reference checkout is not present")

    text = re.sub(r"<[^>]+>", "", reference.read_text(errors="ignore"))
    text = html.unescape(text)
    sample = text[text.index("# Analysis command descriptions:") :]

    parsed = parse(sample)
    assert len(parsed.tasks()) > 50
    assert len(parsed.binds) == 3
    assert set(parsed.parameters) == {"foo", "bar", "foobar", "barfoo"}
    assert [e.label for e in parsed.menu.entries if isinstance(e, MenuNode)] == [
        "Test Web",
        "Test Basics",
        "Test Regions",
        "Test Output",
        "Test Dialogs",
        "Test Params",
        "Test Network",
        "Test Other",
    ]


# -- macros -------------------------------------------------------------------------


@pytest.fixture
def context() -> MacroContext:
    return MacroContext(
        filename="m51.fits[SCI]",
        filename_root="m51.fits",
        filename_full="/data/m51.fits",
        width=512,
        height=256,
        depth=4,
        bitpix=-32,
        directory="/opt/ans",
        xpa="ncrads9",
        xpa_method="local",
        vo_method="xpa",
        environment={"PATH": "/bin", "HOME": "/home/a"},
        regions=lambda options: f"regions[{options}]" if options else "circle(1,2,3)",
        coordinate=lambda axis, system, sky, fmt: f"{axis}:{system}:{sky}:{fmt}",
        value=lambda: "42",
        pan=lambda system, sky, fmt: f"pan:{system}:{fmt}",
        entry=lambda message: f"entered({message})",
        message=lambda kind, body: True,
        message_ok=lambda kind, body: "ok",
        file_dialog=lambda kind: f"/tmp/{kind}.dat",
        parameters=lambda name: {"radius": "10", "shape": "circle"},
        data_file=lambda: "/tmp/frame.fits",
    )


@pytest.mark.parametrize(
    "command,expected",
    [
        ("echo $width", "echo 512"),
        ("echo $height", "echo 256"),
        ("echo $depth", "echo 4"),
        ("echo $bitpix", "echo -32"),
        ("echo $xdim $ydim", "echo 512 256"),
        ("echo $filename", "echo m51.fits[SCI]"),
        ("echo $filename(root)", "echo m51.fits"),
        ("echo $filename(full)", "echo /data/m51.fits"),
        ("echo $filename(root,base)", "echo m51"),
        ("echo $dir", "echo /opt/ans"),
        ("echo $env(HOME)", "echo /home/a"),
        ("echo $env(NOSUCHVAR)", "echo"),
        ("echo $xpa", "echo ncrads9"),
        ("echo $xpa_method", "echo local"),
        ("echo $vo_method", "echo xpa"),
        ("echo $regions", "echo circle(1,2,3)"),
        ("echo $regions(ciao,source)", "echo regions[ciao,source]"),
        ("echo $value", "echo 42"),
        ("echo $pan", "echo pan:physical:degrees"),
        ("echo $pan(fk5,sexagesimal)", "echo pan:wcs:sexagesimal"),
        ("echo $entry(Give me a number)", "echo entered(Give me a number)"),
        ("echo $filedialog(save)", "echo /tmp/save.dat"),
    ],
)
def test_a_macro_expands(command, expected, context):
    assert expand(command, context).command == expected


def test_xpa_method_is_not_eaten_by_xpa(context):
    """`$xpa` matching first would leave `_method` behind."""
    assert expand("echo $xpa_method $xpa", context).command == "echo local ncrads9"


def test_coordinates_carry_their_system(context):
    assert expand("echo $x $y", context).command == "echo x:physical:fk5:degrees y:physical:fk5:degrees"
    assert expand("echo $x(fk5,hms)", context).command == "echo x:wcs:fk5:sexagesimal"
    assert expand("echo $z(image)", context).command == "echo z:image:fk5:degrees"


def test_filename_with_regions_makes_one_per_region(context):
    context.regions = lambda options: "circle(1,2,3)\nbox(4,5,6,7)"
    assert expand("doit $filename[$regions]", context).command == (
        "doit m51.fits[SCI][circle(1,2,3)] m51.fits[SCI][box(4,5,6,7)]"
    )


def test_the_legacy_region_macros_still_work(context):
    """DS9 keeps the SAOtng spellings; an old analysis file uses them."""
    seen = []
    context.regions = lambda options: seen.append(options) or "R"
    expand("echo $include_regions_degrees $source_regions $exclude_regions_hms", context)
    assert seen == ["include,wcs,degrees", "source", "exclude,wcs,sexagesimal"]


def test_a_dollar_dollar_escapes_a_macro(context):
    """DS9's documented example."""
    assert expand('echo "$$data $foo"', context).command == 'echo "$data $foo"'


def test_an_unknown_macro_is_left_alone(context):
    """A shell variable in a command line has to survive."""
    assert expand("echo $HOME/$notamacro", context).command == "echo $HOME/$notamacro"


def test_data_feeds_the_frame_in(context):
    result = expand("$data | funcnts | $text", context)
    assert result.stdin_file == "/tmp/frame.fits"
    assert result.command == "funcnts"


# -- sinks -----------------------------------------------------------------------------


def test_text_is_taken_off_the_line(context):
    result = expand("doit | $text", context)
    assert result.command == "doit"
    assert result.sinks.text is True
    assert result.sinks.include_stderr is False


def test_a_bar_ampersand_asks_for_stderr_too(context):
    assert expand("doit |& $text", context).sinks.include_stderr is True


def test_plot_carries_its_labels(context):
    plot = expand("doit | $plot(Title,X Axis,Y Axis,xyey)", context).sinks.plot
    assert (plot.title, plot.x_label, plot.y_label, plot.dimension) == (
        "Title",
        "X Axis",
        "Y Axis",
        "xyey",
    )


def test_a_bare_plot_takes_the_defaults(context):
    plot = expand("doit | $plot", context).sinks.plot
    assert (plot.dimension, plot.from_stdin) == ("xy", False)


def test_plot_stdin_says_so(context):
    assert expand("doit | $plot(stdin)", context).sinks.plot.from_stdin is True


def test_image_carries_its_target(context):
    assert expand("doit | $image(new)", context).sinks.image.target == "new"
    assert expand("doit | $image", context).sinks.image.target == "current"


def test_null_expects_nothing(context):
    result = expand("doit >/dev/null | $null", context)
    assert result.sinks.null is True
    assert result.command == "doit >/dev/null"


def test_geturl_is_taken_whole(context):
    """Its argument is a URL with a query string, which is full of brackets."""
    result = expand("$geturl(http://x/cgi?f=$filename[$regions]&n=1)|$plot(stdin)", context)
    assert result.geturl == "http://x/cgi?f=m51.fits[SCI][circle(1,2,3)]&n=1"
    assert result.sinks.plot.from_stdin is True
    assert result.command == ""


def test_url_becomes_a_fetch(context):
    assert expand("$url(http://a/b.fits) | $image", context).command == "curl -sL http://a/b.fits"


# -- prompts and cancelling ----------------------------------------------------------------


def test_a_cancelled_entry_abandons_the_command(context):
    context.entry = lambda message: None
    result = expand("echo $entry(anything) | $text", context)
    assert result.cancelled is True
    assert result.command == ""


def test_a_cancelled_file_dialog_abandons_the_command(context):
    context.file_dialog = lambda kind: None
    assert expand("doit $filedialog(open) | $text", context).cancelled is True


def test_a_refused_message_abandons_the_command(context):
    context.message = lambda kind, body: False
    assert expand("$message(okcancel,Really?) | doit | $text", context).cancelled is True


def test_an_accepted_message_disappears(context):
    assert expand("$message(okcancel,Really?)| doit | $text", context).command == "doit"


def test_message_kinds_are_recognised(context):
    seen = []
    context.message = lambda kind, body: seen.append((kind, body)) or True
    expand("$message(yesno,Go on then) | doit | $text", context)
    expand("$message(No comma here) | doit | $text", context)
    assert seen == [("yesno", "Go on then"), ("ok", "No comma here")]


def test_messageok_substitutes_the_button(context):
    assert expand('echo "$messageok(okcancel,Hi)" | $text', context).command == 'echo "ok"'


def test_a_cancelled_parameter_dialog_abandons_the_command(context):
    context.parameters = lambda name: None
    assert expand("$param(sizes); doit $radius | $text", context).cancelled is True


def test_parameters_substitute_into_the_line(context):
    result = expand("$param(sizes); funcnts -r $radius -s $shape | $text", context)
    assert result.command == "funcnts -r 10 -s circle"


# -- running ---------------------------------------------------------------------------------


def test_a_task_runs_and_returns_its_output(context):
    result = run_sync(expand('echo "hello world" | $text', context), label="greet")
    assert result.ok
    assert result.output.strip() == "hello world"
    assert result.label == "greet"


def test_a_failing_task_reports_its_status(context):
    result = run_sync(expand("exit 3 | $text", context), label="fail")
    assert result.status == 3
    assert not result.ok


def test_stderr_is_kept_apart_from_stdout(context):
    result = run_sync(expand("echo out; echo err >&2 | $text", context))
    assert result.output.strip() == "out"
    assert result.errors.strip() == "err"


def test_a_failed_task_shows_its_errors_without_being_asked():
    """Silence is the worst answer when something went wrong."""
    result = TaskResult(output="", errors="boom", status=1)
    assert "boom" in result.text()


def test_a_successful_task_shows_only_stdout_unless_asked():
    result = TaskResult(output="fine", errors="noise", status=0)
    assert result.text() == "fine"
    assert "noise" in result.text(include_errors=True)


def test_a_task_that_times_out_says_so(context):
    result = run_sync(expand("sleep 5 | $text", context), label="slow", timeout=0.3)
    assert "timed out" in result.failure


def test_nothing_to_run_is_not_an_error(context):
    from ncrads9.analysis.macros import Expansion

    assert run_sync(Expansion()).failure == "Nothing to run"


def test_data_reaches_the_command_on_stdin(context, tmp_path):
    payload = tmp_path / "in.txt"
    payload.write_text("piped\n")
    context.data_file = lambda: str(payload)
    result = run_sync(expand("$data | cat | $text", context))
    assert result.output.strip() == "piped"


def test_the_analysis_directory_is_on_the_path(tmp_path):
    from ncrads9.analysis.task_runner import environment

    assert environment(str(tmp_path))["PATH"].startswith(str(tmp_path))


def test_geturl_refuses_anything_but_http():
    """A `file:` URL reaching a fetcher reads something nobody offered."""
    from ncrads9.analysis.task_runner import fetch

    assert "http" in fetch("file:///etc/passwd").failure


# -- wired to the menu (M7-4, M7-5, M7-7, M7-8) ---------------------------------------


@pytest.fixture
def main_window(qapp, monkeypatch):
    import numpy as np

    from ncrads9.ui.main_window import MainWindow
    from ncrads9.utils.preferences import Preferences

    monkeypatch.setattr(
        Preferences,
        "get",
        lambda self, key, default=None: False if key == "use_gpu" else default,
    )
    window = MainWindow()
    window._rebuild_image_viewer(False)
    frame = window.frame_manager.current_frame
    frame.image_data = np.arange(64 * 32, dtype=np.float32).reshape(32, 64)
    frame.original_image_data = frame.image_data
    yield window
    for text in list(window.analysis_tasks._windows.values()):
        text.close()
    window.close()


@pytest.fixture
def loaded(main_window, tmp_path):
    """A main window with the fixture analysis file loaded."""
    path = tmp_path / "ds9.ans"
    path.write_text(FIXTURE)
    assert main_window.analysis_tasks.load_commands(str(path)) is True
    return main_window


def test_loading_a_file_puts_its_tasks_on_the_menu(loaded):
    labels = [action.text() for action in loaded.menu_bar.analysis_menu.actions()]
    assert "Counts" in labels
    assert "Nested" in labels


def test_an_hmenu_becomes_a_submenu(loaded):
    submenu = next(
        action.menu()
        for action in loaded.menu_bar.analysis_menu.actions()
        if action.menu() is not None and action.text() == "Nested"
    )
    assert [entry.text() for entry in submenu.actions() if entry.text()] == [
        "Deeper",
        "Deeper still",
    ]


def test_a_bind_task_becomes_a_keyboard_shortcut(loaded):
    assert len(loaded.analysis_tasks._shortcuts) == 1


def test_a_buttonbar_becomes_buttons(loaded):
    from ncrads9.ui.button_bar import ANALYSIS_CATEGORY

    assert len(loaded.button_bar._page_buttons.get(ANALYSIS_CATEGORY, [])) == 2


def test_a_task_that_does_not_apply_is_greyed_not_hidden(loaded):
    """A menu that changed shape with every file would be unlearnable."""
    counts = next(action for action in loaded.menu_bar.analysis_menu.actions() if action.text() == "Counts")
    # No file is loaded in this frame, and the task wants *.fits.
    assert counts.isEnabled() is False

    loaded.frame_manager.current_frame.filepath = pathlib.Path("/data/m51.fits")
    loaded.analysis_tasks.sync()
    assert counts.isEnabled() is True


def test_clearing_takes_the_tasks_off_the_menu(loaded):
    before = len(loaded.menu_bar.analysis_menu.actions())
    loaded.menu_bar.action_clear_analysis_commands.trigger()
    assert loaded.analysis_tasks.files == []
    assert len(loaded.menu_bar.analysis_menu.actions()) < before
    assert "Counts" not in [a.text() for a in loaded.menu_bar.analysis_menu.actions()]


def test_a_file_that_will_not_parse_is_reported_not_loaded(main_window, tmp_path):
    path = tmp_path / "bad.ans"
    path.write_text("Task\n*\nmangle\necho hi\n")
    assert main_window.analysis_tasks.load_commands(str(path)) is False
    assert main_window.analysis_tasks.files == []
    assert "unknown analysis command type" in main_window.status_bar.currentMessage()


def test_a_missing_file_is_reported_not_fatal(main_window, tmp_path):
    assert main_window.analysis_tasks.load_commands(str(tmp_path / "nope.ans")) is False


# -- running through the menu -----------------------------------------------------------


def _run(window, label: str):
    """Run one loaded task synchronously and return its result."""
    task = next(task for task in window.analysis_tasks.files[0].tasks() if task.label == label)
    return window.analysis_tasks.run(task, sync=True)


def test_a_menu_task_runs_and_its_text_appears(main_window, tmp_path):
    path = tmp_path / "ds9.ans"
    path.write_text('Say hello\n*\nmenu\necho "hello from a task" | $text\n')
    main_window.analysis_tasks.load_commands(str(path))

    result = _run(main_window, "Say hello")
    assert result.ok
    window = main_window.analysis_tasks._windows["Say hello"]
    assert "hello from a task" in window.text()


def test_running_a_task_twice_appends(main_window, tmp_path):
    """Two runs in one window is how they get compared."""
    path = tmp_path / "ds9.ans"
    path.write_text("Count\n*\nmenu\necho 1 | $text\n")
    main_window.analysis_tasks.load_commands(str(path))

    _run(main_window, "Count")
    _run(main_window, "Count")
    assert main_window.analysis_tasks._windows["Count"].text().count("1") == 2


def test_a_help_task_shows_its_message(loaded):
    _run(loaded, "Fixture Help")
    assert "blank line" in loaded.analysis_tasks._windows["Fixture Help"].text()


def test_a_web_task_opens_a_url(loaded, monkeypatch):
    from PyQt6.QtGui import QDesktopServices

    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url.toString())))
    _run(loaded, "Docs")
    assert opened == ["https://example.invalid/docs"]


def test_a_plot_sink_opens_a_plot_window(main_window, tmp_path):
    path = tmp_path / "ds9.ans"
    path.write_text('Profile\n*\nmenu\nprintf "1 2\\n2 4\\n" | $plot(T,X,Y,xy)\n')
    main_window.analysis_tasks.load_commands(str(path))

    _run(main_window, "Profile")
    assert len(main_window.analysis._plots) == 1
    plot = next(iter(main_window.analysis._plots))
    assert plot.state.title == "T"
    assert plot.state.datasets[0].x == [1.0, 2.0]
    plot.close()


def test_a_plot_stdin_sink_reads_its_header(main_window, tmp_path):
    path = tmp_path / "ds9.ans"
    path.write_text('Profile\n*\nmenu\nprintf "Title {X Axis} {Y} xy\\n1 2\\n" | $plot(stdin)\n')
    main_window.analysis_tasks.load_commands(str(path))

    _run(main_window, "Profile")
    plot = next(iter(main_window.analysis._plots))
    assert plot.state.title == "Title"
    assert plot.state.x_axis.label == "X Axis"
    plot.close()


def test_unplottable_output_is_shown_as_text_instead(main_window, tmp_path):
    """Better than an empty plot window that says nothing."""
    path = tmp_path / "ds9.ans"
    path.write_text('Broken\n*\nmenu\necho "not numbers" | $plot\n')
    main_window.analysis_tasks.load_commands(str(path))

    _run(main_window, "Broken")
    assert main_window.analysis._plots == []
    assert "not numbers" in main_window.analysis_tasks._windows["Broken"].text()


def test_a_null_sink_shows_nothing(main_window, tmp_path):
    path = tmp_path / "ds9.ans"
    path.write_text("Quiet\n*\nmenu\necho noise | $null\n")
    main_window.analysis_tasks.load_commands(str(path))

    _run(main_window, "Quiet")
    assert main_window.analysis_tasks._windows == {}


def test_a_task_with_no_sink_still_shows_its_output(main_window, tmp_path):
    """Silence would leave the user unsure it ran."""
    path = tmp_path / "ds9.ans"
    path.write_text("Bare\n*\nmenu\necho bare-output\n")
    main_window.analysis_tasks.load_commands(str(path))

    _run(main_window, "Bare")
    assert "bare-output" in main_window.analysis_tasks._windows["Bare"].text()


def test_a_failing_task_shows_its_errors(main_window, tmp_path):
    path = tmp_path / "ds9.ans"
    path.write_text("Fails\n*\nmenu\nls /no-such-path-xyz |& $text\n")
    main_window.analysis_tasks.load_commands(str(path))

    _run(main_window, "Fails")
    assert "No such file" in main_window.analysis_tasks._windows["Fails"].text()


def test_a_cancelled_prompt_runs_nothing(main_window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)))
    path = tmp_path / "ds9.ans"
    path.write_text("Asks\n*\nmenu\necho $entry(Anything) | $text\n")
    main_window.analysis_tasks.load_commands(str(path))

    assert _run(main_window, "Asks") is None
    assert main_window.analysis_tasks._windows == {}
    assert "cancelled" in main_window.status_bar.currentMessage()


# -- the parameter dialog (M7-5) ---------------------------------------------------------


def test_a_parameter_dialog_substitutes_its_values(loaded, monkeypatch, tmp_path):
    from ncrads9.ui.dialogs import analysis_param_dialog

    class Accepted(analysis_param_dialog.AnalysisParamDialog):
        def exec(self):
            return 1

    monkeypatch.setattr("ncrads9.ui.controllers.analysis_tasks.AnalysisParamDialog", Accepted)
    # A name of its own: DS9 resolves a duplicated `param` name to the
    # first file that defined it (`AnalysisParam`, `analysisparam.tcl:13`),
    # and the fixture already has a `sizes`.
    path = tmp_path / "params.ans"
    path.write_text(
        "param aperture\n  radius entry {Radius} {7} {r}\nendparam\n"
        "Aperture\n*\nmenu\n$param(aperture); echo radius=$radius | $text\n"
    )
    loaded.analysis_tasks.load_commands(str(path))
    task = next(t for t in loaded.analysis_tasks.files[-1].tasks() if t.label == "Aperture")
    result = loaded.analysis_tasks.run(task, sync=True)
    assert result.output.strip() == "radius=7"


def test_the_dialog_offers_every_widget_ds9_documents(qapp):
    from ncrads9.ui.dialogs.analysis_param_dialog import AnalysisParamDialog

    parsed = parse(
        "param foo\n"
        "  var1 entry {Variable 1} {default} {an entry}\n"
        "  var2 text {Variable 2} {static} {text}\n"
        "  var3 checkbox {Variable 3} 1 {a checkbox}\n"
        "  var4 menu {Variable 4} {AAA|BBB|CCC} {a menu}\n"
        "  var5 combobox {Variable 5} {XXX|YYY} {a combobox}\n"
        "  var6 open {Variable 6} {in} {open}\n"
        "  var7 save {Variable 7} {out} {save}\n"
        "endparam\n"
    )
    dialog = AnalysisParamDialog(parsed.parameters["foo"])
    assert dialog.values() == {
        "var1": "default",
        "var2": "static",
        "var3": "1",
        "var4": "AAA",
        "var5": "XXX",
        "var6": "in",
        "var7": "out",
    }


def test_a_static_text_row_cannot_be_edited(qapp):
    """DS9's `text` shows a value the command uses; it is not an entry."""
    from ncrads9.ui.dialogs.analysis_param_dialog import AnalysisParamDialog

    parsed = parse("param p\n  v text {V} {fixed} {}\nendparam\n")
    dialog = AnalysisParamDialog(parsed.parameters["p"])
    assert dialog._widgets["v"].isReadOnly() is True


def test_a_menu_row_is_not_editable_but_a_combobox_is(qapp):
    from ncrads9.ui.dialogs.analysis_param_dialog import AnalysisParamDialog

    parsed = parse("param p\n  m menu {M} {A|B} {}\n  c combobox {C} {X|Y} {}\nendparam\n")
    dialog = AnalysisParamDialog(parsed.parameters["p"])
    assert dialog._widgets["m"].isEditable() is False
    assert dialog._widgets["c"].isEditable() is True


def test_a_parameter_default_may_contain_a_macro(qapp):
    """DS9's own sample uses `{$filename}` and `{$width}` as defaults."""
    from ncrads9.ui.dialogs.analysis_param_dialog import AnalysisParamDialog

    parsed = parse("param p\n  v entry {V} {$width} {}\nendparam\n")
    dialog = AnalysisParamDialog(parsed.parameters["p"], expand=lambda value: "512")
    assert dialog.values()["v"] == "512"


def test_a_tabbed_parameter_set_becomes_a_notebook(qapp):
    from PyQt6.QtWidgets import QTabWidget

    from ncrads9.ui.dialogs.analysis_param_dialog import AnalysisParamDialog

    parsed = parse(FIXTURE)
    dialog = AnalysisParamDialog(parsed.parameters["tabbed"])
    assert dialog.findChild(QTabWidget) is not None


# -- the macro context the window supplies ------------------------------------------------


def test_the_context_reports_the_frames_dimensions(loaded):
    task = loaded.analysis_tasks.files[0].tasks()[0]
    context = loaded.analysis_tasks.context(task)
    assert (context.width, context.height) == (64, 32)
    assert context.bitpix == -32


def test_the_context_reports_the_regions(loaded):
    from ncrads9.regions.region_parser import RegionParser

    loaded.frame_manager.current_frame.regions = RegionParser().parse_string("image\ncircle(10,10,5)\n")
    task = loaded.analysis_tasks.files[0].tasks()[0]
    assert "circle" in loaded.analysis_tasks.context(task).regions("")


def test_the_regions_macro_honours_a_property_filter(loaded):
    from ncrads9.regions.region_parser import RegionParser

    loaded.frame_manager.current_frame.regions = RegionParser().parse_string(
        "image\ncircle(10,10,5)\n-box(20,20,4,4)\n"
    )
    task = loaded.analysis_tasks.files[0].tasks()[0]
    context = loaded.analysis_tasks.context(task)
    assert "box" not in context.regions("include")
    assert "circle" not in context.regions("exclude")


def test_the_regions_macro_honours_a_format(loaded):
    from ncrads9.regions.region_parser import RegionParser

    loaded.frame_manager.current_frame.regions = RegionParser().parse_string("image\ncircle(10,10,5)\n")
    task = loaded.analysis_tasks.files[0].tasks()[0]
    assert "circle" in loaded.analysis_tasks.context(task).regions("ciao")


def test_a_bind_tasks_coordinates_come_from_the_event(loaded):
    task = loaded.analysis_tasks.files[0].binds[0]
    context = loaded.analysis_tasks.context(task, x=12.0, y=7.0)
    assert context.coordinate("x", "image", "fk5", "degrees") == "12"
    assert context.coordinate("y", "image", "fk5", "degrees") == "7"


def test_the_value_macro_reads_the_pixel(loaded):
    task = loaded.analysis_tasks.files[0].binds[0]
    context = loaded.analysis_tasks.context(task, x=1.0, y=1.0)
    assert context.value() == "0"


def test_data_writes_the_frame_out_as_fits(loaded):
    from astropy.io import fits

    task = loaded.analysis_tasks.files[0].tasks()[0]
    path = loaded.analysis_tasks.context(task).data_file()
    assert path is not None
    with fits.open(path) as opened:
        assert opened[0].data.shape == (32, 64)


# -- the startup search (M7-7) --------------------------------------------------------------


def test_the_startup_search_looks_where_ds9_looks(monkeypatch, tmp_path):
    from ncrads9.ui.controllers.analysis_tasks import AnalysisTaskController

    home = tmp_path / "home"
    work = tmp_path / "work"
    (home / "bin").mkdir(parents=True)
    work.mkdir()

    (work / "ds9.ans").write_text("A\n*\nmenu\necho a\n")
    (home / "ds9.analysis").write_text("B\n*\nmenu\necho b\n")
    (home / "bin" / "extra.ds9").write_text("C\n*\nmenu\necho c\n")

    monkeypatch.setattr("pathlib.Path.cwd", staticmethod(lambda: work))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr("os.path.expanduser", lambda path: path.replace("~", str(home)))

    found = [path.name for path in AnalysisTaskController.startup_files()]
    assert "ds9.ans" in found
    assert "ds9.analysis" in found
    assert "extra.ds9" in found


def test_the_startup_search_does_not_list_a_file_twice(monkeypatch, tmp_path):
    """`.` and the working directory are the same place."""
    from ncrads9.ui.controllers.analysis_tasks import AnalysisTaskController

    work = tmp_path / "work"
    work.mkdir()
    (work / "one.ds9").write_text("A\n*\nmenu\necho a\n")

    monkeypatch.setattr("pathlib.Path.cwd", staticmethod(lambda: work))
    monkeypatch.chdir(work)
    monkeypatch.setenv("HOME", str(tmp_path / "nohome"))
    monkeypatch.setattr("os.path.expanduser", lambda path: path.replace("~", str(tmp_path / "nohome")))

    found = AnalysisTaskController.startup_files()
    assert len(found) == len({path.resolve() for path in found})


def test_autoload_skips_a_file_it_cannot_parse(main_window, monkeypatch, tmp_path):
    """One bad file in /usr/local/bin must not cost the rest."""
    from ncrads9.ui.controllers.analysis_tasks import AnalysisTaskController

    good = tmp_path / "good.ds9"
    good.write_text("A\n*\nmenu\necho a | $text\n")
    bad = tmp_path / "bad.ds9"
    bad.write_text("B\n*\nmangle\necho b\n")

    monkeypatch.setattr(AnalysisTaskController, "startup_files", staticmethod(lambda: [bad, good]))
    assert main_window.analysis_tasks.autoload() == 1
    assert len(main_window.analysis_tasks.files) == 1


def test_the_preference_is_on_by_default():
    from ncrads9.utils.preferences import Preferences

    assert Preferences.DEFAULT_PREFS["autoload_analysis_files"] is True


def test_a_duplicated_parameter_name_resolves_to_the_first_file(loaded, tmp_path, monkeypatch):
    """DS9 breaks on the first match (`analysisparam.tcl:13`)."""
    from ncrads9.ui.dialogs import analysis_param_dialog

    class Accepted(analysis_param_dialog.AnalysisParamDialog):
        def exec(self):
            return 1

    monkeypatch.setattr("ncrads9.ui.controllers.analysis_tasks.AnalysisParamDialog", Accepted)

    path = tmp_path / "second.ans"
    path.write_text(
        "param sizes\n  radius entry {Radius} {99} {r}\nendparam\n"
        "Later\n*\nmenu\n$param(sizes); echo radius=$radius | $text\n"
    )
    loaded.analysis_tasks.load_commands(str(path))
    task = next(t for t in loaded.analysis_tasks.files[-1].tasks() if t.label == "Later")
    # The fixture's `sizes` defines radius as 10, and it was loaded first.
    assert loaded.analysis_tasks.run(task, sync=True).output.strip() == "radius=10"


def test_analysis_buttons_do_not_share_the_analysis_menus_category(loaded):
    """Sharing it would let Clear Analysis Commands delete built-in buttons."""
    from ncrads9.ui.button_bar import ANALYSIS_CATEGORY

    assert ANALYSIS_CATEGORY != "Analysis"
    built_in = len(loaded.button_bar._page_buttons["Analysis"])
    loaded.menu_bar.action_clear_analysis_commands.trigger()
    assert len(loaded.button_bar._page_buttons["Analysis"]) == built_in
    assert loaded.button_bar._page_buttons[ANALYSIS_CATEGORY] == []
