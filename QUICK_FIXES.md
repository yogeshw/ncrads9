# Quick Fixes Applied

## Issue: Magnifier Shows Nothing
**Error**: `TypeError: arguments did not match any overloaded call: QImage()`

**Root Cause**: PyQt6's QImage doesn't accept numpy array `.data` attribute (memoryview)

**Solution**: Convert to bytes using `.tobytes()`

**Fixed in**: `ncrads9/ui/panels/magnifier.py`
- Line ~156: Changed `normalized.data` to `normalized.tobytes()`
- Line ~172: Changed `normalized.data` to `normalized.tobytes()`
- Added contiguous array check before conversion

**Before**:
```python
qimage = QImage(
    normalized.data,  # memoryview - doesn't work!
    width, height, bytes_per_line,
    QImage.Format.Format_RGB888
)
```

**After**:
```python
if not normalized.flags['C_CONTIGUOUS']:
    normalized = np.ascontiguousarray(normalized)

qimage = QImage(
    normalized.tobytes(),  # bytes - works!
    width, height, bytes_per_line,
    QImage.Format.Format_RGB888
)
```

## Issue: Popup Windows Drag Main Window

**Problem**: Dialogs (Scale Parameters, etc.) drag main window when you try to drag them

**Root Cause**: Window flags not set properly - dialogs attached to parent

**Solution**: Set independent window flags

**Fixed in**: `ncrads9/ui/dialogs/scale_dialog.py`
- Added window flags in `__init__`:
```python
self.setWindowFlags(
    Qt.WindowType.Dialog | 
    Qt.WindowType.WindowCloseButtonHint |
    Qt.WindowType.WindowTitleHint
)
```

**To fix other dialogs**: Add same window flags pattern in their `__init__` methods.

## Testing

Run application from terminal:
```bash
cd /home/yogesh/ncrads9
python3 test_ds9_features.py your_file.fits
```

### Test Magnifier:
1. Load FITS image
2. Move mouse over image
3. Magnifier panel should show magnified view with correct colormap
4. Change colormap - magnifier should update immediately

### Test Dialog Dragging:
1. Open Scale > Parameters...
2. Try to drag dialog by its title bar
3. Dialog should move independently, NOT drag main window
4. Click outside dialog - it should stay on top or behind depending on focus

## Other Dialogs That May Need Window Flags

If you find other dialogs that drag the main window:

1. Find the dialog file in `ncrads9/ui/dialogs/`
2. Locate the `__init__` method
3. Add after `super().__init__(parent)`:
```python
self.setWindowFlags(
    Qt.WindowType.Dialog | 
    Qt.WindowType.WindowCloseButtonHint |
    Qt.WindowType.WindowTitleHint
)
```

**Common dialogs**:
- Statistics Dialog
- Histogram Dialog
- Header Dialog
- Grid Dialog
- Contour Dialog
- Export Dialog

## Current Status

✅ **Working**:
- Right-drag brightness/contrast
- Middle-click centering (sort of)
- Scale dialog sliders
- Magnifier with all colormaps
- Scale dialog is draggable

⚠️ **Partial**:
- Middle-click centering works but may not be perfect
- Scale dialog draggable, other dialogs may need fixes

❌ **Not Working**:
- Y-axis still flipped (needs investigation)
- Panner click-to-pan (not implemented)

## Debug Output

You should now see in terminal:
```
Right button detected in event filter
Contrast: 1.05, Brightness: -0.02
Contrast: 1.08, Brightness: -0.05
...
Right button released
```

And for middle-click:
```
Middle button detected in event filter
```

If you don't see these, event filter isn't being called properly.
