# NCRADS9 — Implementation Plan

**Goal:** make NCRADS9 a functional clone of SAOImageDS9 (v8.x), written in modern Python/Qt6,
whose GUI is recognizable to a DS9 user, with selected modern UX improvements.

**Status of this document:** derived from a file-by-file comparison of this repository against the
SAOImageDS9 source tree checked out at `.tmp_sao_ds9` (commit `43b71065a`). Every gap listed below
was verified against actual source, not inferred from documentation.

---

## 1. Baseline measurements

| Metric | SAOImageDS9 | NCRADS9 |
|---|---|---|
| Application logic | 98,088 lines Tcl (`ds9/library/*.tcl`, 232 files) | 40,000 lines Python (180 files) |
| Rendering/marker engine | 144,879 lines C++ (`tksao/`) | Qt/NumPy/OpenGL in `rendering/`, `ui/widgets/` |
| Menu entries (excl. separators) | 526 | 286, all wired |
| XPA access points | 143 | 23 |
| Colormaps | 23 built-in + 168 bundled `.sao`/`.lut` files | 23 built-in, 0 bundled files |
| Region/marker shapes | 19 shapes + 7 point glyphs<sup>†</sup> | 16 classes, 8 parseable, **6 interactively creatable** |
| Region file formats | ds9, ciao, saotng, funtools, xy, pros, XML | ds9, ciao, saotng, funtools, xy (parse only) |
| UI locales | 8 (`cs da de es fr ja pt zh`) | 0 |
| Tests | — | 533 tests, all passing, 48.3% coverage (69 with 1 failure before M0) |

DS9's top-level menus: `File Edit View Frame Bin Zoom Scale Color Region Illustrate WCS Analysis Help`.
NCRADS9's: `File Edit View Frame Bin Zoom Scale Color Region VO WCS Analysis Help`.
NCRADS9 substitutes a non-DS9 `VO` menu for DS9's `Illustrate` menu; DS9 reaches VO functionality
from `Analysis`.

Menu counts are measured, not estimated. Regenerate them with:

```bash
python tools/ds9_menu_tree.py                                        # DS9 side
python tools/dump_menus.py --output docs/parity/ncrads9_menus.txt    # our side
python tools/menu_diff.py --summary                                  # per-menu parity
```

At the end of M0 that reports **166 of DS9's 433 comparable menu labels present (38%)** — by menu:
`zoom` 100%, `frame` 96%, `analysis` 66%, `color` 60%, `edit` 28%, `scale` 19%, `region` 13%,
`file` 10%, and `bin`/`view`/`illustrate`/`help` at 0%. Shared labels do not imply equivalent
behaviour; §5 is the feature-level inventory.

---

<sup>†</sup> This table first said 20 shapes. DS9's Region Descriptions table
(`ds9/doc/ref/region.html`) lists **19**: Circle, Ellipse, Box, Polygon,
Point, Line, Vector, Segment, Text, Ruler, Compass, Projection, Annulus,
Ellipse Annulus, Box Annulus, Panda, Epanda, Bpanda and Composite. Corrected
in M6, where a test counts them out of the reference itself so the figure
cannot drift again.

## 2. What already works well

These are genuinely implemented and should be preserved through the refactor:

- **Large-image display path** — memory-mapped FITS, OpenGL tile renderer
  (`rendering/tile_renderer.py`, `rendering/gl_canvas.py`), viewport-only texture uploads,
  strided preview downsampling. This is the strongest part of the codebase.
- **Scale algorithms** — linear, log, power, sqrt, squared, asinh, sinh, histogram equalization,
  zscale (`rendering/scale_algorithms.py`).
- **Colormap core** — `Colormap`, `.sao`/`.lut` parsers, invert, user colormap load/save.
- **Frame model in use** — `frames/simple_frame_manager.py` with single/tile/blink/fade,
  goto/move/show-hide, per-frame view state persistence, RGB channel composition.
- **Contours** — real implementation with level generation, smoothing, export.
- **XPA server** — real socket server with `xpans` registration, so `xpaget`/`xpaset` work.
- **SAMP client** — connect/disconnect, `table.load.votable` / `image.load.fits` handlers,
  catalog overlay with configurable marker colour/shape/size.
- **DS9-style CLI** — ordered option/file stream parsing (`app.py:parse_cli_sequence`) with
  `-zscale -minmax -scale -cmap -invert -wcs -bin -rgb -red/-green/-blue -tile -blink …`.
- **Frame Match/Lock menu surface** — the full DS9 matrix of scopes is present in the menu.

---

## 3. Structural problems to fix first

These are not feature gaps; they are architectural defects that will make every feature below
harder to add. **Fix these before adding features.**

### 3.1 Two-thirds of the package is unreachable code

