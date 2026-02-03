# Testing Notes for DS9 Features

## How to Test

### Test Right-Drag Contrast/Brightness
The event filter should print debug messages when you right-click and drag:
- Right-click: Should print "Right button detected in event filter"
- Drag: Should print contrast/brightness values like "Contrast: 1.05, Brightness: -0.02"
- Release: Should print "Right button released"

If you don't see these messages in the terminal, the event filter isn't being called.

### Test Middle-Click Centering  
- Middle-click on image
- Should print "Middle button detected in event filter"
- Image should re-center with clicked point at viewport center

### Test Scale Dialog
1. Open Scale > Parameters...
2. Move Contrast slider (range 0-100, 50=neutral)
   - Left of 50 = lower contrast
   - Right of 50 = higher contrast
3. Move Bias slider (range 0-100, 50=neutral)
   - Left of 50 = darker
   - Right of 50 = brighter
4. Click "Apply" to see changes
5. Status bar should show "Scale: X, Contrast: Y, Brightness: Z"

### Test Magnifier with Colormaps
- Load FITS image
- Try different colormaps (Color menu)
- Move mouse over image
- Magnifier panel should show magnified view with SAME colormap as main view

## Debug Mode

The following debug prints are currently ENABLED in gl_image_viewer_with_regions.py:
- Line ~161: "Middle button detected in event filter"
- Line ~166: "Right button detected in event filter"  
- Line ~181: Contrast/brightness values during drag
- Line ~188: "Right button released"

These will print to the terminal where you launched the application.

## Common Issues

### Right-drag not working
- Check if region mode is active (turns off transparent mouse events)
- Check terminal for debug prints
- Try clicking in different areas of the image

### Middle-click not centered correctly
- Coordinate calculation might be off
- Try clicking in center vs edges of image

### Scale dialog sliders don't update live
- This is EXPECTED! You must click "Apply" button
- DS9 works the same way - changes preview when you click Apply

### Magnifier shows garbage
- Should be fixed now - was expecting grayscale but getting RGB
- Check shape of data being passed: should be (H, W, 3) for RGB

## Next: Y-Axis Flip Investigation

Need to load SAME FITS file in both DS9 and NCRADS9 and compare:
1. Which pixel is at bottom-left corner in DS9? (should be low Y values)
2. Which pixel is at bottom-left corner in NCRADS9?
3. Are they the same?

Use a FITS file with clear asymmetry (not symmetric) to see orientation clearly.
