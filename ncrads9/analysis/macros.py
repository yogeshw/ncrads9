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
The macros an analysis command line is expanded with before it is run.

DS9's set, from `ds9/doc/ref/analysis.html` and the `Parse*Macro` procedures
in `ds9/library/analysis.tcl`. Three kinds:

  - *values* -- `$filename`, `$width`, `$regions`, `$x`, `$env(PATH)` -- are
    replaced by text;
  - *prompts* -- `$entry(...)`, `$message(...)`, `$filedialog(...)`,
    `$param(...)` -- ask the user, and cancelling any of them abandons the
    command rather than running it with a blank;
  - *sinks* -- `$text`, `$plot`, `$image`, `$null` -- say where the output
    goes, and are removed from the command line before it runs.

The expansion order is DS9's (`analysis.tcl:727`), and it is not arbitrary.
`$xpa_method` must go before `$xpa` and `$filename[$regions]` before
`$filename`, or the shorter name eats the head of the longer one. The sinks
go last, after every prompt, so a cancelled dialog leaves nothing half-done.

`$$` escapes a macro: `echo "$$data"` prints `$data`. Escaped text is parked
under a sentinel for the whole pass and restored at the end, which is how
DS9 does it too -- the alternative is every substitution having to look
behind itself.

A `$<word>` that is not a macro is left exactly as it was, so a shell
variable in a command line survives.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace

#: What `$$` becomes for the length of one expansion. Anything that cannot
#: occur in a command line will do; DS9 uses "WaJaWaJaW".
ESCAPE_SENTINEL = "\x00ds9escape\x00"

#: The sink macros, which say where output goes rather than what to run.
SINK_MACROS = ("$text", "$plot", "$image", "$null")

#: What `$plot` assumes it is being given when the form is not named.
DEFAULT_PLOT_DIMENSION = "xy"

#: Where `$image` puts the result when no frame is named.
DEFAULT_IMAGE_TARGET = "current"


@dataclass(frozen=True)
class PlotSink:
    """`$plot`, and what it was told about the data.

    Attributes:
        title: The plot's title.
        x_label: The x axis label.
        y_label: The y axis label.
        dimension: xy, xyex, xyey or xyexey -- how many columns to read and
            which of them are error bars.
        from_stdin: True for `$plot(stdin)`, where the title and the axis
            labels are the first line of the data rather than given here.
    """

    title: str = ""
    x_label: str = ""
    y_label: str = ""
    dimension: str = DEFAULT_PLOT_DIMENSION
    from_stdin: bool = False


@dataclass(frozen=True)
class ImageSink:
    """`$image`, and which frame it loads into: new, rgb, 3d or current."""

    target: str = DEFAULT_IMAGE_TARGET


@dataclass(frozen=True)
class Sinks:
    """Where a command's output is to go.

    Attributes:
        text: `$text` was given -- show stdout in a text window.
        include_stderr: The pipe into `$text` was `|&`, so show stderr too.
        plot: `$plot`, if given.
        image: `$image`, if given.
        null: `$null` -- expect and report nothing, not even a failure.
    """

    text: bool = False
    include_stderr: bool = False
    plot: PlotSink | None = None
    image: ImageSink | None = None
    null: bool = False

    @property
    def any(self) -> bool:
        """Whether the command said anything about its output at all."""
        return bool(self.text or self.plot or self.image or self.null)


