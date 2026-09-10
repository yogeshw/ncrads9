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
DS9's analysis description files -- `.ds9.ans`, `ds9.analysis`, `*.ds9`.

An analysis file is a list of four-line task blocks:

    Menu label to be used
    A space separated list of file templates
    Command type [menu | bind <event> | button | web]
    The command line for the analysis program

around which a handful of keywords build structure: `---` inserts a
separator, `hmenu <label>` ... `endhmenu` nests a submenu, `help <label>`
... `endhelp` defines a help text, `buttonbar` ... `endbuttonbar` groups
button tasks, and `param <name>` ... `endparam` declares a parameter dialog
the command line can call up with `$param(<name>)`.

The state machine here is DS9's, from `ProcessAnalysis` in
`ds9/library/analysis.tcl:212`, including the parts that are easy to get
wrong by reading only the documentation:

  - a `#` anywhere but the first column truncates the line, so a label may
    carry a trailing comment;
  - help text is the exception: inside `help` ... `endhelp` nothing is
    stripped and blank lines are kept, because they are the message;
  - `end` closes an `hmenu`, a `param` or a `help` -- each block's own
    `endhmenu`/`endparam`/`endhelp` is the spelt-out form;
  - a block is only registered when all four of its lines are non-empty;
  - an unrecognised command type aborts the whole file, which is DS9's
    `return 0`. Half-loading a file whose structure was misread would put
    tasks under the wrong menus.

Parameter lines are Tcl lists, so `{Variable 1}` is one word. `tcl_split`
does that much of Tcl's grammar and no more.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

#: The keyword that inserts a menu separator.
SEPARATOR = "---"

#: The closing keyword every block also accepts.
GENERIC_END = "end"

#: What an `hmenu` with no label is called, as DS9 names it.
DEFAULT_HMENU_LABEL = "Tasks"

#: What a `help` with no label is called.
DEFAULT_HELP_LABEL = "Help"


class TaskFileError(ValueError):
    """An analysis file that cannot be read, for the reason given."""


class TaskType(Enum):
    """The four command types DS9's third line accepts, plus help."""

    MENU = "menu"
    BIND = "bind"
    BUTTON = "button"
    WEB = "web"
    #: Not a command type in the file; the shape a `help` block takes here.
    HELP = "help"


@dataclass(frozen=True)
class Parameter:
    """One row of a `param` block.

    Attributes:
        variable: The name the command line refers to, as `$<variable>`.
        kind: entry, text, checkbox, menu, combobox, open or save.
        title: The label shown beside the field.
        default: Its initial value. For a menu or combobox this is the whole
            `AAA|BBB|CCC` list, whose first entry is the initial value.
        comment: The hint shown after the field.
    """

    variable: str
    kind: str
    title: str = ""
    default: str = ""
    comment: str = ""

    @property
    def choices(self) -> tuple[str, ...]:
        """The options a menu or combobox offers."""
        if self.kind not in ("menu", "combobox"):
            return ()
        return tuple(part for part in self.default.split("|") if part)

    @property
    def initial(self) -> str:
        """The value the field starts at."""
        choices = self.choices
        return choices[0] if choices else self.default


@dataclass(frozen=True)
class ParameterTab:
    """One `tab` of a parameter dialog, or the whole of an untabbed one."""

    title: str = ""
    parameters: tuple[Parameter, ...] = ()


@dataclass(frozen=True)
class ParameterSet:
    """A named `param` block, which `$param(<name>)` calls up."""

    name: str
    tabs: tuple[ParameterTab, ...] = ()
    #: An IRAF parameter file named with `@`, which DS9 reads instead.
    iraf_file: str | None = None

    @property
    def parameters(self) -> tuple[Parameter, ...]:
        """Every parameter, across every tab, in order."""
        return tuple(entry for tab in self.tabs for entry in tab.parameters)


