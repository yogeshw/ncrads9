# NCRADS9 - A Python/Qt6 Clone of SAOImageDS9
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
NCRADS9 Application Setup

This module initializes the Qt application and main window.

Author: Yogesh Wadadekar
"""

from dataclasses import dataclass
from typing import List, Sequence
import logging
import tempfile
import webbrowser
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ncrads9 import __version__
from ncrads9.communication.xpa import XPAServer
from ncrads9.communication.xpa.xpa_commands import XPACommands
from ncrads9.ui.main_window import MainWindow
from ncrads9.utils.config import Config
from ncrads9.utils.logger import setup_logging


@dataclass
class CLIItem:
    """Single parsed startup CLI item."""

    kind: str  # "file" | "option"
    name: str
    args: List[str]


def _cli_help_requested(argv: Sequence[str]) -> bool:
    """Return True when CLI help was requested."""
    help_flags = {"-h", "--help", "-help"}
    return any(str(arg).lower() in help_flags for arg in list(argv)[1:])


def _write_cli_help_document() -> Path:
    """Write CLI help HTML document and return path."""
    html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>NCRADS9 Command Line Options</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem; line-height: 1.5; }
    code { background: #f4f4f4; padding: 0.1rem 0.3rem; border-radius: 4px; }
    pre { background: #f6f8fa; padding: 0.8rem; border-radius: 6px; overflow-x: auto; }
    h1, h2 { margin-bottom: 0.4rem; }
    ul { margin-top: 0.2rem; }
  </style>
</head>
<body>
  <h1>NCRADS9 Command Line Options</h1>
  <p>DS9-style startup options currently implemented in ncrads9.</p>

  <h2>Examples</h2>
  <pre>ncrads9 image.fits
ncrads9 -log -heat -tile image.fits
ncrads9 -rgb -red r.fits -green g.fits -blue b.fits
ncrads9 -frame rgb -zoom 2 -pan 1024 1024 image.fits</pre>

  <h2>Core options</h2>
  <ul>
    <li><code>-h</code>, <code>--help</code>, <code>-help</code>: open this browser help page.</li>
    <li><code>-rgb</code>: create an RGB frame (with <code>-red/-green/-blue</code>, loads channels and composes).</li>
    <li><code>-red file.fits</code>, <code>-green file.fits</code>, <code>-blue file.fits</code>: assign RGB channel files.</li>
    <li>File paths without a leading dash are opened as FITS files.</li>
  </ul>

  <h2>Display mode options</h2>
  <ul>
    <li><code>-single</code>, <code>-tile</code>, <code>-blink</code>, <code>-fade</code></li>
    <li><code>-tile on|off</code>, <code>-blink on|off</code>, <code>-fade on|off</code> are accepted.</li>
  </ul>

  <h2>Scale options</h2>
  <ul>
    <li><code>-linear</code>, <code>-log</code>, <code>-sqrt</code>, <code>-squared</code>, <code>-power</code>, <code>-asinh</code>, <code>-histeq</code>, <code>-histogram</code></li>
    <li><code>-zscale</code>, <code>-minmax</code></li>
    <li><code>-scale mode</code> (for example <code>-scale log</code>)</li>
  </ul>

  <h2>Color options</h2>
  <ul>
    <li><code>-invert</code>, <code>-noinvert</code>, <code>-uninvert</code></li>
    <li><code>-cmap name</code>, <code>-colormap name</code>, <code>-color name</code></li>
    <li>Direct colormap names are accepted (for example <code>-heat</code>, <code>-viridis</code>).</li>
  </ul>

  <h2>WCS and binning</h2>
  <ul>
    <li><code>-wcs fk5|fk4|icrs|galactic|ecliptic</code></li>
    <li><code>-fk5</code>, <code>-fk4</code>, <code>-icrs</code>, <code>-galactic</code>, <code>-ecliptic</code></li>
    <li><code>-sexagesimal</code>, <code>-degrees</code></li>
    <li><code>-bin N</code></li>
  </ul>

  <h2>XPA-style startup options</h2>
  <p>The following are also supported at startup using DS9/XPA-compatible syntax:</p>
  <ul>
    <li><code>-frame</code>, <code>-zoom</code>, <code>-pan</code>, <code>-scale</code>, <code>-cmap</code>, <code>-colorbar</code>, <code>-regions</code>, <code>-wcs</code>, <code>-tile</code>, <code>-blink</code>, <code>-match</code>, <code>-lock</code>, <code>-width</code>, <code>-height</code>, <code>-save</code>, <code>-version</code>, <code>-about</code></li>
  </ul>
</body>
</html>
"""
    help_path = Path(tempfile.gettempdir()) / "ncrads9_cli_help.html"
    help_path.write_text(html, encoding="utf-8")
    return help_path