> **M1 reduced this from 116 orphans to 71, M3 to 60, and M4 to 56**, and
> `tests/unit/test_no_orphan_modules.py` now fails on any new one that is not
> listed against the milestone that adopts it. The remaining 56 are inventoried in
> `docs/parity/skeletons.md`. The table below records the original finding.
>
> M3 adopted `ui/panels/info_panel.py`, `coordinates/physical_coords.py` and the
> three `ui/themes/` modules, and **deleted six** that were duplicates rather
> than gaps: `ui/panels/colorbar_panel.py` (a second colorbar, without the
> orientation, numerics, font, size or tick controls the one in use has) and the
> five per-system coordinate value objects
> `coordinates/{wcs_coords,fk4_fk5,galactic,ecliptic,image_coords}.py`, each a
> thin wrapper over `SkyCoord` whose job M1's `CoordinateContext` took over.
> Nothing imported any of the six, and M3's information panel — the milestone
> that was meant to adopt the coordinate five — was finished without them.
>
> M4 adopted `core/cube_handler.py`, `ui/panels/cube_panel.py`,
> `io/fits_writer.py` and `ui/dialogs/open_dialog.py` (the last rewritten as an
> HDU chooser, its old contents being a second file-open dialog), and marked
> two more for deletion: `io/fits_reader.py`, a strict subset of
> `core/fits_handler.py`, and `ui/dialogs/save_dialog.py`, whose format combo
> DS9's per-format `Save as` entries replace.

An import-reachability analysis from `ncrads9.app` / `ncrads9.__main__` /
`ncrads9.ui.main_window` found **116 of 191 modules were never imported by the running
application**. Verified examples:

| Orphaned | The app instead… |
|---|---|
| `coordinates/` (all 8 modules: `coord_system`, `wcs_coords`, `fk4_fk5`, `galactic`, `ecliptic`, `sexagesimal`, `image_coords`, `physical_coords`) | calls `astropy.coordinates` inline in `main_window.py` — `coord_system` and `physical_coords` adopted in M1/M3, five of the rest deleted in M3 |
| `io/` (all 15 readers/writers + `io/session/`) | uses `QPixmap.save()` and `QPrinter` inline |
| `printing/` (`page_setup`, `postscript`, `print_engine`) | uses `QPrinter` inline in `_print_image()` |
| `analysis/statistics`, `analysis/histogram`, `analysis/pixel_table`, `analysis/centroid` | recomputes with NumPy inline in `main_window.py` |
| `grid/` (`grid_renderer`, `grid_labels`, `ast_wrapper`, `grid_config`) | draws a pixel grid in `contour_overlay.py` |
| `frames/frame.py`, `frames/frame_manager.py`, `frames/tile_layout.py`, `frames/blink_controller.py`, `frames/rgb_frame.py`, `frames/hsv_frame.py`, `frames/hls_frame.py`, `frames/frame_3d.py` | uses `frames/simple_frame_manager.py` + an ad-hoc `self._tile_layout` dict |
| `regions/region_manager.py`, `regions/region_renderer.py`, `regions/group_manager.py` | uses a third `Region` class inside `ui/widgets/region_overlay.py` |
| `ui/panels/info_panel.py`, `cube_panel.py`, `colorbar_panel.py` | never docked; coordinates go to the status bar — `info_panel` rewritten and shown in M3, `colorbar_panel` deleted there, `cube_panel` is M4 |
| `ui/themes/{default,dark,native}.py` | never applied |
| `core/image_data.py`, `core/cube_handler.py`, `core/header_parser.py`, `core/data_cache.py` | uses `astropy.io.fits` directly |
| `prism/`, `image_servers/{dss,eso,skyview,sdss_image,twomass_image}`, `communication/iis/`, `rendering/colormap_engine.py`, `rendering/rgb_compositor.py` | not used at all |

Many of these orphans are **skeletons whose methods `raise NotImplementedError` or contain only
`# TODO`** — e.g. `image_servers/dss.py:71`, `grid/grid_renderer.py:87`,
`grid/ast_wrapper.py:77`, `prism/prism_main.py:89`, `printing/print_engine.py:122`.
They give a false impression of coverage.

**Decision required per orphan: adopt, or delete.** The plan below adopts the ones that map onto
DS9 features and deletes the pure duplicates.

### 3.2 `main_window.py` was a god object — fixed in M2

4,719 lines and 238 methods when surveyed. M1 trimmed it to ~4,600; **M2 brought it to 546 lines
and 28 methods**, split across twelve per-menu controllers plus a display pipeline
(`ui/controllers/`, `ui/display.py`). `tests/unit/test_controllers.py` ratchets the size and
asserts that no moved method was left behind as a shim.

Controllers still reach shared state through `self.window`, which is an intermediate step;
`ui/controllers/base.py` documents why, and what the end state is.

It holds file I/O, rendering, colormaps, scaling, blocking, smoothing, contours, grid, mask,
crosshair, WCS formatting, frames, tiling, RGB composition, regions, SAMP, VO queries, printing,
preferences and analysis-command execution. Nothing else can be unit-tested in isolation, and this
is where nearly all real logic lives.

### 3.3 Three incompatible `Region` types — fixed in M1

Originally three: `regions/base_region.py:BaseRegion`, `frames/frame.py:Region`, and
`ui/widgets/region_overlay.py:Region` (the one actually drawn), with
`main_window.py:_overlay_regions_to_base()` / `_base_region_to_overlay()` translating between two
of them and dropping colour, width, text, tags and every DS9 property in the process.

`BaseRegion` is now the only region type. It carries DS9's full property set, the overlay creates
and edits it directly, and `RegionRenderer` paints it. Round-tripping is covered by
`tests/unit/test_region_roundtrip.py`.

### 3.4 `Bin` and `Block` are the same code, and both are wrong — fixed in M5

