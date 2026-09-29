# SnowIn API policy

SnowIn is a small scientific package for snow-focused InSAR retrievals. Its
stable root API operates on normalized xarray objects. Product adapters and
geometry functions live in domain modules; product search, cloud staging,
ancillary-data access, file export, and plotting stay in companion workflows.

## Core API

The root facade exports the named xarray retrieval methods, reference-phase
operations, support composition and metrics, and directed temporal
accumulation. It does not expose product-specific readers or study policies.

    from snowin import (
        accumulate_dswe,
        build_support_dataset,
        compose_support_mask,
        compute_dswe,
        compute_guneriussen_dswe,
        compute_leinss_dswe,
        compute_metrics,
        compute_oveisgharan_dswe,
        reference_phase,
        summarize_support,
    )

Use one named retrieval function per scientific model. The compute_dswe name
continues to mean the Leinss retrieval; it is not a model dispatcher. Inputs
must already use SnowIn's canonical secondary-minus-reference phase and
explicit units and coordinates.

## NISAR adapter

The NISAR adapter is optional and product-specific. It reads local GUNW
products through nisar-pytools and normalizes phase and product metadata:

    from snowin.io import open_gunw

    pair = open_gunw("product.h5")

Local-incidence geometry is a separate optional capability. It requires a
caller-prepared DEM and does not download or cache ancillary data:

    from snowin.io import add_gunw_incidence

    add_gunw_incidence(
        pair,
        "product.h5",
        dem="/path/to/prepared_dem.tif",
        dem_source="nisar_cop30",
    )

The optional package extras are nisar for GUNW reading, geometry for local
incidence, and dask for Dask-backed arrays. The base installation remains
NumPy and xarray.

## Caller-owned workflow operations

Use nisar-pytools directly for ASF search and validated downloads. Companion
tools or study workflows prepare SNOTEL, CDEC, ASO, lidar, DEM, vector masks,
and other ancillary inputs. They pass aligned arrays or local file paths to
SnowIn. Matplotlib and xarray's plotting methods are available in notebook and
workflow environments; SnowIn has no custom plotting, report, or CLI layer.

SnowIn no longer exposes the legacy NumPy phase_to_dswe dispatcher,
phase_raster_to_dswe, gunw_to_dswe, or the default GUNW quality-mask policy.
Use named xarray retrieval methods and compose explicit support layers.
Study workflows that previously used those convenience functions should
migrate their inputs and policy choices in their own repository.

## Dependency groups

Development, docs, and notebook requirements use PEP 735 dependency groups.
The PyPA specification says group contents are not included in built package
metadata; runtime capabilities that users install by feature remain optional
extras. See the
[PyPA dependency-groups specification](https://packaging.python.org/en/latest/specifications/dependency-groups/).

Only promote a product adapter or convenience API when SnowIn can maintain its
scientific contract, dependency set, documentation, and downstream use.