@dataclass
class MacroContext:
    """Everything the macros need to know, and everyone they need to ask.

    The values are plain; the prompts are callables, so this module never
    imports Qt and can be tested without it. A prompt that returns None
    means the user cancelled.

    Attributes:
        filename: `$filename` -- the file with its extension, section and
            filter, as loaded.
        filename_root: `$filename(root)` -- no path, no section, no filter.
        filename_full: `$filename(full)` -- absolute, no section or filter.
        width, height, depth, bitpix: `$width` and friends. `$xdim` and
            `$ydim` are DS9's older names for the first two.
        directory: `$dir` -- where the analysis file was found.
        xpa, xpa_method, vo_method: the access-point macros.
        environment: what `$env(NAME)` reads.
        regions: called with the option string, returning the region text.
        coordinate: called with (axis, system, sky, format) for `$x`, `$y`
            and `$z`; axis is "x", "y" or "z".
        value: `$value` -- the pixel under a bind event.
        pan: called with (system, sky, format) for `$pan`.
        data_file: `$data` -- called for a path to the current frame written
            out as FITS, to be fed to the command's stdin.
        entry: `$entry(msg)` -- prompt for a string.
        message: `$message([kind,]msg)` -- show a message; False cancels.
        message_ok: `$messageok([kind,]msg)` -- show one and substitute the
            button pressed.
        file_dialog: `$filedialog(open|save)` -- prompt for a path.
        parameters: `$param(name)` -- run a parameter dialog, returning the
            variables it set, or None if cancelled.
    """

    filename: str = ""
    filename_root: str = ""
    filename_full: str = ""
    width: int = 0
    height: int = 0
    depth: int = 0
    bitpix: int = 0
    directory: str = ""
    xpa: str = "ncrads9"
    xpa_method: str = "local"
    vo_method: str = "xpa"
    environment: Mapping[str, str] = field(default_factory=lambda: os.environ)

    regions: Callable[[str], str] | None = None
    coordinate: Callable[[str, str, str, str], str] | None = None
    value: Callable[[], str] | None = None
    pan: Callable[[str, str, str], str] | None = None
    data_file: Callable[[], str | None] | None = None

    entry: Callable[[str], str | None] | None = None
    message: Callable[[str, str], bool] | None = None
    message_ok: Callable[[str, str], str | None] | None = None
    file_dialog: Callable[[str], str | None] | None = None
    parameters: Callable[[str], dict[str, str] | None] | None = None


@dataclass
class Expansion:
    """A command line after expansion, and what to do with it.

    Attributes:
        command: The command to run, sinks removed.
        sinks: Where its output goes.
        cancelled: True if a prompt was cancelled, in which case nothing
            should run.
        stdin_file: A file to feed to the command's stdin, from `$data`.
        geturl: A URL to fetch instead of running anything, from `$geturl`.
    """

    command: str = ""
    sinks: Sinks = field(default_factory=Sinks)
    cancelled: bool = False
    stdin_file: str | None = None
    geturl: str | None = None


#: `$name(args)`, where the arguments do not themselves contain a bracket.
def _call(name: str) -> re.Pattern[str]:
    """A pattern matching `$name(...)` with its argument captured."""
    return re.compile(rf"\${name}\(([^)]*)\)")


#: `$name` not followed by a letter, digit or underscore, so `$xpa` does not
#: match inside `$xpa_method`.
def _bare(name: str) -> re.Pattern[str]:
    """A pattern matching a bare `$name`."""
    return re.compile(rf"\${name}(?![A-Za-z0-9_])")


_ENV = _call("env")
_ENTRY = _call("entry")
_MESSAGE = _call("message")
_MESSAGE_OK = _call("messageok")
_FILE_DIALOG = _call("filedialog")
_PARAM = _call("param")
_REGIONS_CALL = _call("regions")
_FILENAME_CALL = _call("filename")
_PAN_CALL = _call("pan")
#: `$geturl(...)` and `$url(...)` are greedy to the last closing bracket,
#: which is DS9's own pattern (`analysis.tcl:1919`): the argument is a URL
#: with a query string, and a query string is full of brackets.
_GETURL = re.compile(r"\$geturl\((.*)\)")
_URL = re.compile(r"\$url\((.*)\)")
_PLOT_CALL = _call("plot")
_IMAGE_CALL = _call("image")

#: `$filename[$regions]` and `$filename[$regions(...)]`, which DS9 expands
#: before either of its two halves.
_FILENAME_REGIONS = re.compile(r"\$filename\[\$regions(?:\(([^)]*)\))?\]")

#: `$x(...)`, `$y(...)`, `$z(...)`, and their bare forms.
_COORDINATE_CALL = re.compile(r"\$([xyz])\(([^)]*)\)")
_COORDINATE_BARE = re.compile(r"\$([xyz])(?![A-Za-z0-9_(])")

#: DS9's older per-property region macros, e.g. `$include_regions_degrees`.
_LEGACY_REGIONS = re.compile(
    r"\$(include|exclude|source|background)?_?regions(_pixels|_degrees|_hms)?" r"(?![A-Za-z0-9_(])"
)