@dataclass(frozen=True)
class Task:
    """One analysis task: what to show, when to offer it, what to run.

    Attributes:
        label: The menu entry, button face, or help title.
        templates: The file patterns the task applies to, e.g. `("*.fits",)`.
            `("*",)` means any file.
        task_type: Which of DS9's four types, or HELP.
        command: The command line, before macro expansion. For a `web` task
            this is the URL; for a HELP task it is the message.
        event: The key a `bind` task is bound to; empty otherwise.
        directory: The directory the file was found in, which `$dir`
            expands to and which DS9 also puts on PATH.
    """

    label: str
    templates: tuple[str, ...]
    task_type: TaskType
    command: str
    event: str = ""
    directory: str = ""

    def applies_to(self, filename: str | None) -> bool:
        """Whether this task is offered for a given file.

        A task with no file loaded is offered only if one of its templates
        is the catch-all, which is what DS9 does: a task declared for
        `*.fits` has nothing to run against.
        """
        from fnmatch import fnmatch

        name = Path(filename).name if filename else ""
        for template in self.templates:
            if template in ("*", "*.*"):
                return True
            if name and fnmatch(name, template):
                return True
        return False


@dataclass
class MenuNode:
    """A menu, holding tasks, separators and submenus in file order.

    Attributes:
        label: The cascade's label. Empty for the root.
        entries: Tasks, nested `MenuNode`s, and `None` for a separator.
    """

    label: str = ""
    entries: list[Task | MenuNode | None] = field(default_factory=list)

    def tasks(self) -> list[Task]:
        """Every task in this menu and below it, in order."""
        found: list[Task] = []
        for entry in self.entries:
            if isinstance(entry, Task):
                found.append(entry)
            elif isinstance(entry, MenuNode):
                found.extend(entry.tasks())
        return found


@dataclass
class AnalysisFile:
    """Everything one analysis file declares.

    Attributes:
        menu: The tree of menu entries.
        binds: The `bind` tasks, which are not on any menu.
        buttonbars: Each `buttonbar` block's tasks, in order.
        parameters: The `param` blocks, by name.
        directory: Where the file was read from.
    """

    menu: MenuNode = field(default_factory=MenuNode)
    binds: list[Task] = field(default_factory=list)
    buttonbars: list[list[Task]] = field(default_factory=list)
    parameters: dict[str, ParameterSet] = field(default_factory=dict)
    directory: str = ""

    def tasks(self) -> list[Task]:
        """Every task the file declares, menus and binds and buttons."""
        return [
            *self.menu.tasks(),
            *self.binds,
            *(task for bar in self.buttonbars for task in bar),
        ]


def tcl_split(line: str) -> list[str]:
    """Split a line into words the way Tcl's list parser does.

    Enough of Tcl for a `param` row: whitespace separates words, `{...}`
    and `"..."` group one, and braces nest. Anything cleverer -- backslash
    escapes, command substitution -- is not in these files.
    """
    words: list[str] = []
    current: list[str] = []
    depth = 0
    quoted = False
    started = False

    for character in line:
        if depth:
            if character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    continue
            current.append(character)
            continue

        if quoted:
            if character == '"':
                quoted = False
                continue
            current.append(character)
            continue

        if character == "{" and not current and not started:
            depth = 1
            started = True
            continue
        if character == '"' and not current and not started:
            quoted = True
            started = True
            continue
        if character.isspace():
            if current or started:
                words.append("".join(current))
                current = []
                started = False
            continue
        current.append(character)
        started = True

    if current or started:
        words.append("".join(current))
    return words


def _strip_comment(line: str) -> str:
    """Cut a line at its first `#`.

    DS9's rule (`analysis.tcl:243`) is in two halves: a line beginning with
    `#` is dropped entirely -- the caller does that -- and a `#` anywhere
    else truncates, which is what lets its own sample file write
    `Test escape char # this is a comment` as a task label.
    """
    position = line.find("#")
    return line if position <= 0 else line[:position].rstrip()


def _keyword(line: str) -> str:
    """The first word of a line, lowercased."""
    words = line.split(None, 1)
    return words[0].lower() if words else ""


