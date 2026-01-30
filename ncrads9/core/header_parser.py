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

from typing import Optional, Dict, Any, List, Union, Tuple

from astropy.io import fits


def parse_header(header: fits.Header) -> Dict[str, Any]:
    """Parse a FITS header and extract key information.

    Args:
        header: The FITS header to parse.

    Returns:
        Dictionary containing parsed header information.
    """
    result: Dict[str, Any] = {
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


def _get_dimensions(header: fits.Header) -> Optional[List[int]]:
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
    keywords: List[str],
    default: Any = None,
) -> Dict[str, Any]:
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


def get_wcs_keywords(header: fits.Header) -> Dict[str, Any]:
    """Extract WCS-related keywords from header.

    Args:
        header: The FITS header.

    Returns:
        Dictionary of WCS keyword values.
    """
    wcs_keys = [
        "CTYPE1", "CTYPE2", "CTYPE3",
        "CRVAL1", "CRVAL2", "CRVAL3",
        "CRPIX1", "CRPIX2", "CRPIX3",
        "CDELT1", "CDELT2", "CDELT3",
        "CD1_1", "CD1_2", "CD2_1", "CD2_2",
        "PC1_1", "PC1_2", "PC2_1", "PC2_2",
        "CROTA1", "CROTA2",
        "EQUINOX", "RADESYS", "LONPOLE", "LATPOLE",
    ]
    return extract_keywords(header, wcs_keys)


def get_observation_info(header: fits.Header) -> Dict[str, Any]:
    """Extract observation metadata from header.

    Args:
        header: The FITS header.

    Returns:
        Dictionary of observation information.
    """
    obs_keys = [
        "OBJECT", "TELESCOP", "INSTRUME", "OBSERVER",
        "DATE-OBS", "TIME-OBS", "MJD-OBS",
        "EXPTIME", "AIRMASS",
        "RA", "DEC", "EPOCH",
        "FILTER", "BAND",
    ]
    return extract_keywords(header, obs_keys)


def header_to_dict(header: fits.Header) -> Dict[str, Any]:
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


def get_comments(header: fits.Header) -> List[str]:
    """Extract COMMENT cards from header.

    Args:
        header: The FITS header.

    Returns:
        List of comment strings.
    """
    return list(header.get("COMMENT", []))


def get_history(header: fits.Header) -> List[str]:
    """Extract HISTORY cards from header.

    Args:
        header: The FITS header.

    Returns:
        List of history strings.
    """
    return list(header.get("HISTORY", []))
