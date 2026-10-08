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
Reading SAOImageDS9's own backup files.

A DS9 backup (`backup.tcl`) is a Tcl script that rebuilds a session by
being evaluated: `CreateNameNumberFrame Frame1 base`, then the load
(`array set loadParam [list file,name ... ]` and `ProcessLoad`), then one
line per setting written by each subsystem's `*Backup` procedure --
`Frame1 colorscale log`, `Frame1 zoom to 2 2`, `Frame1cb colorbar 13 0.5 1
0` -- and finally the GUI's own arrays (`array set current {...}`).

It is not evaluated here. A backup is a data file that arrives by email as
readily as any other, and running one as code would run whatever it
contains. Instead the script is split into Tcl words, and each command
this module recognises is translated into the XPA command that does the
same thing; everything else is reported and skipped. The XPA grammar is
the one the rest of NCRADS9 is tested against, so a restored session goes
through the same code a script would.

The frame-widget commands are tksao's (`tksao/frame/parser.Y`); their
arguments are the replies of the matching `get` commands, which is how the
backup writes them -- `zoom to` takes "2 2", a colorbar line takes the
colormap's *number*, in the order DS9 creates its colormaps.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

#: DS9's colormaps by the number its colorbar gives them: the eighteen
#: built-ins of `Colorbar::loadDefaultCmaps`, then the bundled groups in
#: the order `colorbar.tcl` preloads them, counting from one.
COLORMAP_IDS: tuple[str, ...] = (
    "grey", "red", "green", "blue", "a", "b",
    "bb", "he", "i8", "aips0", "sls", "hsv",
    "heat", "cool", "rainbow", "standard", "staircase", "color",
    "h5_autumn", "h5_bluered", "h5_bone", "h5_cool", "h5_copper", "h5_dkbluered",
    "h5_gray", "h5_green", "h5_hot", "h5_hsv", "h5_jet", "h5_pink",
    "h5_spring", "h5_summer", "h5_winter", "h5_yarg", "h5_yellow", "viridis",
    "ch05m151008", "ch05m151010", "ch05m151012", "ch05m151410", "ch05p151010", "ch20m151010",
    "cubehelix0", "cubehelix1", "gist_earth", "gist_heat", "gist_rainbow", "gist_yarg",
    "gist_gray", "gist_ncar", "gist_stern", "tpglarf", "tpglhcf", "tpglhwf",
    "tpglpof", "tpglarm", "tpglhcm", "tpglhwm", "tpglpom", "inferno",
    "magma", "plasma", "twilight", "turbo", "scm_acton", "scm_bam",
    "scm_bamO", "scm_bamako", "scm_batlow", "scm_batlowK", "scm_batlowW", "scm_berlin",
    "scm_bilbao", "scm_broc", "scm_brocO", "scm_buda", "scm_bukavu", "scm_cork",
    "scm_corkO", "scm_davos", "scm_devon", "scm_fes", "scm_glasgow", "scm_greyC",
    "scm_hawaii", "scm_imola", "scm_lajolla", "scm_lapaz", "scm_lipari", "scm_lisbon",
    "scm_managua", "scm_navia", "scm_nuuk", "scm_oleron", "scm_oslo", "scm_roma",
    "scm_romaO", "scm_tofino", "scm_tokyo", "scm_turku", "scm_vanimo", "scm_vik",
    "scm_vikO", "mpl_viridis", "mpl_plasma", "mpl_inferno", "mpl_magma", "mpl_cividis",
    "mpl_Greys", "mpl_Purples", "mpl_Blues", "mpl_Greens", "mpl_Oranges", "mpl_Reds",
    "mpl_YlOrBr", "mpl_YlOrRd", "mpl_OrRd", "mpl_PuRd", "mpl_RdPu", "mpl_BuPu",
    "mpl_GnBu", "mpl_PuBu", "mpl_YlGnBu", "mpl_PuBuGn", "mpl_BuGn", "mpl_YlGn",
    "mpl_PiYG", "mpl_PRGn", "mpl_BrBG", "mpl_PuOr", "mpl_RdGy", "mpl_RdBu",
    "mpl_RdYlBu", "mpl_RdYlGn", "mpl_coolwarm", "mpl_bwr", "mpl_seismic", "mpl_twilight",
    "mpl_hsv", "solar_soho_171", "solar_soho_195", "solar_soho_284", "solar_soho_304", "solar_soho_lasco2",
    "solar_soho_lasco3", "solar_sdo_94", "solar_sdo_131", "solar_sdo_171", "solar_sdo_193", "solar_sdo_211",
    "solar_sdo_304", "solar_sdo_335", "solar_sdo_1600", "solar_sdo_1700", "solar_sdo_4500", "solar_stereo_171",
    "solar_stereo_195", "solar_stereo_284", "solar_stereo_304", "solar_stereo_cor1", "solar_stereo_cor2", "solar_stereo_hi1",
    "solar_stereo_hi2", "solar_trace_171", "solar_trace_195", "solar_trace_284", "solar_trace_1216", "solar_trace_1550",
    "solar_trace_1600", "solar_trace_1700", "solar_iris_1330", "solar_iris_1400", "solar_iris_1600", "solar_iris_2796",
    "solar_iris_2832", "solar_iris_5000", "solar_sdo_hmi_color", "solar_yohkoh_sxt", "solar_rhessi", "solar_solo_lya1216",
)