def open_cli_help_in_browser() -> Path:
    """Open CLI help in the default browser and return the file path."""
    help_path = _write_cli_help_document()
    webbrowser.open(help_path.as_uri(), new=2)
    return help_path


def parse_cli_sequence(args: Sequence[str]) -> List[CLIItem]:
    """Parse DS9-style startup arguments into an ordered sequence."""
    def _is_option_token(token: str) -> bool:
        return token.startswith("-") and len(token) > 1

    bool_values = {"0", "1", "on", "off", "yes", "no", "true", "false"}
    optional_bool_options = {"tile", "blink", "fade"}
    one_arg_options = {
        "red",
        "green",
        "blue",
        "wcs",
        "bin",
        "cmap",
        "colormap",
        "color",
        "colour",
        "frame",
        "zoom",
        "width",
        "height",
        "mode",
        "match",
        "lock",
        "regions",
        "save",
        "file",
        "fits",
        "scale",
        "colorbar",
        "cursor",
        "crosshair",
    }
    two_arg_options = {"pan"}

    items: List[CLIItem] = []
    i = 0
    while i < len(args):
        token = str(args[i])
        if _is_option_token(token):
            option = token.lstrip("-").lower()
            option_args: List[str] = []
            i += 1
            if option in optional_bool_options:
                if i < len(args):
                    current = str(args[i])
                    if not _is_option_token(current) and current.strip().lower() in bool_values:
                        option_args.append(current)
                        i += 1
            elif option in two_arg_options:
                for _ in range(2):
                    if i >= len(args):
                        break
                    current = str(args[i])
                    if _is_option_token(current):
                        break
                    option_args.append(current)
                    i += 1
            elif option in one_arg_options:
                if i < len(args):
                    current = str(args[i])
                    if not _is_option_token(current):
                        option_args.append(current)
                        i += 1
            items.append(CLIItem(kind="option", name=option, args=option_args))
            continue
        items.append(CLIItem(kind="file", name=token, args=[]))
        i += 1
    return items


def _load_rgb_channels_from_cli(main_window: MainWindow, channel_paths: dict[str, str]) -> None:
    """Load RGB channel files into separate source frames and create composite frame."""
    source_indices: dict[str, int] = {}
    for channel in ("red", "green", "blue"):
        filepath = channel_paths.get(channel)
        if not filepath:
            continue
        current = main_window.frame_manager.current_frame
        if not source_indices and current is not None and current.image_data is None and current.frame_type == "base":
            pass
        else:
            main_window._new_frame_with_type("base")
        main_window.open_file(filepath=filepath)
        frame = main_window.frame_manager.current_frame
        if frame is not None and frame.image_data is not None:
            source_indices[channel] = main_window.frame_manager.current_index

    if not source_indices:
        return

    main_window._new_frame_with_type("rgb")
    rgb_frame = main_window.frame_manager.current_frame
    if rgb_frame is None:
        return
    rgb_frame.rgb_current_channel = "red" if "red" in source_indices else next(iter(source_indices))
    main_window._apply_rgb_frame_channels_from_sources(rgb_frame, source_indices)
    main_window._apply_frame_view_state(rgb_frame)
    main_window._display_image()


