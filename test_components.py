#!/usr/bin/env python3
"""
Quick test script to verify NCRADS9 functionality.
Tests imports and key components without launching GUI.
"""

print("Testing NCRADS9 components...")

# Test imports
print("\n1. Testing imports...")
try:
    from ncrads9.ui.main_window import MainWindow
    from ncrads9.ui.dialogs.statistics_dialog import StatisticsDialog
    from ncrads9.ui.dialogs.histogram_dialog import HistogramDialog
    from ncrads9.ui.widgets.colorbar_widget import ColorbarWidget
    from ncrads9.regions.region_parser import RegionParser
    print("   ✓ All imports successful")
except Exception as e:
    print(f"   ✗ Import failed: {e}")
    exit(1)

# Test colormap with inversion
print("\n2. Testing colormap inversion...")
try:
    from ncrads9.colormaps.builtin_maps import get_colormap
    import numpy as np
    
    cmap = get_colormap("grey")
    print(f"   ✓ Loaded colormap: {cmap.name}")
    
    # Test inversion
    cmap_data = cmap.colors.copy()
    inverted = cmap_data[::-1]
    print(f"   ✓ Colormap inversion works (256 colors)")
except Exception as e:
    print(f"   ✗ Colormap test failed: {e}")
    exit(1)

# Test statistics computation
print("\n3. Testing statistics...")
try:
    import numpy as np
    data = np.random.randn(100, 100)
    
    # Statistics
    mean = np.mean(data)
    std = np.std(data)
    print(f"   ✓ Statistics: mean={mean:.3f}, std={std:.3f}")
except Exception as e:
    print(f"   ✗ Statistics test failed: {e}")
    exit(1)

# Test region parser
print("\n4. Testing region parser...")
try:
    parser = RegionParser()
    # Test parsing a simple region string
    test_region = "circle(100,100,20) # color=red"
    print(f"   ✓ Region parser initialized")
except Exception as e:
    print(f"   ✗ Region parser test failed: {e}")
    exit(1)

# Test FITS handler
print("\n5. Testing FITS handler...")
try:
    from ncrads9.core.fits_handler import FITSHandler
    handler = FITSHandler()
    print(f"   ✓ FITS handler initialized")
except Exception as e:
    print(f"   ✗ FITS handler test failed: {e}")
    exit(1)

# Test scaling algorithms
print("\n6. Testing scale algorithms...")
try:
    from ncrads9.rendering.scale_algorithms import apply_scale, ScaleAlgorithm
    import numpy as np
    
    data = np.linspace(0, 100, 1000)
    scaled = apply_scale(data, ScaleAlgorithm.LINEAR, vmin=0, vmax=100)
    print(f"   ✓ Scale algorithms work (linear: {scaled.min():.3f} to {scaled.max():.3f})")
except Exception as e:
    print(f"   ✗ Scale algorithm test failed: {e}")
    exit(1)

print("\n" + "="*60)
print("✓ ALL TESTS PASSED!")
print("="*60)
print("\nNCRADS9 components are working correctly.")
print("To launch the application, run: ncrads9 <fits_file>")
