#!/usr/bin/env python
import sys
from PyQt6.QtWidgets import QApplication
from ncrads9.utils.config import Config
from ncrads9.ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    config = Config()
    window = MainWindow(config)
    window.show()
    
    print("Window opened. Test the following:")
    print("1. File -> Open (should show file dialog)")
    print("2. Help -> About Qt (should show About Qt dialog)")
    print("3. Help -> About NCRADS9 (should show About dialog)")
    
    sys.exit(app.exec())
