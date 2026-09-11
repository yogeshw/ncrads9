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

**Status: complete.** File-menu parity with DS9 **6/59 -> 29/59 labels**, total menu entries
**337 -> 371**, orphan modules **60 -> 56**, tests **628 -> 811**, coverage 51.6% -> 55.6%.

| Module | Lines | Owns |
|---|---:|---|
| `core/file_spec.py` | 505 | DS9's `foo.fits[2][100:200,*,4]` grammar |
| `core/fits_handler.py` | 669 | the HDU model, sections, events binning |
| `core/mosaic.py` | 510 | the WCS, IRAF and WFPC2 conventions |
| `core/fits_loaders.py` | 249 | one function per `Open as` entry |
| `core/cube_handler.py` | 388 | slicing, in any of DS9's six axis orders |
| `ui/panels/cube_panel.py` | 315 | DS9's Cube dialog (rewritten) |
| `ui/dialogs/open_dialog.py` | 209 | the extension chooser (rewritten) |

- [x] **M4-1** (M) `core/fits_handler.py`: extension model — enumerate HDUs with type, name,
      dimensions, and whether each is displayable.
- [x] **M4-2** (M) HDU chooser in `ui/dialogs/open_dialog.py` (currently orphaned — adopt it),
      shown when a file has more than one displayable HDU.
- [x] **M4-3** (M) Parse DS9/funtools file syntax: `file.fits[3]`, `file.fits[EVENTS]`,
      `file.fits[x>10&&y<20]`, `file.fits[bin=x,y]`.
- [x] **M4-4** (L) Data cubes: `core/cube_handler.py` for slice extraction and axis order; adopt
      `ui/panels/cube_panel.py` as the Cube dialog (slice slider, axis order, interval, play/stop,
      and the `Frame → Cube` entry).
- [x] **M4-5** (S) `File → Open as → Slice`.
- [x] **M4-6** (M) Multiple Extension Cube and Multiple Extension Frames loaders.
- [x] **M4-7** (L) Mosaic loaders: Mosaic WCS, Mosaic WCS Segment, Mosaic IRAF,
      Mosaic IRAF Segment, Mosaic WFPC2, Mosaic Image variants.
- [x] **M4-8** (S) Tile-compressed (`CompImageHDU`) images.
- [~] **M4-9** (S) URL loading (`File → Open as → URL`) with a progress indicator.
      *The download works, bounded by a 30-second timeout, with the status bar saying what is
      happening. There is no progress bar: one needs the background-worker machinery of M8-13,
      which the catalog and image-server queries will share. Recorded rather than left silent.*
- [x] **M4-10** (M) Implement `save_file()` / `save_file_as()` — write the current frame's data +
      header + updated WCS to FITS.
- [x] **M4-11** (M) `File → Save Image → FITS` (rendered image as FITS) and the remaining
      `Save as` variants for the loaded frame type.
- [x] **M4-12** (S) Multi-extension header viewer: fix
      `ui/dialogs/header_dialog.py:134` extension switching.
- [x] **M4-13** (S) Tests: load each sample image via every path added above.

### Where this deviated from the plan, and why

* **`core/file_spec.py` and `core/fits_loaders.py` are new.** M4-3 said "parse ... syntax" without
  saying where; keeping the grammar in its own Qt-free module means every one of DS9's documented
  examples is a test, and the CLI, the Open dialog and M8's XPA `file` access point share one
  parser. Likewise the `Open as` loaders are functions over an open file rather than controller
  methods, so each is testable without a window.
* **M4-2 says "adopt" the open dialog; it was rewritten.** What was there was a second file-open
  dialog — a list of paths with a header preview, wrapping `QFileDialog.getOpenFileName`, never
  constructed — and not an HDU chooser at all.
* **The chooser is a divergence, and optional.** DS9 never asks. It also carries the two
  "all extensions" choices, so M4-6's loaders are reachable from the place already listing them.
* **M4-7's "Mosaic Image variants" are the same code paths.** DS9's distinction is whole-file
  (`-mosaicimage`) versus several files (`-mosaic`); both assemble the extensions of what they are
  given, so one loader per convention covers both, with the segment variants merging into the
  mosaic already on screen.
* **Events binning is the plain two-dimensional count.** `[bin=colx,coly]` works and gives the
  image its WCS from the columns' own `TCRVL`/`TCRPX`/`TCDLT`/`TCTYP` cards. The Binning
  Parameters dialog, block factors, row filters and binning a third column's *value* are M5,
  where PLAN.md §3.4 puts bin-table work. A specification asking for those is accepted and its
  extra parts ignored rather than refused.
* **HEALPIX tables are recognised but not displayable.** `PIXTYPE = HEALPIX` is classified, so the
  chooser and the error messages name it correctly; reprojecting one is M9.
* **`WCSHandler` now reduces a cube's WCS to its celestial axes.** A frame shows one 2D slice, and
  every readout passes an (x, y) pair, so a three-axis WCS raised from `pixel_to_world`.
* **The centred-section tie-break is a choice.** DS9's `[dim@centre]` for an even width could go
  either side and DS9's source does not say; `centre - width // 2` reproduces its one documented
  example, `[256@512@512]` → 384:639.

### Bugs found and fixed on the way

* **Stepping a cube slice kept the previous slice's clip limits.** A cube whose brightness varies
  with channel came out flat white or flat black as you stepped through it. DS9's default scale
  scope is local, so the limits now follow the displayed slice.
* **A `CompImageHDU` was classified with an empty shape** and so reported as not displayable:
  astropy presents such an HDU as the image it decompresses to, with `NAXIS` rather than the
  `ZNAXIS` the FITS convention writes.
* **A WCS mosaic clipped the last row and column of every input.** The output canvas was sized
  from the corner pixels' *centres* rather than their outer edges.
* **Overlapping mosaic tiles left a hole**, because the fill condition was written to preserve
  existing pixels and did the opposite.
* **`refresh_info` opened files.** `MainWindow.fits_handler` re-opens a frame's file when it has a
  path but no handler, and the information panel called it on every redisplay.
* **`NCSPEC` truncated the extension away** on a long path, since a FITS card's value stops at 68
  characters; it now records the bracket part alone.

---

## M5 — Scale, colour, block/bin

**Status: complete.** Five DS9 menus are now at full label parity -- Scale **31/31**, Color
**25/25**, Bin **22/22**, Edit **18/18**, Zoom **26/26** -- and Block is a display transform
rather than an edit. Overall menu parity **50% -> 66%**, tests **811 -> 1086**, coverage
55.6% -> 58.5%.

| Module | Lines | Owns |
|---|---:|---|
| `rendering/scale_limits.py` | 335 | DS9's limit modes, methods, scope and DATASEC |
| `rendering/block.py` | 80 | DS9's Block, as a transform on a copy |
| `core/bin_table.py` | 407 | DS9's Bin: a table into an image |
| `colormaps/bundled.py` | 358 | DS9's 164 tables on DS9's ten cascades |
| `colormaps/color_tags.py` | 270 | colour tags, and DS9's tag file format |
| `ui/controllers/bin.py` | 354 | the Bin menu and its Parameters dialog |
| `colormaps/data/` | 164 files | the tables themselves, 1.2 MB |

### Scale
- [x] **M5-1** (S) Add Power and SINH to the Scale menu (both algorithms already exist in
      `rendering/scale_algorithms.py`).
- [x] **M5-2** (M) Percentile clipping presets: 99.5, 99, 98, 97, 96, 95, 92.5, 90 %.
- [x] **M5-3** (S) ZMax limit mode.
- [x] **M5-4** (S) Log Exponent parameter.
- [x] **M5-5** (M) Scale scope Global / Local.
- [x] **M5-6** (M) Min/max method: Scan, Sample, DATAMIN/DATAMAX, IRAF-MIN/IRAF-MAX, plus the
      Sample Parameters dialog (sample increment).
- [x] **M5-7** (S) Use DATASEC toggle.
- [x] **M5-8** (M) ZScale Parameters dialog: contrast, number of samples, samples per line.

### Colour
- [x] **M5-9** (M) Bundle DS9's 168 `.sao`/`.lut` colormaps under `ncrads9/colormaps/data/` and
      load them at startup through the existing `sao_parser`/`lut_parser`. Include them in package
      data in `pyproject.toml`. *164 of them, lazily rather than at startup: see below.*
- [x] **M5-10** (M) Build the full category submenus: h5utils, Matplotlib Uniform / Sequential /
      Diverging / Cyclic, Cubehelix, Gist, Topographic, Scientific Colour Maps, Solar, User.
- [x] **M5-11** (L) Colour tags: create/edit/delete value-range highlights on the colorbar;
      the Colorbar pointer mode; load/save/delete tags per frame from the Colormap Parameters
      dialog.
- [x] **M5-12** (M) Multiple colorbars (one per tiled frame) and the RGB/HSV/HLS colorbar
      variants.
- [x] **M5-13** (S) Expose contrast/bias drag as an explicit Colorbar mode with a reset.

