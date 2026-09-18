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
<p>NCRADS9 shows FITS images. If you know SAOImageDS9 the menus are in the
same places; this page is the practical core, and the HTML user guide that
ships with the source has a chapter on each part of it.</p>

<h2>Opening an image</h2>
<p><b>File &rarr; Open</b> reads a FITS file. <b>File &rarr; Open as</b> has
one entry per other way of reading the same bytes: a single slice, an RGB,
HSV or HLS composite, every extension as a cube or as separate frames, a
mosaic laid out by WCS or by IRAF convention, or a file over http.
<b>File &rarr; Import</b> takes what is not FITS &mdash; raw arrays, NRRD,
ENVI, GIF, TIFF, JPEG, PNG.</p>
<p>When a file has more than one displayable extension you are asked which
one; DS9 takes the first without asking, and a preference restores that.
<b>File &rarr; Prism</b> opens a file as a structure &mdash; extensions,
headers, table columns &mdash; which is the way to see what is in it before
deciding how to load it.</p>
<p>An event table has no image in it, only a row per photon.
The <b>Bin</b> menu bins those rows onto a grid: average or sum, a factor,
and the size of the buffer they are binned into.</p>

<h2>Seeing the faint things</h2>
<p>This is the setting that matters most, and the default is deliberately
the unhelpful one: linear between the data's own minimum and maximum, which
on real data means one hot pixel flattens everything else.</p>
<ul>
<li><b>Scale &rarr; ZScale</b> is the usual first move. It fits the middle
of the value distribution and ignores the tails.</li>
<li><b>Scale &rarr; Log</b>, <b>Square Root</b> or <b>ASINH</b> for a large
dynamic range. ASINH is the one that behaves near and below zero, which
matters in interferometric maps.</li>
<li>The percentage limits, <b>99.5%</b> down to <b>90%</b>, are a blunter
and more predictable alternative to zscale.</li>
<li><b>Scale Parameters</b> draws the histogram with the limits on it, which
usually explains at a glance why an image looks the way it does.</li>
<li><b>Global</b> or <b>Local</b> decides whether the limits are measured
over the whole image or only the part on screen.</li>
</ul>
<p>Right-dragging on the image slides the contrast and bias on top of all
this. <b>Color &rarr; Reset Contrast/Bias</b> undoes it.</p>

<h2>Colour</h2>
<p><b>Color</b> holds 164 bundled tables &mdash; the classic ones, the
matplotlib families, and further collections &mdash; and <b>User &rarr; Load
Colormap</b> reads <code>.sao</code> and <code>.lut</code> files you already
have. For a figure, prefer grey or one of the perceptually uniform maps:
rainbow and HSV have bright bands in the middle that read as edges in the
data and do not survive being printed in black and white.</p>

<h2>Moving around</h2>
<p><b>Zoom</b> has the fixed steps, <b>Zoom Fit</b>, the flips and the
rotations, and <b>Align</b> to put north up by the WCS. Middle-click centres
on a point; the scroll wheel zooms about the cursor. The <b>panner</b> shows
where you are in the whole image and which way north and east point; the
<b>magnifier</b> shows the pixels under the cursor.</p>

<h2>Coordinates</h2>
<p>The panel above the image reads out the position under the cursor in
image, physical and world coordinates at once. <b>WCS</b> picks the system
&mdash; fk5, fk4, ICRS, galactic, ecliptic &mdash; and sexagesimal or
degrees. That choice applies to the readout, to region files written in
world coordinates, and to what XPA reports, so check it before comparing
positions with a catalogue.</p>

<h2>Several images at once</h2>
<p><b>Frame &rarr; New Frame</b>, then <b>Tile</b> to see them side by side,
<b>Blink</b> to cycle them in place, or <b>Fade</b> to cross-fade.
<b>Match</b> makes the others match this one now; <b>Lock</b> keeps them
matched from now on. Locking by <b>WCS</b> is what you want for two images
of the same field from different instruments: pan one and the other follows
to the same piece of sky whatever its pixel grid.</p>

