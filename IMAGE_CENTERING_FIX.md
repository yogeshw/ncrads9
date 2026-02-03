# Image Centering and Dialog Fixes

## Issue 1: Dialog Windows Drag Main Window

**Problem**: When trying to drag Scale Parameters dialog (or other dialogs), the main window moves along with it.

**Root Cause**: Dialog was parented to main window, making it move together.

**Solution**: Make dialog a truly independent top-level window.

**Fixed in**: `ncrads9/ui/dialogs/scale_dialog.py`

**Changes**:
```python
# Pass None as parent instead of parent widget
super().__init__(None)  # Not super().__init__(parent)

# Set as independent top-level window
self.setWindowFlags(
    Qt.WindowType.Window |  # Top-level window
    Qt.WindowType.WindowCloseButtonHint |
    Qt.WindowType.WindowTitleHint |
    Qt.WindowType.WindowStaysOnTopHint  # Stay on top
)

# Non-modal so main window stays interactive
self.setWindowModality(Qt.WindowModality.NonModal)
```

**Note**: This same fix can be applied to other dialogs if they have the same issue.

## Issue 2: Image Loads in Wrong Position

**Problem**: When image is loaded, only about 1/4 of it is visible at lower-right. User has to manually drag image to see the whole thing.

**Root Cause**: GPU rendering viewport was not centering the image. The pan coordinates were set to (0,0), but the OpenGL viewport calculation expects pan to be at the image center.

**Technical Details**:

The OpenGL rendering uses this viewport calculation:
```python
viewport_x = self._pan_x - view_w / 2
viewport_y = self._pan_y - view_h / 2
```

When `_pan_x = 0` and `_pan_y = 0`, the viewport shows coordinates from:
- X: -view_w/2 to +view_w/2
- Y: -view_h/2 to +view_h/2

But the image pixels are at coordinates:
- X: 0 to image_width
- Y: 0 to image_height

So only the overlap region was visible (lower-right quarter).

**Solution**: Set pan to image center on load.

**Fixed in**: 
1. `ncrads9/rendering/gl_canvas.py` - `set_tile_provider()`
2. `ncrads9/rendering/gl_canvas.py` - `zoom_to_fit()`
3. `ncrads9/ui/main_window.py` - `_load_fits_file()`

**Changes**:

### 1. In `set_tile_provider()`:
```python
self._image_width = width
self._image_height = height
self._tile_provider = data_provider

# Center the image when loading
self._pan_x = width / 2.0
self._pan_y = height / 2.0

self._tile_renderer.set_image(width, height, data_provider)
```

### 2. In `zoom_to_fit()`:
```python
self._zoom = min(view_w / self._image_width, view_h / self._image_height)

# Center the image by panning to image center
self._pan_x = self._image_width / 2.0
self._pan_y = self._image_height / 2.0

self.zoom_changed.emit(self._zoom)
self.pan_changed.emit(self._pan_x, self._pan_y)  # Emit pan change too
```

### 3. In `_load_fits_file()`:
```python
# Display the image
self._display_image()

# Fit image to window on initial load
self._zoom_fit()

# Update status bar image info
```

Now images are:
1. Centered when first loaded
2. Centered when zoom-to-fit is applied
3. Properly fitted to window size

## Coordinate System Explanation

```
Image coordinates:     Viewport with pan at (0, 0):
┌────────────┐        ┌────────────┐
│(0,0)    (W,0)      │(-W/2,-H/2) (W/2,-H/2)
│            │        │            │
│            │   vs   │     ✓      │  Only this quarter
│            │        │            │  overlaps with image!
│(0,H)    (W,H)      │(-W/2,H/2)  (W/2,H/2)
└────────────┘        └────────────┘

Viewport with pan at (W/2, H/2):
┌────────────┐
│(0,0)    (W,0)      ✓ Entire image
│            │         is now visible!
│            │
│            │
│(0,H)    (W,H)
└────────────┘
```

## Testing

1. **Dialog Dragging**:
   - Open Scale > Parameters...
   - Drag dialog by title bar
   - Dialog should move independently
   - Main window should stay still

2. **Image Centering**:
   - Load a FITS file
   - Full image should be visible and centered
   - No need to manually drag image
   - Zoom to fit should maintain centering

## Status

✅ **Fixed**:
- Dialog windows now draggable independently
- Images load centered and fully visible
- Zoom to fit maintains proper centering

## Files Modified

1. `ncrads9/ui/dialogs/scale_dialog.py` - Dialog independence
2. `ncrads9/rendering/gl_canvas.py` - Image centering in GPU mode
3. `ncrads9/ui/main_window.py` - Auto zoom-to-fit on load
