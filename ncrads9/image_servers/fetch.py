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
Fetching a cutout from an image server and putting it in a file.

One transport for all nine servers, injectable as everywhere else in this
codebase, so a test can hand over a FITS file it made itself instead of
asking Harvard for one.

Two details that decide whether this works in practice:

  - the reply is checked for being FITS before it is saved. These CGIs
    answer an out-of-range position or a survey with no coverage with an
    HTML page and a 200 status, and a `.fits` file full of HTML is a
    confusing thing to be handed.
  - a gzipped reply is decompressed. Three of the servers are asked for
    `c=gz` because that is what DS9 asks for, and the reply then is a
    gzip stream whatever the extension says.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import gzip
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .servers import ImageServer, Protocol

#: How long to wait for a server, in seconds. Cutout CGIs are slow.
DEFAULT_TIMEOUT = 120.0

#: What a FITS file starts with.
FITS_MAGIC = b"SIMPLE  ="

#: What a gzip stream starts with.
GZIP_MAGIC = b"\x1f\x8b"

#: How much of a non-FITS reply to quote back in the error.
ERROR_EXCERPT = 300


class ImageServerError(RuntimeError):
    """A cutout that could not be fetched, for the reason given."""


@dataclass
class ImageRequest:
    """What cutout to ask for.

    Attributes:
        server: Which server.
        longitude, latitude: Where, in degrees.
        width, height: How big, in the server's own size unit.
        survey: Which survey, or empty for the server's default.
        timeout: How long to wait.
    """

    server: ImageServer
    longitude: float
    latitude: float
    width: float
    height: float
    survey: str = ""
    timeout: float = DEFAULT_TIMEOUT

    def url(self) -> str:
        """The URL this request would fetch."""
        return self.server.query(self.longitude, self.latitude, self.width, self.height, self.survey)


#: A transport: called with (url, timeout), returning the response bytes.
Transport = Callable[[str, float], bytes]


def fetch(url: str, timeout: float = DEFAULT_TIMEOUT) -> bytes:
    """Retrieve a URL. The only function here that uses the network.

    Raises:
        ImageServerError: If the request fails, or the URL is not http.
    """
    from urllib.error import URLError
    from urllib.request import urlopen

    if not url.lower().startswith(("http://", "https://")):
        raise ImageServerError(f"not an http URL: {url}")
    try:
        with urlopen(url, timeout=timeout) as response:
            return response.read()
    except (URLError, OSError, ValueError) as exc:
        raise ImageServerError(f"could not reach the image server: {exc}") from exc


def unpack(payload: bytes) -> bytes:
    """Decompress a reply if it is gzipped, and hand it back if not."""
    if payload[:2] == GZIP_MAGIC:
        try:
            return gzip.decompress(payload)
        except OSError as exc:
            raise ImageServerError(f"the reply is not readable gzip: {exc}") from exc
    return payload


def is_fits(payload: bytes) -> bool:
    """Whether some bytes look like a FITS file."""
    return payload[:9] == FITS_MAGIC


def retrieve(request: ImageRequest, transport: Transport | None = None) -> Path:
    """Fetch one cutout and save it to a temporary FITS file.

    Args:
        request: What to ask for.
        transport: How to fetch. The real client by default.

    Returns:
        The path of the saved file.

    Raises:
        ImageServerError: If the fetch fails or the reply is not an image.
    """
    caller = transport or fetch
    payload = unpack(caller(request.url(), request.timeout))

    if request.server.protocol is Protocol.SIA:
        payload = unpack(caller(_first_image(payload), request.timeout))

    if not is_fits(payload):
        raise ImageServerError(f"{request.server.label} did not return a FITS image: " f"{_excerpt(payload)}")

    with tempfile.NamedTemporaryFile(
        prefix=f"{request.server.name}_", suffix=".fits", delete=False
    ) as handle:
        handle.write(payload)
        return Path(handle.name)


def _first_image(payload: bytes) -> str:
    """The first FITS image link in a SIA reply.

    Raises:
        ImageServerError: If the reply lists no FITS image.
    """
    import io

    try:
        from astropy.io.votable import parse as parse_votable

        votable = parse_votable(io.BytesIO(payload))
    except Exception as exc:
        raise ImageServerError(f"the image list could not be read: {exc}") from exc

    for table in votable.iter_tables():
        rows = table.to_table(use_names_over_ids=True)
        if not len(rows):
            continue
        # The access URL is named several ways across SIA versions, and the
        # format column tells FITS from JPEG previews.
        lookup = {name.lower(): name for name in rows.colnames}
        access = next(
            (lookup[key] for key in ("access_url", "accessurl", "acref", "url") if key in lookup),
            None,
        )
        if access is None:
            continue
        formats = next(
            (lookup[key] for key in ("access_format", "format", "content_type") if key in lookup),
            None,
        )
        for row in rows:
            if formats is not None and "fits" not in str(row[formats]).lower():
                continue
            link = str(row[access]).strip()
            if link:
                return link

    raise ImageServerError("the image server listed no FITS image for that position")


def _excerpt(payload: bytes) -> str:
    """The start of a non-FITS reply, for an error message.

    These CGIs answer a bad position with an HTML page and a 200, so the
    page's own words are the only explanation available.
    """
    import re

    text = payload[:ERROR_EXCERPT].decode("utf-8", errors="replace")
    text = re.sub(r"<[^>]+>", " ", text)
    text = " ".join(text.split())
    return text or "an empty reply"
