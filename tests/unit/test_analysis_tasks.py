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