#: How the legacy suffixes map onto `$regions(...)` options.
_LEGACY_SUFFIX = {
    "_pixels": "image",
    "_degrees": "wcs,degrees",
    "_hms": "wcs,sexagesimal",
}


class _Cancelled(Exception):
    """Raised inside a substitution when the user cancels a prompt."""


def expand(command: str, context: MacroContext) -> Expansion:
    """Expand one analysis command line.

    Args:
        command: The command as written in the analysis file.
        context: What to substitute, and whom to ask.

    Returns:
        The command to run and where its output goes. `cancelled` is True
        when a prompt was dismissed, and nothing should be run.
    """
    text = command.replace("$$", ESCAPE_SENTINEL)
    result = Expansion()

    try:
        text = _data(text, context, result)
        text = _simple(text, context)
        text = _dimensions(text, context)
        text = _filename_regions(text, context)
        text = _filename(text, context)
        text = _file_dialog(text, context)
        text = _regions(text, context)
        text = _bare(r"dir").sub(lambda _m: context.directory, text)
        text = _environment(text, context)
        text = _pan(text, context)
        text = _coordinates(text, context)
        text = _prompts(text, context)
    except _Cancelled:
        return Expansion(cancelled=True)

    # DS9's order (`analysis.tcl:798`): text, plot and null, then $url,
    # then $geturl, then $image last. It matters: `$geturl` takes everything
    # to the *last* closing bracket on the line, so a trailing `$plot(stdin)`
    # has to be gone before it looks.
    text, sinks = _text_plot_null(text)
    text = _url(text, context)
    text, result.geturl = _geturl(text)
    text, image = _image(text)
    result.sinks = replace(sinks, image=image)

    result.command = text.replace(ESCAPE_SENTINEL, "$").strip()
    return result


# -- values -----------------------------------------------------------------


def _data(text: str, context: MacroContext, result: Expansion) -> str:
    """`$data` -- feed the current frame to the command as FITS on stdin."""
    if not _bare("data").search(text):
        return text
    result.stdin_file = context.data_file() if context.data_file else None
    # DS9 removes the macro and pipes the file in; the leading `| ` it
    # leaves behind would be a syntax error in a shell.
    text = _bare("data").sub("", text)
    return text.lstrip().lstrip("|").lstrip()


def _simple(text: str, context: MacroContext) -> str:
    """The macros that are a plain lookup, longest name first."""
    for name, value in (
        ("xpa_method", context.xpa_method),
        ("xpa", context.xpa),
        ("vo_method", context.vo_method),
    ):
        text = _bare(name).sub(lambda _m, v=value: v, text)
    return text


def _dimensions(text: str, context: MacroContext) -> str:
    """`$width`, `$height`, `$depth`, `$bitpix`, and DS9's older names."""
    for name, value in (
        ("width", context.width),
        ("height", context.height),
        ("depth", context.depth),
        ("bitpix", context.bitpix),
        ("xdim", context.width),
        ("ydim", context.height),
    ):
        text = _bare(name).sub(lambda _m, v=value: str(v), text)
    return text


def _filename_regions(text: str, context: MacroContext) -> str:
    """`$filename[$regions]` -- the file, once per region.

    Expanded before either half, or `$filename` would take the first part
    and leave `[$regions]` dangling.
    """

    def replace(match: re.Match[str]) -> str:
        options = match.group(1) or ""
        regions = context.regions(options) if context.regions else ""
        lines = [line.strip() for line in regions.splitlines() if line.strip()]
        if not lines:
            return context.filename
        return " ".join(f"{context.filename}[{line}]" for line in lines)

    return _FILENAME_REGIONS.sub(replace, text)


def _filename(text: str, context: MacroContext) -> str:
    """`$filename`, `$filename(root)` and `$filename(full)`.

    `,base` strips the extension, which is what DS9's `root,base` means.
    """

    def replace(match: re.Match[str]) -> str:
        options = [part.strip().lower() for part in match.group(1).split(",") if part.strip()]
        name = context.filename_full if "full" in options else context.filename_root
        if "base" in options:
            name = name.rsplit(".", 1)[0] if "." in os.path.basename(name) else name
        return name

    text = _FILENAME_CALL.sub(replace, text)
    return _bare("filename").sub(lambda _m: context.filename, text)


