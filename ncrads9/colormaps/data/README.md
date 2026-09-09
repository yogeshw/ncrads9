# Bundled colour tables

The 164 colour tables SAOImageDS9 ships in its own `ds9/cmaps/` directory,
copied verbatim: 46 in DS9's `.sao` control-point format and 118 as plain
`.lut` triples. `ncrads9/colormaps/bundled.py` groups them into the ten
cascades DS9's Color menu uses, with DS9's own membership taken from the
`icolorbar(<category>,cmaps)` lists in `ds9/library/colorbar.tcl`.

Provenance, as DS9 records it in the files' own comment headers:

| Family | Origin |
|---|---|
| `h5_*` | h5utils, Steven G. Johnson |
| `mpl_*` | Matplotlib's colormaps |
| `ch*` | Cubehelix, D. A. Green (2011) |
| `gist_*` | the Gist graphics package, via Matplotlib |
| `tp*` | topographic tables, cptutils |
| `scm_*` | Scientific Colour Maps, Fabio Crameri |
| `solar_*` | SDO, SOHO and STEREO instrument tables |

Four tables DS9 ships here — `viridis`, `inferno`, `magma` and `plasma` — are
**not** copied: NCRADS9 has built-ins of those names, and the same tables are
present as `mpl_viridis` and friends, which is what DS9's own cascade calls
them. One name resolving to two sources is a bug waiting to happen.

Regenerate from a DS9 checkout with:

    cp <ds9>/ds9/cmaps/*.sao <ds9>/ds9/cmaps/*.lut ncrads9/colormaps/data/
    rm -f ncrads9/colormaps/data/{viridis,inferno,magma,plasma}.*