### Block vs Bin
- [x] **M5-14** (M) Make Block a **non-destructive display transform**: move it into the render
      pipeline instead of overwriting `frame.image_data` in `_set_bin()`. Add factors 64, 128, 256.
- [x] **M5-15** (S) Remove the `Bin` menu's block-averaging behaviour; keep the menu, repurpose
      it below.
- [x] **M5-16** (L) FITS bin-table support: open a bin table, choose X/Y columns, bin function
      (average/sum), buffer size (128²…8192²), a third `depth` column, and a row filter
      expression.
- [x] **M5-17** (M) Bin centring from `TDMIN/TDMAX`, `TLMIN/TLMAX`, `TALEN`, `AXLEN`, falling back
      to the middle of the data space.
- [x] **M5-18** (S) Bin In / Bin Out / Bin Fit.
- [x] **M5-19** (M) Binning Parameters dialog.
- [x] **M5-20** (S) Fix `Frame → Match/Lock → Bin` and `→ Block` to mean the right things.
- [x] **M5-21** (S) Test with a real event list (add a small synthetic one to `sampleimages/`).

### Where this deviated from the plan, and why

* **Three transfer functions were wrong, not missing.** M5-1 reads as "add Power and SINH", but
  Power *was* `x**2` -- which is DS9's *Squared*, an entry NCRADS9 did not have -- and Sinh was
  `sinh(x)/sinh(1)` against DS9's `sinh(3x)/10`. Read off `tksao/frame/colorscale.C` and now
  matching DS9 exactly, which is what makes the two applications render an image alike.
* **DS9 has one exponent, not two.** `scale(log)` drives both the log and the power functions, so
  M5-4's Log Exponent is a single setting, offered as a submenu of eight presets plus Other where
  DS9 offers only a dialog.
* **The limit settings are per window, not per frame.** DS9 keeps them per frame and ties frames
  with `Frame -> Lock -> Scale`; this keeps one set and caches the *computed* limits per frame, so
  switching frames still restores what you saw. Per-frame settings are a Lock question, for M9.
* **164 tables, not 168, and loaded lazily.** `viridis`, `inferno`, `magma` and `plasma` are
  shipped by DS9 as files *and* exist as NCRADS9 built-ins under the same names; the same tables
  are on Matplotlib Uniform as `mpl_viridis` and friends. One name resolving to two sources is a
  bug waiting to happen. Six topographic tables DS9 ships but never menus go on Topographic, and
  `turbo`/`twilight` on Sequential and Cyclic by what they are. Reading all 164 at startup costs
  about a second for tables almost none of which will be looked at, so they are parsed on first
  use. All recorded in `colormaps/data/README.md`.
* **Block converts coordinates at four places, not everywhere.** The viewers work in the units of
  whatever array they were handed, so rather than thread a factor through the whole coordinate
  path, the two mapping functions of the CPU viewer and the two of the region overlay multiply by
  it, with the GL path's cursor and click signals doing the same.
* **The Bin menu got a controller of its own.** It belonged to Analysis, where it block-averaged
  the displayed image. A change to any Bin setting means re-binning the table the frame came from,
  which has nothing to do with the Analysis menu.
* **The Colour Tag dialog has a Delete button** where DS9's has only OK and Cancel: a tag created
  by a stray click on the colorbar is otherwise awkward to be rid of, DS9's own Delete Color Tag
  deleting all of them.
* **Two readings of DS9's Bin documentation, both recorded in `core/bin_table.py`.** DS9 calls the
  buffer size "the overall size of the image generated ... no relation to min and max values of
  the columns", which read strictly would make a 512-unit detector come up as 1024x1024 with the
  data in the middle; it is treated as a cap here, which is the reading under which "Bin to Fit
  ... calculate[s] a bin block factor" means anything. And `BinSettings.depth` is recorded and
  offered in the dialog but only two-dimensional binning is implemented -- DS9 can bin a table
  into a cube.

### Bugs found and fixed on the way

* **Every one of DS9's 46 `.sao` colour tables would have loaded as a flat colour.** DS9 writes an
  entire channel on one line -- two hundred-odd `(position,value)` pairs of it -- and the parser
  stripped the punctuation, split on whitespace and took the first two numbers. One control point
  per channel, so `np.interp` returned a constant. It did that without raising, which is what
  PLAN.md §3.1 meant by code that gives a false impression of coverage.
* **Eighteen cascade entries could not have been applied.** The menu registers colormap actions
  under a lowercased key while eighteen of DS9's files are mixed-case (`mpl_Greys`,
  `scm_batlowK`); lookups now ignore case at both ends.
* **The Scale menu could not have had an effect even once it existed.** All three places the
  display pipeline computed limits called `compute_zscale_limits` directly, bypassing any setting.
* **Stepping a cube slice kept the previous slice's clip limits**, so a cube whose brightness
  varies with channel went flat white or flat black.
* **A coarse bin factor lost events off the top edge.** The grid was anchored on bin *centres*, so
  a 1..64 column at a factor of four discarded everything above 63.
* **A binned image's `CDELT` did not scale with the bin factor**, so its sky scale was wrong for
  every factor but one.
* **A filter given in a specification survived one load and no more**: it was folded in inside the
  loader, so the next change from the Bin menu re-binned the whole table and dropped it.
* **`&&` in a row filter raised a type error.** Python binds `&` tighter than `>`, so a bare
  substitution turns `pha>50&&x<32` into `pha > (50 & x) < 32`. Each conjunct is parenthesised.
* **A `#rrggbb` colour in a tag file was stripped as a comment.** Comments are now line-leading
  only, with anything after the third field ignored, which lets a hex colour and a trailing
  comment coexist.
* **`Frame -> Match -> Bin` copied the block factor**, which is neither what DS9's Bin means nor
  what its Block means.

---

## M6 — Regions to parity

Depends on M1, M2.

### Missing shapes
- [x] **M6-1** (S) `regions/shapes/segment.py`.
- [x] **M6-2** (M) `regions/shapes/epanda.py` (elliptical panda).
- [x] **M6-3** (M) `regions/shapes/bpanda.py` (box panda).

### Interactive creation and editing
- [x] **M6-4** (L) Extend `RegionMode` and the overlay's creation gestures from 6 to all 19
      shapes: annulus, ellipse annulus, box annulus, panda, epanda, bpanda, vector, ruler,
      compass, projection, segment, text, composite.
- [x] **M6-5** (M) Point glyphs: circle, box, diamond, cross, x, arrow, boxcircle + size.
- [x] **M6-6** (L) Selection handles: resize, rotate, and per-shape parameter handles
      (annulus radii, panda angles, vector length/angle).
- [x] **M6-7** (M) Per-shape "Get Information" dialog with coordinate-system and format menus,
      matching DS9's marker dialogs.

### Properties
- [x] **M6-8** (M) Property flags: include/exclude, source/background,
      fixed-in-size, can-edit, can-move, can-rotate, can-delete. Enforce them in the overlay.
- [x] **M6-9** (S) `dash` and `fill` rendering properties.
- [x] **M6-10** (S) Region Colour / Width / Font submenus, applied to selection and as new-region
      defaults.

### File formats
- [x] **M6-11** (L) Parser: add every shape missing from
      `regions/region_parser.py:_create_region()` — ellipse annulus, box annulus, panda, epanda,
      bpanda, vector, ruler, compass, projection, segment, composite, and the `n=` /
      multi-radius annulus forms.
- [x] **M6-12** (M) Writer: emit every shape and every property, in ds9/ciao/saotng/funtools/xy
      formats and each coordinate system.
- [x] **M6-13** (M) Round-trip test driven by the shape examples in
      `.tmp_sao_ds9/ds9/doc/ref/region.html` — parse, write, reparse, assert identity.

### Management
- [x] **M6-14** (M) Selection ops: All, None, Invert, Front, Back, Move to Front, Move to Back.
- [x] **M6-15** (S) Save Selection, List Selection, Delete Selection; List (all).
- [x] **M6-16** (M) Groups: adopt `regions/group_manager.py`; New Group + Groups dialog.
- [x] **M6-17** (M) Composite regions: Create / Dissolve.
- [x] **M6-18** (M) Templates: WCS-independent Open / Save.
- [x] **M6-19** (S) Bundle DS9's instrument FOV templates (Chandra, XMM, MMT, HEASARC from
      `.tmp_sao_ds9/ds9/template/`) under an Instrument FOV submenu.
- [x] **M6-20** (M) Centroid: adopt `analysis/centroid.py`; Centroid + Centroid Parameters
      (iterations, radius).
- [x] **M6-21** (S) Autoload FITS regions on open (preference).

### Region-driven analysis
- [x] **M6-22** (M) Statistics from a region — adopt `analysis/statistics.py`.
- [x] **M6-23** (M) Histogram from a region — adopt `analysis/histogram.py`.
- [x] **M6-24** (M) Radial profile from an annulus/panda.
- [x] **M6-25** (M) Plot 2D (projection cut) and Plot 3D (cube slice through a region).
- [x] **M6-26** (S) Auto Plot 2D / Auto Plot 3D / Auto Statistics / Auto Centroid toggles.

