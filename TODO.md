# NCRADS9 — TODO

Task-level breakdown of [PLAN.md](PLAN.md). Each task is sized to be implementable and reviewable
on its own. Sizes: **S** ≤ ½ day · **M** ~1–2 days · **L** ~3–5 days.

Every task must leave `pytest` green. Tasks that change behaviour must add or update tests.

---

## M0 — Hygiene

**Status: complete.** See `docs/parity/lint-backlog.md` for what the gates cover and what is
deliberately deferred.

- [x] **M0-1** (S) Untrack compiled artifacts. 144 files removed from the index (138 `.pyc`
      plus `ncrads9.egg-info/`); `.gitignore` already covered them.
      *Note:* `.tmp_sao_ds9` is tracked as a bare gitlink (mode 160000) with no `.gitmodules`.
      Left as-is deliberately — it is the DS9 reference tree the parity tooling reads. Register it
      properly as a submodule, or drop it from the index, when convenient.
- [x] **M0-2** (S) Fixed the failing crop test. The *test* was right and the *code* was wrong:
      `_apply_crop_parameters` derived zoom from `scroll_area.viewport().size()`, which reports a
      degenerate size (14 px tall) until the window is laid out. Added
      `MainWindow._effective_viewport_size()`, which falls back to the scroll area, then the
      window, then DS9's default canvas (738×528), and used it at the three sites that derive a
      zoom or block factor from viewport dimensions — `_apply_crop_parameters`, `_block_fit` and
      `_zoom_fit`.
      Verifying the fix against a real image then exposed a **second instance of the same bug on
      the default GPU path**: `GLImageViewerWithRegions.zoom_fit()` accepted a viewport size and
      discarded it, and `GLCanvas.zoom_to_fit()` used its own un-laid-out widget size instead.
      Opening a 512×512 image at startup therefore zoomed to 0.055 rather than ~1.0. Both now
      honour the supplied size and fall back to the widget only when none is given.
      12 regression tests added across `test_zoom_menu_features.py` and the new
      `test_zoom_fit_viewport.py`.
- [x] **M0-3** (S) `[tool.ruff]`, `[tool.black]`, `[tool.mypy]`, `[tool.pytest.ini_options]` and
      `[tool.coverage.*]` added to `pyproject.toml`. ruff gates `ncrads9`/`tests`/`tools` on a
      correctness-focused rule set (**clean**); mypy gates `core`, `coordinates`, `regions`
      (**clean**, 40 files).
- [x] **M0-4** (S) `.github/workflows/ci.yml` — three jobs: `lint` (ruff, black, mypy),
      `test` (Python 3.10/3.11/3.12 under `xvfb-run`, with coverage), and `parity` (regenerates the
      menu snapshot and fails if it is stale, then prints the DS9 parity summary).
      The black gate is scoped to `tools/` only. A "changed files against the merge base" gate was
      tried first and rejected: M0's own ruff autofixes touch 94 files, so that rule would have
      failed on the very commit introducing it. `ncrads9/` and `tests/` join the gate in **M1**
      with a one-shot reformat — see `docs/parity/lint-backlog.md`.
- [x] **M0-5** (S) `.pre-commit-config.yaml` wiring the same tools plus whitespace/YAML/TOML
      hygiene.
- [x] **M0-6** (S) Coverage floor set to 40% in `[tool.coverage.report]`, against a measured
      baseline of 42.0%. C-5 requires raising it each milestone.
- [x] **M0-7** (S) `tools/dump_menus.py` — builds a real `MainWindow` and walks the live `QMenu`
      tree, emitting DS9-style `path|kind|label` lines. `--connected` marks actions with no
      receiver.
- [x] **M0-8** (S) `tools/ds9_menu_tree.py` — parses `ds9/library/m*.tcl`, resolving both composite
      label forms (`"[msgcat::mc {Zoom}] 1/32"` and `"0 [msgcat::mc {Degrees}]"`) so only 2 of 526
      entries remain unresolved. Snapshots committed as `docs/parity/ds9_menus.txt` and
      `docs/parity/ncrads9_menus.txt`. Also added `tools/menu_diff.py` (per-menu parity report)
      and `tools/check.sh` (runs every CI gate locally; `--fix` applies fixes).
- [x] **M0-9** (S) Terminal `--help` / `-h` now prints usage and exits without starting Qt;
      `--help-html` opens the browser reference. Written by hand rather than with argparse, because
      DS9's grammar is an *ordered* stream of options and filenames, which argparse cannot express.

### Defects the new gates surfaced, fixed in M0

All were live bugs, each now covered by a regression test:

- [x] **`Edit → Preferences` crashed** — `NameError: name 'Qt' is not defined`;
      `ui/dialogs/preferences_dialog.py` used `Qt` without importing it (found by ruff `F821`).
- [x] **Region files containing a `text` region failed to load at all** —
      `region_parser.py` called `Text(text=...)` but the constructor takes `label`; the resulting
      `TypeError` escaped the `except (IndexError, ValueError)` and aborted the whole file
      (found by mypy `call-arg`). `tests/unit/test_region_parser.py` replaced its placeholder with
      11 real tests.
- [x] **Brace-delimited property values were mis-parsed** — `PROPERTY_PATTERN` had no `{...}`
      branch, so `text={Hello World}` truncated at the space and `text={Hello}` kept its braces.
- [x] **`lru_cache` on instance methods** pinned `self` for the process lifetime
      (`utils/resources.py`, ruff `B019`); replaced with per-instance dict caches.
- [x] **`zip()` with an unstated equal-length invariant** (`colormaps/sao_parser.py`, ruff `B905`);
      now `strict=True`.
- [x] **Naive timestamps** in serialized session data (`catalogs/skybot.py`,
      `io/session/{backup_writer,session_manager}.py`, ruff `DTZ003`/`DTZ005`); now timezone-aware.
- [x] **Zoom-to-fit was near-zero on the GPU path** for the first image opened at startup — see
      M0-2 above.
