# This file is part of ncrads9.
#
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
The image servers DS9 fetches cutouts from.

Nine of them, each with its own CGI and its own idea of how to ask
(`servers.py`), one transport that fetches and checks the reply
(`fetch.py`), and a Simple Image Access client for the one that needs it.

Author: Yogesh Wadadekar
"""

from . import fetch, servers
from .fetch import ImageRequest, ImageServerError, retrieve
from .servers import SERVERS, ImageServer, Protocol, SizeUnit, Survey, by_name
from .sia_client import SIAClient

__all__ = [
    "SERVERS",
    "ImageRequest",
    "ImageServer",
    "ImageServerError",
    "Protocol",
    "SIAClient",
    "SizeUnit",
    "Survey",
    "by_name",
    "fetch",
    "retrieve",
    "servers",
]
