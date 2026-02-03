# Colorbar Ticks and Panner Functionality

## Feature 1: Colorbar with Intermediate Tick Values

### Problem
Colorbar was showing only the minimum and maximum values, making it hard to judge intermediate data values.

### Solution
Added 7 evenly-spaced tick marks with labels showing intermediate values.

### Implementation

**File**: `ncrads9/ui/widgets/colorbar_widget.py`

**Changes**:
1. Removed separate min/max labels (now shown in ticks)
2. Increased widget width to accommodate tick labels (120px min, 150px max)
3. Modified `_update_colorbar()` to draw ticks and labels

**Key Code**:
```python
# Draw tick marks and labels (7 ticks total)
num_ticks = 7
for i in range(num_ticks):
    y_pos = int(i * (height - 1) / (num_ticks - 1))
    value = self.vmax - (self.vmax - self.vmin) * i / (num_ticks - 1)
    
    # Draw tick mark
    painter.drawLine(bar_width, y_pos, bar_width + tick_length, y_pos)
    
    # Draw label
    label = f"{value:.3g}"
    painter.drawText(bar_width + tick_length + 2, y_pos + 4, label)
```

### Visual Layout
```
┌─────────────┐
│  colormap   │ ← Name label
├─────────────┤
│ ████████ ─ max   ← Top tick (vmax)
│ ████████ ─ val1
│ ████████ ─ val2
│ ████████ ─ mid   ← Middle tick
│ ████████ ─ val3
│ ████████ ─ val4
│ ████████ ─ min   ← Bottom tick (vmin)
└─────────────┘
```

### Benefits
- Shows 5 intermediate values (7 total including min/max)
- Values formatted with `.3g` format (3 significant figures)
- Tick marks clearly indicate value positions
- Easy to interpolate data values visually

---

## Feature 2: Panner Click-to-Pan Functionality

### Problem
Panner panel displayed the image thumbnail but clicking on it did nothing.

### Solution
Implemented click-to-pan: clicking on the panner centers the main view at that image location.

### Implementation

**File**: `ncrads9/ui/main_window.py`

**Method**: `_on_panner_pan(x: float, y: float)`

**Logic**:

#### For GPU Mode (OpenGL):
```python
# Pan coordinates represent the image point at viewport center
self.image_viewer.set_pan(x, y)
```

Simple! Just set pan to the clicked coordinates.

#### For CPU Mode (QScrollArea):
```python
zoom = self.image_viewer.get_zoom()
viewport_center_x = viewport.width() / 2
viewport_center_y = viewport.height() / 2

# Calculate zoomed position
zoomed_x = x * zoom
zoomed_y = y * zoom

# Calculate scroll position to center this point
scroll_x = int(zoomed_x - viewport_center_x)
scroll_y = int(zoomed_y - viewport_center_y)

# Apply scroll
self.scroll_area.horizontalScrollBar().setValue(scroll_x)
self.scroll_area.verticalScrollBar().setValue(scroll_y)
```

More complex: need to calculate scroll bar positions to center the clicked point.

### Usage

1. **Load FITS image**
2. **Look at Panner panel** (top-right) - shows thumbnail of full image
3. **Click anywhere on the thumbnail**
4. **Main view centers on clicked location**
5. **Status bar shows**: "Panned to (x, y)"
6. **Pan state is saved** to frame

### Benefits
- Quick navigation to different parts of large images
- Visual feedback: see where you're clicking in thumbnail
- Preserves zoom level
- Works in both GPU and CPU rendering modes
- Pan state persists when switching frames

---

## Testing

### Test Colorbar Ticks:
1. Load a FITS image
2. Look at colorbar on right side
3. Should see 7 labeled tick marks
4. Values should range from vmin (bottom) to vmax (top)
5. Try changing scale (Scale menu) - ticks should update
6. Try different colormaps - ticks remain visible

### Test Panner Click:
1. Load a FITS image (preferably large)
2. Zoom in (so you're viewing only part of the image)
3. Look at Panner panel - shows thumbnail with view rectangle
4. Click somewhere else on the panner thumbnail
5. Main view should immediately center on that location
6. View rectangle in panner should move to new position
7. Status bar should show "Panned to (x, y)"

### Test Panner with Zoom:
1. Load image, zoom in 2x
2. Click on panner
3. Should maintain 2x zoom, just change center position
4. Zoom in more (4x)
5. Click on panner again
6. Should still maintain 4x zoom

---

## Status

✅ **Implemented**:
- Colorbar shows 7 tick marks with values
- Panner click-to-pan works in both GPU and CPU modes
- Pan state persists to frame manager

⚠️ **Known Limitations**:
- Panner view rectangle doesn't update dynamically when panning with mouse
  (Only updates on zoom or when image changes)
- Future enhancement: Update panner rectangle on every pan event

---

## Files Modified

1. **ncrads9/ui/widgets/colorbar_widget.py**
   - Removed min/max labels
   - Added tick marks and intermediate value labels
   - Increased widget width
   - Fixed tobytes() for PyQt6 compatibility

2. **ncrads9/ui/main_window.py**
   - Implemented `_on_panner_pan()` with full logic
   - Handles both GPU and CPU rendering modes
   - Persists pan state to frame manager

---

## Future Enhancements

### Colorbar:
- Make number of ticks configurable (5, 7, 10)
- Add scientific notation for very large/small values
- Add option to show logarithmic scale ticks

### Panner:
- Update view rectangle in real-time during panning
- Add ability to drag view rectangle (not just click)
- Show crosshair on panner at cursor position
- Synchronize panner view rectangle with all pan/zoom operations

---

## Technical Notes

### Colorbar Tick Calculation:
```python
# For i in [0, 1, 2, ..., num_ticks-1]
y_position = i * (height - 1) / (num_ticks - 1)  # Screen position
value = vmax - (vmax - vmin) * i / (num_ticks - 1)  # Data value
```

Top (i=0) → vmax  
Bottom (i=num_ticks-1) → vmin

### Panner Coordinate Transform:
```
Panner thumbnail click (x_thumb, y_thumb)
  ↓ Scale to full image size
Image coordinates (x_img, y_img)
  ↓ Pass to _on_panner_pan()
GPU: Set as pan center directly
CPU: Calculate scroll bar position
  ↓
Main view centers on that point
```

The PannerPanel handles the thumbnail-to-image coordinate conversion internally before emitting the `pan_to` signal.