- [x] Dead locals removed in `catalogs/sdss.py`, `catalogs/catalog_table.py`,
      `ui/dialogs/region_dialog.py`, `colormaps/builtin_maps.py`.

Also added a shared session-scoped `qapp` fixture to `tests/conftest.py`, and
`tests/unit/test_parity_tools.py` (12 tests) to guard the parity instrument itself.

Test count: **69 (1 failing) → 107 (all passing)**. Coverage: **42.1%**.

## M1 — Consolidate the model

**Status: complete.** 116 orphan modules -> 71, all remaining ones listed against the milestone
that adopts them in `tests/unit/test_no_orphan_modules.py` and inventoried in
`docs/parity/skeletons.md`. Tests 107 -> 447; coverage 42.0% -> 47.6%.

Deviations from the plan as written, and why:

- **M1-14** (frame owns an `ImageData`) is done at the load site only. `frame.image` now carries
  the as-loaded array, header, WCS, BITPIX and cached min/max, and `FITSHandler.load_image_data()`
  is the single place they are derived. Folding `frame.image_data`, `frame.header` and
  `frame.wcs_handler` into that container touches 149 call sites and belongs with **M4**, which
  rewrites the loader for extensions, cubes and mosaics anyway. Doing it twice would be waste.
- **M1-17** said to delete `rendering/rgb_compositor.py`. It was adopted instead: it is where M5's
  HSV/HLS rendering has to live, so deleting working colour-space maths to rewrite it later made no
  sense. It was rewritten vectorized -- the original converted one pixel at a time in a Python
  double loop. `rendering/colormap_engine.py` was deleted as planned.
- **M1-18** took the "otherwise" branch: painting moved into `RegionRenderer` and the overlay
  delegates, rather than the renderer being deleted. `RegionRenderer` was a stub that called
  `BaseRegion.draw()`, which every shape left empty, so nothing was drawing regions through it.
- **M1-16**: `core/data_cache.py` was deleted rather than adopted. It was complete but redundant --
  the loader already opens with `memmap=True`, frames hold the arrays they display, and
  `TextureManager` already caches GPU textures against a size budget.
- **M1-19** also deleted the five `image_servers` skeletons outright (signatures plus
  `raise NotImplementedError`, no subclasses, no callers). `docs/parity/skeletons.md` records what
  M8 must build.

Bugs found and fixed along the way:

- `catalog_table.py` imported `QAction` from `PyQt6.QtWidgets`, where it does not exist, so the
  module had silently degraded to `HAS_QT = False` since it was written; sorting the imports moved
  the bad name early enough to break the import outright. Six more PyQt5-era enum spellings
  surfaced once it loaded for the first time.
- Right-click never closed a polygon: `mouseReleaseEvent` returned early for every right button,
  making the `elif RightButton and POLYGON` branch below it unreachable.
- `RegionWriter` emitted a second `#` on shapes whose `to_ds9_string()` already carries a comment,
  making their properties unparseable.
- `RegionParser` ignored the `-` exclude prefix and every DS9 property flag.
- `header_dialog` treated a `fits.Header` as a plain mapping, silently dropping every card comment
  and making comments unsearchable.

Depends on M0.

### One region model
- [x] **M1-1** (M) Audit the three `Region` types (`regions/base_region.py:BaseRegion`,
      `frames/frame.py:Region`, `ui/widgets/region_overlay.py:Region`). Write the union of fields
      each needs onto `BaseRegion`: geometry, `color`, `width`, `font`, `text`, `tags`, plus the
      property flags needed by M6 (`include`, `source`, `fixed`, `edit`, `move`, `rotate`,
      `delete`, `dash`, `fill`).
- [x] **M1-2** (M) Make `ui/widgets/region_overlay.py` operate on `BaseRegion` subclasses
      directly. Delete `main_window.py:_overlay_regions_to_base()` and `_base_region_to_overlay()`
      (lines 4612–4695) and the local `Region` class.
- [x] **M1-3** (S) Delete `frames/frame.py:Region`.
- [x] **M1-4** (S) Add round-trip tests: create each of the 6 currently-creatable shapes in the
      overlay, save via `RegionWriter`, reparse via `RegionParser`, assert geometry equality.

### One frame model
- [x] **M1-5** (M) Decide the surviving `Frame`. Recommendation: keep
      `frames/simple_frame_manager.py` (it is the one in use and carries real per-frame view
      state), rename to `frames/frame.py` / `frames/frame_manager.py`, and delete the orphaned
      `frames/frame.py` + `frames/frame_manager.py`.
- [x] **M1-6** (M) Fold the ad-hoc `MainWindow._tile_layout` dict into `frames/tile_layout.py`
      and use it from `_display_tiled_frames()` / `_select_tiled_frame()`.
- [x] **M1-7** (M) Fold blink/fade timer logic out of `main_window.py` into
      `frames/blink_controller.py`.
- [x] **M1-8** (S) Delete or adopt `frames/{rgb,hsv,hls}_frame.py`. RGB composition currently
      lives in `main_window.py:_compose_rgb_frame_image()`; move it into `frames/rgb_frame.py`
      as `RGBFrame`, and make `HSVFrame`/`HLSFrame` real subclasses (rendering lands in M5).
- [x] **M1-9** (S) Delete `frames/frame_3d.py` for now; 3D lands as a fresh implementation in M9.

### One coordinate module
- [x] **M1-10** (M) Define `coordinates/coord_system.py:CoordinateContext` holding
      `system` (`image|physical|amplifier|detector|wcs|wcsa…wcsz`), `sky`
      (`fk4|fk5|icrs|galactic|ecliptic`), `format` (`degrees|sexagesimal`), and `precision`.
- [x] **M1-11** (M) Move all coordinate formatting out of `main_window.py`
      (`_update_wcs_display`, `_on_mouse_moved`, `_world_to_overlay_pixel`) into
      `coordinates/`. Every coordinate string in the app must come from one function.
