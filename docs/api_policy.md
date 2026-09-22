# SnowIn API policy

SnowIn exposes a small stable facade at the package root and keeps
domain-specific functionality in named submodules. This gives users a simple
starting point without making every reader, compatibility helper, diagnostic,
or implementation detail part of the long-term API.

## Import levels

Root-level imports are the stable, recommended facade. The functions exported
from `snowin` are the preferred entry points for generic scientific operations:

```python
from snowin import (
    accumulate_dswe,
    build_support_dataset,
    compose_support_mask,
    compute_dswe,
    compute_metrics,
    reference_phase,
    summarize_support,
)
```

Submodule imports are public for domain-specific functionality. Use them when
the operation is tied to a product, file format, correction family, or lower-
level diagnostic:

```python
from snowin.io import add_gunw_incidence, open_gunw
from snowin.corrections import PhaseCorrectionConfig, apply_phase_corrections
from snowin.reference import estimate_reference_offset

# NISAR-specific detail is also grouped by domain:
from snowin.io.dem import DEMSource
from snowin.io.geometry import compute_cop30_local_incidence
from snowin.io.phase_normalization import normalize_gunw_pair
```

Underscore-prefixed names are internal implementation details and are not part
of the public API. They may change without compatibility guarantees.

Legacy submodule APIs remain available where practical for compatibility, but
are not recommended for new workflows. In particular, use
`snowin.reference.reference_phase` instead of the older
`snowin.reference.apply_reference_phase`, and use `snowin.compute_dswe` instead
of the older NumPy method-selector functions in `snowin.snow`.

Only the root-level facade receives long-term stability guarantees. A
domain-specific function becomes a candidate for root-level promotion only
after its scientific contract, provenance, dependencies, and downstream use
are reviewed.

## GUNW workflow status

The canonical NISAR workflow is explicitly composed:

```python
from snowin import compute_dswe
from snowin.io import add_gunw_incidence, open_gunw

pair = open_gunw("product.h5")
add_gunw_incidence(pair, "product.h5")
dswe = compute_dswe(
    pair["phase"],
    pair["incidence_angle"],
    wavelength_m=pair.attrs["wavelength_m"],
)
```

`gunw_to_dswe` is a legacy compatibility workflow. It retains the older
NumPy-oriented reader and configuration path and must not be treated as
scientifically interchangeable with the canonical two-step workflow. Current
Colorado evidence shows that its frozen `T0_DELIVERED` workflow consumes raw
GUNW phase with a historical sign convention, so it must not be silently
rewired to the canonical path. Retirement or an explicitly configured
migration can happen after Colorado approves the boundary and post-migration
output comparisons.
