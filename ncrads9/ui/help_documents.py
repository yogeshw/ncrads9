# This file is part of ncrads9.
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
The documents DS9's Help menu offers, written for NCRADS9.

DS9's Help menu has eight entries and every one of them opens a page of its
bundled documentation (`ds9/library/mhelp.tcl`). NCRADS9 had none of them:
its Help menu offered an in-app contents page, a shortcut list and two
About boxes, so a user arriving from DS9 found nothing under any name they
knew, and the menu scored zero on parity.

Each document here is DS9's entry answered with NCRADS9's own material --
not a link to DS9's manual, which describes a different program.

Two of them are *generated* rather than written, so they cannot fall
behind the code: the reference manual lists the XPA access points from the
table that implements them, and the release notes read the package
version. A written page that lists commands goes stale the first time one
is added, and a stale reference is worse than none.

The colours come from the widget's palette rather than being written into
the HTML. The contents page had `color: #2e3436` in its stylesheet, which
under the dark theme drew near-black text on a near-black ground -- the
same grey-on-grey fault that was reported for the popups, surviving inside
one of them because it was in the *document* rather than the widget.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtGui import QPalette

from .. import __version__

#: Where NCRADS9 itself lives, for the pages that have to point somewhere.
PROJECT_URL = "https://github.com/yogeshw/ncrads9"

#: SAOImageDS9's own home, for the pages that credit it.
DS9_URL = "https://sitael.cfa.harvard.edu/rd/ds9/"


@dataclass(frozen=True)
class HelpDocument:
    """One entry in the Help menu.

    Attributes:
        name: The key the menu and the controller use.
        label: What the menu shows, with its accelerator mark.
        title: The heading the document opens with.
        body: The document as an HTML fragment, or a callable returning one
            -- callable for the pages that are generated from the code, so
            they are built when opened rather than at import.
    """

    name: str
    label: str
    title: str
    body: str | Callable[[], str]

    def html(self) -> str:
        """The document's body, generating it if it is generated."""
        return self.body() if callable(self.body) else self.body


def stylesheet(palette: QPalette) -> str:
    """A document stylesheet in the colours the widget is actually using.

    `QTextBrowser` renders HTML with its own defaults unless the document
    says otherwise, and a document that names its colours outright ignores
    the theme. Taking them from the palette means the same document is
    readable under every theme, including the desktop's own.
    """
    text = palette.color(QPalette.ColorRole.Text).name()
    base = palette.color(QPalette.ColorRole.Base).name()
    link = palette.color(QPalette.ColorRole.Link).name()
    alternate = palette.color(QPalette.ColorRole.AlternateBase).name()
    # `Link` for the headings, not `Highlight`. Highlight is a *selection
    # background* and is chosen to sit close to the window's own colour --
    # under the dark theme it is #094771, a luma gap of 20 from the page,
    # which is another shade of the same grey-on-grey. A link colour has to
    # be readable against the page by definition.
    return f"""
    body {{ color: {text}; background-color: {base}; line-height: 1.4; }}
    h1 {{ color: {text}; font-size: 22px; }}
    h2 {{ color: {link}; font-size: 17px; margin-top: 18px; }}
    h3 {{ color: {text}; font-size: 14px; margin-top: 14px; }}
    p, li, td, th {{ color: {text}; }}
    a {{ color: {link}; }}
    code, pre {{ background-color: {alternate}; color: {text};
                 font-family: monospace; padding: 1px 4px; }}
    th {{ text-align: left; }}
    td {{ padding-right: 12px; vertical-align: top; }}
    """


def render(title: str, body: str, palette: QPalette) -> str:
    """A whole HTML document, in the palette's colours."""
    return (
        f"<html><head><style>{stylesheet(palette)}</style></head><body><h1>{title}</h1>{body}</body></html>"
    )


# -- the generated pages -----------------------------------------------------------


def reference_manual() -> str:
    """Every XPA access point, read off the table that implements them.

    DS9's Reference Manual is its command reference, and for NCRADS9 the
    commands are the XPA access points -- the same names `xpaset` and
    `xpaget` take, and the same names DS9 documents. Generated from
    `ALL_POINTS`, so a point added without a line here is impossible.
    """
    from ..communication.xpa.access_points import ALL_POINTS

    rows = []
    for point in sorted(ALL_POINTS, key=lambda item: item.name):
        names = ", ".join([point.name, *(point.aliases or ())])
        ways = []
        if point.get is not None or point.query is not None:
            ways.append("get")
        if point.set is not None:
            ways.append("set")
        rows.append(
            f"<tr><td><code>{names}</code></td><td>{'/'.join(ways) or '--'}</td><td>{point.summary}</td></tr>"
        )
    return (
        "<p>Every name NCRADS9 answers over XPA, which is also how a script "
        "drives it. Read one with <code>xpaget ncrads9 &lt;name&gt;</code> and "
        "set one with <code>xpaset -p ncrads9 &lt;name&gt; &lt;value&gt;</code>.</p>"
        "<p>This list is generated from the table that implements the access "
        "points, so it cannot fall behind them.</p>"
        f"<p>{len(ALL_POINTS)} access points.</p>"
        "<table><tr><th>Name</th><th>Direction</th><th>What it is</th></tr>" + "".join(rows) + "</table>"
    )


