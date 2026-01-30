# NCRADS9

A full-featured Python/Qt6 clone of SAOImageDS9 for astronomical imaging and data visualization.

## Description

NCRADS9 is a modern reimplementation of SAOImageDS9, the popular astronomical imaging application, built with Python and Qt6. It provides all the functionality of DS9 with a modern, maintainable codebase leveraging the Astropy ecosystem.

## Features

- **FITS Image Display**: Full support for FITS images, including multi-extension files, data cubes, and mosaics
- **Multiple Colormaps**: All standard DS9 colormaps plus custom colormap support
- **Scale Algorithms**: Linear, log, power, sqrt, squared, sinh, asinh, histogram equalization
- **Region Support**: All DS9 region shapes with full DS9 region file compatibility
- **WCS Coordinates**: Complete WCS support via Astropy including all standard projections
- **Multi-Frame Display**: Multiple frames, tiling, blinking, RGB compositing
- **3D Visualization**: Data cube navigation and 3D rendering
- **Catalog Access**: VizieR, SIMBAD, NED, 2MASS, SDSS catalog queries
- **Image Servers**: DSS, SkyView, and VO SIA protocol support
- **External Communication**: XPA and SAMP protocol support
- **Analysis Tools**: Statistics, histograms, radial profiles, contours

## Installation

```bash
pip install ncrads9
```

Or from source:

```bash
git clone https://github.com/yourusername/ncrads9.git
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

## Documentation

Documentation is available in both HTML and LaTeX formats in the `docs/` directory.

## License

NCRADS9 is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for details.

## Author

**Yogesh Wadadekar**

## Acknowledgments

This project is inspired by SAOImageDS9, developed at the Smithsonian Astrophysical Observatory.
