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
FITS header parsing utilities.

Provides functions for parsing and extracting information from FITS headers.

Author: Yogesh Wadadekar
"""

from typing import Any

from astropy.io import fits


def parse_header(header: fits.Header) -> dict[str, Any]:
    """Parse a FITS header and extract key information.

    Args:
        header: The FITS header to parse.

    Returns:
        Dictionary containing parsed header information.
    """
    result: dict[str, Any] = {
        "dimensions": _get_dimensions(header),
        "data_type": header.get("BITPIX"),
        "object": header.get("OBJECT"),
        "telescope": header.get("TELESCOP"),
        "instrument": header.get("INSTRUME"),
        "observer": header.get("OBSERVER"),
        "date_obs": header.get("DATE-OBS"),
        "exptime": header.get("EXPTIME"),
        "has_wcs": _has_wcs(header),
    }
    return result


def _get_dimensions(header: fits.Header) -> list[int] | None:
    """Extract image dimensions from header.

    Args:
        header: The FITS header.

    Returns:
        List of dimensions, or None if not available.
    """
    naxis = header.get("NAXIS", 0)
    if naxis == 0:
        return None

    dims = []
    for i in range(1, naxis + 1):
        dim = header.get(f"NAXIS{i}")
        if dim is not None:
            dims.append(dim)
    return dims if dims else None


def _has_wcs(header: fits.Header) -> bool:
    """Check if header contains WCS information.

    Args:
        header: The FITS header.

    Returns:
        True if WCS keywords are present.
    """
    wcs_keywords = ["CTYPE1", "CRVAL1", "CRPIX1", "CDELT1", "CD1_1"]
    return any(kw in header for kw in wcs_keywords)


def extract_keywords(
    header: fits.Header,
    keywords: list[str],
    default: Any = None,
) -> dict[str, Any]:
    """Extract specific keywords from a header.

    Args:
        header: The FITS header.
        keywords: List of keywords to extract.
        default: Default value for missing keywords.

    Returns:
        Dictionary of keyword values.
    """
    result = {}
    for kw in keywords:
        result[kw] = header.get(kw, default)
    return result


def get_wcs_keywords(header: fits.Header) -> dict[str, Any]:
    """Extract WCS-related keywords from header.

    Args:
        header: The FITS header.

    Returns:
        Dictionary of WCS keyword values.
    """
    wcs_keys = [
        "CTYPE1",
        "CTYPE2",
        "CTYPE3",
        "CRVAL1",
        "CRVAL2",
        "CRVAL3",
        "CRPIX1",
        "CRPIX2",
        "CRPIX3",
        "CDELT1",
        "CDELT2",
        "CDELT3",
        "CD1_1",
        "CD1_2",
        "CD2_1",
        "CD2_2",
        "PC1_1",
        "PC1_2",
        "PC2_1",
        "PC2_2",
        "CROTA1",
        "CROTA2",
        "EQUINOX",
        "RADESYS",
        "LONPOLE",
        "LATPOLE",
    ]
    return extract_keywords(header, wcs_keys)


def get_observation_info(header: fits.Header) -> dict[str, Any]:
    """Extract observation metadata from header.

    Args:
        header: The FITS header.

    Returns:
        Dictionary of observation information.
    """
    obs_keys = [
        "OBJECT",
        "TELESCOP",
        "INSTRUME",
        "OBSERVER",
        "DATE-OBS",
        "TIME-OBS",
        "MJD-OBS",
        "EXPTIME",
        "AIRMASS",
        "RA",
        "DEC",
        "EPOCH",
        "FILTER",
        "BAND",
    ]
    return extract_keywords(header, obs_keys)


def header_to_dict(header: fits.Header) -> dict[str, Any]:
    """Convert entire header to dictionary.

    Args:
        header: The FITS header.

    Returns:
        Dictionary representation of the header.
    """
    result = {}
    for card in header.cards:
        if card.keyword and card.keyword not in ("COMMENT", "HISTORY", ""):
            result[card.keyword] = card.value
    return result


def get_comments(header: fits.Header) -> list[str]:
    """Extract COMMENT cards from header.

    Args:
        header: The FITS header.

    Returns:
        List of comment strings.
    """
    return list(header.get("COMMENT", []))


def get_history(header: fits.Header) -> list[str]:
    """Extract HISTORY cards from header.

    Args:
        header: The FITS header.

    Returns:
        List of history strings.
    """
    return list(header.get("HISTORY", []))


def header_to_lines(header: fits.Header | dict[str, Any]) -> list[str]:
    """Render a header as aligned ``KEYWORD = value / comment`` lines.

    Works from ``header.cards`` when given a real ``fits.Header``, so comments,
    COMMENT and HISTORY cards all survive; a plain mapping is rendered without
    comments, since it has none to give.

    Args:
        header: An ``astropy.io.fits.Header``, or any mapping of keyword to
            value.

    Returns:
        One line per card, in header order.
    """
    cards = getattr(header, "cards", None)
    if cards is None:
        return [f"{key!s:<8} = {value!r}" for key, value in dict(header).items()]

    lines: list[str] = []
    for card in cards:
        keyword = card.keyword or ""
        if keyword in ("COMMENT", "HISTORY"):
            lines.append(f"{keyword:<8}   {card.value}")
            continue
        if not keyword:
            # A blank card is a deliberate spacer in the header.
            lines.append("")
            continue
        rendered = f"{keyword:<8} = {card.value!r}"
        if card.comment:
            rendered = f"{rendered} / {card.comment}"
        lines.append(rendered)
    return lines


def summarize_header(header: fits.Header) -> list[str]:
    """Return a short human-readable summary of what the header describes.

    Shown above the raw cards so the interesting facts -- object, instrument,
    dimensions, whether there is a WCS -- do not have to be hunted for.
    """
    info = parse_header(header)
    dimensions = info.get("dimensions")

    rows = [
        ("Object", info.get("object")),
        ("Telescope", info.get("telescope")),
        ("Instrument", info.get("instrument")),
        ("Date-Obs", info.get("date_obs")),
        ("Exposure", info.get("exptime")),
        ("Dimensions", " x ".join(str(d) for d in dimensions) if dimensions else None),
        ("BITPIX", info.get("data_type")),
        ("WCS", "yes" if info.get("has_wcs") else "no"),
    ]
    return [f"{label:<11} {value}" for label, value in rows if value not in (None, "")]
