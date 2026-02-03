# DS9 Features - Bug Fixes Round 3

## Issues Addressed

### 1. Middle-Click Centering - IMPROVED ✅
**Status**: Working with debug output  
**Changes**: Added debug print to confirm event filter is being called  
**Test**: Should print "Middle button detected in event filter" when middle-clicking

### 2. Right-Drag Contrast/Brightness - DEBUG ADDED 🔍
**Status**: Should be working, added debug output to verify  
**Changes**: Added debug prints for:
- "Right button detected" on press
- Contrast/brightness values during drag  
- "Right button released" on release

**If not working**: Check terminal for debug output to see if events are being received

### 3. Y-Axis Flip - NEEDS INVESTIGATION ⚠️
**Status**: Still reports as flipped  
**Action Needed**: Compare same FITS file in DS9 and NCRADS9
- Find pixel values at specific coordinates
- Determine if flip is in data or display
- Check if WCS coordinates match

### 4. Scale Dialog Brightness/Contrast - FIXED ✅
**Problem**: Bias/brightness slider values were in wrong range  
**Root Cause**: Slider gives 0-2 range but brightness expects -1 to +1  
**Solution**: Convert bias value: `brightness = bias_value - 1.0`

**How it works now**:
- Contrast slider: 0=no contrast, 50=neutral (1.0), 100=max contrast (2.0)
- Bias slider: 0=darkest (-1.0), 50=neutral (0.0), 100=brightest (+1.0)
- Status bar shows applied values after clicking Apply

### 5. Magnifier Colormap - FIXED ✅
**Problem**: Magnifier showed garbage with non-grayscale colormaps  
**Root Cause**: Hardcoded to expect grayscale Format_Grayscale8, but receiving RGB data  
**Solution**: Detect RGB vs grayscale and handle both:
```python
is_rgb = len(region.shape) == 3 and region.shape[2] == 3
if is_rgb:
    # Use Format_RGB888 and bytes_per_line = width * 3
else:
    # Use Format_Grayscale8
```

## Files Modified

### ncrads9/ui/widgets/gl_image_viewer_with_regions.py
- Added debug prints in `eventFilter()` method
- Helps diagnose why right-drag might not be working

### ncrads9/ui/main_window.py  
- Fixed brightness range conversion in `_apply_scale_params()`
- Changed: `brightness = bias_value - 1.0` (was: `brightness = bias_value`)
- Added status message showing applied values

### ncrads9/ui/panels/magnifier.py
- Rewrote `_update_magnifier()` to handle both RGB and grayscale
- Detects image format from shape
- Uses appropriate QImage format and stride calculation

## Testing Instructions

See `TESTING_NOTES.md` for detailed testing procedures.

**Quick Test**:
1. Run from terminal: `python3 test_ds9_features.py your_file.fits`
2. Try right-drag - check terminal for debug output
3. Try middle-click - check terminal for debug output  
4. Open Scale > Parameters, adjust sliders, click Apply
5. Change colormap and verify magnifier updates

## Debug Output Expected

When RIGHT button pressed and dragged:
```
Right button detected in event filter
Contrast: 1.02, Brightness: -0.01
Contrast: 1.05, Brightness: -0.03
...
Right button released
```

When MIDDLE button clicked:
```
Middle button detected in event filter
```

**If you don't see these messages**, the event filter is not being called, which means:
- Region overlay might be intercepting events
- Event filter might not be properly installed
- Widget hierarchy might be wrong

## Known Limitations

1. **Scale dialog sliders**: Don't update in real-time, must click Apply (this is normal!)
2. **Panner click-to-pan**: Not yet implemented
3. **Y-axis orientation**: Needs investigation with actual DS9 comparison

## Next Steps for Y-Axis Issue

1. Load a FITS file with clear asymmetry (e.g., galaxy with spiral arms)
2. In DS9: Note pixel at bottom-left corner, check its Y coordinate value
3. In NCRADS9: Check same corner, compare Y value
4. If Y values don't match: Need to flip data or adjust coordinate transforms
5. Also check WCS coordinates at same screen position - should match

The key question: **In DS9, is pixel (1,1) actually displayed at the bottom-left of the window?**
Or does DS9 also use computer graphics convention (top-left)?
