"""Render the window in each DS9 layout, headless, for docs/parity/screenshots.

Run from the repository root:
    QT_QPA_PLATFORM=offscreen python tools/screenshots.py
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ncrads9.ui.layout.view_state import ViewLayout
from ncrads9.ui.main_window import MainWindow

SAMPLE = "ncrads9/sampleimages/SDSS9_M51_r.fits"
OUT = "docs/parity/screenshots"

app = QApplication([])
window = MainWindow()
# The offscreen platform has no framebuffer, so the GPU viewer cannot paint.
window._rebuild_image_viewer(False)
window.resize(1100, 800)
window.show()
app.processEvents()
window.display.load_fits(SAMPLE)
app.processEvents()
window._on_mouse_moved(256, 300)
app.processEvents()

for field in ("minmax", "lowhigh", "bunit"):
    window.view.set_info_field(field, True)
app.processEvents()

for layout in ViewLayout:
    window.view.set_layout(layout)
    app.processEvents()
    path = f"{OUT}/after-m3-{layout.value}.png"
    window.grab().save(path)
    print("wrote", path)

window.view.set_layout(ViewLayout.HORIZONTAL)
app.processEvents()
window.grab().save(f"{OUT}/after-m3.png")
print("wrote", f"{OUT}/after-m3.png")
sys.exit(0)
