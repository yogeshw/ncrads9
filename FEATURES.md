# NCRADS9 - Working Features

## ✅ FULLY FUNCTIONAL - All Core Features Working!

### File Loading
- **File → Open**: File dialog to select FITS files ✓
- **Command line**: `ncrads9 image.fits` loads file on startup ✓
- **Supported formats**: .fits, .fit, .fts, .fits.gz, .fit.gz ✓
- **Error handling**: Shows error dialog if file fails to load ✓

### Image Display
- Automatic ZScale contrast/brightness limits ✓
- Real-time image rendering with scaling and colormaps ✓
- Scrollable viewing area for large images ✓

### Mouse Controls (DS9-style)
- **Mouse wheel**: Zoom in/out (scroll up/down) ✓
- **Right-click + drag**: Adjust contrast/brightness ✓
  - Horizontal drag: Changes contrast
  - Vertical drag: Changes brightness
- **Mouse movement**: Live coordinate tracking ✓

### Button Bar Controls (All Working!)
**Zoom Buttons:**
- Fit, 1/4, 1/2, 1, 2, 4, 8 - All functional ✓

**Scale Buttons:**
- Linear, Log, Sqrt, Squared, Asinh, HistEq - All working ✓

**Colormap Buttons:**
- Gray, Heat, Cool, Rainbow - All working ✓

**Region Buttons:**
- None, Circle, Ellipse, Box, Polygon, Line (stubs)

### Zoom Controls
- **Zoom menu → Zoom In** (Ctrl++): Zoom in 20% ✓
- **Zoom menu → Zoom Out** (Ctrl+-): Zoom out 20% ✓
- **Zoom menu → Zoom to Fit**: Fit image to window ✓
- **Zoom menu → Zoom 1:1**: Display at actual pixel size ✓
- **Button bar zoom**: All preset zoom levels work ✓
- Current zoom level shown in status bar ✓

### Scale Algorithms
All available via **Scale menu** and **Button bar**:
- Linear (default) ✓
- Log ✓
- Sqrt ✓
- Squared (Power) ✓
- Asinh ✓
- Histogram Equalization ✓
- **ZScale**: Reset to auto-computed limits ✓
- **MinMax**: Set limits to data min/max ✓

Real-time switching - image updates instantly ✓
Menu and button bar stay synchronized ✓

### Colormaps
Available via **Color menu** and **Button bar**:
- Grey (default) ✓
- Heat ✓
- Cool ✓
- Rainbow ✓
- Plus 15 more DS9-compatible maps ✓

Real-time switching - image updates instantly ✓
Menu and button bar stay synchronized ✓

### Status Bar Information
Displays continuously:
- **Pixel coordinates**: X: 256 Y: 256 ✓
- **WCS coordinates**: RA: 13:29:52.56 Dec: +47:11:44.34 (if available) ✓
- **Pixel value**: Value: 11.5495 ✓
- **Image info**: 512x512 BITPIX=-32 ✓
- **Zoom level**: Zoom: 1x ✓

### WCS Support
- Automatic WCS detection from FITS header ✓
- Real-time RA/Dec display on mouse movement ✓
- Sexagesimal format (HH:MM:SS.SS ±DD:MM:SS.S) ✓

### View Controls
- **Fullscreen** (F11): Toggle fullscreen mode ✓
- **Show Toolbar**: Toggle toolbar visibility ✓
- **Show Status Bar**: Toggle status bar visibility ✓

## Menu System - ALL WORKING ✓

### File Menu
- Open... (Ctrl+O) ✓
- Save... (Ctrl+S) - Stub
- Save As... (Ctrl+Shift+S) - Stub
- Exit (Ctrl+Q) ✓

### Edit Menu
- Undo/Redo - Stubs
- Preferences - Stub

### View Menu
- Fullscreen (F11) ✓
- Show Toolbar ✓
- Show Status Bar ✓

### Frame Menu
- All items - Stubs (multi-frame not implemented)

### Bin Menu
- All binning options - Stubs

### Scale Menu
- All 6 algorithms ✓
- ZScale (reset) ✓
- MinMax ✓

### Color Menu
- 4 main colormaps ✓
- Invert - Stub

### Zoom Menu
- Zoom In/Out/Fit/1:1 ✓
- Center - Stub

### Region Menu
- Load/Save - Stubs

### WCS Menu
- Coordinate systems - Stubs

### Analysis Menu
- Statistics, Histogram, etc - Stubs

### Help Menu
- About NCRADS9 ✓
- About Qt ✓

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
2. **Zoom**: 
   - Scroll wheel
   - Zoom buttons on left
   - Zoom menu
3. **Adjust display**: 
   - Right-click + drag horizontally/vertically
   - Or use ZScale/MinMax from Scale menu
4. **Change colormap**: 
   - Color buttons on left
   - Color menu
5. **Change scale**: 
   - Scale buttons on left
   - Scale menu
6. **View coordinates**: Move mouse over image
7. **Fullscreen**: View menu or F11

### Keyboard Shortcuts
- `Ctrl+O`: Open file
- `Ctrl+Q`: Quit
- `Ctrl++`: Zoom in
- `Ctrl+-`: Zoom out
- `F11`: Fullscreen

## Not Yet Implemented
- Region drawing/editing (UI ready, functionality stub)
- Multi-frame support (UI ready)
- Cube/3D data
- Analysis dialogs (UI ready, need implementation)
- Catalog overlays
- Print/export (UI ready)
- Binning
- Full keyboard shortcuts
- Preferences
- Session save/restore

## Repository
- **GitHub**: https://github.com/yogeshw/ncrads9
- **License**: GPL v3
- **Author**: Yogesh Wadadekar