def _regions(text: str, context: MacroContext) -> str:
    """`$regions`, `$regions(...)`, and DS9's older per-property spellings."""

    def call(match: re.Match[str]) -> str:
        return context.regions(match.group(1)) if context.regions else ""

    text = _REGIONS_CALL.sub(call, text)

    def legacy(match: re.Match[str]) -> str:
        if not context.regions:
            return ""
        options = [part for part in (match.group(1), _LEGACY_SUFFIX.get(match.group(2) or "")) if part]
        return context.regions(",".join(options))

    return _LEGACY_REGIONS.sub(legacy, text)


def _environment(text: str, context: MacroContext) -> str:
    """`$env(NAME)` -- a shell variable, or empty if it is not set."""
    return _ENV.sub(lambda match: context.environment.get(match.group(1).strip(), ""), text)


def _pan(text: str, context: MacroContext) -> str:
    """`$pan` and `$pan(system,format)` -- where the frame is centred."""
    if context.pan is None:
        return _bare("pan").sub("", _PAN_CALL.sub("", text))

    def call(match: re.Match[str]) -> str:
        return context.pan(*_coordinate_options(match.group(1)))

    text = _PAN_CALL.sub(call, text)
    return _bare("pan").sub(lambda _m: context.pan("physical", "fk5", "degrees"), text)


def _coordinates(text: str, context: MacroContext) -> str:
    """`$x`, `$y`, `$z` and `$value` -- where a bind event happened."""
    if context.coordinate is not None:

        def call(match: re.Match[str]) -> str:
            axis = match.group(1)
            return context.coordinate(axis, *_coordinate_options(match.group(2)))

        text = _COORDINATE_CALL.sub(call, text)
        text = _COORDINATE_BARE.sub(
            lambda match: context.coordinate(match.group(1), "physical", "fk5", "degrees"), text
        )

    if context.value is not None:
        text = _bare("value").sub(lambda _m: context.value(), text)
    return text


def _coordinate_options(options: str) -> tuple[str, str, str]:
    """Read a coordinate macro's arguments into (system, sky, format).

    DS9 lets them appear in any order and leaves out what is not given, so
    each word is classified by what it is rather than by its position.
    """
    system, sky, sky_format = "physical", "fk5", "degrees"
    skies = {"fk4", "b1950", "fk5", "j2000", "icrs", "galactic", "ecliptic"}
    formats = {"hms", "sexagesimal", "degrees"}

    for raw in options.split(","):
        word = raw.strip().lower()
        if not word:
            continue
        if word in skies:
            sky = word
            if system == "physical":
                system = "wcs"
        elif word in formats:
            sky_format = "sexagesimal" if word == "hms" else word
        else:
            system = word
    return (system, sky, sky_format)


# -- prompts ------------------------------------------------------------------


def _file_dialog(text: str, context: MacroContext) -> str:
    """`$filedialog(open|save)` -- a path, or a cancelled command."""

    def call(match: re.Match[str]) -> str:
        kind = match.group(1).strip().lower() or "open"
        chosen = context.file_dialog(kind) if context.file_dialog else None
        if chosen is None:
            raise _Cancelled
        return chosen

    return _FILE_DIALOG.sub(call, text)


def _prompts(text: str, context: MacroContext) -> str:
    """`$message`, `$messageok`, `$entry` and `$param`, in DS9's order."""

    def message_ok(match: re.Match[str]) -> str:
        kind, body = _message_parts(match.group(1))
        answer = context.message_ok(kind, body) if context.message_ok else None
        if answer is None:
            raise _Cancelled
        return answer

    text = _MESSAGE_OK.sub(message_ok, text)

    def message(match: re.Match[str]) -> str:
        kind, body = _message_parts(match.group(1))
        proceed = context.message(kind, body) if context.message else True
        if not proceed:
            raise _Cancelled
        # The macro is removed; it says something, it is not something.
        return ""

    text = _MESSAGE.sub(message, text)

    def entry(match: re.Match[str]) -> str:
        answer = context.entry(match.group(1)) if context.entry else None
        if answer is None:
            raise _Cancelled
        return answer

    text = _ENTRY.sub(entry, text)
    return _parameters(text, context)


