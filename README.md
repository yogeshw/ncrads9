# NCRADS9

A Python/Qt6 FITS viewer inspired by SAOImageDS9 for astronomical imaging and data visualization.

## Description

NCRADS9 is a modern reimplementation of SAOImageDS9, built with Python and Qt6. It currently focuses on core FITS viewing/analysis workflows with a maintainable codebase leveraging the Astropy ecosystem.

## Feature Status (v0.1.0)

### Implemented
- **FITS viewing**: Open FITS files (`.fits`, `.fit`, `.fts`, including gzip variants)
- **Display controls**: Zoom, pan, binning, zscale/minmax limits, colormap inversion
- **Colormaps and scales**: Gray/heat/cool/rainbow/viridis/plasma/inferno/magma with linear, log, sqrt, squared(power), asinh, and histogram equalization
- **Regions**: Circle/ellipse/box/polygon/line/point creation plus DS9 region load/save (`.reg`)
- **WCS tools**: FK5/FK4/ICRS/Galactic/Ecliptic display with sexagesimal/degree formatting and direction arrows
- **Multi-frame workflow**: New/delete/navigate frames, tile view, blink mode, and match image/WCS settings
- **Analysis dialogs**: Statistics, histogram, contours (with export), pixel table, FITS header viewer
- **Communication**: Built-in XPA server; SAMP connect/disconnect and catalog overlay support

### Partial / In Progress
- **VO tools**: 2MASS SIAP image query and VizieR catalog overlay are wired in the UI; broader catalog/image-server coverage is incomplete
- **Save workflow**: `Save` and `Save As` are not yet writing FITS data
- **Advanced modules**: Some packages exist as scaffolding (for example image-server backends and prism/3D-oriented components)

## Installation

```bash
pip install ncrads9
```

Or from source:

```bash
git clone https://github.com/ncra/ncrads9.git
cd ncrads9
pip install -e .
```

## Usage

```bash
# Launch the application
ncrads9

# Open a FITS file
ncrads9 image.fits

# Open multiple files
ncrads9 image1.fits image2.fits
```

## Dependencies

- Python >= 3.10
- PyQt6 >= 6.4
- PyOpenGL >= 3.1
- Astropy >= 5.0
- Astroquery >= 0.4
- NumPy >= 1.23
- SciPy >= 1.9
- Pillow >= 9.0
- requests >= 2.28

## Documentation

Documentation is available in both HTML and LaTeX formats in the `docs/` directory.

## License

NCRADS9 is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for details.

## Author

**Yogesh Wadadekar**

## Acknowledgments

This project is inspired by SAOImageDS9, developed at the Smithsonian Astrophysical Observatory.
