# NCRADS9

A Python/Qt6 FITS viewer inspired by SAOImageDS9 for astronomical imaging and data visualization.

## Description

NCRADS9 is a modern reimplementation of SAOImageDS9, built with Python and Qt6.
It aims to be a functional clone: the menus, the keyboard, the region files, the
XPA access points and the SAMP and IIS protocols are DS9's, so a script or a
habit carries over. Underneath it is Astropy, NumPy and SciPy rather than Tcl
and C++, and where a modern interface is plainly better -- a modeless dialog
that does not block the window behind it, a preferences window generated from
one table so it cannot disagree with the settings it edits -- it takes that
instead.

## Feature Status

Nine milestones (M0–M9) are complete: the roadmap is in [PLAN.md](PLAN.md) and
the itemised record, deviations and bugs included, in [TODO.md](TODO.md).
Menu parity against DS9 is **92%** of its labels, measured by
`python tools/menu_diff.py --summary`, and 3200 tests cover about 77% of the
code.

### Implemented

- **FITS** — images, cubes, multi-extension files, mosaics (WCS, IRAF, WFPC2)
  and binary tables binned into images; DS9's file specification syntax
  (`file.fits[3][bin=x,y][100:200,*]`); RGB, HSV and HLS frames from cubes or
  extensions; import and export of array, NRRD, ENVI, GIF, TIFF, JPEG and PNG;
  save as FITS in each of those shapes.
- **Large images** — memory-mapped reads, OpenGL tile rendering, viewport-only
  texture uploads and downsampled panner previews.
- **Display** — zoom, pan, rotate, orient, crop, block and bin; DS9's scales
  (linear, log, power, square root, squared, sinh, asinh, histogram
  equalisation) with zscale, zmax, minmax and user limits; the extended
  colormap menu with `.lut`/`.sao` load and save, contrast and bias; a
  colorbar with numerics, ticks and per-frame colormaps.
- **Frames** — create, delete, clear, reset; single, tile, blink and fade;
  match and lock by image, WCS, crop, slice, bin, scale, colorbar and block;
  the Tile Parameters dialog.
- **Regions** — every DS9 shape, its file formats (DS9, XML, CIAO, SAOtng,
  SAOimage, PROS, X/Y), templates, groups, composites, centroiding, the
  properties and font cascades, per-region analysis windows, and regions read
  out of a FITS `REGION` extension.
- **Analysis** — contours (generate, load, save, copy, paste, export),
  coordinate grid, smoothing, statistics, histogram, radial profile, the pixel
  table, horizontal and vertical cut graphs, the Plot Tool, and DS9's external
  analysis files (`.ans`) with its macro language.
- **3D** — a rendered cube at any azimuth and elevation, DS9's methods, and
  the 3D dialog.
- **Catalogues and archives** — VizieR, SIMBAD, NED, SDSS, SkyBot and cone
  search; the catalogue tool with filtering, sorting, matching and plotting; image
  servers for the DSS (SAO, ESO, STScI), 2MASS, SkyView, VLA, NVSS and VLSS;
  footprint services; the VO registry.
- **Communication** — an XPA server answering **all 143 of DS9's access
  points**, checked against DS9's own documented examples
  (`tests/unit/test_xpa_conformance.py`); SAMP with a hub, image and table
  broadcast and catalogue overlays; the IIS protocol, so IRAF's `display` and
  `imexam` work.
- **Sessions** — backup and restore, a five-minute autosave, notes, an undo
  stack, Preserve During Load, and DS9's Preferences over 29 topics with
  editable keyboard shortcuts.
- **Printing** — a PostScript driver with page setup, and print to printer or
  file.
- **Illustrate** — DS9's non-WCS annotation layer and its file format.
- **Interface** — DS9's window layout, menus and button bars; the magnifier,
  panner and information panel; a Python console where DS9 has a Tcl one;
  themes; and the menus in DS9's eight languages, from DS9's own catalogues.

### Partial

- **Translations** — the menus are translated into Czech, Danish, German,
  Spanish, French, Japanese, Portuguese and Chinese. The dialogs go through
  the same mechanism but stay in English: DS9's catalogue is a catalogue of
  *menu* labels and covers about a fifth of what a dialog says, and a dialog
  is translated only when enough of it can be. Status messages are not
  translated.
- **URL loading** — `File → Open as → URL` downloads and opens, but without a
  progress indicator on a slow fetch.

### Deliberately different from DS9

Recorded with reasons in [PLAN.md](PLAN.md) section 7. In short: Python
replaces Tcl in the console and in analysis scripting; Prism shows one block
of a table at a time and leaves sorting to the catalogue tool, which holds the
whole of it; and some DS9 dialogs are modeless here where DS9 blocks.

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