> **M5 separated them.** Block is now a display transform: `rendering/block.py`
> reduces a copy on its way to the screen and `frame.image_data` stays at full
> resolution, so coordinates, regions and `Save` are unaffected — with tests
> asserting each of those directly, since getting it wrong is silent. Factors
> run to 256, and `Frame → Match/Lock → Bin` no longer means Block.
>
> Bin is now DS9's Bin: `core/bin_table.py` turns a FITS table into an image
> with the function, factor, buffer size, third column and row filter its
> menu offers, centred by DS9's four-card search, and `ui/controllers/bin.py`
> owns the menu — a controller of its own, since a change to any setting means
> re-binning the table rather than touching the frame's pixels. The finding
> below is what was there.

`menu_bar.py` exposes a `Bin` menu (factors 1/2/4/8) and an `Analysis → Block` submenu
(1/2/4/8/16/32). Both call `MainWindow._set_bin()` → `_rebin_image()`, a NumPy block-mean.
In DS9 these are different features:

- **Block** = display-time pixel replication/averaging of an *image*. NCRADS9's implementation is
  roughly this, but it destructively overwrites `frame.image_data` instead of being a display
  transform.
- **Bin** = constructing an image from a **FITS bin table** (event list) by binning two columns,
  with a bin function (average/sum), a bin buffer size (128²–8192²), a third binning column
  (`depth`), a row filter expression, and centering derived from `TDMIN/TDMAX`, `TLMIN/TLMAX`,
  `TALEN`, `AXLEN`. **NCRADS9 cannot open a FITS bin table at all.**

### 3.5 "Coordinate Grid" is a pixel grid, not a WCS grid

`ui/widgets/contour_overlay.py:140` draws evenly spaced dotted lines in *image pixel* space with
pixel-index labels. DS9's grid is a WCS graticule (curved lines, tick marks, sexagesimal/custom
numeric formats, axes, border, title, per-element colour/font), produced by the AST library.

### 3.6 FITS loading is single-HDU only — fixed in M4

> **M4 replaced the loader.** `core/fits_handler.py` now carries DS9's HDU
> model — the algorithm from `ds9/doc/ref/file.html`, an `HDUInfo` per HDU and
> the events/compressed/HEALPIX classification — and `core/file_spec.py`
> parses DS9's whole bracket grammar, so an extension, an image or cube
> subsection, a bin-table's columns and a row filter can all be named in the
> path. Cubes, multiple-extension cubes and frames, the three mosaic
> conventions, colour channels and URLs each have a loader. Save writes.
> File-menu parity 6/59 → 29/59 labels. The finding below is what was there.

`main_window.py:_load_fits_file()` always uses `fits_handler.get_data()` → HDU 0. There is no
extension chooser, no cube handling, no bin-table handling, no mosaic handling, no compressed-image
(tile-compressed) handling, no `file.fits[ext]` / `[filter]` syntax, no URL loading.

### 3.7 Layout does not resemble DS9 — fixed in M3

> **M3 replaced every `QDockWidget` with `ui/layout/shell.py`.** The window now
> holds one grid, re-gridded by `WindowShell.relayout()` from a `ViewState` that
> mirrors DS9's `view(...)` array, in all four of DS9's arrangements. The
> information panel is shown for the first time, with DS9's field table; the
> buttonbar is DS9's two rows; and the View menu went from 3 shared entries with
> DS9 to 26 of 27 (see §9 on why the twenty-seventh is a tooling artefact).
> The information panel follows DS9 in both of its grids: one line per field
> across seven columns when the panel sits above the canvas, and the same field
> broken over several lines in two columns when it sits beside it. `docs/parity/screenshots/` records before and after.
> The finding below is what was there.