def release_notes() -> str:
    """The version, read from the package rather than written here."""
    return f"""
    <p>NCRADS9 version <b>{__version__}</b>.</p>

    <h2>What this is</h2>
    <p>A reimplementation of SAOImageDS9 in Python and Qt6. The menus, the
    region format, the session format and the XPA interface follow DS9's,
    so a DS9 user and a DS9 script should both find what they expect.</p>

    <h2>What works</h2>
    <p>Loading and saving FITS (including cubes, RGB and mosaics); the scale
    algorithms and limit modes; DS9's bundled colour tables and the
    matplotlib ones; every region shape DS9 can draw, read and written in
    DS9's own format; WCS in the usual systems and formats; contours;
    coordinate grids; the panner, magnifier and pixel table; binning of
    event tables; smoothing; the analysis tools; catalogues and image
    servers; SAMP and XPA.</p>

    <h2>What is not finished</h2>
    <p>The Help menu's documents are these pages rather than a manual.
    Bin and Smooth lock settings are per-window rather than per-frame, so
    frames always match on those two. Some of DS9's own search windows and
    its per-column catalogue editing are absent; <code>xpaget ncrads9
    &lt;name&gt;</code> reports what any particular name does.</p>

    <h2>Where to look</h2>
    <p><a href="{PROJECT_URL}">{PROJECT_URL}</a></p>
    """


# -- the written pages -------------------------------------------------------------


_USER_MANUAL = """
<p>NCRADS9 shows FITS images the way SAOImageDS9 does. If you know DS9, the
menus are in the same places; this page is the short version.</p>

<h2>Opening an image</h2>
<p><b>File &rarr; Open</b> reads a FITS file. <b>File &rarr; Open as</b> has
one entry per way of reading the same file -- as a data cube, an RGB
composite, a mosaic, a compressed array, or an event table to be binned.
On the command line, <code>ncrads9 image.fits</code> does the same thing.</p>

<h2>Seeing the faint things</h2>
<p><b>Scale</b> chooses how pixel values become brightness: linear, log,
power, square root, squared, histogram equalisation or the asinh and sinh
curves. <b>Scale &rarr; Limits</b> chooses which values to spread across
that range -- minmax for everything, zscale or zmax for the values that
matter in an astronomical image, or a pair you type in. Dragging with the
right mouse button adjusts contrast and bias without changing either.</p>

<h2>Colour</h2>
<p><b>Color</b> holds DS9's bundled colour tables and matplotlib's. Invert
one with <b>Color &rarr; Invert Colormap</b>; the colour bar under the image
shows what is in force, and <b>Color &rarr; Colormap Parameters</b> is where
contrast and bias can be set by hand.</p>

<h2>Moving around</h2>
<p><b>Zoom</b> has the fixed steps, <b>Zoom Fit</b> and the rotations and
flips. The <b>panner</b> shows where you are in the whole image and which
way north and east point; the <b>magnifier</b> shows the pixels under the
cursor. Middle-click centres the image where you click.</p>

<h2>Regions</h2>
<p><b>Edit &rarr; Region</b> arms the pointer for drawing, and <b>Region
&rarr; Shape</b> chooses what a drag draws -- every shape DS9 has, with the
seven point symbols under <b>Point</b>. Double-click a region to edit its
position, size and text. <b>Region &rarr; Open</b> reads a DS9 region file
and adds it to what is there; <b>Delete All and Open</b> replaces instead.
<b>Region &rarr; List</b> shows the file that would be written.</p>

<h2>Coordinates</h2>
<p>The panel above the image reads out the position under the cursor in
image, physical and world coordinates. <b>WCS</b> chooses the system (fk5,
fk4, ICRS, galactic, ecliptic) and the format (degrees or sexagesimal).
<b>Analysis &rarr; Coordinate Grid</b> draws the grid.</p>

<h2>Measuring</h2>
<p><b>Analysis</b> holds the pixel table, the horizontal and vertical cut
graphs, contours, smoothing, and the block and bin controls. A region's own
right-click menu has its statistics, its radial profile and its histogram.</p>

<h2>Saving what you see</h2>
<p><b>File &rarr; Save Image</b> writes the view as it appears -- at the
zoom you are at, with the regions, contours and grid on it. <b>File &rarr;
Export</b> writes the data instead, and <b>File &rarr; Print</b> sends the
view to a printer or a PostScript file. <b>File &rarr; Backup</b> saves the
whole session, frames and all, to be restored later.</p>

<h2>Keeping a menu open</h2>
<p>Every menu and submenu has a dashed line across the top. Click it and
the menu detaches into a window of its own that stays open, so a menu you
are working through -- Scale, Colormap, Region &rarr; Shape -- can sit
beside the image instead of being reopened for every change. Detached
menus are ordinary windows: move them, and push them behind the main one
when they are in the way. Close one and the menu goes back to normal.</p>
<p>Turn it off under <b>Edit &rarr; Preferences &rarr; Menus and
Buttons</b> if the dashed lines are not wanted.</p>

<h2>Driving it from a script</h2>
<p>NCRADS9 answers XPA, so <code>xpaset</code> and <code>xpaget</code> work
as they do with DS9, and pyds9 and its successors talk to it. The Reference
Manual in this menu lists every name it answers.</p>
"""


