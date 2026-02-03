# DS9 Features - Bug Fixes Round 2

## Issues Fixed

### 1. Middle-Click Centering - FIXED ✅
**Problem**: Middle-click events were not reaching the handler  
**Root Cause**: In GPU mode, `gl_canvas` widget receives mouse events, not the wrapper `GLImageViewerWithRegions`  
**Solution**: Installed event filter on `gl_canvas` to intercept middle/right button events before gl_canvas processes them

**Changes**:
- Added `eventFilter()` method to `GLImageViewerWithRegions`
- Filters `MouseButtonPress`, `MouseMove`, `MouseButtonRelease` events
- Returns `True` for middle/right buttons (handled), `False` for left button (let gl_canvas handle panning)

### 2. Right-Drag Contrast/Brightness - FIXED ✅
**Problem**: Same as #1 - events not reaching handler  
**Solution**: Same event filter handles right-button drag for contrast/brightness adjustment

### 3. Y-Axis Flip - REVERTED ❌
**Problem**: Pixel (1,1) still at top-left instead of bottom-left  
**Analysis**: 
- FITS convention: (1,1) at bottom-left
- Numpy array indexing: [0,0] at top-left (row 0 = top)
- Initial "fix" added `flipud()` which made it worse
- **Reverted the flip** - need to investigate DS9 behavior more carefully

**Status**: Needs further investigation with actual DS9 comparison

### 4. Scale Dialog Application - FIXED ✅
**Problem**: Changing settings in Scale Parameters dialog had no effect  
**Root Cause**: Signal was connected but handler was a stub  
**Solution**: Implemented `_apply_scale_params()` handler

**Changes**:
- Maps dialog scale names to `ScaleAlgorithm` enum
- Applies min/max limits when auto-limits is disabled
- Applies contrast/bias from sliders
- Calls `_display_image()` and `_persist_frame_view_state()` to update display

### 5. Panner & Magnifier Issues - PARTIALLY FIXED ✅
**Problem**: Magnifier didn't update colormap, Panner doesn't respond to clicks  
**Solution**: Pass colormapped RGB data to both panels instead of raw image data

**Changes**:
- Modified `_display_image()` to create `rgb_full` variable for both GPU and CPU modes
- Pass `rgb_full` to `panner_panel.set_image()` and `magnifier_panel.set_image()`
- This ensures panels display with current colormap applied

**Remaining Issues**:
- Panner click-to-pan not yet implemented (TODO in `_on_panner_pan()`)
- Panner view rectangle doesn't update when main view pans/zooms

## Files Modified

1. **ncrads9/ui/widgets/gl_image_viewer_with_regions.py**
   - Added imports: `QEvent`, `QObject`, `QMouseEvent`
   - Installed event filter in `__init__`
   - Added `eventFilter()` method (50+ lines)
   - Removed duplicate mouse event handlers (now handled by filter)

2. **ncrads9/ui/main_window.py**
   - Implemented `_apply_scale_params()` (40+ lines)
   - Modified `_display_image()` to create `rgb_full` for panels
   - Removed Y-flip code (reverted)

## Testing Checklist

- [x] Middle-click centers image
- [x] Right-drag adjusts contrast/brightness
- [ ] Y-axis matches DS9 (needs investigation)
- [x] Scale dialog applies changes
- [x] Magnifier updates with colormap
- [ ] Panner click-to-pan (not yet implemented)

## Next Steps

1. **Y-Axis Investigation**: Load same FITS in DS9 and NCRADS9, compare pixel locations
2. **Panner Click**: Implement `_on_panner_pan()` to calculate scroll/pan position
3. **View Rect Sync**: Update panner's view rectangle on pan/zoom changes
4. **Coordinate Transform**: Ensure mouse coordinates account for any Y-axis conventions

## Technical Notes

### Event Filter Pattern
```python
def eventFilter(self, obj: QObject, event: QEvent) -> bool:
    if obj == self.gl_canvas:
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.MiddleButton:
                # Handle middle click
                return True  # Event consumed
        # ... handle other events
    return False  # Let widget handle event
```

This pattern is crucial for intercepting events before child widgets process them.

### RGB Data Flow
```
image_data (raw FITS)
  → clip to [z1, z2]
  → apply scale algorithm  
  → apply colormap
  → rgb_full (uint8 RGB)
  → panels + display
```

Both panner and magnifier now receive `rgb_full`, ensuring consistent colormap application.
