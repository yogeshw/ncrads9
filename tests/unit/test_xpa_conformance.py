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
XPA conformance against DS9's own examples (C-6).

`ds9/doc/ref/xpa.html` documents every access point with a list of real
command lines. `tools/import_ds9_xpa_examples.py` extracts them into
`docs/parity/ds9_xpa_examples.json` -- fifteen hundred of them -- and this
runs every one against a live window.

Three things are asserted, in increasing strength:

1. **Nothing raises.** A point may refuse a command, but it may not throw:
   an XPA caller gets a reply, never a traceback. This is absolute.
2. **Every point is known.** An `xpaset` to a name DS9 has and we do not
   is a script that breaks on the name rather than on the feature.
3. **The number that succeed does not fall.** A ratchet with a floor, like
   the menu-parity one. Raising it is the point of the exercise; lowering
   it to make a build pass is not.

What conformance means here is that DS9's documented command *is accepted
and does something*, not that the pixels match -- that would need DS9
itself running, which CI does not have. Where a command is legitimately
refused (a survey a server does not offer, a scope we do not implement),
the refusal is a message, and the report says which.
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from ncrads9.communication.xpa.xpa_commands import XPACommands

CORPUS = Path(__file__).resolve().parents[2] / "docs" / "parity" / "ds9_xpa_examples.json"

#: `NCRADS9_XPA_PROGRESS=1 pytest -s ...` prints each command as it runs,
#: which is how you find the one that hangs.
_PROGRESS = bool(os.environ.get("NCRADS9_XPA_PROGRESS"))

SIZE = 24

#: Points whose examples are not run, and why. Not "these do not work" --
#: each is a thing that must not happen inside a test process.
SKIPPED: dict[str, str] = {
    "exit": "closes the application",
    "quit": "closes the application",
    "sleep": "sleeps for real seconds",
    "iexam": "blocks until someone clicks the image",
    "imexam": "blocks until someone clicks the image",
    "raise": "raises a window, which the offscreen platform warns about endlessly",
    "iconify": "iconifies the window the other tests are using",
    "print": "sends to a printer",
    "psprint": "sends to a printer",
    "pagesetup": "opens the printer's own dialog on some platforms",
    "pspagesetup": "same",
    "console": "runs arbitrary Python from DS9's Tcl examples",
    "tcl": "same",
    "source": "same",
    "web": "opens a browser",
    "url": "downloads over the network",
    "samp": "talks to a hub",
    "shm": "attaches shared memory the example does not create",
    "movie": "encodes a movie",
    "backup": "writes a session next to the test",
    "restore": "reads one that is not there",
}

#: Commands whose *arguments* reach past the process even though their
#: point is safe: a printer dialog, a browser, another application. The
#: grammar around them is still exercised by the point's other examples.
_UNSAFE_WORDS = (
    "http://",
    "https://",
    "ftp://",
    "broadcast",
    "send ",
    " print",
    " pagesetup",
    " page setup",
)


def _runnable(command: str) -> bool:
    """Whether one documented example can be run inside a test."""
    name = command.split()[0].lower()
    if name in SKIPPED:
        return False
    return not any(word in command for word in _UNSAFE_WORDS)


@pytest.fixture(scope="module")
def corpus() -> dict:
    if not CORPUS.is_file():
        pytest.skip(f"{CORPUS} is missing; run tools/import_ds9_xpa_examples.py")
    return json.loads(CORPUS.read_text())


@pytest.fixture(scope="module")
def quiet(monkeypatch_module):
    """No dialog may block: the corpus opens a great many of them.

    Every modal entry point is stubbed rather than just `exec`, because
    the static helpers (`QMessageBox.information`, `QFileDialog.get*`)
    do not go through it.
    """
    from PyQt6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox

    ok = QMessageBox.StandardButton.Ok
    monkeypatch_module.setattr(QMessageBox, "exec", lambda self: ok)
    for name in ("information", "warning", "critical", "about", "question"):
        monkeypatch_module.setattr(QMessageBox, name, staticmethod(lambda *a, **k: ok))
    monkeypatch_module.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))
    monkeypatch_module.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    monkeypatch_module.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))
    monkeypatch_module.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)))
    monkeypatch_module.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("", False)))
    monkeypatch_module.setattr(QInputDialog, "getInt", staticmethod(lambda *a, **k: (0, False)))
    monkeypatch_module.setattr(QInputDialog, "getDouble", staticmethod(lambda *a, **k: (0.0, False)))
    monkeypatch_module.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)