<h2>Regions</h2>
<p><b>Edit &rarr; Region</b> puts the left button into drawing mode and
<b>Region &rarr; Shape</b> chooses what a drag draws &mdash; every shape DS9
has, with the seven point symbols under <b>Point</b>. Double-click a region
to type exact coordinates, set its text, or reach its statistics, radial
profile and histogram.</p>
<p><b>Properties</b> carries the flags that matter for measurement:
<b>Include</b> or <b>Exclude</b> (an excluded region is written with a
leading <code>-</code>, and is how you mask a star out of an aperture), and
<b>Source</b> or <b>Background</b>.</p>
<p><b>Region &rarr; Open</b> <i>adds</i> a region file to what is already
there; <b>Delete All and Open</b> replaces. <b>List</b> shows the text that
would be written without writing it. The format is DS9's, so the files pass
to CASA, topcat and the astropy <code>regions</code> package.</p>

<h2>Measuring</h2>
<p><b>Analysis</b> holds the pixel table, statistics, the histogram, the
radial profile, contours, the coordinate grid, blocking and smoothing, the
catalogue and image services, and the plot tool. <b>View &rarr; Horizontal
Graph</b> and <b>Vertical Graph</b> add live cuts along the row and column
under the cursor.</p>
<p><b>Block</b> and <b>Smooth</b> change what the analysis tools see, not
just the picture. Turn them off before measuring.</p>

<h2>Getting it back out</h2>
<p>Four different things, kept apart:</p>
<ul>
<li><b>Save</b> / <b>Save As</b> &mdash; the data, as FITS. It writes what is
<i>displayed</i>: the block, smooth or cube slice on screen is what lands in
the file, with the axis cards corrected to match.</li>
<li><b>Export</b> &mdash; the data, in another format.</li>
<li><b>Save Image</b> &mdash; the <i>picture</i>, at the zoom you are at,
with the regions, contours and grid on it. This is the one for a figure.</li>
<li><b>Backup</b> &mdash; the whole session, to <b>Restore</b> later.</li>
</ul>
<p><b>Print</b> sends the same view to a printer or a PostScript file.</p>

<h2>Keeping a menu open</h2>
<p>Every menu and submenu has a dashed line across the top. Click it and the
menu detaches into a window of its own that stays open, so a menu you are
working through &mdash; Scale, Colormap, Region &rarr; Shape &mdash; can sit
beside the image instead of being reopened for every change. Detached menus
are ordinary windows: move them, and push them behind the main one when they
are in the way.</p>
<p>Turn it off under <b>Edit &rarr; Preferences &rarr; Menus and
Buttons</b>.</p>

<h2>Driving it from a script</h2>
<p>NCRADS9 answers XPA, so <code>xpaset</code> and <code>xpaget</code> work
as they do with DS9 once you address <code>ncrads9</code>, and pyds9 and its
successors talk to it. The <b>Reference Manual</b> in this menu lists every
name it answers, generated from the table that implements them. SAMP
connects it to topcat and Aladin. <b>File &rarr; Open Python Console</b>
gives you a prompt inside the running program, with <code>window</code>
bound to the main window.</p>
"""


_FAQ = f"""
<h2>Is this SAOImageDS9?</h2>
<p>No. It is a separate program, written in Python and Qt6, whose interface
is modelled on DS9's and which reads and writes DS9's region, session and
contour files. DS9 is the original and is developed at the Smithsonian
Astrophysical Observatory; see <b>About SAOImageDS9</b> in this menu. The
ideas both programs express are older than either &mdash; <b>Story of
SAOImageDS9</b> says where they came from.</p>

<h2>Will my DS9 region files, colour tables and scripts work?</h2>
<p>Region files, contour files, session backups and DS9's <code>.sao</code>
and <code>.lut</code> colour tables are read and written in DS9's own
formats. Scripts that use XPA work if they address <code>ncrads9</code>
instead of <code>ds9</code>; the Reference Manual lists the names answered,
and a name that is missing replies saying so rather than failing silently.
Tcl scripts do not run &mdash; the console here is Python.</p>

<h2>Why is everything black?</h2>
<p>Almost always the scale. The default limits are the data's own minimum
and maximum, and a single hot pixel flattens the rest. Try <b>Scale &rarr;
ZScale</b>, then <b>Log</b>. <b>Scale &rarr; Scale Parameters</b> shows the
histogram with the limits marked, which usually makes the reason plain. If
it is still black, turn off the GPU renderer in <b>Preferences &rarr;
General</b>: some drivers hand back an empty frame.</p>