DS9's window is a fixed vertical stack: **menu bar → info panel | panner | magnifier (one row)
→ buttonbar (two rows: category, then that category's buttons) → image canvas → colorbar**,
with optional horizontal/vertical cut graphs and a horizontal/vertical layout switch.

NCRADS9 uses free-floating `QDockWidget`s: button bar (left, as vertical `QGroupBox` stacks),
colorbar + panner + magnifier (right), graphs (bottom). The info panel — the element a DS9 user
looks at most — is never shown; coordinates go to the status bar with fewer fields.
`View` menu offers only Fullscreen / Toolbar / Statusbar, versus DS9's 20+ visibility toggles.

Three bugs that only came to light once the panels were laid out rather than docked:

* `ui/display.py` guarded every panner and magnifier update with
  `hasattr(self, "panner_panel")`, where `self` is the `DisplayPipeline` and not the
  window. The condition was never true, so **neither panel had been fed since M2
  extracted the pipeline** — both were permanently black. The same mistake hid the
  cut graphs' `set_image`.
* The panner and the magnifier were each a `QDockWidget` set as the widget of
  *another* `QDockWidget`, so each carried two title bars.
* Applying a theme called `QApplication.setStyle`, which walks every live widget.
  Nothing called it before M3; once `apply_preferences` did, every window
  construction restyled the whole process. Guarding it on an actual change cut the
  test suite from 94 s to 17 s.

### 3.8 Dead menu wiring

Three declared actions have no connected receiver: `action_cut`, `action_copy`,
`action_paste`. `action_undo`/`action_redo` are connected, but only to a
"not implemented" status message (`main_window.py:408-409`).
`save_file()` / `save_file_as()` are connected but do nothing
(`main_window.py:3587-3600`).

> An earlier draft of this document put the figure at 20, from a static grep for
> each `action_*` name in `main_window.py`. That over-counted: many actions are
> connected by iterating over a group or dict rather than by name
> (`colormap_actions` at `main_window.py:584`, `zoom_preset_actions` at 692), and
> `menu_bar.py:211` aliases `action_match_wcs` to `action_match_frame_wcs`. The
> authoritative check is now `python tools/dump_menus.py --connected`, which
> inspects live `QAction` receivers; `tests/unit/test_parity_tools.py` pins the
> count so it cannot drift upward unnoticed.

### 3.9 Project tooling — addressed in M0

Originally: no CI, no `pre-commit`, no `ruff`/`mypy`/`black` configuration (the dev extras declared
them but nothing configured or ran them), no coverage gate, and 144 build artifacts tracked in git
despite `.gitignore`.

M0 added all of it — see `docs/parity/lint-backlog.md` for what is gated now and what is
deliberately deferred. Setting the gates up immediately surfaced eight live defects, listed at the
end of that file; the most visible was that **`Edit → Preferences` crashed** with
`NameError: name 'Qt' is not defined`, and **loading any region file containing a `text` region
aborted the entire load** with a `TypeError`.

`tests/integration/` is still empty (task C-7).

---

## 4. Target architecture

```
ncrads9/
  core/            FITS access: HDU/extension model, cubes, bin tables, mosaics, compressed,
                   `file[ext][filter]` syntax, URL loading, data cache
  coordinates/     THE coordinate module: system (image/physical/amplifier/detector/wcs..wcsz),
                   sky frame (fk4/fk5/icrs/galactic/ecliptic), format (degrees/sexagesimal),
                   precision. All coordinate text in the app routes through here.
  frames/          ONE Frame + FrameManager. Frame owns: data ref, header, WCS, colormap, scale,
                   limits, block, bin, smooth, crop, pan/zoom/rotate/orient, slice, regions,
                   contours, grid, mask. Subclasses: RGBFrame, HSVFrame, HLSFrame, Frame3D.
  rendering/       Pipeline: data -> block -> smooth -> scale -> clip -> colormap -> composite
                   -> transform -> paint. CPU and GL backends behind one interface.
  regions/         ONE region model (`BaseRegion` + shapes), parser, writer, manager, groups,
                   templates, renderer, hit-testing, handles. Overlay widget draws these.
  illustrate/      NEW: non-WCS annotation layer (DS9's Illustrate menu).
  analysis/        Statistics, histogram, radial profile, pixel table, centroid, contour, smooth,
                   plus the external-task engine (.ds9.ans) and plot tool.
  catalogs/        Catalog tool: query, table window, symbol editor, filtering, match, plot.
  image_servers/   Real DSS/2MASS/SkyView/VLA/NVSS/VLSS/SDSS/ESO backends + SIA.
  io/              Readers/writers actually used by File → Import/Export/Save Image + backup.
  printing/        Postscript/PDF driver actually used by File → Print / Page Setup.
  communication/   XPA, SAMP (client + hub), IIS/imexam.
  prism/           FITS table/header browser.
  ui/
    layout/        NEW: DS9-fidelity window shell (header row, buttonbar, canvas, colorbar)
    controllers/   NEW: one controller per menu (FileController, ScaleController, …).
                   MainWindow shrinks to composition + shared state.
    panels/        info, panner, magnifier, colorbar, graphs, cube
    dialogs/       parameter dialogs, one per DS9 dialog
  utils/           prefs, config, logging, threading, i18n
```

**Key principle:** every menu action, XPA access point and CLI option must resolve to the *same*
controller method. DS9 achieves consistency this way (`ProcessXXXCmd` shared between XPA, SAMP and
the command line); NCRADS9 currently has parallel paths in `menu_bar`→`main_window` and
`xpa_commands`, which is why they have diverged.

---

## 5. Feature gap inventory

Legend: **✅** implemented · **◐** partial · **○** absent · **✗** wrong semantics

### 5.1 File menu

| DS9 feature | State | Notes |
|---|---|---|
| Open | ◐ | HDU 0 only; no extension picker, no `[ext]`/`[filter]` syntax |
| Open as → Slice / RGB Image / RGB Cube / HSV Image / HSV Cube / HLS Image / HLS Cube / Multi-Ext Cube / Multi-Ext Frames / Mosaic WCS / Mosaic WCS Segment / Mosaic IRAF / Mosaic IRAF Segment / Mosaic WFPC2 / URL | ○ | 15 loaders, none present |
| Save / Save as (same 10 variants) | ○ | `save_file()` is a no-op |
| Import → Array / NRRD / ENVI / RGB Array / HSV Array / HLS Array / GIF / TIFF / JPEG / PNG | ○ | `io/array_reader.py`, `nrrd_reader.py`, `envi_reader.py` exist but are orphaned |
| Export → same 10 formats | ◐ | Export dialog does PNG/JPEG/TIFF/BMP screen-grab only |
| Prism (FITS browser) | ○ | `prism/` is a skeleton |
| Save Image → FITS / EPS / GIF / TIFF / JPEG / PNG | ◐ | screen grab, 4 raster formats, no FITS, no EPS |
| Create Movie | ○ | `io/mpeg_writer.py` orphaned |
| Backup / Restore (full session) | ○ | `io/session/` orphaned |
| Header | ✅ | `header_dialog.py`; no per-extension switching (`header_dialog.py:134`) |
| Notes | ○ | |
| Preserve During Load → Pan / Region | ○ | |
| XPA → Information / Connect / Disconnect | ○ | server runs but has no UI |
| SAMP → Connect / Disconnect / Broadcast Image / Broadcast Table | ◐ | connect/disconnect only; no broadcast |
| SAMP Hub → Information / Start / Stop | ○ | `samp_hub.py` exists, no UI |
| Open TCL Console / Source TCL | n/a | Python equivalent: a Python console — a modern-UX substitute |
| Page Setup | ○ | `printing/page_setup.py` orphaned |
| Print | ◐ | `QPrinter` screen grab; no Postscript level/colour-model/resolution control |
| Exit | ✅ | |

### 5.2 Edit menu

| DS9 feature | State |
|---|---|
| Undo / Cut / Copy / Paste | ○ (`action_undo`/`redo` show "not implemented"; cut/copy/paste unconnected) |
| Pointer mode: None | ✅ |
| Pointer mode: Region | ✅ |
| Pointer mode: Crosshair | ○ |
| Pointer mode: Colorbar (colour tags) | ○ |
| Pointer mode: Pan / Zoom / Rotate | ◐ (mouse pan works; no explicit modes) |
| Pointer mode: Crop | ○ (dialog only) |
| Pointer mode: Catalog / Footprint | ○ |
| Pointer mode: Examine | ○ |
| Pointer mode: 3D | ○ |
| Pointer mode: Illustrate | ○ |
| Preferences | ✅ (7 tabs vs DS9's ~25 topic panels) |

### 5.3 View menu

DS9 has 20+ toggles; NCRADS9 has 3.

○ Layout Horizontal/Vertical · ○ Basic/Advanced · ○ Information Panel · ◐ Panner ·
◐ Magnifier · ◐ Buttons · ○ Icons · ◐ Colorbar · ○ Multiple Colorbars ·
◐ Horizontal Graph · ◐ Vertical Graph · ○ info-panel field toggles
(Filename, Object, Keyword, Min Max, Low High, Units, WCS, Multiple WCS a–z, Image, Physical,
Amplifier, Detector, Frame Information)

(◐ = the widget exists as a dock but has no View-menu toggle.)

### 5.4 Frame menu

✅ New/Delete/Delete All/Clear/Reset/Refresh · ✅ New RGB/HSV/HLS/3D (frame types created, but
HSV/HLS/3D have no rendering) · ✅ Single/Tile/Blink/Fade · ✅ Goto/Show-Hide/Move ·
✅ First/Prev/Next/Last · ✅ Match & Lock menu surface · ◐ Match/Lock semantics (WCS match is
partial; `action_match_frame_wcs` unconnected) · ✅ RGB dialog · ○ HSV/HLS/3D dialogs ·
○ Cube dialog (axis order, slice, interval, play) — `ui/panels/cube_panel.py` orphaned ·
✅ Tile mode Grid/Column/Row · ○ Tile Parameters (grid rows/cols, gap, direction) ·
✅ Blink/Fade interval · ○ Display Size

### 5.5 Bin menu — **rebuild** (see §3.4)

○ FITS bin-table loading · ○ bin columns X/Y/Z · ○ bin function average/sum ·
○ bin buffer size 128²–8192² · ○ bin filter expression · ○ bin centre from
TDMIN/TDMAX/TLMIN/TLMAX/TALEN/AXLEN · ○ Bin In/Out/Fit · ○ Binning Parameters dialog ·
✗ current `Bin` menu is block-averaging (belongs in Block)

### 5.6 Zoom menu

✅ Center Image · ◐ Align (WCS) · ✅ Zoom In/Out/Fit · ◐ presets (DS9: 1/32…32, 11 steps) ·
✗ Invert X/Y/XY — menu present, actions unconnected · ✗ 0/90/180/270° — menu present,
actions unconnected · ○ arbitrary rotation angle · ◐ Crop Parameters (dialog exists;
no interactive crop mode) · ◐ Pan Zoom Rotate Parameters

### 5.7 Scale menu

✅ Linear/Log/Power/Sqrt/Squared/ASINH/SINH/HistEq (algorithms all exist in
`scale_algorithms.py`; the menu omits Power and SINH) · ○ Log Exponent ·
◐ limits: Min Max ✅, ZScale ✅, User ◐, **○ 99.5% / 99% / 98% / 97% / 96% / 95% / 92.5% / 90%
clipping presets**, ○ ZMax · ○ Scale Scope Global/Local ·
○ Min Max method: Scan / Sample / DATAMIN-DATAMAX / IRAF-MIN-IRAF-MAX + Sample Parameters ·
○ Use DATASEC · ○ ZScale parameters dialog (contrast, samples, samples-per-line) ·
✅ Scale Parameters dialog (with histogram)

### 5.8 Color menu

◐ 23 built-in colormaps, but **0 of DS9's 168 bundled `.sao`/`.lut` files are shipped** ·
○ colormap categories h5utils / Matplotlib Sequential / Diverging / Cyclic / Cubehelix / Gist /
Topographic / Scientific Colour Maps / Solar (only "Matplotlib Uniform" with 4 entries) ·
✅ User load/save · ✅ Invert · ✅ Reset · ✅ Colorbar orientation / numerics / font / size /
ticks · ○ **Colour tags** (highlight/hide value ranges — DS9 Colorbar pointer mode) ·
○ Multiple colorbars · ○ RGB/HSV/HLS colorbar variants · ◐ contrast/bias drag (exists, not
exposed as a mode) · ✅ Colormap Parameters dialog

### 5.9 Region menu

| Area | State |
|---|---|
| Interactive creation | ◐ **6 of 20** shapes (circle, ellipse, box, polygon, line, point) |
| Shape classes present but not creatable | annulus, ellipse annulus, box annulus, panda, compass, ruler, projection, vector, composite |
| Shape classes absent | segment, epanda, bpanda |
| Point glyphs | ○ (DS9: circle/box/diamond/cross/x/arrow/boxcircle + size) |
| Parser coverage | ◐ 8 shapes; no annulus variants, panda family, vector, ruler, compass, projection, segment, composite |
| Properties | ○ include/exclude, source/background, fixed/edit/move/rotate/delete, dash, fill |
| Selection ops | ○ All / None / Invert / Front / Back / Move to Front / Move to Back |
| Groups | ○ New Group / Groups dialog (`regions/group_manager.py` orphaned) |
| Composite | ○ Create / Dissolve |
| Templates | ○ Open / Save (WCS-independent templates) |
| Instrument FOV | ○ (DS9 ships Chandra, XMM, MMT, HEASARC templates) |
| Centroid | ○ + Centroid Parameters (`analysis/centroid.py` orphaned) |
| Get Information dialog (per-shape editor) | ○ |
| List / Save Selection / List Selection / Delete Selection | ○ |
| Load / Save / Delete All | ✅ |
| Auto Plot 2D / 3D / Statistics / Centroid | ○ |
| Marker analysis (radial profile, histogram, plot2d/3d, stats from a region) | ◐ radial profile only, not region-driven |
| Region colour / width / font submenus | ○ |

### 5.10 Illustrate menu — **entirely absent**

DS9 8.x adds a second annotation layer that is *not* tied to WCS: circle, ellipse, box, polygon,
line, text, image; with colour, width, fill, front/back, select-all/none/invert, open/save/list,
and its own file format (`illustrate*.tcl`, 3,900 lines). NCRADS9 has no equivalent.

### 5.11 WCS menu

✗ NCRADS9 conflates *coordinate system* with *sky frame*. DS9's WCS menu is:
system (`wcs`, `wcsa`…`wcsz`, `image`, `physical`, `amplifier`, `detector`) ×
sky (`fk4`, `fk5`, `icrs`, `galactic`, `ecliptic`) × format (`degrees`, `sexagesimal`).

✅ fk4/fk5/icrs/galactic/ecliptic · ✅ degrees/sexagesimal · ○ Multiple WCS (a–z) ·
○ image/physical/amplifier/detector as display systems · ○ WCS Parameters dialog (edit/replace
WCS, reset, load/save WCS from file) · ✅ direction arrows *(modern addition, keep)*

### 5.12 Analysis menu

| DS9 feature | State |
|---|---|
| Pixel Table | ✅ (`analysis/pixel_table.py` orphaned; UI recomputes) |
| Name Resolution (SIMBAD/NED/CDS) | ✅ |
| Mask Parameters | ◐ threshold masking; no mask *file* loading, no mask blend/colour/range/transparency |
| Crosshair Parameters | ◐ dialog only, no crosshair mode |
| Graph Parameters (cut graphs: method, log/linear, grid, thickness) | ◐ |
| Contours + Parameters | ✅ (copy/paste contours, load/save contour files: ○) |
| Coordinate Grid + Parameters | ✗ pixel grid, not a WCS graticule (§3.5) |
| Block In/Out/Fit + Parameters | ◐ destructive; duplicated with Bin |
| Smooth + Parameters | ✅ (boxcar/tophat/gaussian; DS9 also has elliptic gaussian) |
| Image Servers → DSS(SAO/ESO/STScI), 2MASS, VLA, NVSS, VLSS, SkyView | ◐ **2MASS SIAP only**; the 5 server modules are `NotImplementedError` skeletons |
| Archives → Chandra by ObsId / by Cone Search, SIMBAD SAO/CDS, ADS SAO/CDS | ○ |
| Catalogs (VizieR, CDS, CXC, NED, SDSS, SIMBAD, SkyBot, 2MASS, local starbase/CSV/VOTable) | ◐ VizieR overlay only; `catalogs/{ned,sdss,simbad,skybot,twomass,cone_search}.py` orphaned |
| Catalog Tool (list window, sort, filter, symbol editor, header, print, match, plot, region export) | ○ `catalogs/catalog_table.py` + `catalog_display.py` orphaned |
| Search for Catalogs / Clear All / Match | ○ |
| Footprint Servers | ○ |
| Plot Tool → Line / Bar (+ scatter; axis config, multiple datasets, zoom stack, print, backup) | ○ menu entries exist, unimplemented |
| Virtual Observatory (registry browse, SIA/SSA/cone/TAP) | ◐ dialog exists, narrow |
| Web Browser (internal HTML/HTTP client) | ◐ opens system browser |
| Analysis Command Log | ✅ |
| Load / Clear Analysis Commands | ✗ custom `label\|command` format, **not** DS9's `.ds9.ans` |

**DS9 `.ds9.ans` format** — a real gap worth its own milestone. Task blocks of
`label / file-template / type / command`, with types `menu`, `button`, `bind <key>`, `web`;
macros `$data $filename $filename(root|full) $regions $x $y $z $width $height $depth $bitpix
$env(VAR) $entry(msg) $filedialog(open|save) $dir $pan $zoom $cmap $scale $wcs $param(...) $geturl`;
output sinks `$text $plot $plot(...) $image $null`; hierarchical `hmenu`; `param`/`endparam`
parameter dialogs; startup autoload from `./ds9.ans`, `$HOME/ds9.ans`, `*.ds9` in `.`,
`$HOME/bin`, `/usr/local/bin`, `/opt/local/bin`.

### 5.13 3D frames — absent

DS9's 3D frame is a threaded ray-tracer with MIP and AIP projections, azimuth/elevation controls,
per-slice highlighting, and its own scale/colormap application. NCRADS9's `frames/frame_3d.py` is
an orphaned skeleton.

### 5.14 Communication

| DS9 | State |
|---|---|
| XPA: 143 access points | ◐ **23** (`file fits frame zoom pan scale cmap colorbar regions wcs crosshair cursor mode tile blink match lock width height save exit quit version about`) |
| XPA `-xpa local\|inet\|localhost`, `-port`, `xpaaccess`, `xpainfo` | ◐ |
| SAMP client | ◐ (see §5.1) |
| SAMP hub + web hub | ○ |
| IIS / IRAF `imexam` (`iis.tcl`, `iexam.tcl`) | ○ `communication/iis/iis_server.py` orphaned |
| Shared memory (`shm.tcl`) | ○ |
| XML-RPC | ○ |

### 5.15 Cross-cutting

○ Undo/redo framework · ○ i18n (DS9 ships 8 locales) · ● theme application
(M3-8) · ○ configurable keyboard/mouse bindings ·
○ auto-recovery / autosave · ○ tracked `.pyc` cleanup · ○ CI · ○ lint/type gates ·
○ integration tests · ○ per-menu preference panels

---

## 6. Roadmap

Ordered so that structural work unblocks feature work, and so each milestone is independently
shippable. Estimates are rough working-days for one developer.

### M0 — Hygiene (2 d)
Untrack `.pyc`; add `ruff`/`black`/`mypy` config and a GitHub Actions matrix; fix the failing
zoom test; enable `pytest --cov` with a floor. Cheap, and makes everything after it safer.

### M1 — Consolidate the model (10 d)
One `Region` type. One `Frame`/`FrameManager`. Adopt `coordinates/` as the single coordinate
formatter. Adopt `core/` for FITS access. Delete the true duplicates. **No behaviour change** —
the 69 existing tests plus new model tests must pass throughout.

### M2 — Extract controllers from `main_window.py` (12 d)
Split into `ui/controllers/{file,edit,view,frame,bin,zoom,scale,color,region,wcs,analysis}.py`.
Route menu, XPA and CLI through the same controller methods. Target: `main_window.py` under
600 lines.

### M3 — DS9 window layout (8 d) — **done**
Replace docks with the DS9 header row (info panel | panner | magnifier), the two-row category
buttonbar, canvas, and colorbar. Wire the full `View` menu including info-panel field toggles and
the horizontal/vertical layout switch. Apply `ui/themes/`. This is the milestone that makes the
app *look* like DS9.

Delivered: `ui/layout/{view_state,shell}.py`; a rewritten `ui/panels/info_panel.py` with DS9's
fourteen field rows plus the twenty-six alternate WCS systems; a rewritten `ui/button_bar.py`
driving `MenuBar` actions directly, so a button and its menu entry cannot disagree; all four DS9
layouts; the compass moved into the panner; themes wired to the Preferences setting; and
alternate-WCS support (`WCSHandler(key=...)`) so the `Multiple WCS` rows carry real values.
View-menu parity 3/27 → 26/27, total menu entries 287 → 337, orphans 71 → 60.

### M4 — FITS coverage (12 d) — **done**
Extension model + HDU chooser; `file[ext][filter]` syntax; data cubes with the Cube dialog
(axis order, slice, interval, play) using `ui/panels/cube_panel.py`; multi-extension cube/frames;
mosaics (WCS, IRAF, WFPC2, segments); tile-compressed images; URL loading; real
`Save`/`Save as`/`Save Image → FITS`.

### M5 — Scale, colour, block/bin done properly (10 d) — **done**
Percentile clipping presets and ZMax; scale scope global/local; min/max method scan/sample/
DATAMIN/IRAF; ZScale parameter dialog; log exponent; Power and SINH in the menu.
Ship DS9's 168 `.sao`/`.lut` colormaps with the full category submenus. Colour tags + Colorbar
pointer mode. Separate Block (non-destructive display transform) from Bin, and implement true
FITS bin-table binning with the Binning Parameters dialog.

### M6 — Regions to parity (14 d) — **done**
All 19 shapes creatable and editable with handles; 7 point glyphs; full property set
(include/exclude, source/background, fixed/edit/move/rotate/delete, dash, fill);
parser/writer round-trip for every shape in every supported format; selection operations;
groups; composite create/dissolve; templates and the bundled instrument FOVs; centroid;
per-shape Get Information dialog; region-driven marker analysis (radial profile, histogram,
statistics, plot2d/3d).

Region menu parity went from 6 entries to 118, matching 54 of DS9's 69 labels. The shapes are
nineteen, not the twenty this plan first said; see the M6 deviations in TODO.md, along with two
modules the plan said to adopt and that were rewritten instead, because what they held could not
have worked.

### M7 — Analysis platform (12 d) — **done**
The `.ds9.ans` engine (all four task types, the full macro set, `$text`/`$plot`/`$image` sinks,
hierarchical menus, parameter dialogs, startup autoload). A real WCS coordinate grid
(graticule, ticks, numeric formats, axes, border, title) — adopt `grid/` and back it with
`astropy.visualization.wcsaxes` rather than porting AST. The Plot Tool (line/bar/scatter, axis
config, multiple datasets, zoom stack, print, save/restore).

The graticule is built on `astropy.wcs`'s own transforms rather than on wcsaxes, whose transform
machinery is tied to a matplotlib axes object while the drawing here is QPainter; AST is not
ported either way, and `grid/ast_wrapper.py` is deleted. See the M7 deviations in TODO.md, and
the bugs -- two of which were in the display pipeline, not in M7's own code.

### M8 — Catalogs, image servers, VO (12 d)
Catalog Tool: query, sortable/filterable table window, symbol editor driven by column
expressions, live table↔overlay selection sync, header view, print, local starbase/CSV/VOTable
load & save, catalog match, catalog plot, region export. Real DSS(SAO/ESO/STScI), 2MASS, VLA,
NVSS, VLSS, SkyView, SDSS, ESO backends. Archives menu. Footprint servers. VO registry browser.

### M9 — Remaining subsystems (16 d)
Crosshair mode + lock/match. Interactive crop mode. Pointer modes for pan/zoom/rotate/examine.
Mask files with blend/colour/range. Illustrate layer. Prism. Movie creation. Backup/Restore.
Import/Export for all 10 formats. Postscript print driver + Page Setup. Notes. Undo/redo.
3D frames (MIP/AIP ray tracer). SAMP hub + broadcast. IIS/imexam. XPA to full 143 access points.
i18n with the 8 DS9 locales. Per-menu preference panels.

---

## 7. Deliberate divergences from DS9

Kept as modern-UX improvements; documented so they are not mistaken for gaps:

- **Direction arrows over the image** in the WCS menu — not in DS9. As of M3 the N/E compass is
  drawn in the panner, which is where DS9 puts it; this toggle additionally draws it over the
  data, and now defaults off.
- **`View → Fullscreen` and `Show Status Bar`** — not in DS9's View menu. DS9's `Icons` toggle
  and our `Show Toolbar` are the same action rather than two entries that could disagree.
- **`Color → Show Colorbar`** — DS9 keeps colorbar visibility in View only. Ours appears in both
  menus, as one shared `QAction`.
- **A wrapped buttonbar.** DS9 lets a category's buttons run the width of its window; ours wrap
  at fourteen, because Qt's buttons are wider than Tk's and the window minimum is 800 px.
- **GPU tile rendering** with a CPU fallback — DS9 is CPU-only.
- **A Python console** in place of DS9's TCL console; `Source TCL` becomes `Run Python Script`.
- **`--help` opens HTML docs in a browser** rather than printing to the terminal. Reconsider:
  a terminal `--help` is the expected convention and cheap to add alongside.
- **Preferences as tabs** rather than DS9's list-plus-panel. Fine, but the *coverage* must grow
  to DS9's ~25 topic panels.
- **Astropy/AstroQuery** for WCS, coordinates and archive access instead of DS9's bundled
  AST/funtools/wcssubs.
- **An extension chooser on Open** when a file has more than one displayable HDU. DS9 applies its
  algorithm silently and takes the first, which for an instrument file with SCI, ERR and DQ is a
  coin toss. The `prompt_for_hdu` preference restores DS9's behaviour.
- **Mosaic resampling is nearest-neighbour**, so a mosaic is a display aid and conserves no flux.
  DS9 resamples too; anyone wanting a photometric mosaic should use `reproject` or SWarp and load
  the result.
- **`Save` writes what is displayed**, not the array as it came off disk — the block, smooth or
  cube slice on screen is what lands in the file, with the header's axis cards corrected to match
  and an `NCSPEC` card recording the specification it was loaded from.

## 8. Explicit non-goals

- Porting the `tksao` C++ engine, AST, funtools, or the bundled Tcl/Tk stack.
- DS9's X11 visual selection (`-visual`), 8-bit pseudocolor support.
- Windows-specific and macOS-aqua-specific code paths beyond what Qt gives for free.
- Bit-identical Postscript output.

---

## 9. How to verify parity

For each milestone, parity is demonstrated by:

1. **Menu diff** — a script that dumps NCRADS9's menu tree and diffs it against the DS9 menu tree
   extracted from `.tmp_sao_ds9/ds9/library/m*.tcl`. Reuse the extraction approach that produced
   §5 of this document. One caveat found in M3: the extractor does not expand DS9's
   `foreach l {a b c ...}` loops, so DS9's twenty-six `Multiple WCS` entries appear in the
   snapshot as the single literal `WCS $l`. The View menu therefore reads 26/27 rather than
   27/27; the missing entry is that artefact, not a gap.
2. **XPA conformance** — for each of DS9's 143 access points, `xpaget`/`xpaset` against both
   applications on the same FITS file and compare responses.
3. **Region round-trip** — parse every shape from DS9's own reference examples
   (`.tmp_sao_ds9/ds9/doc/ref/region.html`), write it back, and diff.
4. **Screenshot comparison** for the layout milestone. `tools/screenshots.py` renders the window
   headless in each of the four layouts into `docs/parity/screenshots/`; `before-m3.png` is the
   dock-based layout at `c41f62a`.
5. **Session backup round-trip** once M9 lands.

See `TODO.md` for the task-level breakdown.