def apply_startup_cli(main_window: MainWindow, argv: Sequence[str]) -> None:
    """Apply startup CLI options to an existing main window."""
    logger = logging.getLogger(__name__)
    items = parse_cli_sequence(list(argv)[1:])
    xpa_commands = XPACommands(main_window)
    xpa_supported = set(xpa_commands.get_available_commands())
    available_colormaps = set(main_window.get_available_colormaps())
    rgb_channel_paths: dict[str, str] = {}
    rgb_requested = False

    for item in items:
        if item.kind == "file":
            main_window.open_file(filepath=item.name)
            continue

        option = item.name
        args = item.args
        option_aliases = {
            "colormap": "cmap",
            "color": "cmap",
            "colour": "cmap",
        }
        option = option_aliases.get(option, option)
        if option == "rgb":
            rgb_requested = True
            continue
        if option in {"red", "green", "blue"}:
            if args:
                rgb_channel_paths[option] = args[0]
                rgb_requested = True
            continue
        if option == "single":
            main_window._set_frame_display_mode("single")
            continue
        if option == "tile":
            enabled = True if not args else str(args[0]).lower() not in {"0", "off", "no", "false"}
            main_window._tile_frames(enabled)
            continue
        if option == "blink":
            enabled = True if not args else str(args[0]).lower() not in {"0", "off", "no", "false"}
            main_window._toggle_blink(enabled)
            continue
        if option == "fade":
            enabled = True if not args else str(args[0]).lower() not in {"0", "off", "no", "false"}
            main_window._toggle_fade(enabled)
            continue
        if option in {"linear", "log", "sqrt", "squared", "power", "asinh", "histeq", "histogram", "zscale", "minmax"}:
            xpa_commands.handle("scale", {"args": [option]})
            continue
        if option in {"fk5", "fk4", "icrs", "galactic", "ecliptic"}:
            main_window._set_wcs_system(option)
            continue
        if option in {"sexagesimal", "degrees"}:
            main_window._set_wcs_format(option)
            continue
        if option == "wcs" and args:
            main_window._set_wcs_system(str(args[0]).lower())
            continue
        if option == "bin" and args:
            try:
                main_window._set_bin(int(args[0]))
            except ValueError:
                logger.warning("Invalid -bin value: %s", args[0])
            continue
        if option == "invert":
            main_window._toggle_invert_colormap(True)
            continue
        if option in {"noinvert", "uninvert"}:
            main_window._toggle_invert_colormap(False)
            continue
        if option in available_colormaps:
            main_window._set_colormap(option)
            continue
        if option in xpa_supported:
            response = xpa_commands.handle(option, {"args": args})
            if response.get("status") != "ok":
                logger.warning("CLI option -%s failed: %s", option, response.get("message", "unknown"))
            continue
        logger.warning("Unsupported startup option: -%s", option)

    if rgb_requested and rgb_channel_paths:
        _load_rgb_channels_from_cli(main_window, rgb_channel_paths)
    elif rgb_requested:
        main_window._new_frame_with_type("rgb")


def run_application(argv: List[str]) -> int:
    """
    Initialize and run the NCRADS9 application.

    Args:
        argv: Command line arguments.

    Returns:
        Exit code.
    """
    if _cli_help_requested(argv):
        open_cli_help_in_browser()
        return 0

    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create application
    app = QApplication(argv)
    app.setApplicationName("NCRADS9")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("NCRA")

    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    # Load configuration
    config = Config()

    # Create main window
    main_window = MainWindow(config)
    main_window.show()

    xpa_enabled = bool(config.get("communication.xpa.enabled", True))
    xpa_server = None
    if xpa_enabled:
        xpa_server = XPAServer(
            name=str(config.get("communication.xpa.name", "ncrads9")),
            host=str(config.get("communication.xpa.host", "localhost")),
            port=int(config.get("communication.xpa.port", 0)),
            viewer=main_window,
        )
        if not xpa_server.start():
            logger.warning("Failed to start XPA server on %s", xpa_server.address)

    # Apply startup files/options
    apply_startup_cli(main_window, argv)

    if xpa_server is not None:
        app.aboutToQuit.connect(xpa_server.stop)

    return app.exec()