_FAQ = f"""
<h2>Is this SAOImageDS9?</h2>
<p>No. It is a separate program that reimplements DS9's interface and file
formats in Python and Qt6. DS9 is the original, developed at the
Smithsonian Astrophysical Observatory; see <b>About SAOImageDS9</b> in this
menu.</p>

<h2>Will my DS9 region files, colour tables and scripts work?</h2>
<p>Region files and DS9's <code>.sao</code> and <code>.lut</code> colour
tables are read and written in DS9's own formats. Scripts that use XPA work
if they address <code>ncrads9</code> instead of <code>ds9</code>; the
Reference Manual lists the names answered. A script that finds a name
missing gets a message saying so rather than silence.</p>

<h2>Why is my image upside down?</h2>
<p>It probably is not. FITS counts rows from the bottom and screens count
them from the top, so an image with no WCS can look flipped compared with
another program's default. <b>Zoom &rarr; Invert Y</b> settles it either
way, and the coordinate readout is the thing to trust.</p>

<h2>The colours in the image look wrong after I dragged with the mouse.</h2>
<p>Right-drag adjusts contrast and bias, which is DS9's behaviour.
<b>Color &rarr; Reset Colormap</b> puts them back.</p>

<h2>Nothing happens when I click a colour or a shape button.</h2>
<p>The buttons above the image mirror the menus, so whatever the menu entry
does the button does. If a button appears to do nothing, the menu entry is
the thing to check, and the status line at the bottom says what happened.</p>

<h2>What is the dashed line at the top of every menu?</h2>
<p>A tear-off handle, as in DS9. Click it and that menu -- or submenu --
becomes a window of its own that stays open, which saves reopening a menu
you are using repeatedly. It is an ordinary window, so it can be moved and
pushed behind the image. <b>Edit &rarr; Preferences &rarr; Menus and
Buttons</b> turns the handles off.</p>

<h2>Can I open several images at once?</h2>
<p>Yes. <b>Frame &rarr; New Frame</b> makes another, <b>Frame &rarr;
Tile</b> shows them side by side, and <b>Frame &rarr; Lock</b> ties their
panning, zoom, scale or colour together.</p>

<h2>Everything is grey and hard to read.</h2>
<p><b>Edit &rarr; Preferences</b> chooses the theme. <b>System</b> follows
the desktop's own colours, including a dark mode set outside NCRADS9.</p>

<h2>How do I report a problem?</h2>
<p><b>Help &rarr; Help Desk</b> says what to include. The short answer is
<a href="{PROJECT_URL}/issues">{PROJECT_URL}/issues</a>.</p>
"""


_HELP_DESK = f"""
<p>NCRADS9 has no help desk of its own. Problems and questions go to the
project's issue tracker:</p>

<p><a href="{PROJECT_URL}/issues">{PROJECT_URL}/issues</a></p>

<h2>What to include</h2>
<ul>
<li>the version, which <b>Help &rarr; About NCRADS9</b> shows, and your
operating system;</li>
<li>what you did, what you expected, and what happened instead;</li>
<li>for a problem with a particular file, its header --
<b>File &rarr; Header</b> shows it and it can be copied out;</li>
<li>for a problem with a script, the exact <code>xpaset</code> or
<code>xpaget</code> line, and what it answered.</li>
</ul>

<h2>Questions about DS9 itself</h2>
<p>Questions about SAOImageDS9 -- its own behaviour, its manual, its
releases -- belong with SAO rather than here:
<a href="{DS9_URL}">{DS9_URL}</a>.</p>
"""