#: A frame widget's name, `Frame12`, and the colorbar that goes with it.
_FRAME = re.compile(r"^Frame(\d+)(cb)?$")


class DS9BackupError(ValueError):
    """A file that is not a DS9 backup, or cannot be read as one."""


@dataclass
class Step:
    """One thing to do to restore the session.

    Attributes:
        kind: "frame" to make a frame, "xpa" to run an XPA command on a
            frame, "load" for one that reads the file named last, "gui"
            for a command on no particular frame.
        frame: The frame's number, or None.
        words: For "frame", the frame type; otherwise the XPA command and
            its arguments.
    """

    kind: str
    frame: int | None
    words: list[str]


@dataclass
class DS9Backup:
    """A DS9 backup, translated."""

    steps: list[Step] = field(default_factory=list)
    #: The frame that was current when the backup was made.
    current_frame: int | None = None
    #: What could not be translated, one line each.
    skipped: list[str] = field(default_factory=list)
    #: The backup's notes, DS9's `ds9notes`.
    notes: str = ""


# -- Tcl words ---------------------------------------------------------------------


def is_ds9_backup(path: str | Path) -> bool:
    """Whether a file is one of DS9's Tcl backups rather than one of ours."""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            head = handle.read(512)
    except OSError:
        return False
    return head.lstrip().startswith("global ds9") or "CreateNameNumberFrame" in head


def commands(script: str) -> list[list[str]]:
    """Split a Tcl script into commands, each a list of words.

    Enough of Tcl's rules for what DS9 writes: words separated by blanks,
    commands by newlines and semicolons, `{...}` and `"..."` grouping,
    `[...]` kept whole, `#` comments, and backslash-newline continuation.
    A braced word keeps its contents verbatim; a quoted one loses its
    quotes. Nothing is substituted.
    """
    script = script.replace("\\\n", " ")
    result: list[list[str]] = []
    words: list[str] = []
    i, n = 0, len(script)

    def end_command() -> None:
        nonlocal words
        if words:
            result.append(words)
        words = []

    while i < n:
        c = script[i]
        if c in " \t\r":
            i += 1
            continue
        if c in "\n;":
            end_command()
            i += 1
            continue
        if c == "#" and not words:
            while i < n and script[i] != "\n":
                i += 1
            continue
        if c == "{":
            depth, j = 1, i + 1
            while j < n and depth:
                if script[j] == "\\":
                    j += 2
                    continue
                if script[j] == "{":
                    depth += 1
                elif script[j] == "}":
                    depth -= 1
                j += 1
            words.append(script[i + 1 : j - 1])
            i = j
            continue
        if c == '"':
            j = i + 1
            chars = []
            while j < n and script[j] != '"':
                if script[j] == "\\" and j + 1 < n:
                    chars.append(script[j + 1])
                    j += 2
                    continue
                chars.append(script[j])
                j += 1
            words.append("".join(chars))
            i = j + 1
            continue
        # A bare word, which may contain a bracketed substitution.
        j = i
        depth = 0
        while j < n:
            ch = script[j]
            if ch == "\\" and j + 1 < n:
                j += 2
                continue
            if ch == "[":
                depth += 1
            elif ch == "]" and depth:
                depth -= 1
            elif depth == 0 and ch in " \t\r\n;":
                break
            j += 1
        words.append(script[i:j])
        i = j
    end_command()
    return result


def words(text: str) -> list[str]:
    """One Tcl list, as its elements: `{a b} c` is ["a b", "c"]."""
    found = commands(text.replace("\n", " "))
    return found[0] if found else []