def _message_parts(argument: str) -> tuple[str, str]:
    """Split `[kind,]message` into its two halves.

    Only `ok`, `okcancel` and `yesno` are kinds; anything else is the start
    of the message, which may itself contain commas.
    """
    kinds = ("ok", "okcancel", "yesno")
    head, _, rest = argument.partition(",")
    if head.strip().lower() in kinds:
        return (head.strip().lower(), rest.strip())
    return ("ok", argument.strip())


def _parameters(text: str, context: MacroContext) -> str:
    """`$param(name)` -- run a parameter dialog and substitute its variables.

    The macro itself disappears; what it leaves behind are the `$var` names
    the dialog set, substituted into the rest of the line. DS9 puts the
    macro at the head of the command and separates it with `;`, which goes
    with it.
    """
    match = _PARAM.search(text)
    if match is None:
        return text

    values = context.parameters(match.group(1).strip()) if context.parameters else None
    if values is None:
        raise _Cancelled

    text = text[: match.start()] + text[match.end() :]
    text = text.lstrip().lstrip(";").lstrip()
    # Longest name first: `$var1` must not be eaten by a `$var` beside it.
    for name in sorted(values, key=len, reverse=True):
        text = _bare(re.escape(name)).sub(lambda _m, v=values[name]: v, text)
    return text


# -- sinks -----------------------------------------------------------------------


def _text_plot_null(text: str) -> tuple[str, Sinks]:
    """Take `$text`, `$plot` and `$null` off the line and read them."""
    sinks = Sinks()

    if _bare("text").search(text):
        # `|& $text` asks for stderr as well as stdout.
        sinks = replace(sinks, text=True, include_stderr="|&" in text)
        text = _bare("text").sub("", text)

    plot = _PLOT_CALL.search(text)
    if plot is not None:
        sinks = replace(sinks, plot=_plot_sink(plot.group(1)))
        text = text[: plot.start()] + text[plot.end() :]
    elif _bare("plot").search(text):
        sinks = replace(sinks, plot=PlotSink())
        text = _bare("plot").sub("", text)

    if _bare("null").search(text):
        sinks = replace(sinks, null=True)
        text = _bare("null").sub("", text)

    return (_tidy(text), sinks)


def _image(text: str) -> tuple[str, ImageSink | None]:
    """Take `$image` off the line. Last, as DS9 does it."""
    call = _IMAGE_CALL.search(text)
    if call is not None:
        target = call.group(1).strip().lower() or DEFAULT_IMAGE_TARGET
        return (_tidy(text[: call.start()] + text[call.end() :]), ImageSink(target=target))
    if _bare("image").search(text):
        return (_tidy(_bare("image").sub("", text)), ImageSink())
    return (text, None)


def _plot_sink(argument: str) -> PlotSink:
    """Read `$plot(title,x,y,dim)` or `$plot(stdin)`."""
    parts = [part.strip() for part in argument.split(",")]
    if parts and parts[0].lower() == "stdin":
        return PlotSink(from_stdin=True)

    dimensions = ("xy", "xyex", "xyey", "xyexey")
    dimension = DEFAULT_PLOT_DIMENSION
    if len(parts) > 3 and parts[3].lower() in dimensions:
        dimension = parts[3].lower()
    return PlotSink(
        title=parts[0] if parts else "",
        x_label=parts[1] if len(parts) > 1 else "",
        y_label=parts[2] if len(parts) > 2 else "",
        dimension=dimension,
    )


def _geturl(text: str) -> tuple[str, str | None]:
    """`$geturl(...)` -- fetch a URL instead of running a command."""
    match = _GETURL.search(text)
    if match is None:
        return (text, None)
    url = match.group(1).strip()
    return (_tidy(text[: match.start()] + text[match.end() :]), url)


def _url(text: str, context: MacroContext) -> str:
    """`$url(...)` -- DS9 downloads to a temporary file and pipes that in.

    Left as a `curl` here rather than downloading behind the user's back:
    the command line is what runs, and it should say what it does.
    """
    return _URL.sub(lambda match: f"curl -sL {match.group(1).strip()}", text)


def _tidy(text: str) -> str:
    """Clean up the pipes a removed sink leaves behind."""
    text = re.sub(r"\|&?\s*$", "", text.strip())
    text = re.sub(r"^\s*\|&?\s*", "", text)
    return re.sub(r"\s{2,}", " ", text).strip()