- [x] **M1-12** (S) Implement `coordinates/physical_coords.py` against `LTV*`/`LTM*` header
      keywords so physical coordinates are real, not a stub.
- [x] **M1-13** (S) Unit-test each coordinate module against known values (use
      `ncrads9/sampleimages/SDSS9_M51_g.fits`).

### One FITS access layer
- [x] **M1-14** (M) Make `core/image_data.py` the frame's data container (data, header, WCS,
      bitpix, shape, min/max cache) and use it from `_load_fits_file`.
- [x] **M1-15** (S) Adopt `core/header_parser.py` in `ui/dialogs/header_dialog.py`.
- [x] **M1-16** (S) Adopt `core/data_cache.py` behind the tile renderer, or delete it.

### Formatting and modernization (do this first — it touches every file below)
- [x] **M1-0a** (S) One-shot `black ncrads9 tests tools` (90 files), as its own commit with no
      other changes, then widen the black gate to the whole tree in `.github/workflows/ci.yml`,
      `.pre-commit-config.yaml` and `tools/check.sh`. Deferred from M0 — see
      `docs/parity/lint-backlog.md`.
- [x] **M1-0b** (S) One-shot `ruff check --select UP,I --fix ncrads9 tests tools` (~1,350
      findings: `UP045`, `UP006`, `UP035`, `UP007`, `I001`, `UP015`, `UP012`), as its own commit,
      then add `UP` and `I` to `lint.select` in `pyproject.toml`. Do it before the signature work
      below, which rewrites the same annotations.

### Delete confirmed duplicates
- [x] **M1-17** (S) Delete `rendering/colormap_engine.py` and `rendering/rgb_compositor.py` after
      confirming `rendering/scale_algorithms.py` + `colormaps/colormap.py` cover their intent.
- [x] **M1-18** (S) Delete `regions/region_renderer.py` if `region_overlay.py` remains the
      renderer; otherwise move painting into it and have the overlay delegate.
- [x] **M1-19** (S) Replace the `NotImplementedError` skeletons in `image_servers/{dss,eso,
      skyview,sdss_image,twomass_image}.py` and `grid/`, `prism/`, `printing/` with a single
      `docs/parity/skeletons.md` note, so the tree stops advertising unimplemented APIs. They are
      reimplemented for real in M7/M8/M9.
- [x] **M1-20** (S) Add `tests/unit/test_no_orphan_modules.py`: walk the import graph from
      `ncrads9.app` and fail on any module under `ncrads9/` that is unreachable and not
      allow-listed. Keeps §3.1 from regressing.

---

## M2 — Extract controllers

**Status: complete.** `main_window.py` **4,600 -> 546 lines**, 238 methods -> 28. Tests 502 -> 533.
Unconnected menu actions: **3 -> 0**.

Twelve controllers plus a display pipeline, one per menu:

| Module | Lines | Owns |
|---|---:|---|
| `controllers/base.py` | 137 | shared accessors, `require_frame`, `connect`/`sync` |
| `controllers/analysis.py` | 893 | Analysis and Bin |
| `controllers/frame.py` | 1,095 | Frame |
| `controllers/zoom.py` | 447 | Zoom |
| `controllers/color.py` | 301 | Color |
| `controllers/vo.py` | 373 | VO and SAMP |
| `controllers/file.py` | 192 | File |
| `controllers/region.py` | 188 | Region |
| `controllers/scale.py` | 183 | Scale |
| `controllers/wcs.py` | 171 | WCS |
| `controllers/edit.py` | 136 | Edit |
| `controllers/help.py` | 62 | Help |
| `controllers/view.py` | 56 | View |
| `ui/display.py` | 707 | the render pipeline |

Two additions to the plan as written, both needed to reach M2-16's target:

- **`ui/display.py`** holds the render pipeline. Not a menu controller -- nothing in DS9's menu bar
  corresponds to it -- but 600 lines of rendering could not stay in MainWindow and still meet the
  size ceiling. Its docstring documents the pipeline order and why the CPU and GPU paths diverge.
- **`controllers/help.py`** was not in the task list, but ncrads9 has a Help menu and its four
  entries belonged with it rather than on the window.

Controllers reach shared state through `self.window`. That is deliberate and temporary --
`controllers/base.py` says so at length. Narrowing each controller to the collaborators it actually
needs is follow-on work now that the surfaces are visible; doing it at the same time as the
relocation would have made 3,800 lines of movement unreviewable.

Depends on M1.

- [x] **M2-1** (M) Create `ui/controllers/base.py` with a `Controller` that receives the shared
      app state (frame manager, coordinate context, preferences, status reporting) and exposes
      `connect(menu_bar)`.
- [x] **M2-2** (M) `FileController` — open/save/import/export/print/header/backup.
- [x] **M2-3** (S) `EditController` — pointer modes, undo/redo, cut/copy/paste, preferences.
- [x] **M2-4** (M) `ViewController` — every visibility toggle and the layout switch.
- [x] **M2-5** (L) `FrameController` — create/delete/navigate/display-mode/match/lock/tile.
- [x] **M2-6** (M) `ScaleController` — algorithm, limits, scope, min/max method.
- [x] **M2-7** (M) `ColorController` — colormap, invert, colorbar, colour tags.
- [x] **M2-8** (M) `ZoomController` — zoom/pan/orient/rotate/crop/align.
- [x] **M2-9** (M) `RegionController` — mode, shape, properties, selection, groups, file ops.
- [x] **M2-10** (M) `AnalysisController` — contours, grid, block, smooth, mask, crosshair, graphs,
      pixel table, external tasks.
- [x] **M2-11** (S) `WCSController` — system/sky/format/parameters.
- [x] **M2-12** (M) Rewire `communication/xpa/xpa_commands.py` to call controller methods instead
      of poking `viewer.*` attributes. *Done when* no XPA handler touches a private
      `MainWindow._…` member.