def pairs(text: str) -> dict[str, str]:
    """A Tcl `array get` list as a dict."""
    items = words(text)
    if len(items) == 1 and " " in items[0].strip():
        items = words(items[0])
    return {items[k]: items[k + 1] for k in range(0, len(items) - 1, 2)}


def _unquote(word: str) -> str:
    """`{"x"}` and `"x"` are how the backup quotes a value; this is x."""
    word = word.strip()
    if len(word) >= 2 and word[0] == word[-1] == '"':
        return word[1:-1]
    return word


def _yes(word: str) -> str:
    return "yes" if word.strip() not in ("0", "", "no", "false") else "no"


# -- translation ---------------------------------------------------------------------

#: `clip mode` words that are not a percentile.
_CLIP_MODES = {"minmax", "zscale", "zmax", "user"}

#: `ProcessLoad` file modes and the XPA point that loads each.
_LOAD_POINTS = {
    "rgb image": "rgbimage",
    "rgb cube": "rgbcube",
    "hsv image": "hsvimage",
    "hsv cube": "hsvcube",
    "hls image": "hlsimage",
    "hls cube": "hlscube",
    "ext cube": "mecube",
    "mosaic wcs": "mosaicimagewcs",
    "mosaic image wcs": "mosaicimagewcs",
    "mosaic iraf": "mosaicimageiraf",
    "mosaic image iraf": "mosaicimageiraf",
    "mosaic wfpc2": "mosaicimagewfpc2",
    "mosaic image wfpc2": "mosaicimagewfpc2",
}