@pytest.fixture(scope="module")
def offline(monkeypatch_module):
    """No socket may be opened.

    DS9's examples include `catalog sdss`, `vo`, `footprint cxc` and the
    image servers, all of which reach out. A test that queries VizieR is
    slow, flaky, and rude to the archive; refusing the socket itself is
    surer than stubbing each client, and turns a query into an immediate,
    catchable error -- which is a fair thing for the point to report.
    """
    import socket

    def refuse(*_args, **_kwargs):
        raise OSError("the conformance test runs offline")

    monkeypatch_module.setattr(socket.socket, "connect", refuse)
    monkeypatch_module.setattr(socket, "create_connection", refuse)
    monkeypatch_module.setattr(socket, "getaddrinfo", refuse)


@pytest.fixture(scope="module")
def sandbox(tmp_path_factory, monkeypatch_module):
    """Run the corpus somewhere writable that is not the repository.

    DS9's examples name files -- `saveimage ds9.tiff`, `export tsv
    foo.tsv` -- and the points that take them write to the working
    directory. Without this the suite leaves a scatter of `foo.*` in the
    checkout, which is both untidy and a way to make a later test pass for
    the wrong reason.
    """
    monkeypatch_module.chdir(tmp_path_factory.mktemp("cwd"))


@pytest.fixture(scope="module")
def monkeypatch_module():
    """`monkeypatch`, but lasting the module -- the built-in one is
    function-scoped and the corpus runs once for the whole module."""
    patcher = pytest.MonkeyPatch()
    yield patcher
    patcher.undo()


@pytest.fixture(scope="module")
def window(qapp, tmp_path_factory):
    """One window for the whole corpus.

    Fifteen hundred commands against a fresh window each would take
    minutes; against one window they take seconds, and running them in
    sequence against a window that accumulates state is closer to what a
    script does anyway.
    """
    from ncrads9.ui.controllers.edit import EditController
    from ncrads9.ui.main_window import MainWindow

    tmp_path = tmp_path_factory.mktemp("conformance")
    original = EditController.preferences_path
    EditController.preferences_path = staticmethod(lambda: tmp_path / "prefs.json")

    rows, columns = np.indices((SIZE, SIZE))
    header = fits.Header(
        {
            "CRPIX1": SIZE // 2,
            "CRPIX2": SIZE // 2,
            "CRVAL1": 202.48,
            "CRVAL2": 47.21,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
        }
    )
    path = tmp_path / "sky.fits"
    fits.PrimaryHDU(data=(rows + columns).astype(np.float32), header=header).writeto(path)

    made = MainWindow()
    made._rebuild_image_viewer(False)
    made.display.load_fits(str(path))
    # Nothing here touches the network: an image server that would fetch
    # gets the local file back instead.
    made.image_servers.transport = lambda url, timeout=0: path.read_bytes()
    yield made
    made.close()
    EditController.preferences_path = original


@pytest.fixture(scope="module")
def results(corpus, window, quiet, offline, sandbox) -> list[dict]:
    """Every runnable example, run once, with what came back.

    Module-scoped: the corpus is run once and the assertions below read
    the same results, rather than running fifteen hundred commands per
    test.
    """
    commands = XPACommands(window)
    known = set(commands.get_available_commands())
    found = []
    for name, examples in corpus["commands"].items():
        for kind in ("get", "set"):
            for command in examples[kind]:
                if not _runnable(command):
                    continue
                words = shlex.split(command) if "'" in command else command.split()
                request = {"get": True, "args": words[1:]} if kind == "get" else {"args": words[1:]}
                record = {"point": name, "kind": kind, "command": command, "known": name in known}
                if _PROGRESS:
                    print(f"  {kind} {command}", flush=True)
                try:
                    reply = commands.handle(words[0], request)
                    record["status"] = reply.get("status")
                    record["message"] = reply.get("message", "")
                # Catching everything is the point of this test.
                except BaseException as exc:
                    record["status"] = "raised"
                    record["message"] = f"{type(exc).__name__}: {exc}"
                found.append(record)
    return found