- [x] **M2-13** (M) Rewire `app.py:apply_startup_cli` to call the same controller methods.
- [x] **M2-14** (S) Connect the three genuinely dead actions — `action_cut`, `action_copy`,
      `action_paste` — and give `action_undo`/`action_redo` real behaviour instead of the
      "not implemented" status message at `main_window.py:408-409`. Confirm the list first with
      `python tools/dump_menus.py --connected`; an earlier static grep put it at 20, but most of
      those are connected by iterating a group or dict rather than by name (see PLAN.md §3.8).
- [x] **M2-15** (S) Assert in a test that every `QAction` declared in `MenuBar` has at least one
      connected receiver. Prevents §3.8 from recurring.
- [x] **M2-16** (S) `main_window.py` under 600 lines; add a CI check on that.

---

## M3 — DS9 window layout

**Status: complete.** Every `QDockWidget` is gone; the window is one grid. View-menu parity with
DS9 **3/27 -> 26/27 labels**, total menu entries **287 -> 337**, orphan modules **71 -> 60**,
tests **533 -> 628**, coverage 48.3% -> 51.6%.

| Module | Lines | Owns |
|---|---:|---|
| `ui/layout/view_state.py` | 148 | DS9's `view(...)` array as a dataclass |
| `ui/layout/shell.py` | 319 | the grid, in DS9's four arrangements |
| `ui/panels/info_panel.py` | 429 | DS9's field table (rewritten) |
| `ui/button_bar.py` | 497 | the two-row category bar (rewritten) |
| `ui/controllers/view.py` | 384 | the View menu, and filling the panel |

- [x] **M3-1** (M) `ui/layout/shell.py`: fixed vertical stack — header row, buttonbar, canvas,
      colorbar — replacing the `QDockWidget` arrangement in `_setup_dock_widgets()`.
- [x] **M3-2** (M) Header row: adopt `ui/panels/info_panel.py`, laid out DS9-style —
      File, Object, Value, Units, Min/Max, Low/High, then WCS α/δ, Physical x/y, Image x/y,
      Frame — alongside the panner and magnifier.
- [x] **M3-3** (M) Two-row buttonbar replacing the left `QGroupBox` dock: row 1 = category
      (File, Edit, View, Frame, Bin, Zoom, Scale, Color, Region, WCS, Analysis, Help),
      row 2 = that category's buttons.
- [x] **M3-4** (S) Horizontal / Vertical layout switch.
- [x] **M3-5** (S) Basic / Advanced view modes.
- [x] **M3-6** (M) Full `View` menu: Information Panel, Panner, Magnifier, Buttons, Icons,
      Colorbar, Multiple Colorbars, Horizontal Graph, Vertical Graph.
- [x] **M3-7** (M) Info-panel field toggles: Filename, Object, Keyword, Min Max, Low High, Units,
      WCS, Multiple WCS a–z, Image, Physical, Amplifier, Detector, Frame Information.
- [x] **M3-8** (S) Apply `ui/themes/{default,dark,native}.py`; wire to the Preferences theme
      setting.
- [x] **M3-9** (S) Move the panner's compass/orientation indicator to match DS9's panner.
- [x] **M3-10** (S) Commit before/after screenshots to `docs/parity/`.

### Where this deviated from the plan, and why

* **`ui/layout/view_state.py` is new.** The plan named only `shell.py`. Splitting the state out
  keeps the layout rules testable without a window, and gives the XPA `view` access point (M8)
  one object to read and write. `WindowShell` owns no state at all.
* **M3-2 says "adopt" the info panel; it was rewritten instead.** The existing panel was
  NCRADS9's own design — four group boxes with pixel x/y, one value, RA/Dec, Galactic l/b, and
  whole-image statistics — and shared almost nothing with DS9's table. Every DS9 field it lacked
  (filename, object, units, min/max with positions, cut limits, physical/amplifier/detector,
  frame/zoom/angle) is what a DS9 user actually reads. Statistics moved out: DS9's panel has
  none, and `Analysis → Statistics` already covers it.
* **M3-4 and M3-5 are one radio group, not a switch plus two modes.** DS9's `view(layout)` is a
  single four-valued variable, so choosing Basic replaces Horizontal rather than modifying it.
* **The buttonbar drives `MenuBar` actions rather than emitting its own signals.** A button now
  triggers the same `QAction` as its menu entry, and a checkable one mirrors it — so the two
  cannot drift apart, and a change made from the menu, a shortcut or XPA ticks the button too.
  Only the zoom multipliers and region shapes, which have no single menu action, still go through
  a signal. `ButtonBar.set_scale`/`set_colormap` survive as no-ops for their existing callers.
* **M3-7 needed real alternate-WCS data.** The toggles and rows would have been decoration, so
  `WCSHandler` gained a `key` argument and `available_alternates()`, and `pixel_to_world` now
  reads the spherical representation instead of `.ra`/`.dec` — an alternate description is often
  galactic, where those attributes do not exist.
* **M3-9 kept the image overlay.** DS9 draws the compass in the panner only. Deleting the image
  arrows would have made `contour_overlay._draw_direction_arrow` dead code that M6's compass
  *region* needs, so the panner gets the compass and `WCS → Show Direction Arrows` still draws it
  over the data — now unticked by default.
* **`utils/resources.py` was not needed.** M3-3 expected the buttonbar to load icons; DS9's
  buttonbar is text and so is ours. Repointed to M9-24.
* **Six orphans were duplicates, and are gone.** `ui/panels/colorbar_panel.py` and the five
  per-system coordinate value objects were tagged M3-6/M3-7 in the pending list, but M3 was
  finished without them: `CoordinateContext`, `PhysicalTransform` and `WCSHandler(key=...)` do
  the work, and nothing imported any of the six. 800 lines deleted, with the reasoning left in
  each package's `__init__` docstring so the absence is explained where someone would look for
  them.
