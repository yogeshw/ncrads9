# Lint, type and format backlog

Companion to [PLAN.md](../../PLAN.md) M0-3. The CI gate starts narrow and is
widened one milestone at a time; this file records what is deferred and why, so
widening is a deliberate step rather than an accident.

Regenerate the counts with:

```bash
tools/check.sh                                      # everything CI runs
ruff check ncrads9 tests tools --select ALL --statistics   # every rule
mypy ncrads9                                        # whole tree
black --check ncrads9 tests tools
python tools/menu_diff.py --summary                 # DS9 menu parity
```

---

## What is gated today

| Gate | Scope | State |
|---|---|---|
| `ruff check` | `ncrads9`, `tests`, `tools` — rule set in `pyproject.toml`, incl. `UP` and `I` since M1-0b | **clean** |
| `mypy` | `ncrads9/core`, `ncrads9/coordinates`, `ncrads9/regions` | **clean** (40 files) |
| `black --check` | `ncrads9`, `tests`, `tools` — whole tree since M1-0a | **clean** |
| `pytest` | whole suite | **clean**, 107 tests |
| coverage | whole tree | **42.1%**, floor 40% |

---

## Deferred: black formatting of `ncrads9/` and `tests/`

`black --check ncrads9 tests` would reformat **90 files** (80 under `ncrads9/`,
10 under `tests/`).

Not done in M0, because:

- It would produce a diff spanning most of the codebase, burying M0's eight bug
  fixes in unreviewable noise.
- M1 and M2 restructure or delete a large share of those files, so the tree
  would be reformatted twice.
- `git blame` continuity across most of the codebase would be lost in one
  commit.

So the black gate is scoped to **`tools/`** — written from scratch in M0 and
therefore clean — in CI, in `pre-commit`, and in `tools/check.sh`.

A "changed files only" gate was tried first and rejected: M0's own ruff
autofixes touch 94 files, so that rule would have failed on the very commit
introducing it, and it would keep failing on any milestone that sweeps the tree.
Scoping by directory is honest about where the debt is.

**M1 must do the one-shot reformat**, alongside the `UP*`/`I001` pass that
rewrites the same signatures:

```bash
black ncrads9 tests tools
```

then widen the gate in all three places — `.github/workflows/ci.yml`,
`.pre-commit-config.yaml` (`files:`), and `tools/check.sh`:

```bash
black --check ncrads9 tests tools
```

---

## Deferred: ruff rule families

Counts are from the full default rule set with no exemptions, measured at the
end of M0. All are style or modernization, none are correctness.

| Rule | Count | What it wants | Enable at |
|---|---:|---|---|
| `UP045` | 634 | `Optional[X]` → `X \| None` | M1 (touches every model signature) |
| `UP006` | 416 | `List`/`Dict` → `list`/`dict` | M1 |
| `I001` | 129 | import sorting | M1 |
| `UP035` | 127 | deprecated `typing` imports | M1 |
| `UP007` | 43 | `Union[A, B]` → `A \| B` | M1 |
| `SIM105` | 21 | `contextlib.suppress` | M2 |
| `RUF012` | 14 | mutable class default | M1/M2 (Qt constructors) |
| `SIM108` | 10 | ternary instead of if/else | M2 |
| `UP015` | 10 | redundant `open()` mode | M1 |
| `RUF046` | 8 | unnecessary `int()` cast | M2 |
| `RUF059` | 6 | unused unpacked variable | M2 |
| `UP041` | 5 | `socket.timeout` → `TimeoutError` | M9 |
| `SIM102` | 4 | collapsible `if` | M2 |
| `UP012` | 4 | unnecessary `.encode("utf-8")` | M1 |
| `SIM116` | 2 | dict lookup instead of `if`/`elif` chain | M2 |

The whole-tree `--select ALL` run reports considerably more (922 `W293`
whitespace-only lines, 900 `D413` docstring-section, 724 `D212` docstring-summary,
329 `S101` asserts in tests, 185 `COM812` trailing commas, 182 `PLR2004` magic
values, 181 `SLF001` private access in tests, 117 `ANN201` missing return types).
Those families are documentation and annotation conventions rather than defects,
and are not planned for adoption; `W293` will disappear as a side effect of the
black rollout.

The `UP*` and `I001` families are best applied in one pass at the start of M1,
together with the model consolidation that rewrites those signatures anyway:

```bash
ruff check --select UP,I --fix ncrads9 tests tools
```

### Permanently exempted, with reasons