#: Picture formats, by suffix, for a `photo` load.
_PHOTO_POINTS = {".gif": "gif", ".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".tif": "tiff", ".tiff": "tiff"}

#: Commands that build DS9's own windows or redraw its canvas; restoring
#: the state they show is what the other lines do.
_IGNORED = {
    "global",
    "set",
    "switch",
    "proc",
    "update",
    "RealizeDS9",
    "RGBDialog",
    "HSVDialog",
    "HLSDialog",
    "3DDialog",
    "CubeDialog",
    "MaskDialog",
    "LayoutView",
    "UpdateDS9",
    "image",
}


class _Translator:
    def __init__(self, base: Path) -> None:
        self.base = base
        self.backup = DS9Backup()
        self.load_params: dict[str, str] = {}
        #: `clip user`'s limits, which apply only if `clip mode user` follows.
        self.user_limits: tuple[str, str] | None = None

    # Paths in a backup are relative to the backup's own directory, which
    # DS9 changes into before evaluating it.
    def path(self, name: str) -> str:
        name = _unquote(name)
        spec = ""
        if "[" in name and not Path(name).exists():
            name, spec = name[: name.index("[")], name[name.index("[") :]
        candidate = Path(name)
        if not candidate.is_absolute():
            candidate = (self.base / candidate).resolve()
        return f"{candidate}{spec}"

    def xpa(self, frame: int | None, *command: str) -> None:
        self.backup.steps.append(Step("xpa", frame, [str(word) for word in command]))

    def load(self, frame: int | None, *command: str) -> None:
        """A step that reads a file, the last word: checked before it runs."""
        self.backup.steps.append(Step("load", frame, [str(word) for word in command]))

    def gui(self, *command: str) -> None:
        self.backup.steps.append(Step("gui", None, [str(word) for word in command]))

    def skip(self, command: list[str]) -> None:
        self.backup.skipped.append(" ".join(command)[:120])

    # -- the commands ----------------------------------------------------------

    def run(self, script: str) -> DS9Backup:
        for command in commands(script):
            head = command[0]
            match = _FRAME.match(head)
            if match:
                frame = int(match.group(1))
                handled = (self.colorbar if match.group(2) else self.frame_command)(frame, command[1:])
                if not handled:
                    self.skip(command)
                continue
            handler = getattr(self, f"cmd_{head.replace('-', '_')}", None)
            if handler is not None:
                handler(command[1:])
            elif head in _IGNORED:
                if head == "set" and len(command) == 3 and command[1] == "ds9notes":
                    self.backup.notes = command[2]
            else:
                self.skip(command)
        return self.backup

    def cmd_if(self, args: list[str]) -> None:
        # `if [BackupFindFile loadParam] { ProcessLoad }` is how every load
        # is written; the file check is made when the load runs. Any other
        # condition is DS9 asking itself something, and is not followed.
        if len(args) >= 2 and "BackupFindFile" in args[0]:
            self.run(args[1])

    def cmd_CreateNameNumberFrame(self, args: list[str]) -> None:
        match = _FRAME.match(args[0]) if args else None
        if match:
            kind = args[1] if len(args) > 1 else "base"
            self.backup.steps.append(Step("frame", int(match.group(1)), [kind]))

    def cmd_array(self, args: list[str]) -> None:
        if len(args) < 3 or args[0] != "set":
            return
        name, body = args[1], args[2]
        if body.startswith("[list ") and body.endswith("]"):
            body = body[6:-1]
        values = pairs(body)
        if name == "loadParam":
            self.load_params = values
        elif name == "current":
            self.current(values)
        elif name == "view":
            self.view(values)
        elif name == "tile":
            if values.get("mode"):
                self.gui("tile", "mode", values["mode"])
        elif name == "blink":
            if values.get("interval"):
                self.gui("blink", "interval", str(float(values["interval"]) / 1000.0))

    def cmd_ProcessLoad(self, _args: list[str]) -> None:
        params, self.load_params = self.load_params, {}
        frame = self.last_frame()
        name = params.get("file,name", "")
        if not name:
            self.backup.skipped.append("ProcessLoad with no file name")
            return
        path = self.path(name)
        mode = params.get("file,mode", "")
        kind = params.get("file,type", "fits")
        if params.get("load,layer") == "mask":
            self.load(frame, "mask", "load", path)
        elif mode in _LOAD_POINTS:
            self.load(frame, _LOAD_POINTS[mode], path)
        elif kind == "photo":
            self.load(frame, _PHOTO_POINTS.get(Path(path.split("[")[0]).suffix.lower(), "png"), path)
        elif kind in ("array", "nrrd", "envi"):
            self.load(frame, kind, path)
        else:
            self.load(frame, "fits", path)

    def cmd_LoadColormapFile(self, args: list[str]) -> None:
        if args:
            self.gui("cmap", "load", self.path(args[0]))

    def cmd_colorbar(self, args: list[str]) -> None:
        # `colorbar configure -size 20`, and the rest of DS9's options.
        if len(args) >= 3 and args[0] == "configure":
            option, value = args[1].lstrip("-"), args[2]
            if option in ("numerics",):
                value = _yes(value)
            self.gui("colorbar", option, value)

    def cmd_panner(self, args: list[str]) -> None:
        if len(args) >= 2 and args[0] == "compass":
            self.gui("panner", "compass", _yes(args[1]))

    def last_frame(self) -> int | None:
        for step in reversed(self.backup.steps):
            if step.kind == "frame":
                return step.frame
        return None

    # -- GUI arrays ------------------------------------------------------------

    def current(self, values: dict[str, str]) -> None:
        match = _FRAME.match(values.get("frame", ""))
        if match:
            self.backup.current_frame = int(match.group(1))
        display = values.get("display")
        if display in ("single", "tile", "blink", "fade"):
            self.gui(display) if display == "single" else self.gui(display, "yes")
        mode = values.get("mode")
        if mode:
            self.gui("mode", mode)

    def view(self, values: dict[str, str]) -> None:
        if values.get("layout") in ("horizontal", "vertical"):
            self.gui("view", "layout", values["layout"])
        for key in ("info", "panner", "magnifier", "buttons", "colorbar"):
            if key in values:
                self.gui("view", key, _yes(values[key]))
        for key, axis in (("graph,horz", "horizontal"), ("graph,vert", "vertical")):
            if key in values:
                self.gui("view", "graph", axis, _yes(values[key]))

    # -- one frame's settings --------------------------------------------------

    def colorbar(self, frame: int, args: list[str]) -> bool:
        """`Frame1cb colorbar <id> <bias> <contrast> <invert>`."""
        if not args or args[0] != "colorbar":
            return args[:1] == ["tag"]
        values = args[1:]
        if len(values) == 1:
            values = words(values[0])
        if values and values[0] in ("rgb", "hsv", "hls"):
            # A colour frame keeps a bias and a contrast per channel; the
            # first channel's stand for all three.
            if len(values) >= 8:
                self.xpa(frame, "cmap", "value", values[4], values[1])
                self.xpa(frame, "cmap", "invert", _yes(values[7]))
            return True
        if len(values) < 4:
            return False
        try:
            name = COLORMAP_IDS[int(values[0]) - 1]
        except (ValueError, IndexError):
            # A user colormap, loaded with LoadColormapFile: its number is
            # past the bundled ones and its name is in the GUI's arrays.
            name = None
        if name is not None:
            self.xpa(frame, "cmap", name)
        self.xpa(frame, "cmap", "value", values[2], values[1])
        self.xpa(frame, "cmap", "invert", _yes(values[3]))
        return True

    def frame_command(self, frame: int, args: list[str]) -> bool:
        if not args:
            return False
        verb, rest = args[0], args[1:]
        x = lambda *command: self.xpa(frame, *command)  # noqa: E731

        if verb == "colormap":
            return True  # the colorbar line carries the colormap
        if verb == "magnifier" and len(rest) >= 2:
            key = {"graphics": "region"}.get(rest[0], rest[0])
            value = _yes(rest[1]) if key in ("region", "cursor") else rest[1]
            x("magnifier", key, value)
            return True
        if verb == "colorscale":
            if rest[:1] == ["log"] and len(rest) > 1:
                x("scale", "log", "exp", rest[1])
            elif rest:
                x("scale", rest[0])
            return True
        if verb == "datasec" and rest:
            x("scale", "datasec", _yes(rest[0]))
            return True
        if verb == "clip":
            return self.clip(frame, rest)
        if verb == "block" and rest[:1] == ["to"] and len(rest) > 1:
            x("block", rest[1])
            return True
        if verb == "bin":
            return self.bin(frame, rest)
        if verb == "pan":
            if rest[:2] == ["to", "physical"] and len(rest) >= 4:
                x("pan", "to", rest[2], rest[3], "physical")
            return True  # `pan preserve` has no counterpart worth restoring
        if verb == "zoom" and rest[:1] == ["to"] and len(rest) > 1:
            x("zoom", "to", rest[1])
            return True
        if verb == "rotate" and rest[:1] == ["to"] and len(rest) > 1:
            x("rotate", "to", rest[1])
            return True
        if verb == "orient" and rest:
            x("orient", rest[0])
            return True
        if verb == "wcs":
            if rest[:1] == ["align"] and len(rest) > 1:
                x("wcs", "align", _yes(rest[1]))
                return True
            if len(rest) >= 3 and rest[0] not in ("replace", "append", "reset"):
                x("wcs", rest[0], rest[1], rest[2])
                return True
            return False
        if verb == "crop":
            if rest[:1] == ["3d"] and len(rest) >= 3:
                x("crop", "3d", rest[1], rest[2], *(rest[3:4] or ["image"]))
            elif len(rest) >= 5:
                x("crop", *rest[:4], rest[4])
            return True
        if verb == "cube" and rest[:1] == ["axes"] and len(rest) > 1:
            # The backup's `cube axes` is XPA's `cube order`; DS9 writes it
            # for every frame, cube or not, so the default is not restored.
            if rest[1] != "123":
                x("cube", "order", rest[1])
            return True
        if verb == "update" and rest[:2] == ["fits", "slice"] and len(rest) > 2:
            x("cube", words(" ".join(rest[2:]))[0])
            return True
        if verb == "marker":
            if rest[:1] == ["load"] and len(rest) >= 3:
                x("regions", "load", self.path(rest[-1]))
                return True
            if rest[:1] == ["centroid"] and len(rest) >= 3:
                x("regions", "centroid", rest[1], rest[2])
                return True
            return False
        if verb == "crosshair" and len(rest) >= 3:
            x("crosshair", rest[1], rest[2], rest[0])
            return True
        if verb == "mask" and len(rest) >= 2:
            x("mask", *rest)
            return True
        if verb == "smooth" and len(rest) >= 6:
            function, radius, radius_minor, sigma, sigma_minor, angle = rest[:6]
            x("smooth", "function", function)
            x("smooth", "radius", radius)
            x("smooth", "radiusminor", radius_minor)
            x("smooth", "sigma", sigma)
            x("smooth", "sigmaminor", sigma_minor)
            x("smooth", "angle", angle)
            x("smooth", "yes")
            return True
        if verb == "contour":
            return self.contour(frame, rest)
        if verb == "grid" and rest[:1] == ["create"] and len(rest) >= 5:
            system, sky, sky_format, kind = rest[1:5]
            x("grid", "yes")
            x("grid", "system", system)
            x("grid", "sky", sky)
            x("grid", "skyformat", sky_format)
            x("grid", "type", kind)
            return True
        if verb in ("rgb", "hsv", "hls") and rest:
            if rest[0] == "channel" and len(rest) > 1:
                x(verb, "channel", rest[1])
            elif rest[0] == "view" and len(rest) >= 4:
                channels = {"rgb": ("red", "green", "blue"), "hsv": ("hue", "saturation", "value"), "hls": ("hue", "lightness", "saturation")}[verb]
                for channel, shown in zip(channels, rest[1:4], strict=False):
                    x(verb, "view", channel, _yes(shown))
            elif rest[0] == "system" and len(rest) > 1:
                x(verb, "system", rest[1])
            else:
                return False
            return True
        if verb == "3d" and rest:
            if rest[:2] == ["view", "point"]:
                return True
            x("3d", *rest)
            return True
        if verb == "colorbar":
            return rest[:1] == ["tag"]
        return False

    def clip(self, frame: int, rest: list[str]) -> bool:
        if rest[:1] == ["user"] and len(rest) >= 3:
            # The user limits are stored whatever the mode; they take
            # effect only if the mode, which follows, is user.
            self.user_limits = (rest[1], rest[2])
            return True
        if rest[:1] == ["mode"] and len(rest) > 1:
            mode = rest[1]
            if mode == "user" and self.user_limits:
                self.xpa(frame, "scale", "limits", *self.user_limits)
            elif mode in _CLIP_MODES or re.fullmatch(r"[0-9.]+", mode):
                self.xpa(frame, "scale", "mode", mode)
            return True
        if rest[:1] == ["scope"] and len(rest) > 1:
            self.xpa(frame, "scale", "scope", rest[1])
            return True
        if rest[:2] == ["minmax", "mode"] and len(rest) > 2:
            self.xpa(frame, "minmax", "mode", rest[2])
            return True
        if rest[:2] == ["minmax", "sample"] and len(rest) > 2:
            self.xpa(frame, "minmax", "interval", rest[2])
            return True
        if rest[:1] == ["zscale"] and len(rest) > 2:
            self.xpa(frame, "zscale", rest[1], rest[2])
            return True
        return False

    def bin(self, frame: int, rest: list[str]) -> bool:
        x = lambda *command: self.xpa(frame, "bin", *command)  # noqa: E731
        if rest[:2] == ["factor", "to"] and len(rest) > 2:
            x("factor", rest[2])
        elif rest[:1] == ["depth"] and len(rest) > 1:
            x("depth", rest[1])
        elif rest[:1] == ["filter"]:
            text = _unquote(" ".join(rest[1:]))
            if text:
                x("filter", text)
        elif rest[:2] == ["buffer", "size"] and len(rest) > 2:
            x("buffersize", rest[2])
        elif rest[:1] == ["about"] and len(rest) > 2:
            x("about", rest[1], rest[2])
        elif rest[:1] == ["function"] and len(rest) > 1:
            x("function", rest[1])
        elif rest[:1] == ["cols"]:
            columns = [_unquote(word) for word in rest[1:] if _unquote(word)]
            if len(columns) >= 2:
                x("cols", *columns[:2])
        else:
            return False
        return True

    def contour(self, frame: int, rest: list[str]) -> bool:
        x = lambda *command: self.xpa(frame, "contour", *command)  # noqa: E731
        if rest[:1] == ["create"] and len(rest) >= 14:
            color, width, dash, method, levels_n, smooth, scale, log, mode, scope, low, high = rest[1:13]
            levels = _unquote(rest[13])
            x("color", color)
            x("width", width)
            x("dash", _yes(dash))
            x("method", method)
            x("nlevels", levels_n)
            x("smooth", smooth)
            x("scale", scale)
            x("log", "exp", log)
            x("mode", mode)
            x("limits", low, high)
            if levels.split():
                x("levels", "{" + levels + "}")
            x("yes")
            return True
        if rest[:1] == ["load"] and len(rest) > 1:
            x("load", self.path(rest[-1]))
            return True
        return False


def read(path: str | Path) -> DS9Backup:
    """Translate one of DS9's backups.

    Raises:
        DS9BackupError: If the file cannot be read or is not a DS9 backup.
    """
    path = Path(path)
    try:
        script = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise DS9BackupError(f"cannot read {path}: {exc}") from exc
    if "CreateNameNumberFrame" not in script and not script.lstrip().startswith("global ds9"):
        raise DS9BackupError(f"{path.name} is not a DS9 backup")
    return _Translator(path.parent).run(script)