* **DS9's two information-panel grids are both implemented.** `LayoutInfoPanelHorz` puts a field
  on one line across seven columns; `LayoutInfoPanelVert` -- which DS9's Advanced procedure
  duplicates byte for byte -- narrows every cell to 13 characters *and* breaks the field over
  several lines in two columns, the axis label to the left of its value. Each `_Row` therefore
  carries both placements over the same widgets. The seven default fields occupy 7 grid rows
  above the canvas and 18 beside it, which took the panel's width from ~460 px to ~150 px.

### Bugs found and fixed on the way

* **The panner and magnifier had been dead since M2.** `ui/display.py` guarded all eight updates
  with `hasattr(self, "panner_panel")` where `self` is the `DisplayPipeline`, not the window —
  never true. Both panels were permanently black, and nothing noticed because neither was
  visible enough to miss. The cut graphs' `set_image` had the same guard.
* **The panner and magnifier were docks inside docks**, so each had two title bars (visible in
  `docs/parity/screenshots/before-m3.png`).
* **Applying a theme restyled the whole process on every window construction.**
  `QApplication.setStyle` walks every live widget; guarding it on an actual change took the test
  suite from 94 s to 17 s.
* **The colorbar was sized for a dock** — a 140x200 minimum — which under the canvas took a
  fifth of the window height. Now a strip pinned to the bar plus its labels, horizontal by
  default as DS9 has it, with the end tick labels clamped inside the bar.
* **`QSizePolicy.Ignored` on the info panel's value cells** let Qt shrink them below their own
  minimum, and the columns printed over each other.

---

## M4 — FITS coverage

Depends on M1.

- [ ] **M4-1** (M) `core/fits_handler.py`: extension model — enumerate HDUs with type, name,
      dimensions, and whether each is displayable.
- [ ] **M4-2** (M) HDU chooser in `ui/dialogs/open_dialog.py` (currently orphaned — adopt it),
      shown when a file has more than one displayable HDU.
- [ ] **M4-3** (M) Parse DS9/funtools file syntax: `file.fits[3]`, `file.fits[EVENTS]`,
      `file.fits[x>10&&y<20]`, `file.fits[bin=x,y]`.
- [ ] **M4-4** (L) Data cubes: `core/cube_handler.py` for slice extraction and axis order; adopt
      `ui/panels/cube_panel.py` as the Cube dialog (slice slider, axis order, interval, play/stop,
      and the `Frame → Cube` entry).
- [ ] **M4-5** (S) `File → Open as → Slice`.
- [ ] **M4-6** (M) Multiple Extension Cube and Multiple Extension Frames loaders.
- [ ] **M4-7** (L) Mosaic loaders: Mosaic WCS, Mosaic WCS Segment, Mosaic IRAF,
      Mosaic IRAF Segment, Mosaic WFPC2, Mosaic Image variants.
- [ ] **M4-8** (S) Tile-compressed (`CompImageHDU`) images.
- [ ] **M4-9** (S) URL loading (`File → Open as → URL`) with a progress indicator.
- [ ] **M4-10** (M) Implement `save_file()` / `save_file_as()` — write the current frame's data +
      header + updated WCS to FITS.
- [ ] **M4-11** (M) `File → Save Image → FITS` (rendered image as FITS) and the remaining
      `Save as` variants for the loaded frame type.
- [ ] **M4-12** (S) Multi-extension header viewer: fix
      `ui/dialogs/header_dialog.py:134` extension switching.
- [ ] **M4-13** (S) Tests: load each sample image via every path added above.

---

## M5 — Scale, colour, block/bin

Depends on M1, M2.

### Scale
- [ ] **M5-1** (S) Add Power and SINH to the Scale menu (both algorithms already exist in
      `rendering/scale_algorithms.py`).
- [ ] **M5-2** (M) Percentile clipping presets: 99.5, 99, 98, 97, 96, 95, 92.5, 90 %.
- [ ] **M5-3** (S) ZMax limit mode.
- [ ] **M5-4** (S) Log Exponent parameter.
- [ ] **M5-5** (M) Scale scope Global / Local.
- [ ] **M5-6** (M) Min/max method: Scan, Sample, DATAMIN/DATAMAX, IRAF-MIN/IRAF-MAX, plus the
      Sample Parameters dialog (sample increment).
- [ ] **M5-7** (S) Use DATASEC toggle.
- [ ] **M5-8** (M) ZScale Parameters dialog: contrast, number of samples, samples per line.

### Colour
- [ ] **M5-9** (M) Bundle DS9's 168 `.sao`/`.lut` colormaps under `ncrads9/colormaps/data/` and
      load them at startup through the existing `sao_parser`/`lut_parser`. Include them in package
      data in `pyproject.toml`.
- [ ] **M5-10** (M) Build the full category submenus: h5utils, Matplotlib Uniform / Sequential /
      Diverging / Cyclic, Cubehelix, Gist, Topographic, Scientific Colour Maps, Solar, User.
- [ ] **M5-11** (L) Colour tags: create/edit/delete value-range highlights on the colorbar;
      the Colorbar pointer mode; load/save/delete tags per frame from the Colormap Parameters
      dialog.
- [ ] **M5-12** (M) Multiple colorbars (one per tiled frame) and the RGB/HSV/HLS colorbar
      variants.
- [ ] **M5-13** (S) Expose contrast/bias drag as an explicit Colorbar mode with a reset.

### Block vs Bin
- [ ] **M5-14** (M) Make Block a **non-destructive display transform**: move it into the render
      pipeline instead of overwriting `frame.image_data` in `_set_bin()`. Add factors 64, 128, 256.
- [ ] **M5-15** (S) Remove the `Bin` menu's block-averaging behaviour; keep the menu, repurpose
      it below.
- [ ] **M5-16** (L) FITS bin-table support: open a bin table, choose X/Y columns, bin function
      (average/sum), buffer size (128²…8192²), a third `depth` column, and a row filter
      expression.
- [ ] **M5-17** (M) Bin centring from `TDMIN/TDMAX`, `TLMIN/TLMAX`, `TALEN`, `AXLEN`, falling back
      to the middle of the data space.