def _label_after(line: str, default: str) -> str:
    """The rest of a `hmenu`/`help` line, which may contain spaces."""
    position = line.find(" ")
    return line[position + 1 :].strip() if position > 0 else default


class _Parser:
    """DS9's `ProcessAnalysis` state machine, one method per state."""

    def __init__(self, directory: str) -> None:
        self.directory = directory
        self.result = AnalysisFile(directory=directory)
        self.stack: list[MenuNode] = [self.result.menu]

        # The block being read, when one is open.
        self._block: list[str] = []
        # The buttonbar being filled, when one is open.
        self._buttonbar: list[Task] | None = None
        # The parameter set being read, and its tabs.
        self._param_name: str = ""
        self._param_tabs: list[ParameterTab] = []
        self._param_rows: list[Parameter] = []
        self._param_tab_title: str = ""
        self._param_iraf: str | None = None
        # The help block being read.
        self._help_label: str = ""
        self._help_lines: list[str] = []

        self.state = "top"

    @property
    def parent(self) -> MenuNode:
        """The menu new entries are added to."""
        return self.stack[-1]

    def parse(self, text: str) -> AnalysisFile:
        """Read the whole file.

        Raises:
            TaskFileError: If a task declares a command type DS9 does not
                know, which is where DS9 abandons the file.
        """
        for raw in text.splitlines():
            if self.state == "help":
                self._help_line(raw)
                continue

            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            line = _strip_comment(line)
            if not line:
                continue

            if self.state == "param":
                self._param_line(line)
            elif self.state == "top":
                self._top_line(line)
            else:
                self._block_line(line)

        self._finish()
        return self.result

    # -- the top level -----------------------------------------------------

    def _top_line(self, line: str) -> None:
        """Either a structural keyword, or the first line of a task."""
        keyword = _keyword(line)

        if keyword == "param":
            words = tcl_split(line)
            if len(words) > 1:
                self._open_param(words[1])
            return
        if keyword == "help":
            self._help_label = _label_after(line, DEFAULT_HELP_LABEL)
            self._help_lines = []
            self.state = "help"
            return
        if keyword == "hmenu":
            node = MenuNode(label=_label_after(line, DEFAULT_HMENU_LABEL))
            self.parent.entries.append(node)
            self.stack.append(node)
            return
        if keyword in ("endhmenu", GENERIC_END):
            if len(self.stack) > 1:
                self.stack.pop()
            return
        if keyword == "buttonbar":
            self._buttonbar = []
            return
        if keyword == "endbuttonbar":
            if self._buttonbar:
                self.result.buttonbars.append(self._buttonbar)
            self._buttonbar = None
            return
        if line == SEPARATOR:
            self.parent.entries.append(None)
            return

        # Anything else opens a task block, this line being its label.
        self._block = [line]
        self.state = "block"

    def _block_line(self, line: str) -> None:
        """The second, third and fourth lines of a task."""
        self._block.append(line)
        if len(self._block) < 4:
            return
        label, templates, type_line, command = self._block
        self._block = []
        self.state = "top"
        self._add_task(label, templates, type_line, command)

    def _add_task(self, label: str, templates: str, type_line: str, command: str) -> None:
        """Register one finished block.

        Raises:
            TaskFileError: If the command type is not one DS9 knows.
        """
        if not (label and templates and type_line and command):
            return

        words = type_line.split()
        name = words[0].lower()
        try:
            task_type = TaskType(name)
        except ValueError as exc:
            raise TaskFileError(f"unknown analysis command type {words[0]!r} for task {label!r}") from exc
        if task_type is TaskType.HELP:
            raise TaskFileError(f"'help' is a block, not a command type, in task {label!r}")

        task = Task(
            label=label,
            templates=tuple(templates.split()),
            task_type=task_type,
            command=command,
            event=words[1] if task_type is TaskType.BIND and len(words) > 1 else "",
            directory=self.directory,
        )

        if task_type is TaskType.BIND:
            # A bind with no key binds to nothing, so DS9 drops it.
            if task.event:
                self.result.binds.append(task)
        elif task_type is TaskType.BUTTON:
            if self._buttonbar is None:
                # A button outside a buttonbar has no bar to go on; DS9
                # collects it into the pending one, so open one implicitly.
                self._buttonbar = []
            self._buttonbar.append(task)
        else:
            self.parent.entries.append(task)

    # -- help --------------------------------------------------------------

    def _help_line(self, raw: str) -> None:
        """A line of help text, kept exactly as written until `endhelp`."""
        if _keyword(raw.strip()) in ("endhelp", GENERIC_END):
            self.parent.entries.append(
                Task(
                    label=self._help_label,
                    templates=("*",),
                    task_type=TaskType.HELP,
                    command="\n".join(self._help_lines).strip("\n"),
                    directory=self.directory,
                )
            )
            self._help_lines = []
            self.state = "top"
            return
        self._help_lines.append(raw.rstrip())

    # -- parameters ----------------------------------------------------------

    def _open_param(self, name: str) -> None:
        """Start a `param` block."""
        self._param_name = name
        self._param_tabs = []
        self._param_rows = []
        self._param_tab_title = ""
        self._param_iraf = None
        self.state = "param"

    def _param_line(self, line: str) -> None:
        """One row of a parameter block, or a keyword closing part of it."""
        if line.startswith("@"):
            self._param_iraf = line[1:].strip()
            return

        keyword = _keyword(line)
        if keyword == "tab":
            self._close_tab()
            words = tcl_split(line)
            self._param_tab_title = words[1] if len(words) > 1 else ""
            return
        if keyword == "endtab":
            self._close_tab()
            return
        if keyword in ("endparam", GENERIC_END):
            self._close_tab()
            self.result.parameters[self._param_name] = ParameterSet(
                name=self._param_name,
                tabs=tuple(self._param_tabs),
                iraf_file=self._param_iraf,
            )
            self.state = "top"
            return

        words = tcl_split(line)
        if len(words) < 2:
            return
        self._param_rows.append(
            Parameter(
                variable=words[0],
                kind=words[1].lower(),
                title=words[2] if len(words) > 2 else words[0],
                default=words[3] if len(words) > 3 else "",
                comment=words[4] if len(words) > 4 else "",
            )
        )

    def _close_tab(self) -> None:
        """Bank the rows read so far as one tab."""
        if not self._param_rows and not self._param_tab_title:
            return
        self._param_tabs.append(ParameterTab(title=self._param_tab_title, parameters=tuple(self._param_rows)))
        self._param_rows = []
        self._param_tab_title = ""

    def _finish(self) -> None:
        """Close anything the file left open.

        A file that ends mid-block is not an error: DS9 simply never
        registers the unfinished task, and the rest of the file has already
        been read.
        """
        if self.state == "param":
            self._close_tab()
            self.result.parameters[self._param_name] = ParameterSet(
                name=self._param_name,
                tabs=tuple(self._param_tabs),
                iraf_file=self._param_iraf,
            )
        elif self.state == "help":
            self.parent.entries.append(
                Task(
                    label=self._help_label,
                    templates=("*",),
                    task_type=TaskType.HELP,
                    command="\n".join(self._help_lines).strip("\n"),
                    directory=self.directory,
                )
            )
        if self._buttonbar:
            self.result.buttonbars.append(self._buttonbar)


def parse(text: str, directory: str = "") -> AnalysisFile:
    """Read an analysis description.

    Args:
        text: The file's contents.
        directory: Where it came from, which `$dir` expands to.

    Returns:
        Everything it declares.

    Raises:
        TaskFileError: If a task names a command type DS9 does not know.
    """
    return _Parser(directory).parse(text)


def parse_file(path: str | Path) -> AnalysisFile:
    """Read an analysis file from disk.

    Raises:
        TaskFileError: If it cannot be parsed.
        OSError: If it cannot be read.
    """
    location = Path(path)
    return parse(location.read_text(encoding="utf-8", errors="replace"), str(location.parent))
