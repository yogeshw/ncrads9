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
Catalog overlay display for DS9 visualization.

Author: Yogesh Wadadekar
"""

from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from astropy.coordinates import SkyCoord
from astropy.table import Table
import astropy.units as u


class MarkerShape(Enum):
    """Supported marker shapes for catalog overlays."""

    CIRCLE = "circle"
    BOX = "box"
    DIAMOND = "diamond"
    CROSS = "cross"
    X = "x"
    ELLIPSE = "ellipse"
    POINT = "point"


@dataclass
class MarkerStyle:
    """Style configuration for catalog markers."""

    shape: MarkerShape = MarkerShape.CIRCLE
    color: str = "green"
    size: float = 10.0
    width: int = 1
    font: str = "helvetica 10 normal"
    show_label: bool = False
    label_column: Optional[str] = None


@dataclass
class CatalogOverlay:
    """Container for catalog overlay data."""

    name: str
    table: Table
    coords: List[SkyCoord]
    style: MarkerStyle = field(default_factory=MarkerStyle)
    visible: bool = True


class CatalogDisplay:
    """Class for rendering catalog overlays on DS9."""

    def __init__(self, ds9_instance: Any = None) -> None:
        """
        Initialize catalog display.

        Parameters
        ----------
        ds9_instance : Any, optional
            DS9 connection instance.
        """
        self.ds9: Any = ds9_instance
        self._overlays: Dict[str, CatalogOverlay] = {}
        self._default_style: MarkerStyle = MarkerStyle()

    def add_overlay(
        self,
        name: str,
        table: Table,
        coords: Optional[List[SkyCoord]] = None,
        style: Optional[MarkerStyle] = None,
    ) -> bool:
        """
        Add a catalog overlay.

        Parameters
        ----------
        name : str
            Unique name for the overlay.
        table : Table
            Catalog result table.
        coords : list of SkyCoord, optional
            Pre-extracted coordinates. If None, will attempt extraction.
        style : MarkerStyle, optional
            Marker style configuration.

        Returns
        -------
        bool
            True if overlay was added successfully.
        """
        if coords is None:
            coords = self._extract_coordinates(table)
            if coords is None:
                print(f"Could not extract coordinates from table for {name}")
                return False

        overlay = CatalogOverlay(
            name=name,
            table=table,
            coords=coords,
            style=style or MarkerStyle(),
        )

        self._overlays[name] = overlay
        return True

    def remove_overlay(self, name: str) -> bool:
        """
        Remove a catalog overlay.

        Parameters
        ----------
        name : str
            Name of the overlay to remove.

        Returns
        -------
        bool
            True if overlay was removed.
        """
        if name in self._overlays:
            del self._overlays[name]
            return True
        return False

    def show_overlay(self, name: str) -> None:
        """Set overlay visibility to True."""
        if name in self._overlays:
            self._overlays[name].visible = True

    def hide_overlay(self, name: str) -> None:
        """Set overlay visibility to False."""
        if name in self._overlays:
            self._overlays[name].visible = False

    def set_style(self, name: str, style: MarkerStyle) -> None:
        """Set marker style for an overlay."""
        if name in self._overlays:
            self._overlays[name].style = style

    def render(self, overlay_name: Optional[str] = None) -> str:
        """
        Render overlays as DS9 region format.

        Parameters
        ----------
        overlay_name : str, optional
            Specific overlay to render. If None, renders all visible.

        Returns
        -------
        str
            DS9 region format string.
        """
        regions: List[str] = []
        regions.append("# Region file format: DS9 version 4.1")
        regions.append("global color=green dashlist=8 3 width=1")
        regions.append("fk5")

        overlays = (
            [self._overlays[overlay_name]]
            if overlay_name and overlay_name in self._overlays
            else self._overlays.values()
        )

        for overlay in overlays:
            if not overlay.visible:
                continue

            style = overlay.style
            for i, coord in enumerate(overlay.coords):
                region = self._format_region(coord, style, overlay, i)
                regions.append(region)

        return "\n".join(regions)

    def _format_region(
        self,
        coord: SkyCoord,
        style: MarkerStyle,
        overlay: CatalogOverlay,
        index: int,
    ) -> str:
        """Format a single region entry."""
        ra = coord.ra.deg
        dec = coord.dec.deg
        shape = style.shape.value
        color = style.color
        size = style.size

        if shape == "circle":
            region = f"circle({ra},{dec},{size}\")"
        elif shape == "box":
            region = f"box({ra},{dec},{size}\",{size}\",0)"
        elif shape == "diamond":
            region = f"polygon({ra},{dec-size/3600},{ra+size/3600},{dec},{ra},{dec+size/3600},{ra-size/3600},{dec})"
        elif shape == "cross":
            region = f"cross({ra},{dec},{size}\")"
        elif shape == "x":
            region = f"x({ra},{dec},{size}\")"
        elif shape == "ellipse":
            region = f"ellipse({ra},{dec},{size}\",{size/2}\",0)"
        elif shape == "point":
            region = f"point({ra},{dec})"
        else:
            region = f"circle({ra},{dec},{size}\")"

        props = f" # color={color} width={style.width}"

        if style.show_label and style.label_column:
            try:
                label = str(overlay.table[index][style.label_column])
                props += f' text="{label}"'
            except (IndexError, KeyError):
                pass

        return region + props

    def _extract_coordinates(self, table: Table) -> Optional[List[SkyCoord]]:
        """Extract coordinates from table."""
        ra_col: Optional[str] = None
        dec_col: Optional[str] = None

        for col in table.colnames:
            col_lower = col.lower()
            if col_lower in ("ra", "_ra", "raj2000", "ra_icrs", "ra_j2000"):
                ra_col = col
            elif col_lower in (
                "dec",
                "_dec",
                "dej2000",
                "de",
                "dec_icrs",
                "dec_j2000",
            ):
                dec_col = col

        if ra_col is None or dec_col is None:
            return None

        coords: List[SkyCoord] = []
        for row in table:
            try:
                coord = SkyCoord(
                    ra=float(row[ra_col]),
                    dec=float(row[dec_col]),
                    unit=(u.deg, u.deg),
                    frame="icrs",
                )
                coords.append(coord)
            except Exception:
                continue

        return coords if coords else None

    def send_to_ds9(self, overlay_name: Optional[str] = None) -> bool:
        """
        Send regions to DS9.

        Parameters
        ----------
        overlay_name : str, optional
            Specific overlay to send. If None, sends all visible.

        Returns
        -------
        bool
            True if regions were sent successfully.
        """
        if self.ds9 is None:
            print("No DS9 connection available")
            return False

        try:
            regions = self.render(overlay_name)
            self.ds9.set("regions", regions)
            return True
        except Exception as e:
            print(f"Error sending regions to DS9: {e}")
            return False

    def clear_ds9_regions(self) -> bool:
        """Clear all regions from DS9."""
        if self.ds9 is None:
            return False

        try:
            self.ds9.set("regions delete all")
            return True
        except Exception as e:
            print(f"Error clearing DS9 regions: {e}")
            return False

    def get_overlay_names(self) -> List[str]:
        """Return list of overlay names."""
        return list(self._overlays.keys())

    def get_overlay(self, name: str) -> Optional[CatalogOverlay]:
        """Get overlay by name."""
        return self._overlays.get(name)

    def set_default_style(self, style: MarkerStyle) -> None:
        """Set default marker style for new overlays."""
        self._default_style = style

    def clear_all(self) -> None:
        """Remove all overlays."""
        self._overlays.clear()