<h2>Why is my image upside down?</h2>
<p>It probably is not. FITS counts rows from the bottom and screens count
them from the top, so an image with no WCS can look flipped compared with
another program's default. <b>Zoom &rarr; Invert Y</b> settles it either
way, and the coordinate readout is the thing to trust. With a WCS,
<b>Zoom &rarr; Align</b> puts north up.</p>

<h2>The colours look wrong after I dragged with the mouse.</h2>
<p>Right-drag adjusts contrast and bias, which is DS9's behaviour.
<b>Color &rarr; Reset Contrast/Bias</b> puts them back without changing
which colour table you are on.</p>

<h2>Dragging pans when I want to draw a region.</h2>
<p>The left button does whatever <b>Edit</b> is set to. Choose
<b>Edit &rarr; Region</b>, then pick a shape under <b>Region &rarr;
Shape</b>.</p>

<h2>Why do my statistics disagree with another tool?</h2>
<p>Check whether <b>Block</b> or <b>Smooth</b> is on &mdash; both change the
values the analysis tools measure, and a smoothed image has correlated
noise. Then check that the region is in the coordinate system you think it
is.</p>

<h2>Can I open several images at once?</h2>
<p>Yes. <b>Frame &rarr; New Frame</b> makes another, <b>Tile</b> shows them
side by side, <b>Blink</b> cycles them, and <b>Lock</b> ties their panning,
zoom, scale or colour together. Lock by WCS to compare the same field from
two instruments.</p>

<h2>What is the dashed line at the top of every menu?</h2>
<p>A tear-off handle. Click it and that menu &mdash; or submenu &mdash;
becomes a window of its own that stays open, which saves reopening a menu
you are using repeatedly. It is an ordinary window, so it can be moved and
pushed behind the image. <b>Edit &rarr; Preferences &rarr; Menus and
Buttons</b> turns the handles off.</p>

<h2>Everything is grey and hard to read.</h2>
<p><b>Edit &rarr; Preferences</b> chooses the theme. <b>System</b> follows
the desktop's own colours, including a dark mode set outside NCRADS9.</p>

<h2>Which "save" do I want?</h2>
<p><b>Save</b> writes the data as FITS. <b>Export</b> writes the data in
another format. <b>Save Image</b> writes the <i>picture</i> &mdash; the
current zoom, with regions, contours and grid on it &mdash; and is the one
you want for a figure. <b>Backup</b> writes the whole session.</p>

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
<p>NCRADS9 is a FITS image viewer written at the National Centre for Radio
Astrophysics in Python and Qt6, so that the viewer sits in the same
language as the analysis around it -- numpy arrays, astropy WCS,
matplotlib plots -- and can be extended in it.</p>

<p>Its interface follows SAOImageDS9's. That is a deliberate choice rather
than an accident: DS9 is the viewer most optical and radio astronomers
already have in their fingers, and a clone that puts Scale somewhere else
would cost its users more than it gained them. So the menus are where DS9
puts them, the region files are DS9's format, the session files are DS9's,
and the XPA names are DS9's, which is what lets an existing pipeline drive
this program instead.</p>

<h2>What came before</h2>

<p>Following DS9's interface is not the same as owing DS9 every idea in
it, and it would be wrong to suggest otherwise. Almost everything this
program does was current practice before SAOImageDS9 was written.</p>

<p>Blink comparison is older than computing -- Pluto was found with a
blink comparator and photographic plates. Displaying an image through a
colour lookup table, and dragging the mouse to slide the contrast and bias
of that table, was how you looked at data on AIPS's TV and in IRAF long
before it was how you looked at data in DS9. Zoom and pan, contour
overlays, coordinate grids drawn from the WCS, apertures and other regions
laid over the pixels, several images tiled for comparison, an intensity
cut along a row or column: AIPS, IRAF, MIDAS and Karma's <i>kvis</i> were
doing these things, in some cases decades ago. The <i>zscale</i> limits
under the Scale menu are IRAF's algorithm, named after IRAF's task.</p>

<p>DS9 itself grew out of that work. It descends from SAOimage, written at
the Smithsonian Astrophysical Observatory by Mike VanHilst, and from
SAOtng after it; its principal author is William Joye, and it is
maintained at SAO with support from the Chandra X-ray Science Center and
NASA's High Energy Astrophysics programme.</p>