- [ ] **M5-18** (S) Bin In / Bin Out / Bin Fit.
- [ ] **M5-19** (M) Binning Parameters dialog.
- [ ] **M5-20** (S) Fix `Frame → Match/Lock → Bin` and `→ Block` to mean the right things.
- [ ] **M5-21** (S) Test with a real event list (add a small synthetic one to `sampleimages/`).

---

## M6 — Regions to parity

Depends on M1, M2.

### Missing shapes
- [ ] **M6-1** (S) `regions/shapes/segment.py`.
- [ ] **M6-2** (M) `regions/shapes/epanda.py` (elliptical panda).
- [ ] **M6-3** (M) `regions/shapes/bpanda.py` (box panda).

### Interactive creation and editing
- [ ] **M6-4** (L) Extend `RegionMode` and the overlay's creation gestures from 6 to all 20
      shapes: annulus, ellipse annulus, box annulus, panda, epanda, bpanda, vector, ruler,
      compass, projection, segment, text, composite.
- [ ] **M6-5** (M) Point glyphs: circle, box, diamond, cross, x, arrow, boxcircle + size.
- [ ] **M6-6** (L) Selection handles: resize, rotate, and per-shape parameter handles
      (annulus radii, panda angles, vector length/angle).
- [ ] **M6-7** (M) Per-shape "Get Information" dialog with coordinate-system and format menus,
      matching DS9's marker dialogs.

### Properties
- [ ] **M6-8** (M) Property flags: include/exclude, source/background,
      fixed-in-size, can-edit, can-move, can-rotate, can-delete. Enforce them in the overlay.
- [ ] **M6-9** (S) `dash` and `fill` rendering properties.
- [ ] **M6-10** (S) Region Colour / Width / Font submenus, applied to selection and as new-region
      defaults.

### File formats
- [ ] **M6-11** (L) Parser: add every shape missing from
      `regions/region_parser.py:_create_region()` — ellipse annulus, box annulus, panda, epanda,
      bpanda, vector, ruler, compass, projection, segment, composite, and the `n=` /
      multi-radius annulus forms.
- [ ] **M6-12** (M) Writer: emit every shape and every property, in ds9/ciao/saotng/funtools/xy
      formats and each coordinate system.
- [ ] **M6-13** (M) Round-trip test driven by the shape examples in
      `.tmp_sao_ds9/ds9/doc/ref/region.html` — parse, write, reparse, assert identity.

### Management
- [ ] **M6-14** (M) Selection ops: All, None, Invert, Front, Back, Move to Front, Move to Back.
- [ ] **M6-15** (S) Save Selection, List Selection, Delete Selection; List (all).
- [ ] **M6-16** (M) Groups: adopt `regions/group_manager.py`; New Group + Groups dialog.
- [ ] **M6-17** (M) Composite regions: Create / Dissolve.
- [ ] **M6-18** (M) Templates: WCS-independent Open / Save.
- [ ] **M6-19** (S) Bundle DS9's instrument FOV templates (Chandra, XMM, MMT, HEASARC from
      `.tmp_sao_ds9/ds9/template/`) under an Instrument FOV submenu.
- [ ] **M6-20** (M) Centroid: adopt `analysis/centroid.py`; Centroid + Centroid Parameters
      (iterations, radius).
- [ ] **M6-21** (S) Autoload FITS regions on open (preference).

### Region-driven analysis
- [ ] **M6-22** (M) Statistics from a region — adopt `analysis/statistics.py`.
- [ ] **M6-23** (M) Histogram from a region — adopt `analysis/histogram.py`.
- [ ] **M6-24** (M) Radial profile from an annulus/panda.
- [ ] **M6-25** (M) Plot 2D (projection cut) and Plot 3D (cube slice through a region).
- [ ] **M6-26** (S) Auto Plot 2D / Auto Plot 3D / Auto Statistics / Auto Centroid toggles.

---

## M7 — Analysis platform

Depends on M2.

### External analysis tasks (`.ds9.ans`)
- [ ] **M7-1** (M) `analysis/task_file.py` — parser for the 4-line task block format
      (label, file template, type, command) with `#` comments and `---` separators.
- [ ] **M7-2** (M) Task types: `menu`, `button`, `bind <key>`, `web`.
- [ ] **M7-3** (L) Macro expansion: `$data $filename $filename(root|full|,base) $regions
      $filename[$regions] $x $y $z $width $height $depth $bitpix $env(VAR) $entry(msg)
      $filedialog(open|save) $dir $pan $zoom $cmap $scale $wcs $geturl`, and `$$` escaping.
- [ ] **M7-4** (M) Output sinks: `$text` (text window), `$plot` / `$plot(...)` (plot window),
      `$image` (load result into a frame), `$null`.
- [ ] **M7-5** (M) Hierarchical menus (`hmenu`) and `param`/`endparam` parameter dialogs — adopt
      the pattern in `.tmp_sao_ds9/ds9/library/analysisparam.tcl`.
- [ ] **M7-6** (M) Async subprocess execution with cancellation and a progress indicator; sync
      mode for XPA.
- [ ] **M7-7** (S) Startup autoload from `./ds9.ans`, `./ds9.analysis`, `$HOME/ds9.ans`, and
      `*.ds9` in `.`, `$HOME/bin`, `/usr/local/bin`, `/opt/local/bin`.
- [ ] **M7-8** (S) Replace the current `label|command` loader in
      `main_window.py:_load_analysis_commands()` with the real parser.
- [ ] **M7-9** (S) Tests with a fixture `.ds9.ans` covering each type and macro.

### WCS coordinate grid
- [ ] **M7-10** (L) Replace the pixel grid in `ui/widgets/contour_overlay.py:140` with a real WCS
      graticule. Back it with `astropy.visualization.wcsaxes` transforms rather than porting AST;
      adopt `grid/grid_renderer.py` + `grid/grid_labels.py` as the implementation home and delete
      `grid/ast_wrapper.py`.
