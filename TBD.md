# NCRADS9 — TBD

Decisions left open for the maintainer. Each entry says what was shipped, what
the alternative is, and what it would cost to switch — so that choosing later
costs no more than choosing now.

Settled items belong in [TODO.md](TODO.md); this file is only for the ones
still waiting on a call.

---

## 1. Which box the coordinate grid is drawn in

**Shipped:** the upright bounding box of the *turned* image. Rotate a frame and
the picture and the graticule turn together under a border that stays square to
the window, with the numbers along the screen's own edges. This is DS9's
`PUBLICATION` box: `Grid2d::doit` sets

```c
Matrix mm = fits->imageToWidget;
BBox b = pp->imageBBox(pp->context->secMode());
// ... the bounding box of the image's four corners, in widget coordinates
```

**The alternative:** DS9's `ANALYSIS` box, which is the whole canvas —

```c
gbox[0] = pbox[0] = 0;
gbox[2] = pbox[2] = pp->options->width-1;
```

The border would then sit at the window's edges rather than the image's, so the
numbers could never scroll out of view, and the graticule would carry on across
the empty canvas around a small image. `GridConfig.grid_type` already carries
DS9's Analysis/Publication distinction, so the two could coexist.

**What it would cost.** The grid is presently computed once per frame and cached
in image coordinates; panning and zooming only re-map it. A canvas-sized box
depends on the viewport size, the zoom and the pan, so it would have to be
recomputed on every one of those — which is the property
`test_the_grid_is_cached_in_image_coordinates` exists to protect, and the reason
`refresh_grid` is cheap enough to call from `refresh_transformed_view`. The
renderer would also need the viewport handed to it, which it has so far been
able to stay ignorant of.

**Worth knowing either way:** turning a frame widens the box, so the interval can
coarsen — a field that shows a line every 2′ upright may show one every 5′ at
30°. That is correct (more sky is inside the border) but it reads as a change if
you are comparing screenshots.

---

## 2. Which dialogs stay modal

**Shipped:** every window that *applies* something to the image while it is open
is modeless — Contour, Coordinate Grid, Smooth, Mask and Colormap Parameters,
Preferences, the catalogue Symbol Editor, the Radial Profile plot and the
catalogue header viewer. They go through `Controller.show_window` and
`dialogs.modeless.make_modeless`.

**Left modal:** the windows that return a value and change nothing until you
accept them — file open/save, print and page setup, message boxes, and the
OK/Cancel prompts behind Bin Parameters, Centroid Parameters, the analysis-task
parameter sets and Tile Parameters. Nothing of theirs is hidden behind them, so
the reported fault does not apply.

**The alternative:** DS9 has no modal parameter windows at all, so strict parity
would convert these too.

**What it would cost.** Each is written as `if not dialog.exec(): return`,
followed by the code that reads the dialog's values. Going modeless means
restructuring each into a signal and a handler, as the live-apply dialogs
already are — mechanical, but it touches the control flow of every caller, and
`Bin Parameters` in particular re-bins and re-zooms inline after the `exec()`.