# -- 1. nothing raises -------------------------------------------------------------


def test_no_documented_command_raises(results):
    """An XPA caller gets a reply, never a traceback. Absolute: a point may
    refuse anything, but it must refuse it in words."""
    raised = [record for record in results if record["status"] == "raised"]
    assert raised == [], "\n".join(f"{r['command']} -> {r['message']}" for r in raised[:20])


# -- 2. every point is known -------------------------------------------------------


def test_every_documented_point_is_known(results):
    """A name DS9 has and we do not is a script that breaks on the name
    rather than on the feature, which is the harder failure to diagnose."""
    unknown = sorted({record["point"] for record in results if not record["known"]})
    assert unknown == []


def test_the_corpus_covers_most_of_ds9s_points(corpus):
    """A corpus that shrank because the reference moved is worth catching:
    every assertion here is only as good as what it runs."""
    assert corpus["points"] >= 100
    assert corpus["examples"] >= 1400


# -- 3. the ratchet ----------------------------------------------------------------

#: How many of DS9's documented commands are accepted today, of 1407 that
#: can be run in a test process. A floor, not a target: raise it when a
#: milestone improves things, and never lower it to make a build pass -- a
#: command that stopped being accepted is a regression, and the report
#: below names it.
#:
#: Writing this suite took the number from 633 to 940, by finding: a
#: dispatcher that ran the *setter* for a read with arguments, in both
#: halves, so `xpaget ds9 contour clear` cleared the contours and `xpaget
#: ds9 frame delete` deleted the frame; `xpaset -p ds9 file foo.fits`, the
#: commonest XPA command there is, refused because the path was read as
#: the verb; `catalog` and `footprint` pointed at methods that do not
#: exist; `scale sideways` accepted and quietly left the scale linear,
#: with `scale mode`, `limits`, `scope` and `datasec` doing nothing at
#: all; `saveimage jpeg out.jpeg 75` reading the format as the filename;
#: and `contour` and `frame` answering a fraction of their grammars.
#:
#: Most of what is still refused is a feature we do not have rather than a
#: bug -- DS9's own search windows, its per-column catalogue editing --
#: and the report says which.
ACCEPTED_FLOOR = 935


def test_the_number_accepted_does_not_fall(results, capsys):
    accepted = [record for record in results if record["status"] == "ok"]
    with capsys.disabled():
        print(f"\nXPA conformance: {len(accepted)}/{len(results)} of DS9's documented commands accepted")
    assert len(accepted) >= ACCEPTED_FLOOR, (
        f"{len(accepted)} accepted, below the floor of {ACCEPTED_FLOOR}. "
        "Something that used to be accepted no longer is."
    )


def test_the_refusals_are_reported(results, tmp_path_factory, capsys):
    """Write the refusals out. Not an assertion -- a refusal can be
    correct -- but the list is what says where to work next, and burying
    it in a variable nobody prints would waste the whole exercise."""
    refused = [record for record in results if record["status"] != "ok"]
    report = tmp_path_factory.mktemp("report") / "xpa_conformance.txt"
    report.write_text("\n".join(f"{record['command']}\n    {record['message']}" for record in refused) + "\n")
    with capsys.disabled():
        print(f"XPA conformance: {len(refused)} refused; the list is at {report}")
    assert report.is_file()


def test_a_refusal_always_says_why(results):
    """A point that refuses without a message tells a caller nothing, and
    is indistinguishable from a bug."""
    silent = [r for r in results if r["status"] not in ("ok", "raised") and not r["message"].strip()]
    assert silent == [], "\n".join(record["command"] for record in silent[:20])
