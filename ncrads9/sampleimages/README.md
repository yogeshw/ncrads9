# Sample images

| File | What it is |
|---|---|
| `SDSS9_M51_g.fits`, `_r.fits`, `_i.fits` | SDSS DR9 cutouts of M51 in three bands, 512×512. The three together exercise RGB frames and `Open as → RGB Image`. |
| `uncover_4k_cutout_f444w.fits` | A 4000×4000 JWST/NIRCam F444W cutout from the UNCOVER survey. Large enough to exercise blocking, the GPU tile path and the preview downsampler. |
| `synthetic_events.fits` | **Not real data.** A synthetic X-ray event list, written by the snippet below: 12,985 rows on a 512×512 detector with `TIME`, `X`, `Y`, `PHA`, `ENERGY` and `CCD_ID` columns, a bright point source at (256, 256), a faint extended one at (180, 330), and a flat background. It carries `TLMIN`/`TLMAX`, `TDMIN`/`TDMAX` and per-column `TC*` WCS cards, so it exercises bin centring, the WCS a binned image inherits, and row filters — the core has harder photons, so `[PHA>500]` leaves the point source and little else. |

`synthetic_events.fits` was generated with:

```python
import numpy as np
from astropy.io import fits

rng = np.random.default_rng(20260909)
xs, ys = [], []
for n, cx, cy, sigma in ((6000, 256, 256, 2.5), (3000, 180, 330, 14.0)):
    xs.append(rng.normal(cx, sigma, n))
    ys.append(rng.normal(cy, sigma, n))
xs.append(rng.uniform(1, 513, 4000))
ys.append(rng.uniform(1, 513, 4000))
x, y = np.concatenate(xs), np.concatenate(ys)
keep = (x >= 1) & (x <= 512) & (y >= 1) & (y <= 512)
x, y = x[keep], y[keep]

pha = rng.integers(20, 400, x.size)
core = np.hypot(x - 256, y - 256) < 8
pha[core] = rng.integers(600, 1200, int(core.sum()))
```

with the remaining columns derived from those and the header cards listed
above. The seed is fixed, so it can be reproduced exactly.
