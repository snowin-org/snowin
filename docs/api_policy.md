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
    compute_gun_dswe,
    compute_leinss_dswe,
    compute_ove_dswe,
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
from snowin.spatial import rasterize_vector_mask
```

Underscore-prefixed names are internal implementation details and are not part
of the public API. They may change without compatibility guarantees.

Legacy submodule APIs remain available where practical for compatibility, but
are not recommended for new workflows. In particular, use
`snowin.reference.reference_phase` instead of the older
`snowin.reference.apply_reference_phase`, and use a named retrieval such as
`snowin.compute_leinss_dswe` instead of the older NumPy method-selector
functions in `snowin.snow`. `snowin.compute_dswe` remains a compatibility
spelling of the Leinss method.

Only the root-level facade receives long-term stability guarantees. A
domain-specific function becomes a candidate for root-level promotion only
after its scientific contract, provenance, dependencies, and downstream use
are reviewed.

## GUNW workflow status

The canonical NISAR workflow is explicitly composed:

```python
from snowin import compute_leinss_dswe
from snowin.io import add_gunw_incidence, open_gunw

pair = open_gunw("product.h5")
add_gunw_incidence(pair, "product.h5")
dswe = compute_leinss_dswe(
    pair["phase"],
    pair["incidence_angle"],
    wavelength_m=pair.attrs["wavelength_m"],
)
```

`gunw_to_dswe` is a legacy compatibility workflow. It retains the older
reader and configuration path and must not be treated as scientifically
interchangeable with the canonical two-step workflow. New code should use the
product adapter to normalize phase and preserve product metadata, then select
the named dSWE method whose assumptions match the intended retrieval.

## Wavelength policy

The dSWE methods accept a positive `wavelength_m` or an explicitly selected
stock `sensor` and `band`. For NISAR GUNW products, the adapter resolves
wavelength from the product `centerFrequency` metadata using `c / f` and
records the source in `wavelength_source`. `compute_dswe` remains a
backwards-compatible spelling of the Leinss method. SnowIn does not guess a
sensor, silently substitute a wavelength, or reconcile conflicting sources.