_STORY = f"""
<p>SAOImageDS9 is the FITS image viewer that this program reimplements. Its
line began with SAOimage, written at the Smithsonian Astrophysical
Observatory, continued through SAOtng, and became DS9 -- named, as
astronomers' software often is, after something on television. Its
principal author is William Joye, and it has been developed and maintained
at SAO with support from the Chandra X-ray Science Center and NASA's High
Energy Astrophysics programme.</p>

<p>DS9 is written in Tcl/Tk over C and C++, and two of its decisions shaped
everything built around it: regions are plain text in a documented format,
so they pass between programs and can be written by hand, and XPA lets
another process read and set almost anything in a running DS9, which is why
so many pipelines drive it rather than reimplementing its display.</p>

<h2>Where NCRADS9 comes from</h2>
<p>NCRADS9 was written at the National Centre for Radio Astrophysics as a
reimplementation of DS9 in Python and Qt6, so that the viewer sits in the
same language as the analysis around it -- numpy arrays, astropy WCS,
matplotlib plots -- and can be extended in it.</p>

<p>It follows DS9 rather than improving on it: the menus are where DS9 puts
them, the region and session files are DS9's, and the XPA names are DS9's.
Where it diverges it is because something is not finished, or because a
divergence is deliberate and recorded -- the project keeps a menu-by-menu
parity count against DS9 and a list of the places it departs on purpose.</p>

<p><a href="{PROJECT_URL}">{PROJECT_URL}</a></p>
"""


_ACKNOWLEDGMENT = f"""
<h2>SAOImageDS9</h2>
<p>NCRADS9 exists because SAOImageDS9 does. Its interface, its region
format, its session format and its XPA names are DS9's work, developed at
the Smithsonian Astrophysical Observatory with support from the Chandra
X-ray Science Center and NASA's High Energy Astrophysics programme. The
164 bundled colour tables are DS9's own. Credit for the design belongs
there; the faults here are this program's.</p>

<h2>The libraries this is built on</h2>
<ul>
<li><b>astropy</b> -- FITS, WCS and tables</li>
<li><b>numpy</b> and <b>scipy</b> -- the arrays and the filtering</li>
<li><b>PyQt6</b> and <b>Qt</b> -- the interface</li>
<li><b>matplotlib</b> -- the plots and a second set of colour tables</li>
<li><b>astroquery</b> -- the catalogue and image services</li>
</ul>

<h2>If NCRADS9 helped your work</h2>
<p>Cite SAOImageDS9 as its authors ask, since the design is theirs, and
name NCRADS9 and its version as the software used:
<a href="{PROJECT_URL}">{PROJECT_URL}</a>.</p>

<h2>This program</h2>
<p>Copyright &copy; 2026 Yogesh Wadadekar. Licensed under the GNU General
Public License, version 3 or later.</p>
"""


_ABOUT_DS9 = f"""
<p><b>SAOImageDS9</b> is an astronomical imaging and data visualisation
application developed at the Smithsonian Astrophysical Observatory. It is
the program NCRADS9 reimplements, and it is not this program.</p>

<h2>What it is</h2>
<p>A FITS image viewer with support for multiple frames, RGB composites,
data cubes, mosaics, world coordinate systems, regions in a documented text
format, binning of event tables, contours, coordinate grids, catalogue and
image services, and scripting through XPA and SAMP. Its principal author is
William Joye; it is written in Tcl/Tk over C and C++, and it runs on Linux,
macOS and Windows.</p>

<h2>Where to get it</h2>
<p><a href="{DS9_URL}">{DS9_URL}</a></p>

<h2>Its licence</h2>
<p>SAOImageDS9 is free software under the GNU General Public License. It is
distributed by SAO, not with NCRADS9, and no part of it is included here.</p>

<h2>Which of the two you are running</h2>
<p>This is NCRADS9 {__version__}. <b>Help &rarr; About NCRADS9</b> has its
version and licence; <b>Help &rarr; Story of SAOImageDS9</b> says how the
two are related.</p>
"""


#: DS9's eight Help entries, in DS9's order (`.help` in the menu snapshot).
DOCUMENTS: tuple[HelpDocument, ...] = (
    HelpDocument("reference_manual", "&Reference Manual", "Reference Manual", reference_manual),
    HelpDocument("user_manual", "&User Manual", "User Manual", _USER_MANUAL),
    HelpDocument("faq", "&FAQ", "Frequently Asked Questions", _FAQ),
    HelpDocument("release_notes", "Release &Notes", "Release Notes", release_notes),
    HelpDocument("help_desk", "Help &Desk", "Help Desk", _HELP_DESK),
    HelpDocument("story", "&Story of SAOImageDS9", "The Story of SAOImageDS9", _STORY),
    HelpDocument("acknowledgment", "&Acknowledgment", "Acknowledgment", _ACKNOWLEDGMENT),
    HelpDocument("about_ds9", "About SAOImage&DS9", "About SAOImageDS9", _ABOUT_DS9),
)

#: Name -> document, for the controller.
BY_NAME: dict[str, HelpDocument] = {document.name: document for document in DOCUMENTS}
