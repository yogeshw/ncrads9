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
#
# Author: Yogesh Wadadekar

"""Tests for core.fits_handler module."""

from pathlib import Path

from ncrads9.core.fits_handler import FITSHandler


class TestFitsHandler:
    """Test cases for FitsHandler class."""

    def test_load_uses_memmap_and_lazy_reading_by_default(self, monkeypatch):
        calls = {}

        def _fake_open(path, **kwargs):
            calls["path"] = path
            calls["kwargs"] = kwargs
            return ["dummy-hdu"]

        monkeypatch.setattr("ncrads9.core.fits_handler.fits.open", _fake_open)
        handler = FITSHandler()
        handler.load("/tmp/example.fits")

        assert calls["path"] == Path("/tmp/example.fits")
        assert calls["kwargs"]["memmap"] is True
        assert calls["kwargs"]["lazy_load_hdus"] is True
        assert calls["kwargs"]["mode"] == "readonly"

    def test_load_can_disable_memmap(self, monkeypatch):
        calls = {}

        def _fake_open(path, **kwargs):
            calls["kwargs"] = kwargs
            return ["dummy-hdu"]

        monkeypatch.setattr("ncrads9.core.fits_handler.fits.open", _fake_open)
        handler = FITSHandler()
        handler.load("/tmp/example.fits", memmap=False)

        assert calls["kwargs"]["memmap"] is False