### Deviations from the plan as written

* **Nineteen shapes, not twenty.** PLAN.md and this file both said twenty. DS9's Region
  Descriptions table lists nineteen (`ds9/doc/ref/region.html`): circle, ellipse, box, polygon,
  point, line, vector, segment, text, ruler, compass, projection, annulus, ellipse annulus, box
  annulus, panda, epanda, bpanda, composite. A test counts them from that table so the number
  cannot drift again. Eighteen of them are drawable; a composite is made from regions that already
  exist, so it has no gesture of its own.
* **M6-16 did not adopt `regions/group_manager.py`; it replaced it.** The module keyed group
  membership on positions in the region list, which deleting a region, loading a second file, or
  M6-14's own Move to Front each silently corrupt. DS9 has no group object at all -- a group is
  the set of regions carrying a tag -- so the module is now tag-backed, and membership survives a
  round trip through a region file.
* **M6-7 did not adopt `ui/dialogs/region_dialog.py` either.** It edited a plain dict of nine
  hardcoded shape names and could not describe an annulus, a panda or a segment. The rewrite reads
  its fields off each shape's own constructor, so a shape cannot gain a parameter the dialog does
  not show.
* **M6-22 and M6-23 did adopt theirs.** `analysis/statistics.py` and `analysis/histogram.py` both
  already took a pixel mask, which is exactly what a region is.
* **The Region menu gained two cascades the plan did not mention**, because DS9 has them and the
  entries had nowhere else to live: Composite Region (Create/Dissolve, `mregion.tcl:143`) and
  Region Parameters (Show, Show Text, the three Auto Plot toggles, Auto Centroid and Centroid
  Parameters, `mregion.tcl:78`).
* **`mmt/megacam/megacam-amp-guide.tpl` has an unclosed parenthesis in DS9's own file**
  (`# composite(0,0,0|| composite=1`). Its 149 members load as ordinary regions rather than as a
  composite, which draws the same thing. The other twenty-two templates parse exactly.
* **DS9's per-region analysis is reachable from the region's own dialog, as in DS9, and not from
  the Analysis menu.** The whole-frame Statistics and Histogram entries there are untouched.

### Bugs found and fixed on the way

* **Six parts of DS9's own region format could not be parsed**, found by trying to read DS9's
  twenty-three bundled instrument templates: only one of them parsed at all. Unit suffixes (`16"`,
  `3'`); whitespace as a parameter separator, which DS9's own documentation gives
  (`circle 100 100 10`); a coordinate system sharing the line (`image; circle 100 100 10`); shapes
  written behind a `#`, which is how DS9 writes text, vector, ruler, compass, projection and
  segment; `||`, which marks a composite member; and `wcs0`, the template system.
* **Eleven of the nineteen shapes drew a four-pixel tick and nothing else** -- the annuli, the
  three pandas, the vector, the ruler, the projection, the compass, the segment and the composite
  all fell through the renderer to its final `else`.
* **A composite drew none of its children.** It is its children.
* **A text region was drawn twice**, once as the shape and once again as its own label.
* **`Text` held its string twice**, in `_label` and in `BaseRegion.text`. Setting one changed what
  was drawn but not what was written to a region file, which the Get Information dialog does both
  of. `label` is now a view onto `text`.
* **`# composite(x,y,angle)` was thrown away with the comments**, so a composite never parsed.
* **Multiple `tag=` properties collapsed to one**, which would have lost every group but the last.
* **A point's size was dropped**: `point=diamond 15` was cut at the space.
* **Selection handles were drawn but inert**, and eleven shapes reported nothing but their centre
  to draw them at, so there was nothing to make draggable.
* **`main_window.py` reached 604 lines** when the region defaults were put on the window; the M2
  guard caught it and they moved to the controller.
* **The statistics mask counted a ten-pixel box as eleven columns wide**, a 28% overstatement of
  the area every surface brightness is divided by. The mask is half-open on the upper edge;
  `contains` stays inclusive, because that is hit-testing rather than area.
* **A composite's centre is the mean of its members**, so converting it when placing a template
  put the Chandra field of view at a NaN.
* **Three type errors surfaced in `analysis/` once it was reachable**: an integer contour
  coordinate returned where floats were promised, a rank-any shape assigned to a two-tuple, and a
  numpy index used unconverted.
* **A test that triggered every selection action hung the suite forever**: Save Selection opens a
  file dialog and List Selection a message box, and a modal dialog under the offscreen platform
  waits for a click that never comes.
* **Reading a rendered canvas through `np.frombuffer(QImage.constBits())` borrows Qt's memory**,
  which is freed when the QImage goes out of scope. It segfaulted in a script and handed back
  stale pixels in a test.

---

## M7 — Analysis platform

Depends on M2.

### External analysis tasks (`.ds9.ans`)
- [x] **M7-1** (M) `analysis/task_file.py` — parser for the 4-line task block format
      (label, file template, type, command) with `#` comments and `---` separators.
- [x] **M7-2** (M) Task types: `menu`, `button`, `bind <key>`, `web`.
- [x] **M7-3** (L) Macro expansion: `$data $filename $filename(root|full|,base) $regions
      $filename[$regions] $x $y $z $width $height $depth $bitpix $env(VAR) $entry(msg)
      $filedialog(open|save) $dir $pan $zoom $cmap $scale $wcs $geturl`, and `$$` escaping.
- [x] **M7-4** (M) Output sinks: `$text` (text window), `$plot` / `$plot(...)` (plot window),
      `$image` (load result into a frame), `$null`.
- [x] **M7-5** (M) Hierarchical menus (`hmenu`) and `param`/`endparam` parameter dialogs — adopt
      the pattern in `.tmp_sao_ds9/ds9/library/analysisparam.tcl`.
- [x] **M7-6** (M) Async subprocess execution with cancellation and a progress indicator; sync
      mode for XPA.
- [x] **M7-7** (S) Startup autoload from `./ds9.ans`, `./ds9.analysis`, `$HOME/ds9.ans`, and
      `*.ds9` in `.`, `$HOME/bin`, `/usr/local/bin`, `/opt/local/bin`.
- [x] **M7-8** (S) Replace the current `label|command` loader in
      `main_window.py:_load_analysis_commands()` with the real parser.
- [x] **M7-9** (S) Tests with a fixture `.ds9.ans` covering each type and macro.

### WCS coordinate grid
- [x] **M7-10** (L) Replace the pixel grid in `ui/widgets/contour_overlay.py:140` with a real WCS
      graticule. Back it with `astropy.visualization.wcsaxes` transforms rather than porting AST;
      adopt `grid/grid_renderer.py` + `grid/grid_labels.py` as the implementation home and delete
      `grid/ast_wrapper.py`.
- [x] **M7-11** (M) Grid elements: grid lines, axes, tick marks, border, title, numbers — each
      with independent colour, width, style, and font.
- [x] **M7-12** (M) Numeric formats per coordinate system, supporting DS9's format characters
      (`+`, `z`, `i`, `b`, `l`, `g`) and `printf`-style specs.
- [x] **M7-13** (M) Grid Parameters dialog rebuilt to cover all of the above; load/save grid
      settings.
- [x] **M7-14** (S) Axes placement: interior/exterior, and the grid's coordinate-system menu.

### Plot tool
- [x] **M7-15** (M) `analysis/plot/` — plot window with line, bar, and scatter modes.
- [x] **M7-16** (M) Axis configuration: title, range, log/linear, grid, format.
- [x] **M7-17** (M) Multiple datasets with per-dataset colour/width/shape/legend.
- [x] **M7-18** (S) Zoom stack (zoom in/out/pan with history), matching DS9's
      `plotzoomstack.tcl`.
- [x] **M7-19** (S) Plot print and plot save/restore.
- [x] **M7-20** (S) Wire `Analysis → Plot Tool → Line / Bar` (currently dead menu entries).

### Contours
- [x] **M7-21** (M) Contour file load/save in DS9's contour format (header, global properties,
      coordinate system, levels, points).
- [x] **M7-22** (S) Copy / Paste contours between frames.
- [x] **M7-23** (S) Contour method BLOCK vs SMOOTH, matching DS9's semantics.

### Other analysis
- [x] **M7-24** (M) Mask files: load a FITS mask, with blend mode, colour, value range, and
      transparency (DS9 `mask.tcl`).
- [x] **M7-25** (S) Elliptical-gaussian smoothing kernel.
- [x] **M7-26** (S) Adopt `analysis/pixel_table.py` in the pixel-table dialog; add DS9's
      3×3/5×5/7×7/9×9 sizes and per-cell coordinate display.

### Deviations from the plan as written

* **The graticule is built on `astropy.wcs`'s transforms, not on
  `astropy.visualization.wcsaxes`.** M7-10 named wcsaxes; its transform machinery is bound to a
  matplotlib axes object and the drawing here is QPainter, so the transform is taken from the WCS
  directly and the sampling done in `grid/grid_renderer.py`. The point of the suggestion -- do not
  port AST -- stands either way, and `grid/ast_wrapper.py` is deleted as planned.
