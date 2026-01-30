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

"""Prism package for spectral analysis.

Author: Yogesh Wadadekar
"""

from .prism_main import PrismWindow
from .spectrum_plot import SpectrumPlot
from .line_id import LineIdentifier, SpectralLine

__all__ = ["PrismWindow", "SpectrumPlot", "LineIdentifier", "SpectralLine"]