- [ ] **M7-11** (M) Grid elements: grid lines, axes, tick marks, border, title, numbers — each
      with independent colour, width, style, and font.
- [ ] **M7-12** (M) Numeric formats per coordinate system, supporting DS9's format characters
      (`+`, `z`, `i`, `b`, `l`, `g`) and `printf`-style specs.
- [ ] **M7-13** (M) Grid Parameters dialog rebuilt to cover all of the above; load/save grid
      settings.
- [ ] **M7-14** (S) Axes placement: interior/exterior, and the grid's coordinate-system menu.

### Plot tool
- [ ] **M7-15** (M) `analysis/plot/` — plot window with line, bar, and scatter modes.
- [ ] **M7-16** (M) Axis configuration: title, range, log/linear, grid, format.
- [ ] **M7-17** (M) Multiple datasets with per-dataset colour/width/shape/legend.
- [ ] **M7-18** (S) Zoom stack (zoom in/out/pan with history), matching DS9's
      `plotzoomstack.tcl`.
- [ ] **M7-19** (S) Plot print and plot save/restore.
- [ ] **M7-20** (S) Wire `Analysis → Plot Tool → Line / Bar` (currently dead menu entries).

### Contours
- [ ] **M7-21** (M) Contour file load/save in DS9's contour format (header, global properties,
      coordinate system, levels, points).
- [ ] **M7-22** (S) Copy / Paste contours between frames.
- [ ] **M7-23** (S) Contour method BLOCK vs SMOOTH, matching DS9's semantics.

### Other analysis
- [ ] **M7-24** (M) Mask files: load a FITS mask, with blend mode, colour, value range, and
      transparency (DS9 `mask.tcl`).
- [ ] **M7-25** (S) Elliptical-gaussian smoothing kernel.
- [ ] **M7-26** (S) Adopt `analysis/pixel_table.py` in the pixel-table dialog; add DS9's
      3×3/5×5/7×7/9×9 sizes and per-cell coordinate display.

---

## M8 — Catalogs, image servers, VO

Depends on M2.

### Catalog tool
- [ ] **M8-1** (L) `catalogs/catalog_window.py` — the catalog list window: sortable columns,
      row selection, header view, print, close.
- [ ] **M8-2** (M) Live two-way selection sync between table rows and overlay symbols.
- [ ] **M8-3** (L) Symbol editor: shape, size, colour, angle and text driven by column
      expressions; save/load symbol sets (DS9 `catsym.tcl`).
- [ ] **M8-4** (M) Filtering: expression-based row filter with immediate overlay update
      (DS9 `catopt.tcl`).
- [ ] **M8-5** (M) Local catalog load/save: starbase (rdb), CSV with and without header, VOTable,
      TSV — adopt `catalogs/catalog_table.py`.
- [ ] **M8-6** (M) Catalog match between two loaded catalogs with a radius (DS9 `catmatch.tcl`).
- [ ] **M8-7** (S) Catalog plot (feed columns to the M7 plot tool).
- [ ] **M8-8** (S) Export catalog selection as regions (DS9 `catreg.tcl`).
- [ ] **M8-9** (S) Clear All / per-catalog clear.
- [ ] **M8-10** (M) Search for Catalogs — CDS catalog search by title, keyword, mission,
      wavelength, object type (DS9 `catcdssrch.tcl`).

### Catalog backends
- [ ] **M8-11** (M) Adopt `catalogs/{simbad,ned,sdss,twomass,skybot,vizier,cone_search}.py`
      behind a common `CatalogBase` interface; add the CDS and CXC servers.
- [ ] **M8-12** (S) Populate `Analysis → Catalogs` with DS9's server list.

### Image servers
- [ ] **M8-13** (M) Real DSS backends: SAO, ESO, STScI (replace the
      `NotImplementedError` skeletons in `image_servers/dss.py`, `eso.py`).
- [ ] **M8-14** (S) Real 2MASS (NASA/IPAC) backend.
- [ ] **M8-15** (S) Real SkyView (NASA/HEASARC) backend with survey selection.
- [ ] **M8-16** (M) VLA, NVSS, VLSS (NRAO) backends.
- [ ] **M8-17** (S) Real SDSS image backend.
- [ ] **M8-18** (M) Shared image-server dialog: object name or coordinates, size, survey, band,
      colour/format — matching DS9's `imgsvr.tcl`.

### Archives and VO
- [ ] **M8-19** (M) Archives menu: Chandra Public Archive by ObsId and by Cone Search;
      SIMBAD SAO/CDS; ADS SAO/CDS.
- [ ] **M8-20** (M) Footprint servers with a footprint overlay and Clear All (DS9 `fp.tcl`).
- [ ] **M8-21** (M) VO registry browser: discover and query SIA, SSA, cone-search and TAP
      services; broaden `ui/dialogs/vo_query_dialog.py` beyond its current scope.

---

## M9 — Remaining subsystems

Depends on M2, M3.

### Pointer modes
- [ ] **M9-1** (L) Crosshair mode: draggable crosshair, coordinate readout, and the horizontal/
      vertical cut graphs driven by it; Crosshair Parameters dialog made functional; crosshair
      match and lock across frames.
- [ ] **M9-2** (M) Interactive Crop mode (rubber-band crop on the canvas), plus crop match/lock.
- [ ] **M9-3** (M) Explicit Pan, Zoom and Rotate pointer modes.
- [ ] **M9-4** (M) Examine mode (click to centre-and-zoom) and its parameters.
- [ ] **M9-5** (S) Catalog and Footprint pointer modes (click a symbol to select its row).

### Illustrate layer
- [ ] **M9-6** (L) `illustrate/` package: a non-WCS annotation layer with circle, ellipse, box,
      polygon, line, text and image elements.
- [ ] **M9-7** (M) Illustrate menu: Shape, Colour, Width, All/None/Invert, Front/Back,
      Move to Front/Back, Open/Save/List, Delete All/Selection, Show.
- [ ] **M9-8** (M) Illustrate file format read/write and its own selection handles.

