# Layout screenshots

Rendered headless by `tools/screenshots.py`, on
`ncrads9/sampleimages/SDSS9_M51_r.fits` at 1100x800, with the Min/Max, Low/High
and Units information-panel rows turned on so the panel's shape is visible.

| File | What it shows |
|---|---|
| `before-m3.png` | The `QDockWidget` layout at `c41f62a`, before M3. No information panel; the panner and magnifier each carry two title bars, being docks nested inside docks, and both are black — see PLAN.md §3.7 for why. |
| `after-m3.png` | The default layout after M3, same as `after-m3-horizontal.png`. |
| `after-m3-horizontal.png` | DS9's `LayoutViewHorz`: header row, buttonbar, canvas, colorbar. |
| `after-m3-vertical.png` | DS9's `LayoutViewVert`: header column and buttonbar down the left. |
| `after-m3-basic.png` | DS9's `LayoutViewBasic`: canvas and colorbar only. |
| `after-m3-advanced.png` | DS9's `LayoutViewAdvanced`: canvas, then header, then buttonbar. |

The GPU viewer cannot paint under Qt's `offscreen` platform, so the script
switches to the CPU backend before loading. Regenerate with:

    python tools/screenshots.py
