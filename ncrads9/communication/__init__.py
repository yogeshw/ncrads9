# NCRADS9 - Communication Package
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
Communication package for NCRADS9.

This package provides communication protocols for interoperability:
- XPA: X Public Access for DS9-compatible command interface
- SAMP: Simple Application Messaging Protocol for VO tools
- IIS: IRAF Image Server for legacy IRAF compatibility

Author: Yogesh Wadadekar
"""

from .xpa import XPAServer, XPACommands
from .samp import SAMPClient, SAMPHandlers, SAMPHub
from .iis import IISServer

__all__ = [
    "XPAServer",
    "XPACommands",
    "SAMPClient",
    "SAMPHandlers",
    "SAMPHub",
    "IISServer",
]