* **`$xcen` and `$ycen` are not implemented, because DS9 does not implement them either.** They
  appear in its own sample analysis file and in none of its `Parse*Macro` procedures; like any
  unknown macro they pass through untouched.
* **`$url` becomes a `curl` in the command line rather than a download behind the user's back.**
  DS9 fetches the URL to a temporary file and pipes that in. The command line is what runs, and it
  should say what it does.
* **An IRAF `@param` file is recorded but not read.** DS9 looks for it in `./`, `$UPARM/` and
  `$HOME/iraf/`; the dialog says so rather than pretending the parameters exist.
* **The Plot Tool is one graph per window.** DS9's Plot menu can add, delete and lay out several
  graphs in one window (grid/row/column/strip). Everything else on its four menus is here.
* **Analysis buttons get a button-bar category called "Tasks", not "Analysis".** That name is
  already the category mirroring the Analysis *menu*, and sharing it would let Clear Analysis
  Commands delete the built-in buttons.

### Bugs found and fixed on the way

* **The displayed image was stretched to the viewport, ignoring aspect ratio.** The image label had
  `setScaledContents(True)` and is sized by the layout rather than by its own `resize`, so an image
  in a viewport of a different shape was drawn *distorted* -- and every overlay (regions, contours,
  the new grid) drew in the correct uniform transform and therefore did not line up with the
  picture underneath it. Found by drawing a coordinate grid and seeing the border miss the image.
* **`WCSHandler.world_to_pixel` assumed ICRS.** It built a `SkyCoord(ra=, dec=)`, so a galactic or
  ecliptic WCS was misprojected -- silently, since the transform still returns numbers. A
  coordinate grid over a galactic image drew nothing at all, which is how it was found.
* **Six parts of DS9's own analysis format could not be read**, found by parsing its documented
  sample: a `#` mid-line truncating a task label, help text needing exemption from that, a bare
  `end` closing any block, and the ordering rules `$xpa_method` before `$xpa`,
  `$filename[$regions]` before `$filename`, and `$plot` before `$geturl` (whose argument is greedy
  to the last bracket).
* **The Smooth dialog's Position angle field did nothing.** The elliptical case passed axis-aligned
  sigmas to `gaussian_filter`, which cannot express an angle.
* **`PixelTable.get_region` clipped at the image edge instead of padding**, returning a smaller
  array whose centre was no longer the centre -- so a pixel table near a corner showed the wrong
  values against the wrong coordinates.
* **A contour file written at `%.8g` lost a tenth of an arcsecond** on a right ascension near 200
  degrees, so a saved contour drifted off the feature it was drawn on.
* **Three type errors in `analysis/` surfaced once the package was reachable**: an integer contour
  coordinate returned where floats were promised, a rank-any shape assigned to a two-tuple, and a
  numpy index used unconverted.
* **A bar plot of widely spaced data drew hairlines**, because matplotlib's default bar width of
  0.8 assumes data spaced about one apart.
* **A log plot axis with non-positive data drew an empty plot and said nothing**; it falls back to
  linear.

---

## M8 — Catalogs, image servers, VO

Depends on M2.

### Catalog tool
- [x] **M8-1** (L) `catalogs/catalog_window.py` — the catalog list window: sortable columns,
      row selection, header view, print, close.
- [x] **M8-2** (M) Live two-way selection sync between table rows and overlay symbols.
- [x] **M8-3** (L) Symbol editor: shape, size, colour, angle and text driven by column
      expressions; save/load symbol sets (DS9 `catsym.tcl`).
- [x] **M8-4** (M) Filtering: expression-based row filter with immediate overlay update
      (DS9 `catopt.tcl`).
- [x] **M8-5** (M) Local catalog load/save: starbase (rdb), CSV with and without header, VOTable,
      TSV — adopt `catalogs/catalog_table.py`.
- [x] **M8-6** (M) Catalog match between two loaded catalogs with a radius (DS9 `catmatch.tcl`).
- [x] **M8-7** (S) Catalog plot (feed columns to the M7 plot tool).
- [x] **M8-8** (S) Export catalog selection as regions (DS9 `catreg.tcl`).
- [x] **M8-9** (S) Clear All / per-catalog clear.
- [x] **M8-10** (M) Search for Catalogs — CDS catalog search by title, keyword, mission,
      wavelength, object type (DS9 `catcdssrch.tcl`).

### Catalog backends
- [x] **M8-11** (M) Adopt `catalogs/{simbad,ned,sdss,twomass,skybot,vizier,cone_search}.py`
      behind a common `CatalogBase` interface; add the CDS and CXC servers.
- [x] **M8-12** (S) Populate `Analysis → Catalogs` with DS9's server list.

### Image servers
- [x] **M8-13** (M) Real DSS backends: SAO, ESO, STScI (replace the
      `NotImplementedError` skeletons in `image_servers/dss.py`, `eso.py`).
- [x] **M8-14** (S) Real 2MASS (NASA/IPAC) backend.
- [x] **M8-15** (S) Real SkyView (NASA/HEASARC) backend with survey selection.
- [x] **M8-16** (M) VLA, NVSS, VLSS (NRAO) backends.
- [x] **M8-17** (S) Real SDSS image backend.
- [x] **M8-18** (M) Shared image-server dialog: object name or coordinates, size, survey, band,
      colour/format — matching DS9's `imgsvr.tcl`.

### Archives and VO
- [x] **M8-19** (M) Archives menu: Chandra Public Archive by ObsId and by Cone Search;
      SIMBAD SAO/CDS; ADS SAO/CDS.
- [x] **M8-20** (M) Footprint servers with a footprint overlay and Clear All (DS9 `fp.tcl`).
- [x] **M8-21** (M) VO registry browser: discover and query SIA, SSA, cone-search and TAP
      services; broaden `ui/dialogs/vo_query_dialog.py` beyond its current scope.

---

### Deviations from the plan as written

* **`catalogs/catalog_table.py` was not adopted for M8-5; it is a table *widget*, not a file
  reader.** The local formats are in a new `catalogs/catalog_file.py`, and the widget was deleted
  as a lesser version of the list window -- its Copy Cell, Copy Row and Pan to Position moved onto
  that window's context menu.
* **`catalogs/catalog_display.py` was not adopted for M8-2 either.** It rendered DS9 *region text*
  and shipped it to an external DS9 over XPA, which is driving somebody else's viewer rather than
  drawing in this one. Deleted; the overlay is `ui/widgets/catalog_overlay.py`.
* **`catalogs/twomass.py` was deleted**: it wrapped the same VizieR path the query layer already
  takes. `catalogs/sdss.py` stays, pending nothing -- its `get_images` is not used, since SDSS
  images come through SIAP, but its SQL and spectra queries have no equivalent.
* **`image_servers/dss.py` and `eso.py` never existed**, so M8-13 was not "replacing the
  NotImplementedError skeletons" in them. Only `sia_client.py` was there.
* **Filter and symbol expressions are Python, not Tcl.** DS9 evaluates them with Tcl's `expr`.
  Every example in its documentation works here, including `[string equal ...]` and `[regexp ...]`,
  which are translated; anything else calling a Tcl command will not.
* **SkyView is offered twenty of its surveys, not all hundred and sixty**, with the survey field
  editable so any other can be typed.
* **`$url` in an analysis file, and SDSS images, go through SIAP or curl rather than DS9's own
  download-to-temporary-file.** See the M7 deviations for the first.
* **The Archives menu's SIMBAD and ADS entries are web links to the services' current URLs.** DS9's
  own handlers for them do not exist in 8.x -- the entries are there and do nothing.
* **Chandra by ObsId opens the archive's own page** rather than reimplementing DS9's archive
  protocol; the information is the same.
* **A TAP service can be discovered but not queried.** Querying one needs a query language and a
  schema browser to write one against, which is a feature of its own and not in M8's scope.

### Bugs found and fixed on the way

* **`SkyCoord.search_around_sky` as a *method* returns the argument's indices first and `self`'s
  second**, which is the reverse of how it reads. A smoke test with two three-row catalogues could
  not tell the difference; a one-row against a three-row raised IndexError at once. Catalog match
  goes through the module-level function, where the order is unambiguous.
* **`&&` in a catalogue filter hit the same precedence trap M5 hit with bin filters.** Python binds
  `&` tighter than `>`, so `$a>1 && $a<2` became `a > (1 & a) < 2`. Each side is parenthesised.
* **`[string equal $Class SNR]` compared the column's *name* with the literal**, so every row came
  out false: the bare word needs quoting and the column reference does not.
* **A `QTableWidgetItem` compares its display text**, so a magnitude column sorted 10 before 9.
  Setting `EditRole` to a float does not help -- Qt aliases EditRole to DisplayRole inside the
  item, so the number replaces the formatted text and the comparison stays textual.
* **`J2000` in an STC-S polygon was read as a declination of two thousand**, on the strength of a
  comment of mine claiming the frame name holds no digits.