| Rule | Reason |
|---|---|
| `BLE001`, `S110`, `S112` | Broad `except` around Qt and network calls is deliberate. Revisit with the error-reporting work in M2. |
| `RUF012` | Mutable class defaults are pervasive in Qt widget constructors, which M1/M2 rewrite. |
| `B008` | PyQt slots legitimately shadow builtins and accept unused arguments. |
| `RUF001`–`RUF003` | Typographic characters (`×`, `°`, `α`, `δ`) are intentional in UI labels. |
| `E741` in `coordinates/galactic.py`, `rendering/rgb_compositor.py`, `frames/hls_frame.py` | `l` is the standard symbol for galactic longitude and for lightness. Domain naming wins. |
| `F401`, `RUF022` in `**/__init__.py` | Package facades re-export names as the public API. |

---

## Deferred: mypy coverage

`mypy ncrads9` reports **473 errors across 29 files** (was 491 across 36 before
the M0 fixes). Per package, measured individually:

| Package | Errors | Gated? | Notes |
|---|---:|---|---|
| `core` | 0 | **yes** | |
| `coordinates` | 0 | **yes** | |
| `regions` | 0 | **yes** | |
| `printing` | 0 | no | skeleton; M9 rewrites it |
| `grid` | 0 | no | skeleton; M7 rewrites it |
| `prism` | 0 | no | skeleton; M9 rewrites it |
| `image_servers` | 0 | no | skeletons; M8 rewrites them |
| `io` | 2 | no | add in M9 |
| `utils` | 2 | no | add in M1 |
| `analysis` | 3 | no | add in M6/M7 |
| `rendering` | 9 | no | add in M5 |
| `colormaps` | 10 | no | see below |
| `catalogs` | 12 | no | add in M8 |
| `frames` | 18 | no | add in M1 |
| `communication` | 89 | no | add in M9 |
| `ui` | 470 | no | add per controller in M2/M3 |

(Per-package figures exceed the whole-tree total because a package checked alone
re-reports errors that the whole-tree run attributes to a single file.)

Widen the gate by adding the package to the `[[tool.mypy.overrides]]` module
list in `pyproject.toml` **and** to `MYPY_PATHS` in `tools/check.sh` **and** to
the `mypy` step in `.github/workflows/ci.yml`.

The `ui` figure is dominated by `main_window.py`; it is expected to fall sharply
once M2 splits it into controllers, so there is little point chasing it before
then.

---

## Known-broken orphans

Found while setting up the gates. All are unreachable from `ncrads9.app`
(PLAN.md §3.1), so none of these fail at runtime today — but each would crash
immediately if wired up as-is. They are recorded here rather than fixed,
because the milestone that adopts each module rewrites it.

| Module | Problem | Adopted in |
|---|---|---|
| `colormaps/colorbar_widget.py` | PyQt5 enum access throughout — `QImage.Format_RGBA8888`, `QPainter.Antialiasing`, `Qt.AlignCenter`, `Qt.AlignLeft`, `Qt.AlignVCenter`, `Qt.IgnoreAspectRatio`, `Qt.SmoothTransformation`. None of these exist in PyQt6. The live widget is `ui/widgets/colorbar_widget.py`. | M5, or delete |
| `image_servers/{dss,eso,skyview,sdss_image,twomass_image}.py` | Every method raises `NotImplementedError`; no concrete backend. | M8 |
| `grid/{grid_renderer,grid_labels,ast_wrapper}.py` | Bodies are `# TODO`; return empty results. | M7 |
| `prism/{prism_main,spectrum_plot}.py` | Bodies are `# TODO`. | M9 |
| `printing/{postscript,print_engine}.py` | Image drawing and printing are `# TODO`. | M9 |

---

## Fixed during M0

Real defects the new gates surfaced immediately, all with regression tests:

| Defect | Found by | Where |
|---|---|---|
| `Edit → Preferences` crashed with `NameError: name 'Qt' is not defined` | `ruff` F821 | `ui/dialogs/preferences_dialog.py` |
| Loading any region file containing a `text` region raised `TypeError` and aborted the whole file | `mypy` call-arg | `regions/region_parser.py` |
| `text={Hello World}` truncated at the first space; brace delimiters were never stripped | follow-on from the above | `regions/region_parser.py` |
| `lru_cache` on instance methods pinned `self` for the process lifetime | `ruff` B019 | `utils/resources.py` |
| `zip()` over two sequences with an unstated equal-length invariant | `ruff` B905 | `colormaps/sao_parser.py` |
| Naive `datetime.now()`/`utcnow()` in serialized timestamps | `ruff` DTZ003/DTZ005 | `catalogs/skybot.py`, `io/session/*` |
| Zoom and block factors computed from an unlaid-out viewport | the failing M0-2 test | `ui/main_window.py` |
| Zoom-to-fit near-zero on the default GPU path: `zoom_fit()` took a viewport size and discarded it | verifying the M0-2 fix against a real image | `ui/widgets/gl_image_viewer_with_regions.py`, `rendering/gl_canvas.py` |