### Prism
- [ ] **M9-9** (L) Rewrite `prism/` as a real FITS browser: HDU list, header view, table view
      with sortable columns, image preview, plot a column, load an HDU into a frame.
- [ ] **M9-10** (S) `File → Prism` and the `prism` XPA point.

### Session and files
- [ ] **M9-11** (L) Backup / Restore: adopt `io/session/` to serialise all frames, their data
      references, view state, regions, contours, grids, colormaps and colour tags.
- [ ] **M9-12** (S) Auto-recovery / autosave (DS9 `autosave.tcl`).
- [ ] **M9-13** (M) Import: Array, NRRD, ENVI, RGB/HSV/HLS Array, GIF, TIFF, JPEG, PNG — adopt
      `io/{array,nrrd,envi}_reader.py`.
- [ ] **M9-14** (M) Export: the same 10 formats — adopt `io/*_writer.py`; keep the existing
      screen-grab export as `Save Image`.
- [ ] **M9-15** (M) Create Movie: adopt `io/mpeg_writer.py`; frame/slice/3D-rotation sequences
      (DS9 `movie.tcl`).
- [ ] **M9-16** (S) Notes window (`File → Notes`).
- [ ] **M9-17** (S) Preserve During Load → Pan / Region.

### Printing
- [ ] **M9-18** (L) Real Postscript driver: adopt `printing/postscript.py`; levels 1/2/3, colour
      models RGB/CMYK/Grayscale, resolution in pixels-per-inch, vector text and line graphics.
- [ ] **M9-19** (M) Page Setup dialog: adopt `printing/page_setup.py` — paper size, orientation,
      scale, margins.
- [ ] **M9-20** (S) PDF output via `printing/print_engine.py`.

### 3D
- [ ] **M9-21** (L) `frames/frame_3d.py` rewritten: MIP and AIP ray-trace projections over a data
      cube, threaded, with azimuth/elevation controls.
- [ ] **M9-22** (M) 3D dialog (view angles, method, background, threads) and the 3D pointer mode.
- [ ] **M9-23** (S) 3D match/lock and the `3d` XPA point.

### Undo/redo
- [ ] **M9-24** (L) Command-pattern undo stack covering region edits, view changes, colormap
      changes and frame operations; wire `action_undo`/`action_redo`/cut/copy/paste.

### Communication
- [ ] **M9-25** (L) Grow XPA from 23 to DS9's 143 access points. Use
      `.tmp_sao_ds9/ds9/library/xpa.tcl` as the specification and
      `.tmp_sao_ds9/ds9/parsers/*` for each point's grammar. Suggested order:
      **(a)** display: `scale zscale minmax cmap colorbar invert block bin smooth mask
      grid contour crop rotate orient align`;
      **(b)** frames: `single tile blink fade multiframe mecube cube slice datacube 3d rgb hsv hls
      lock match first last next prev`;
      **(c)** files: `array nrrd envi mosaic* rgb* hsv* hls* url sfits memf shm gif jpeg png tiff
      export import saveimage savefits savempeg movie backup restore`;
      **(d)** tools: `analysis catalog cat fp footprint plot prism pixeltable magnifier panner
      nameserver iexam imexam illustrate notes samp vo sia skyview dss* 2mass nvss vla vlss`;
      **(e)** app: `about version prefs theme threads mode cursor iconify raise lower height width
      view source tcl console sleep update nan precision preserve pagesetup psprint print header
      data`.
- [ ] **M9-26** (S) XPA UI: `File → XPA → Information / Connect / Disconnect`.
- [ ] **M9-27** (M) SAMP: broadcast image and broadcast table; the SAMP Hub UI
      (Information / Start / Stop) over the existing `samp_hub.py`.
- [ ] **M9-28** (M) SAMP web hub.
- [ ] **M9-29** (M) IIS / IRAF `imexam`: adopt `communication/iis/iis_server.py`; the `iis` and
      `iexam` XPA points.
- [ ] **M9-30** (S) Shared-memory loading (`shm`).

### Polish
- [ ] **M9-31** (M) i18n: extract all UI strings, add Qt translation files for DS9's 8 locales
      (cs, da, de, es, fr, ja, pt, zh) seeded from `.tmp_sao_ds9/ds9/msgs/*.msg`, and a Language
      preference.
- [ ] **M9-32** (M) Grow Preferences to DS9's topic coverage: General, Precision, Startup,
      Coordinates, Region, Annulus, Panda, Scale, Colour, Contour, Grid, Bin, Smooth, Zoom,
      Graph, Panner, Magnifier, PixelTable, Examine, Catalog, VO, NRES, Analysis, HTTP, Print,
      Page Setup, Menu/Buttonbar customisation.
- [ ] **M9-33** (M) Configurable keyboard and mouse bindings + a Keyboard Shortcuts editor.
- [ ] **M9-34** (S) Python console replacing DS9's TCL console; `Run Python Script` replacing
      `Source TCL`.
- [ ] **M9-35** (S) Display Size (`Frame → Frame Parameters → Display Size`).
- [ ] **M9-36** (S) Tile Parameters: grid rows/columns, automatic/manual, direction, gap.

---

## Continuous

- [ ] **C-1** Keep `docs/parity/ncrads9_menus.txt` regenerated in CI (the `parity` job already
      fails when it is stale) and review the `tools/menu_diff.py --summary` output each milestone.
- [ ] **C-2** Keep `tests/unit/test_no_orphan_modules.py` (M1-20) green — no new orphans.
- [ ] **C-3** Keep the `MenuBar` action-connection test (M2-15) green — no dead menu entries.
- [ ] **C-4** Update `README.md`'s Feature Status section at the end of every milestone.
- [ ] **C-5** Raise the coverage floor at the end of every milestone.
- [ ] **C-6** Add an XPA conformance test per access point as it lands, comparing against real DS9
      where available.
- [ ] **C-7** Populate `tests/integration/` — currently empty — with end-to-end flows
      (open → scale → region → save → reload).