* **A `.rdb` file with no rule of dashes was quietly read as a one-column CSV**, its header line
  becoming the only column name. The extension now forces starbase, so the error says what is
  actually wrong with the file.
* **The mask layer's state was on the window**, which the 600-line guard objected to when the
  catalog controller was added. It belonged on the analysis controller.


---

## M9 — Remaining subsystems

Depends on M2, M3.

### Pointer modes
- [x] **M9-1** (L) Crosshair mode: draggable crosshair, coordinate readout, and the horizontal/
      vertical cut graphs driven by it; Crosshair Parameters dialog made functional; crosshair
      match and lock across frames. `ui/controllers/crosshair.py`,
      `ui/dialogs/crosshair_dialog.py`. Per frame, as DS9's is; drives the readout down the
      window's own pointer path so the info panel, status bar, WCS display, magnifier and both
      cut graphs stay on one code path; the lock matches through the sky, falling back to pixels
      only without a usable WCS. Retired the window's `_crosshair_*` state, which made the
      crosshair follow the pointer -- not what DS9's crosshair does -- and left two controllers
      connected to Crosshair Parameters.
- [x] **M9-2** (M) Interactive Crop mode (rubber-band crop on the canvas), plus crop match/lock.
      `frames/crop.py`, `ui/controllers/crop.py`. A crop chooses the data displayed, not where
      the view is looking: the old Crop Parameters zoomed and panned instead, which is what the
      Zoom mode's rubber band is for. Blanked pixels drop out of the scale limits by themselves
      (DS9's CROPSEC) and are painted in DS9's Blank/Inf/NaN colour, added as a preference here
      because a crop over dark data was otherwise invisible.
- [x] **M9-3** (M) Explicit Pan, Zoom and Rotate pointer modes. `ui/pointer_modes.py` decides
      what a drag means over a `PointerTarget` protocol; `ui/controllers/pointer.py` carries it
      out. The split is what makes every gesture testable without a display.
- [x] **M9-4** (M) Examine mode (click to centre-and-zoom) and its parameters. Opens the spot in
      a second frame at DS9's `pexamine(zoom)` of 4 (`examine.tcl:12`), leaving the first view
      alone -- which is the point of examining.
- [x] **M9-5** (S) Catalog and Footprint pointer modes (click a symbol to select its row). Needed
      the overlay stack rebuilt first: two overlays were accepting mouse events, and a Qt event
      a child ignores goes to its parent rather than to a sibling, so the topmost one ate every
      click. The region overlay is now the only layer taking the mouse and offers a press that
      hits no region to the catalogue layer.

### Illustrate layer
- [x] **M9-6** (L) `illustrate/` package: a non-WCS annotation layer with circle, ellipse, box,
      polygon, line, text and image elements. `illustrate/elements.py` holds the seven shapes,
      in *canvas* coordinates rather than image ones -- that is what makes the layer non-WCS,
      and it is why an illustration stays where it was put when the frame is panned.
- [x] **M9-7** (M) Illustrate menu: Shape, Colour, Width, All/None/Invert, Front/Back,
      Move to Front/Back, Open/Save/List, Delete All/Selection, Show.
      `ui/controllers/illustrate.py` and `ui/dialogs/illustrate_dialog.py`, over
      `illustrate/layer.py`, which holds the selection, the z-order and the clipboard.
- [x] **M9-8** (M) Illustrate file format read/write and its own selection handles.
      `illustrate/illustrate_file.py`, DS9's own `# Illustrate file format: DS9 version 1.0`.
      The handles are the overlay's, which took the `illustrate_handler` slot M9-1 gave it.
      *(These three were finished with the rest of M9 and their boxes were missed; ticked
      here after checking the package, the menu and the 81 tests are all in place.)*

### Prism
- [x] **M9-9** (L) Rewrite `prism/` as a real FITS browser: HDU list, header view, table view
      with sortable columns, image preview, plot a column, load an HDU into a frame.
      `prism/browser.py` reads and pages; `ui/dialogs/prism_dialog.py` is DS9's window --
      extension list, header, extension data, and DS9's File/Edit/Table menus over them.
      What the package held before was a spectral-analysis skeleton nothing called, which was
      a guess at the name rather than at DS9; deleted. Two deviations from the line above,
      both deliberate: **no sortable columns**, because Prism shows one 1000-row block of a
      table at a time and sorting a block would sort the wrong rows -- sorting belongs to the
      catalogue tool, which holds the whole table; and **no image preview**, because DS9 has
      none either, its `Image` button loading the extension into a frame instead, which is
      what ours does.
- [x] **M9-10** (S) `File → Prism` and the `prism` XPA point. `ui/controllers/prism.py`. Opens
      on the current frame's file when it has one, as DS9 does. The XPA point is DS9's whole
      syntax: open, load, import/export xml|rdb|tsv, clear, current, ext by number or name,
      first/next/prev/last, goto, image, mode, histogram with optional limits, and plot with
      DS9's xy|xyex|xyey|xyexey error-column shapes.

### Session and files
- [x] **M9-11** (L) Backup / Restore: adopt `io/session/` to serialise all frames, their data
      references, view state, regions, contours, grids, colormaps and colour tags.
      `io/session/backup.py` is the format and `ui/controllers/session.py` the capture and the
      restore. **Deviation, deliberate:** DS9's backup is a Tcl script that rebuilds the
      session by `eval`ing itself (`backup.tcl`), so a DS9 backup cannot be read by us and
      ours cannot be read by DS9. We cannot eval Tcl, and a data file that executes on being
      opened is not a design to reproduce -- a backup arrives by email as readily as any other
      file. Ours is JSON beside a `.dir` of the same name, which is where DS9 keeps a backup's
      auxiliary files too; a frame with a file behind it is stored as that file's
      specification, and only a frame whose pixels came from elsewhere has them written out.
      The three modules `io/session/` held before (a DS9-shaped text reader and writer and a
      session manager) were skeletons nothing called; deleted, and `test_bug_fixes.py`'s guard
      over one of them replaced by an equivalent over the new reader.
- [x] **M9-12** (S) Auto-recovery / autosave (DS9 `autosave.tcl`). `io/session/autosave.py`.
      DS9's policy exactly: on by default, every five minutes, written to `~/.ncrads9.auto`,
      deleted on a clean exit, and offered back on the next start -- which only happens after
      a crash, since a clean exit removes it. Both the switch and the interval are preferences.
- [x] **M9-13** (M) Import: Array, NRRD, ENVI, RGB/HSV/HLS Array, GIF, TIFF, JPEG, PNG — adopt
      `io/{array,nrrd,envi}_reader.py`. DS9's Import cascade, its Slice sub-cascade included.
      `array_reader.py` gained DS9's whole array specification -- both syntaxes,
      `[xdim=..,bitpix=..,skip=..,arch=..]` and `[array(r256:4l)]`, and the `$DS9_ARRAY`
      default -- because a raw array has no header and the dimensions have to come from
      somewhere; `ui/dialogs/array_dialog.py` asks when the filename does not say.
      `io/raster.py` reads a picture as data, flipping the rows: a picture counts them from
      the top and FITS from the bottom, and a photograph imported without the flip is
      displayed upside down and re-exported right way up, which is how that mistake hides.
      **Bug found:** `nrrd_reader.py` and `envi_reader.py` both ignored the byte order their
      own headers record, so a file written on a big-endian machine read as nonsense on a
      little-endian one with the array's shape still perfectly right. Both now honour it.
- [x] **M9-14** (M) Export: the same 10 formats — adopt `io/*_writer.py`; keep the existing
      screen-grab export as `Save Image`. `io/nrrd_writer.py` and `io/envi_writer.py` are new;
      the four raster formats go through `io/raster.py`. The two directions are not
      symmetrical, and DS9's menu is why: Import reads a picture *as data*, Export writes the
      frame *as a picture*, colormap and stretch already applied, because a GIF has no room
      for a stretch. Save Image's four raster entries now write too, leaving only EPS for
      M9-18. Our single `Export...` action and its dialog are gone -- DS9 has ten formats each
      way and one entry could not say which -- and the button bar's `export` button, which
      pointed at it, is now an import/export pair as DS9's own File bar has.
- [x] **M9-15** (M) Create Movie: adopt `io/mpeg_writer.py`; frame/slice/3D-rotation sequences
      (DS9 `movie.tcl`). `io/movie.py` and `ui/dialogs/movie_dialog.py`, with DS9's four
      groups of choices. Frames and slices are live; the 3D-rotation sequence says it needs
      M9-21, which is where the 3D frame arrives. The animated GIF goes through Pillow, which
      is already a dependency; the MPEG needs ffmpeg, which is not, so its absence is reported
      and the radio button disabled rather than the movie failing at the end. A fade is made
      as extra blended images, so both formats treat it as ordinary frames, and frames of
      different sizes are padded into the largest rather than the movie being refused.
- [x] **M9-16** (S) Notes window (`File → Notes`). `ui/controllers/notes.py`,
      `ui/dialogs/notes_dialog.py`, with DS9's File and Edit menus over an editable text pane.
      The text lives on the controller rather than in the window, so it survives the window
      being closed and goes into the backup -- which is the whole reason DS9 has notes of its
      own rather than leaving you to a text editor.
- [x] **M9-17** (S) Preserve During Load → Pan / Region. Both off by default, as DS9 has them.
      **Behaviour change:** with Preserve Region off -- the default -- loading new data into a
      frame now clears its regions, where before they stayed. DS9 clears them, and it is
      right to: they were drawn around things in the old data. Preserve Pan keeps the view
      instead of refitting, which is what makes stepping through a series of images of one
      field possible without losing your place. Both settings are in the backup.
      Also moved `Header` from the Analysis menu to File, where DS9 keeps it, and put the
      whole File menu into DS9's order.

### Printing
- [x] **M9-18** (L) Real Postscript driver: adopt `printing/postscript.py`; levels 1/2/3, colour
      models RGB/CMYK/Grayscale, resolution in pixels-per-inch, vector text and line graphics.
      Levels 1 (ASCIIHEX, no filters -- Level 1 has none), 2 (RunLength + ASCII85) and 3
      (Flate + ASCII85); RGB, CMYK with the black separated out, and Rec. 601 greyscale;
      resampled to the chosen DPI, so a 4096-pixel mosaic is not a hundred megabytes at a
      resolution nobody can print. Verified by rendering every level and model with
      ghostscript and checking the pixels, including that the print is the right way up --
      those tests skip where `gs` is not installed. **Two deviations:** the graphics are the
      rendered image rather than vector text and line elements (DS9 draws its regions and
      grid as PostScript objects; ours are already in the image the renderer produces, and
      splitting them out means giving every overlay a second PostScript path -- worth doing,
      not yet done); and a Level 1 print cannot ask for its paper, `setpagedevice` being
      Level 2, so it names the size in a comment and relies on the printer, as DS9's does.
- [x] **M9-19** (M) Page Setup dialog: adopt `printing/page_setup.py` — paper size, orientation,
      scale, margins. DS9's seven sizes, poster included, its own in inches or millimetres,
      and its percentage scale, which is allowed to run off the page because that is what a
      percentage is for.
- [x] **M9-20** (S) PDF output via `printing/print_engine.py`, adopting `io/pdf_writer.py`.
      DS9 has no PDF -- it prints PostScript -- and a modern desktop would rather have one;
      the page is laid out by the same geometry, so a PDF and a PostScript print of the same
      settings put the image in the same place. `io/eps_writer.py` is deleted: the real
      driver supersedes it, and `Save Image -> EPS` goes through that.

### 3D
- [x] **M9-21** (L) `frames/frame_3d.py` rewritten: MIP and AIP ray-trace projections over a data
      cube, threaded, with azimuth/elevation controls. The ray trace is DS9's: a ray back into
      the view volume per screen pixel, the largest value along it for MIP and the average for
      AIP, returning *data* so the scale, clip and colormap follow exactly as for a slice.
      The rotation is DS9's own composition (`RotateY3d(az) * RotateX3d(el)`). **Deviation:**
      not threaded. DS9 spreads the trace over POSIX threads because it walks rays one at a
      time; ours walks every ray's Nth sample at once in numpy, so the work is already one C
      loop per step and threads would only add copies -- which is why there is no thread count
      to set. Verified against the geometry rather than against itself: seen from azimuth 90 a
      cube is as wide as it is deep, a z scale of 4 makes it four times that, one bright voxel
      is found from every angle, and a ray that misses is blank rather than zero.
- [x] **M9-22** (M) 3D dialog (view angles, method, background, threads) and the 3D pointer mode.
      `ui/dialogs/frame_3d_dialog.py` with DS9's Render, Highlite, Border and Compass menus over
      its two sliders and the Z Axis Scale; the pointer mode turns the cube, sideways for
      azimuth and up-and-down for elevation. The border, the highlighted slice and the compass
      are projected and drawn over the render by the contour overlay. No thread count, for the
      reason above. Found a bug the 3D frame makes loud: the colormap cast NaN straight to an
      integer index, which warned and gave nonsense -- a 3D render is mostly NaN, every ray
      that misses the cube.
- [x] **M9-23** (S) 3D match/lock and the `3d` XPA point. Match and Lock copy the view to the
      other 3D frames and leave the plain ones alone; the XPA point is DS9's syntax --
      `3d`, `vp`, `az`, `el`, `scale`, `method`, `background`, the three decorations, `lock`,
      `match`, `reset`, `open` and `close`. The view is captured in the backup, per frame.

### Undo/redo
- [x] **M9-24** (L) Command-pattern undo stack covering region edits, view changes, colormap
      changes and frame operations; wire `action_undo`/`action_redo`/cut/copy/paste.
      `utils/undo.py` is the stack -- a named command, an undo and a redo, to a depth -- and
      `ui/controllers/undo.py` records commands as a *before* and an *after* snapshot taken
      around whatever changed, one `with` at the call site rather than an undo method grown
      on every operation. A snapshot of a frame's regions is a few hundred bytes; a parallel
      implementation of every edit is the thing that goes out of date the first time an edit
      gains a field. Cut, copy and paste were already live (M6-14).
      Covered: region create, delete, delete-all, reorder and drag; zoom, rotation and
      orientation; the colormap; and the illustrate layer's deletes. **Not covered, and
      recorded as such:** anything with data behind it -- loading a file, binning a table,
      deleting a frame. Those are megabytes rather than snapshots, and DS9 does not undo them
      either. **Beyond DS9:** DS9 has one Undo, no Redo, and only for the last region or
      illustrate edit; ours is a stack of a hundred with Redo, which our Edit menu already
      had an entry for.
      Two traps the tests pin down: an undo must not record itself, or the undo becomes
      undoable and nothing settles; and an undone zoom has to be pushed back to the *viewer*,
      which holds the zoom, or the next thing that persists the view writes the screen's value
      back over the frame's.

### Communication
- [x] **M9-25** (L) Grow XPA from 23 to DS9's 143 access points. Use
      `.tmp_sao_ds9/ds9/library/xpa.tcl` as the specification and
      `.tmp_sao_ds9/ds9/parsers/*` for each point's grammar.
      **All 143 of DS9's distinct names answer now, up from 24** (145 registrations: DS9
      registers `3d`/`3D` and `iexam`/`imexam` twice each, and the lookup lowers the name). `communication/xpa/access_points.py`
      is a *table* rather than a method per point: DS9's points are almost all the same shape
      -- read something the application knows, or hand an argument to something it does -- and
      145 near-identical methods would be a fifth of the codebase. The ones with real grammars
      (`file`, `frame`, `regions`, `prism`, `3d`, `colorbar`, `scale`, `cmap`, `zoom`, `pan`,
      `wcs`, `save`) keep their hand-written handlers.
      Done: groups (a) display -- `zscale minmax invert block smooth grid contour orient align
      rotate crop magnifier panner mask`; (b) frames -- `single tile blink fade first last next
      prev slice cube datacube lock match`; (c) files -- `array nrrd envi gif tiff tif jpeg jpg
      png export url rgb*/hsv*/hls* mosaic* mecube multiframe backup restore saveimage movie
      savempeg`; (d) tools -- `notes pixeltable illustrate nameserver catalog cat footprint fp
      vo prefs`; (e) app -- `width height iconify raise lower nan preserve mode cursor
      crosshair cd pagesetup psprint print sleep update header about version`.
      Finished last: the image servers -- `dsssao dsseso dssstsci dss 2mass skyview vla nvss
      vlss` share one grammar, so one helper builds all nine points from
      `ds9/parsers/dssesoparser.tac`, which is also where the division between the rules that
      fetch (a bare call, a name, a position, `update`) and the rules that only set (`size`,
      `save`, `frame`, `survey`, `name clear`) comes from; then `analysis view graph data plot
      region rgb hsv hls bin precision theme threads console tcl source bg background web xpa
      savefits sfits memf sia pspagesetup`.
      Two of DS9's reads take arguments -- `xpaget ds9 dsssao size`, `xpaget ds9 data image 3 3
      2 2` -- which the table could not express: a point gained a `query`, and `iexam`, which
      had been named in the dispatcher as the one exception, now goes through it like the rest.
      **Three features had to be built before their access point could be honest**, rather than
      reporting success and changing nothing:
      * the cut graphs had no grid, no log axis, and read a single row -- DS9's `graph grid|log|
        method|thickness|size`. `analysis/cut_graph.py` is the arithmetic (a thick cut averaged
        or summed across its width, and the 0..1 mapping a log axis needs), apart from Qt so it
        is testable; both panels draw from it.
      * SkyView's output size in pixels was hard-coded at 512, so `skyview pixels 600 600` had
        nowhere to go. It is now a query argument, a dialog field, and DS9's own rule.
      * colour frames had no way to pick or hide a channel outside the RGB dialog:
        `FrameController.set_channel` and `set_channel_visible`, which `rgb`, `hsv`, `hls` and
        `view rgb red no` all reach.
      **A dozen more dead points found, in four shapes**, all of which raised or hung: `rgbcube hsvcube
      hlscube rgbimage hsvimage hlsimage srgbcube mosaic mecube multiframe` passed a filename
      to `open_as`, which took none and opened a file dialog instead -- so every one of them
      hung a script; `url` did the same through `open_url`; `sfits`/`memf` named a controller
      method that does not exist; and the plot window's List Data and Statistics called `exec()`
      under a docstring that said modeless, which blocked `plot stats yes` on a window the
      caller could not see. `open_as` and `open_url` now take the path they are given and
      return what went wrong instead of swallowing it.
      **Five bugs found in the 24 that existed**, all in points that reported success while
      doing nothing: `mode` echoed the mode back and never changed it; `cursor` and `crosshair`
      reported the last mouse position and could not move anything; `lock` echoed its argument;
      and `match` matched *frames* whatever scope word it was given, so `match crosshair`
      moved the views. All five are now real, and their tests say what they used to do.
      **Three more found while wiring the table**, each the same shape -- a setter that assumed
      the menu had already ticked itself, so any other caller changed the status bar and
      nothing else: `set_smooth`, `set_contours` and `set_panel`.
      Also fixed here: the pixel table was modal and rebuilt on every open, so it blocked the
      application and always showed the middle of the image. DS9's follows the cursor, and the
      dialog was already built for it -- non-modal, with a `set_center` nothing called.
- [x] **M9-26** (S) XPA UI: `File → XPA → Information / Connect / Disconnect`.
      `ui/controllers/xpa.py`. Information is the only reason anyone opens the submenu: it
      says the name to address, the address, whether it is connected, and how many access
      points there are, with the whole list behind the details button.
- [x] **M9-27** (M) SAMP: broadcast image and broadcast table; the SAMP Hub UI
      (Information / Start / Stop) over the existing `samp_hub.py`.
      `ui/controllers/samp.py`, and DS9's two File submenus. The registered clients appear
      under Image and Table, so an image can go to Topcat and not to Aladin; Broadcast sends
      to everything. SAMP passes a *URL*, so a frame with no file behind it -- an array over
      XPA, a mosaic in memory -- has nothing to send and says so rather than sending a broken
      URL; the same for a catalogue queried from a server and never saved. The VO menu's own
      SAMP entries stay where they are: those are the marker settings for an *incoming* table.
      The `samp` XPA point covers connect, disconnect, image, table and hub.
- [x] **M9-28** (M) SAMP web hub. `samp_hub.py` already took `web_profile`; the hub is started
      with it on, since a browser-based tool can only join over the web profile, and it can be
      turned off from the controller or over XPA (`samp hub web no`). Information says which.
      The hub is stopped on a clean exit, so it does not outlive the application holding its
      port.
- [x] **M9-29** (M) IIS / IRAF `imexam`: adopt `communication/iis/iis_server.py`; the `iis` and
      `iexam` XPA points. `ui/controllers/iis.py` owns the server and the examine.
      **The protocol layer was rewritten, because what was there could not have worked**: an
      8-byte header read as `>HBBHHHH` where the protocol's is eight big-endian shorts, the
      command taken from `tid` instead of `subunit`, no checksum, and a memory write that never
      stored a pixel. It is now DS9's `struct iism70` (`tksao/iis/iis.c:83`) throughout --
      MEMORY, LUT, FEEDBACK, IMCURSOR and WCS, the PACKED and IIS_READ flags, the one-bit-per-
      frame `z`, the checksum that also says which byte order the client is, and the fixed
      160-byte cursor reply IRAF reads. Tested against a client that speaks the protocol over a
      real socket, which is the only way to know short of installing IRAF.
      Interactive examine is DS9's `iexam`: it blocks on its own event loop -- so the window
      still redraws and the click can actually be made -- and answers with a coordinate in any
      system, a box of data values, or an expanded macro string.
      **Deviation:** DS9's `iexam` can wait for a key as well as a button, and IRAF's blocking
      cursor read likewise. Ours is always a button: a key event needs the keyboard grab DS9's
      cursor mode takes, and an unattended reply of the current position is more useful to
      `imexam` than a socket that never answers. The event word is accepted and ignored.
- [x] **M9-30** (S) Shared-memory loading (`shm`). `io/shared_memory.py`, and the `shm` access
      point: a FITS file or a raw array read straight out of a segment, so a pipeline can hand
      us an image without touching a disk. **Deviation:** DS9 takes a *System V* segment by key
      or shmid, and Python's standard library has no System V shared memory at all. Ours reads
      a POSIX segment by name always -- which is what a program written this decade would
      offer -- and a System V one only when the optional `sysv_ipc` package is installed,
      saying so plainly when it is not. Refusing to read anything without a C extension would
      be worse than reading the kind we can.

### Polish
- [~] **M9-31** (M) i18n: extract all UI strings, add Qt translation files for DS9's 8 locales
      (cs, da, de, es, fr, ja, pt, zh) seeded from `.tmp_sao_ds9/ds9/msgs/*.msg`, and a Language
      preference. **The menus are translated into all eight**, from DS9's own catalogues:
      `tools/import_ds9_messages.py` converts `ds9/msgs/*.msg` into `ncrads9/i18n/locales/*.json`
      (2893 translations, SAOImageDS9's work under the same GPL, provenance recorded in each
      file), and `ncrads9/i18n/` looks a label up -- taking the `&` accelerator and the `...`
      off, putting them back, and putting the accelerator on the same letter where the
      translation still has it. The Language preference chooses it at startup.
      **Not JSON versus Qt `.ts` by accident:** `.ts`/`.qm` needs `lrelease` at build time and
      `tr()` at every call site; the menus are built from literals in one readable file, and
      wrapping two thousand of them would put the English a translator needs behind a function
      call. They are translated once, afterwards, and each action keeps its English text so the
      XPA points and the parity tools still find entries by name in Japanese.
      **The dialogs translate the same way, all-or-nothing** (`i18n/dialogs.py`). One event
      filter on the application translates each dialog the first time it is shown -- dialogs
      are built all over the code and some only when first used, so a hook that fires when one
      appears catches every one, including any added later, and no dialog constructor changes.
      A dialog is translated only when the catalogue covers `THRESHOLD` (0.8) of its labels and
      is left wholly English otherwise: DS9's catalogue is a catalogue of *menu* labels, and a
      French Apply beside an English "Auto-calculate limits" is harder to read than honest
      English. The ones left behind are collected by title, which is the list of what a
      translator should do next.
      Deliberately not `QTranslator`: Qt's mechanism installs between a widget and `tr()`,
      which is the call site being avoided, and a per-string mechanism cannot see how much of a
      dialog it failed to translate -- which is what the threshold needs. Also added here: the
      catalogue takes a trailing colon off before looking a label up, since `Width:` is how
      every form row is written and DS9's catalogue holds `Width`.
      **What is left is only the writing.** Measured: DS9's French catalogue covers 42 of 218
      dialog labels, 19%, and no dialog reaches the threshold -- so today the mechanism runs
      and changes nothing, which is the honest result. `test_ds9s_catalogue_does_not_yet_cover_a_dialog`
      records that and fails, usefully, once translations are written and a dialog passes.
      Status messages stay English: there are thousands, DS9 has none of them, and they are
      sentences rather than labels.
      Coverage is also DS9's coverage, which is partial: `Zoom`, `Scale` and `Contours` sit in
      DS9's French file with nothing beside them and so stay in English.
- [x] **M9-32** (M) Grow Preferences to DS9's topic coverage: General, Precision, Startup,
      Coordinates, Region, Annulus, Panda, Scale, Colour, Contour, Grid, Bin, Smooth, Zoom,
      Graph, Panner, Magnifier, PixelTable, Examine, Catalog, VO, NRES, Analysis, HTTP, Print,
      Page Setup, Menu/Buttonbar customisation.
      104 preferences over DS9's 29 topics, in DS9's order, as a *table* --
      `utils/preference_defs.py` -- with the dialog generated from it: topics down the left and
      the chosen one's controls on the right, as DS9 lays it out. Twenty-nine hand-built pages
      is how a preferences dialog comes to disagree with the preferences it edits; a table and
      a renderer cannot. The Edit controller's defaults are now that table's, so nothing is
      listed twice. **Deviation:** the pages hold what DS9's hold, but not yet every one of its
      controls -- DS9's Region page alone has a dozen more -- and a preference in the table is
      not automatically *acted on*: the ones the application already reads (theme, colours,
      GPU, autosave, shortcuts) work, and the rest are stored and offered. Which is which is
      not marked in the table yet; that is worth doing.
- [x] **M9-33** (M) Configurable keyboard and mouse bindings + a Keyboard Shortcuts editor.
      `ui/bindings.py` is the table -- 24 commands worth a shortcut, each a preference -- and
      the Bindings page of Preferences is the editor. Applied at startup from the preferences,
      not only when the dialog is used. A shortcut can be cleared, which is a legitimate thing
      to want, and a combination two commands both ask for is pointed out rather than left to
      Qt to resolve silently. **Deviation:** keyboard only. DS9's mouse behaviour is its
      pointer modes, which the Edit menu already chooses; a separate mouse-binding editor would
      be a second way to say the same thing.
- [x] **M9-34** (S) Python console replacing DS9's TCL console; `Run Python Script` replacing
      `Source TCL`. `ui/dialogs/console_dialog.py`. DS9's console is a TCL interpreter because
      DS9 is written in TCL; ours is a Python one, with `window` and every controller in scope,
      because that is what this application is made of. History on the arrow keys, statements
      over several lines, `exit()` closing nothing.
      **Bug avoided by testing it:** `code.InteractiveInterpreter.runsource` reports an error
      by calling `sys.excepthook` when something has replaced it, which in a GUI means the
      traceback goes to the application's handler rather than to the console window -- the one
      place it is any use. The console compiles and runs the source itself and formats its own
      errors. Running a script opens the console to show what it printed, since a script that
      failed silently is worse than no script.
- [x] **M9-35** (S) Display Size (`Frame → Frame Parameters → Display Size`). The window is
      grown by however much the *display* is short of the size asked for, since that is what
      DS9 sizes -- the display, not the window around it.
- [x] **M9-36** (S) Tile Parameters: grid rows/columns, automatic/manual, direction, gap.
      `TileSettings` in `frames/tile_layout.py`, and DS9's dialog. A manual grid too small for
      the frames is grown along whichever axis the direction fills last, rather than dropping a
      frame: the dialog asks for a shape, not for some of the frames. The hit test follows the
      direction too, or clicking a tiled frame would select its neighbour.

---

## Continuous

- [x] **C-1** Keep `docs/parity/ncrads9_menus.txt` regenerated in CI (the `parity` job already
      fails when it is stale) and review the `tools/menu_diff.py --summary` output each milestone.
      **Now a ratchet rather than a report.** `menu_diff.py --minimum PERCENT` exits non-zero
      below a floor, and `check.sh` and the CI parity job both pass `--minimum 92`, today's
      figure. Reporting alone meant a menu entry lost in a refactor went unnoticed until
      somebody read the summary; a floor fails the build that loses it. Raise the floor when a
      milestone improves parity, never lower it to make a build pass -- and a test checks that
      `check.sh` and CI name the same number, so the two cannot drift apart.
- [ ] **C-2** Keep `tests/unit/test_no_orphan_modules.py` (M1-20) green — no new orphans.
- [ ] **C-3** Keep the `MenuBar` action-connection test (M2-15) green — no dead menu entries.
      **The same gate now covers the button bar** (`tests/unit/test_button_bar.py`), which had
      no test file at all and **sixty of its hundred and seventeen buttons did nothing**. A
      checkable action's button was wired to `QAction.setChecked`, which emits `toggled` but
      *not* `triggered`, and every controller connects to `triggered` -- so a colormap button
      ticked itself and left the colormap alone. That is the worst shape a broken button can
      have: it looks like it worked, which is why it went unnoticed through nine milestones.
      Every checkable button now calls `QAction.trigger()`, exactly as clicking the menu entry
      does, and takes its own tick from the action afterwards so an exclusive button clicked
      twice is not left unticked beside a checked menu entry. Buttons also follow their
      action's *enabled* state now: Undo used to stay clickable beside a greyed Edit menu
      entry, so it looked broken rather than unavailable.
      `test_every_button_reaches_its_action` is the ratchet, and it was checked by reverting
      the fix: it fails on the old wiring and passes on the new. M2-15's test only asks whether
      an action *has a listener*, which every one of these did; the button never reached it.
      Found while fixing this: `ColormapDialog` raised `AttributeError` on construction --
      `setCurrentRow(0)` fired the selection signal, which previewed, which read a check box
      built forty lines later -- so `Color -> Colormap Parameters` could never be opened. Its
      preview also drew the same grey ramp for every colormap, under a comment saying the real
      one "would use matplotlib"; `colormaps/` has done that since M5, and it now shows the
      colormap that is selected.
- [x] **C-4** Update `README.md`'s Feature Status section at the end of every milestone.
      Rewritten after M9. It had gone badly stale -- it still said `Save` and `Save As` were
      "not yet writing FITS data" and that the image servers were "scaffolding", both untrue
      for several milestones -- which is worse than no status section, since a reader trusts
      it. Now it lists what nine milestones actually delivered, names the measured figures
      (92% menu parity, 143 XPA points, ~3250 tests, 77% coverage) rather than adjectives, and
      has a *Partial* section for the translations and the URL progress indicator and a
      *Deliberately different from DS9* section pointing at PLAN.md section 7. Every claim in
      it was checked against the code: the draft credited a searchable preferences window,
      which does not exist, and named catalogues we do not query.
- [x] **C-5** Raise the coverage floor at the end of every milestone.
      Raised from 40 to 76 after M9 (measured 78.8%, kept a couple of points of slack so it
      does not flap between environments -- the GPU paths and a few platform branches are
      covered on some machines and not others). It had sat at the M0 baseline of 40 through
      nine milestones, which meant coverage could have halved without the gate noticing: not a
      floor at all.
- [x] **C-6** Add an XPA conformance test per access point as it lands, comparing against real DS9
      where available.
      **Better than a test per point: DS9's own examples, all 1496 of them.**
      `ds9/doc/ref/xpa.html` documents every access point with a list of real command lines --
      `$xpaget ds9 dsssao size`, `$xpaset -p ds9 bin factor 4`. That is a specification written
      by the people who wrote the thing, and a better corpus than anything hand-written here.
      `tools/import_ds9_xpa_examples.py` extracts them into `docs/parity/ds9_xpa_examples.json`
      (committed, so the tests do not need the DS9 checkout; `--check` fails when stale, and a
      parity test runs that when the checkout is present). Examples are validated against
      `xpa.tcl`'s own `xpacmdadd` list, which caught five typos in DS9's reference --
      `$xpaset -p ds9 connect` where the point is `xpa connect`.
      `tests/unit/test_xpa_conformance.py` runs all 1407 that can run in a test process
      (printers, browsers, `exit` and the blocking examine excluded, sockets refused) and
      asserts three things: **nothing raises** -- a caller gets a reply, never a traceback;
      **every documented point is known**; and **the number accepted does not fall**, a floor
      like the parity one. Refusals are written to a report, since a refusal can be correct and
      the list is what says where to work next.
      **633 to 940 accepted while writing it**, from the bugs it found:
      * *A read performed writes.* A read with arguments fell through to the setter -- in both
        halves of the dispatcher -- so `xpaget ds9 contour clear` cleared the contours and
        `xpaget ds9 frame delete` deleted the frame. A question that answers by changing the
        answer is the worst kind of bug, and 65 of DS9's points take arguments on a read. Now a
        read never writes: a point's `query` answers precisely, and a hand-written handler
        without a dedicated reader answers its plain current value with the arguments dropped.
      * *`xpaset -p ds9 file foo.fits` did not work* -- the commonest XPA command there is. The
        first word was read as the verb, so the path became the verb and the whole thing was
        refused. `file save` was refused too, saying "not implemented", though `save_fits_to`
        had existed since M9-25.
      * *`scale sideways` was accepted* and quietly left the scale linear; `scale mode`,
        `scale limits`, `scale scope` and `scale datasec` answered `ok` and did nothing at all.
      * *`saveimage jpeg out.jpeg 75`* read `jpeg` as the filename, so DS9's own second form
        never worked.
      * *`catalog` and `footprint`* opened methods that do not exist, and had no grammar; both
        now have one, over the catalogue tool.
      * *`contour` and `frame`* answered a fraction of theirs -- `contour` was a yes/no flag
        with a whole controller behind it, and `frame` knew none of DS9's reads (`frame all`,
        `frame active`, `frame has fits cube`) nor `hide`, `show`, `move` or `center`.
      What is still refused is mostly a feature we do not have -- DS9's own search windows, its
      per-column catalogue editing -- rather than a bug, and the report names each one.
- [x] **C-7** Populate `tests/integration/` — currently empty — with end-to-end flows
      (open → scale → region → save → reload).
      Two files, seventeen flows. `test_viewing_flows.py` drives the controllers as a person
      does: the named open → scale → region → save → reload loop; a session backed up,
      everything changed, and restored; a cube stepped through; smoothing that the analysis
      tools must see, not just the renderer; a blank pixel followed from the file through the
      scale to the colormap; and a frame written to FITS and read back identical, WCS and all.
      `test_xpa_flows.py` drives the *same* application through XPA, because a script takes a
      different path through the same code and the bugs live in the difference -- a setter the
      menu calls with a bool and XPA calls with the string "yes". Each flow is a plausible
      script, so a break there is somebody's pipeline breaking.
      One of them, `test_reading_never_changes_anything`, is the regression test for the worst
      bug C-6 found: it sets up a window, runs every dangerous-looking `xpaget`, and asserts
      that nothing moved. It failed when written, which is what it is for.
      Fixtures in `tests/integration/conftest.py`: a real window with its own preferences file,
      every modal dialog answered, and sockets refused.
