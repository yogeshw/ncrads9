# NCRADS9 - Working Features

## Core Functionality ✓

### File Loading
- **File → Open**: File dialog to select FITS files
- **Command line**: `ncrads9 image.fits` loads file on startup
- **Supported formats**: .fits, .fit, .fts, .fits.gz, .fit.gz
- **Error handling**: Shows error dialog if file fails to load

### Image Display
- Automatic ZScale contrast/brightness limits
- Real-time image rendering with scaling and colormaps
- Scrollable viewing area for large images

### Mouse Controls (DS9-style)
- **Mouse wheel**: Zoom in/out (scroll up/down)
- **Right-click + drag**: Adjust contrast/brightness
  - Horizontal drag: Changes contrast
  - Vertical drag: Changes brightness
- **Mouse movement**: Live coordinate tracking

### Zoom Controls
- **Zoom menu → Zoom In** (Ctrl++): Zoom in 20%
- **Zoom menu → Zoom Out** (Ctrl+-): Zoom out 20%
- **Zoom menu → Zoom to Fit**: Fit image to window
- **Zoom menu → Zoom 1:1**: Display at actual pixel size
- Current zoom level shown in status bar

### Scale Algorithms
All available via **Scale menu**:
- Linear (default)
- Log
- Sqrt
- Asinh
- ZScale (auto-limits)

Real-time switching - image updates instantly

### Colormaps
Available via **Color menu**:
- Grey (default)
- Heat
- Cool
- Rainbow
- Plus 15 more DS9-compatible maps

Real-time switching - image updates instantly

### Status Bar Information
Displays continuously:
- **Pixel coordinates**: X: 256 Y: 256
- **WCS coordinates**: RA: 13:29:52.56 Dec: +47:11:44.34 (if available)
- **Pixel value**: Value: 11.5495
- **Image info**: 512x512 BITPIX=-32
- **Zoom level**: Zoom: 1x

### WCS Support
- Automatic WCS detection from FITS header
- Real-time RA/Dec display on mouse movement
- Sexagesimal format (HH:MM:SS.SS ±DD:MM:SS.S)

## Menu System ✓

### File Menu
- Open... (Ctrl+O) - Works
- Save... (Ctrl+S) - Stub
- Save As... (Ctrl+Shift+S) - Stub
- Exit (Ctrl+Q) - Works

### Scale Menu
- Linear, Log, Sqrt, Asinh - All working
- ZScale - Working

### Color Menu
- Grey, Heat, Cool, Rainbow - All working

### Zoom Menu
- Zoom In/Out/Fit/1:1 - All working

### Help Menu
- About NCRADS9 - Works
- About Qt - Works

## Sample Data ✓
Located in `ncrads9/sampleimages/`:
- SDSS9_M51_g.fits (512x512)
- SDSS9_M51_r.fits (512x512)
- SDSS9_M51_i.fits (512x512)

Test images of M51 (Whirlpool Galaxy) from SDSS DR9.

## Usage Examples

### Basic Usage
```bash
# Start viewer
ncrads9

# Load image from command line
ncrads9 /path/to/image.fits

# Load sample image
ncrads9 ncrads9/sampleimages/SDSS9_M51_g.fits
```

### Interactive Controls
1. **Load image**: File → Open (or command line)
2. **Zoom**: Scroll wheel or Zoom menu
3. **Adjust display**: Right-click + drag horizontally/vertically
4. **Change colormap**: Color menu → select colormap
5. **Change scale**: Scale menu → select algorithm
6. **View coordinates**: Move mouse over image

### Keyboard Shortcuts
- `Ctrl+O`: Open file
- `Ctrl+Q`: Quit
- `Ctrl++`: Zoom in
- `Ctrl+-`: Zoom out

## Not Yet Implemented
- Region drawing/editing
- Multi-frame support
- Cube/3D data
- Analysis dialogs (histogram, statistics, etc.)
- Catalog overlays
- Print/export
- Full keyboard shortcuts
- Preferences
- Session save/restore

## Repository
- **GitHub**: https://github.com/yogeshw/ncrads9
- **License**: GPL v3
- **Author**: Yogesh Wadadekar
