# Skeleton modules

Companion to [PLAN.md](../../PLAN.md). Records where the tree still declares an
API it does not implement, so nobody mistakes a signature for a feature, and so
the milestone that builds each one knows what is expected.

Maintained as of **M1**.

---

## Deleted in M1 — nothing was there

These five modules were signatures, docstrings and
`raise NotImplementedError("Subclasses must implement ...")`, with no
subclasses anywhere in the tree and no caller. They are removed rather than
kept, because a module that advertises `get_image()` and raises is worse than
no module: it reads as coverage in a directory listing and in `__all__`.

| Deleted | Class | M8 must provide |
|---|---|---|
| `image_servers/dss.py` | `DSSServer` | DSS cutouts from the SAO, ESO and STScI servers (`Analysis -> Image Servers -> DSS (SAO/ESO/STSCI)`); survey selection across `poss1_*`, `poss2ukstu_*`; FITS and JPEG return |
| `image_servers/eso.py` | `ESOArchive` | ESO archive query and download, with optional authentication; instrument list; cutout by position and size |
| `image_servers/skyview.py` | `SkyViewServer` | NASA/HEASARC SkyView, with its full survey list and multi-survey retrieval in one request |
| `image_servers/sdss_image.py` | `SDSSImage` | SDSS image cutouts per data release and band, FITS and JPEG, plus a coverage check |
| `image_servers/twomass_image.py` | `TwoMassImage` | 2MASS J/H/K cutouts from NASA/IPAC |

`image_servers/sia_client.py` is real, is used by the 2MASS SIAP query, and
stays. M8 tasks **M8-13** to **M8-18** rebuild the list above against a common
backend interface and a shared query dialog.

`core/data_cache.py` was also deleted, for a different reason: it was complete,
but redundant. It cached whole-file arrays in a process-wide singleton keyed by
`(filepath, ext)` behind weakrefs, while the loader already opens files with
`memmap=True` (so arrays are never read eagerly), frames already hold strong
references to the arrays they display, and `TextureManager` already caches GPU
textures against a size budget. Adopting it would have added a second cache in
front of two that work.

---

## Kept — real code with stubbed methods

These hold work worth keeping. The stubs are listed so the adopting milestone
knows what is missing.

### `grid/` — adopted by M7-10..M7-14

| Module | State |
|---|---|
| `grid_config.py` | **Complete.** Config dataclass with `to_dict`/`from_dict`/`copy`. |
| `grid_renderer.py` | `compute_grid_lines()` and `render()` return empty / do nothing. |
| `grid_labels.py` | `compute_labels()`, `format_coordinate()` (HMS/DMS) and `render()` are stubs. |
| `ast_wrapper.py` | Entirely stubbed. **M7-10 deletes this**: the graticule is to be built on `astropy.visualization.wcsaxes`, not a port of AST. |

Note that the coordinate grid the application draws today is a *pixel* grid in
`ui/widgets/contour_overlay.py`, not a WCS graticule -- see PLAN.md §3.5.

### `printing/` — adopted by M9-18..M9-20

| Module | State |
|---|---|
| `page_setup.py` | **Complete.** Paper sizes, orientation, margins, points conversion. |
| `postscript.py` | Real PostScript emission for lines, text and colour; `draw_image()` is a stub, which is the important half. |
| `print_engine.py` | `render_image()`, `render_to_printer()` and `get_available_printers()` are stubs. |

Printing today goes through `QPrinter` inline in `MainWindow._print_image()` as
a screen grab, with no control over PostScript level, colour model or
resolution.

### `prism/` — adopted by M9-9, M9-10

| Module | State |
|---|---|
| `line_id.py` | **Complete.** Spectral line list, redshift handling, identification, redshift estimation. |
| `prism_main.py` | `load_spectrum()`, `show()`, `hide()`, `zoom_to_range()`, `reset_zoom()` are stubs. |
| `spectrum_plot.py` | `_auto_range()`, `refresh()`, coordinate and flux lookups are stubs. |

M9-9 rewrites Prism as a FITS browser (HDU list, header view, table view,
column plotting), which is what DS9's Prism actually is; the spectrum plotting
here is closer to DS9's Plot Tool and belongs with M7-15.

### `communication/iis/` — adopted by M9-29

`iis_server.py` is unreferenced. M9-29 wires it up for IRAF `imexam`.

---

## How this file is checked

`tests/unit/test_no_orphan_modules.py` fails when a module under `ncrads9/`
becomes unreachable from `ncrads9.app` without being listed in its allow-list,
and each allow-list entry names the milestone that adopts it. Adding a module
here is not enough -- it has to be allow-listed there too, which forces the
decision to be explicit.
