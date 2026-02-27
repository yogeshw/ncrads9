# NCRADS9

A Python/Qt6 FITS viewer inspired by SAOImageDS9 for astronomical imaging and data visualization.

## Description

NCRADS9 is a modern reimplementation of SAOImageDS9, built with Python and Qt6. It currently focuses on core FITS viewing/analysis workflows with a maintainable codebase leveraging the Astropy ecosystem.

## Feature Status (v0.1.0)

### Implemented
- **FITS viewing**: Open FITS files (`.fits`, `.fit`, `.fts`, including gzip variants)
- **Large-image handling**: Memory-mapped FITS reads with OpenGL tile rendering, viewport-only texture uploads, and downsampled preview panels for responsive navigation on very large images
- **Display controls**: Zoom, pan, binning, zscale/minmax limits, colormap inversion
- **Colormaps and scales**: DS9-style extended color menu (default + matplotlib/scientific families), user `.lut/.sao` colormap load/save, invert/reset, and configurable colorbar options with linear, log, sqrt, squared(power), asinh, and histogram equalization
- **Regions**: Circle/ellipse/box/polygon/line/point creation plus DS9 region load/save (`.reg`)
- **WCS tools**: FK5/FK4/ICRS/Galactic/Ecliptic display with sexagesimal/degree formatting and direction arrows
- **Multi-frame workflow**: DS9-style expanded Frame menu with frame create/delete/delete-all, clear/reset/refresh, single/tile/blink/fade display modes, goto/show-hide/move controls, extended frame match actions, and RGB channel compositing via Frame→RGB
- **Analysis tools**: DS9-style expanded Analysis menu with name resolution, contour/grid/block/smooth controls, statistics, histogram, radial profile plotting, pixel table, and FITS header viewer
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

# Open command-line option docs in browser
ncrads9 --help

# Open a FITS file
ncrads9 image.fits

# Open multiple files
ncrads9 image1.fits image2.fits

# DS9-style startup options
ncrads9 -log -heat -tile image.fits

# RGB composite startup (creates channel source frames + RGB frame)
ncrads9 -rgb -red r.fits -green g.fits -blue b.fits
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
