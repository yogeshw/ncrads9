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
The user documentation: that it holds together, and what it may claim.

Two things are gated here.

**That it holds together.** Fourteen pages that cross-reference each other
rot quietly: a renamed file leaves a dead link that nobody notices until a
reader hits it, and a new page that the contents page does not list is a
page nobody reads.

**What it may claim about SAOImageDS9.** NCRADS9's interface is modelled on
DS9's, and the region, session and contour formats and the XPA names are
DS9's -- that is worth saying plainly and the documentation says it. What
it must not do is credit DS9 with the ideas underneath. Colour lookup
tables and the mouse dragged across them, blink comparison, contours and
coordinate grids over the data, regions as overlays, tiled frames: AIPS,
IRAF, MIDAS, Karma, SAOimage and SAOtng were doing these things, several
of them decades ago, and DS9 grew out of that work rather than starting
it. An earlier draft of these pages said NCRADS9 "exists because
SAOImageDS9 does" and that "credit for the design belongs there", which
hands DS9 other people's work. The gate keeps the correction in place.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
GUIDE = DOCS / "user_guide"

#: The programs the ideas actually came from. The acknowledgment has to
#: name them, or it is crediting DS9 with their work by omission.
OLDER = ("AIPS", "IRAF", "SAOimage")


def guide_pages() -> list[pathlib.Path]:
    return sorted(page for page in GUIDE.glob("*.html") if page.name != "index.html")


def local_links(page: pathlib.Path) -> list[str]:
    return [
        href
        for href in re.findall(r'href="([^"]+)"', page.read_text(encoding="utf-8"))
        if not href.startswith(("http://", "https://", "mailto:"))
    ]


# -- the guide holds together ------------------------------------------------------


def test_every_link_in_the_documentation_resolves():
    broken = []
    for page in sorted(DOCS.rglob("*.html")):
        for href in local_links(page):
            target = href.split("#", 1)[0]
            if target and not (page.parent / target).resolve().exists():
                broken.append(f"{page.relative_to(ROOT)} -> {href}")
    assert broken == [], "\n".join(broken)


def test_the_contents_page_lists_every_chapter():
    """A page the contents page does not list is a page nobody reads."""
    listed = set(local_links(GUIDE / "index.html"))
    missing = [page.name for page in guide_pages() if page.name not in listed]
    assert missing == [], f"not on the contents page: {missing}"


def test_every_chapter_links_back_to_the_contents():
    orphans = [page.name for page in guide_pages() if "index.html" not in " ".join(local_links(page))]
    assert orphans == [], f"no way back to the contents from: {orphans}"


@pytest.mark.parametrize("page", guide_pages(), ids=lambda p: p.name)
def test_a_chapter_is_a_whole_page(page):
    """Title, breadcrumb, a heading and the previous/next bar."""
    text = page.read_text(encoding="utf-8")
    assert "<title>" in text and "</title>" in text
    assert 'class="breadcrumb"' in text
    assert 'class="nav"' in text
    assert "<h1>" in text


@pytest.mark.parametrize("page", guide_pages(), ids=lambda p: p.name)
def test_a_chapter_says_something(page):
    """The fault this documentation pass was for: the guide was six pages
    of headings with a sentence under each."""
    prose = re.sub(r"<[^>]+>", " ", page.read_text(encoding="utf-8"))
    prose = re.sub(r"\s+", " ", prose)
    assert len(prose) > 1500, f"{page.name} is {len(prose)} characters of prose"


def test_the_guide_covers_the_whole_program():
    """Each of these had no chapter at all before, and each is something a
    user has to do."""
    names = {page.name for page in guide_pages()}
    for chapter in (
        "getting_started.html",
        "opening_files.html",
        "scales.html",
        "colormaps.html",
        "coordinates.html",
        "frames.html",
        "regions.html",
        "analysis.html",
        "saving.html",
        "scripting.html",
        "customising.html",
        "reference.html",
        "troubleshooting.html",
    ):
        assert chapter in names, f"no chapter on {chapter}"


# -- what may be claimed about DS9 -------------------------------------------------


def test_the_acknowledgment_names_what_is_actually_ds9s():
    """Specific and true: the interface, the formats, the XPA names, the
    colour tables."""
    from ncrads9.ui import help_documents

    text = re.sub(r"<[^>]+>", " ", help_documents.BY_NAME["acknowledgment"].html())
    for claim in ("region file format", "XPA", "colour tables"):
        assert claim in text, f"the acknowledgment no longer names {claim!r}"


def test_the_acknowledgment_names_what_came_before_ds9():
    """Without this the page credits DS9 with other people's work by
    saying nothing about whose it was."""
    from ncrads9.ui import help_documents

    text = re.sub(r"<[^>]+>", " ", help_documents.BY_NAME["acknowledgment"].html())
    missing = [name for name in OLDER if name not in text]
    assert missing == [], f"the acknowledgment does not mention {missing}"


def test_the_story_places_the_ideas_before_ds9():
    from ncrads9.ui import help_documents

    text = re.sub(r"<[^>]+>", " ", help_documents.BY_NAME["story"].html())
    missing = [name for name in OLDER if name not in text]
    assert missing == [], f"the story does not mention {missing}"
    assert "SAOtng" in text, "DS9's own ancestry is not given"


@pytest.mark.parametrize(
    "overclaim",
    [
        "exists because SAOImageDS9 does",
        "Credit for the design belongs there",
        "the design is theirs",
        "this program reimplements",
    ],
)
def test_no_page_hands_ds9_the_whole_design(overclaim):
    """The exact sentences that were wrong, kept out of every page that a
    user reads."""
    from ncrads9.ui import help_documents

    for document in help_documents.DOCUMENTS:
        assert overclaim not in document.html(), f"{document.name} still says {overclaim!r}"
    for page in [*guide_pages(), GUIDE / "index.html", ROOT / "README.md"]:
        assert overclaim not in page.read_text(encoding="utf-8"), f"{page.name}: {overclaim!r}"


def test_the_readme_gives_the_same_account():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "modelled on" in text
    for name in OLDER:
        assert name in text, f"the README does not mention {name}"


def test_the_guide_introduction_says_where_the_ideas_came_from():
    text = (GUIDE / "index.html").read_text(encoding="utf-8")
    assert "older than DS9" in text