<h2>What is DS9's own</h2>

<p>Two things DS9 contributed are worth naming, because NCRADS9 uses both
rather than inventing something incompatible. The region file format is
plain text, documented, and written so a person can type one -- which is
why regions pass between DS9, NCRADS9, CASA, topcat and a hundred scripts.
And XPA, SAO's messaging layer, lets another process read and set almost
anything in a running viewer, which is why so many pipelines drive a
viewer rather than reimplementing one. The particular arrangement of the
menus is DS9's too, and so are the 164 bundled colour tables.</p>

<p><a href="{PROJECT_URL}">{PROJECT_URL}</a></p>
"""


_ACKNOWLEDGMENT = f"""
<h2>SAOImageDS9</h2>
<p>NCRADS9's interface is modelled on SAOImageDS9's, and it reads and
writes DS9's region files, DS9's session files and DS9's XPA names so that
the two interoperate. The arrangement of the menus is DS9's work, as are
the region file format, those XPA names, and the 164 bundled colour
tables. DS9 is developed at the Smithsonian Astrophysical Observatory with
support from the Chandra X-ray Science Center and NASA's High Energy
Astrophysics programme.</p>

<h2>And what came before it</h2>
<p>The ideas underneath -- colour lookup tables and the mouse dragged
across them, blink comparison, zoom and pan, contours and coordinate grids
over the data, regions as overlays, tiled frames, cuts along a row --
belong to a longer tradition than any one program: AIPS, IRAF, MIDAS,
Karma, SAOimage and SAOtng, several of them decades old. The <i>zscale</i>
limits are IRAF's algorithm. Crediting DS9 with all of that would be
crediting it with other people's work.</p>

<h2>The libraries this is built on</h2>
<ul>
<li><b>astropy</b> -- FITS, WCS and tables</li>
<li><b>numpy</b> and <b>scipy</b> -- the arrays and the filtering</li>
<li><b>scikit-image</b> -- the contour tracer</li>
<li><b>PyQt6</b> and <b>Qt</b> -- the interface</li>
<li><b>matplotlib</b> -- the plots and a second set of colour tables</li>
<li><b>astroquery</b> -- the catalogue and image services</li>
</ul>

<h2>If NCRADS9 helped your work</h2>
<p>Name NCRADS9 and its version as the software used:
<a href="{PROJECT_URL}">{PROJECT_URL}</a>. If you also used DS9, or your
figures depend on its region format or its colour tables, cite
SAOImageDS9 as its authors ask.</p>

<h2>This program</h2>
<p>Copyright &copy; 2026 Yogesh Wadadekar. Licensed under the GNU General
Public License, version 3 or later.</p>
"""


_ABOUT_DS9 = f"""
<p><b>SAOImageDS9</b> is an astronomical imaging and data visualisation
application developed at the Smithsonian Astrophysical Observatory. It is
the program whose interface NCRADS9 is modelled on, and it is not this
program.</p>

<h2>What it is</h2>
<p>A FITS image viewer with support for multiple frames, RGB composites,
data cubes, mosaics, world coordinate systems, regions in a documented
text format, binning of event tables, contours, coordinate grids,
catalogue and image services, and scripting through XPA and SAMP. Its
principal author is William Joye; it descends from SAOimage and SAOtng, is
written in Tcl/Tk over C and C++, and runs on Linux, macOS and
Windows.</p>

<h2>Why this entry is here</h2>
<p>NCRADS9 follows DS9's menus and file formats closely enough that
somebody may reasonably wonder which of the two they have open, and DS9
deserves naming rather than being an unattributed resemblance. The debt is
to DS9's interface and its formats; the ideas those express are older than
DS9 and belong to the wider tradition that produced it --
<b>Help &rarr; Story of SAOImageDS9</b> says where they came from.</p>

<h2>Where to get it</h2>
<p><a href="{DS9_URL}">{DS9_URL}</a></p>

<h2>Its licence</h2>
<p>SAOImageDS9 is free software under the GNU General Public License. It
is distributed by SAO, not with NCRADS9, and no part of it is included
here.</p>

<h2>Which of the two you are running</h2>
<p>This is NCRADS9 {__version__}. <b>Help &rarr; About NCRADS9</b> has its
version and licence.</p>
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
