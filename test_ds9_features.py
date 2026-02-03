#!/usr/bin/env python3
"""
Manual test script for DS9-style features.

Tests:
1. Middle-click centering
2. Right-drag contrast/brightness 
3. Y-axis flip matching DS9
4. Scale parameters dialog
5. Pan and Magnifier panels

Usage:
    python test_ds9_features.py [fits_file]
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from ncrads9.ui.main_window import MainWindow
from ncrads9.utils.config import Config

def main():
    """Run manual test of DS9-style features."""
    app = QApplication(sys.argv)
    
    config = Config()
    window = MainWindow(config)
    window.show()
    
    # Load a test FITS file if provided
    if len(sys.argv) > 1:
        fits_file = Path(sys.argv[1])
        if fits_file.exists():
            window.open_file(str(fits_file))
            print(f"Loaded: {fits_file}")
        else:
            print(f"File not found: {fits_file}")
    
    print("\n=== DS9-Style Features Test ===")
    print("1. Middle-click on image to center at cursor (preserves zoom)")
    print("2. Right-drag to adjust brightness/contrast")
    print("3. Check Y-axis matches DS9 (not flipped)")
    print("4. Scale > Parameters... to open scale dialog")
    print("5. Check Panner and Magnifier panels on right")
    print("\nPress Ctrl+C in terminal or close window to exit.\n")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
