"""Data-free integration through SnowIn's normalized pairwise science path."""

from __future__ import annotations

import math

import numpy as np
import xarray as xr

from snowin import (
    accumulate_dswe,
    build_support_dataset,
    compose_support_mask,
    compute_leinss_dswe,
    reference_phase,
)
from snowin.io import normalize_gunw_pair

WAVELENGTH_M = 0.24
ANGLE_RAD = math.radians(35.0)
COORDS = {"y": [4200.0, 4190.0], "x": [500000.0, 500010.0]}


def _normalized_edge(
    true_phase_value: float,
    reference_offset_rad: float,
    reference_time: str,
    secondary_time: str,
    *,
    product_valid: np.ndarray,
) -> xr.Dataset:
    true_phase = np.full((2, 2), true_phase_value, dtype=np.float64)
    measured_phase = true_phase
    source_phase = xr.DataArray(
        -measured_phase,
        dims=("y", "x"),
        coords=COORDS,
        name="unwrappedPhase",
        attrs={"units": "radians"},
    )
    incidence = xr.DataArray(
        np.full((2, 2), ANGLE_RAD),
        dims=("y", "x"),
        coords=COORDS,
        name="incidence_angle",
        attrs={"units": "rad", "incidence_angle_reference": "local"},
    )
    spatial_ref = xr.DataArray(
        0,
        name="spatial_ref",
        attrs={"epsg_code": 32613, "spatial_ref": "EPSG:32613"},
    )
    pair = normalize_gunw_pair(
        source_phase,
        incidence,
        wavelength_m=WAVELENGTH_M,
        reference_time=reference_time,
        secondary_time=secondary_time,
        source_phase_difference_definition="reference_minus_secondary",
        spatial_ref=spatial_ref,
        source_granule_id="synthetic-integration-pair",
    )
    np.testing.assert_allclose(pair.phase.values, measured_phase)

    referenced = reference_phase(
        pair,
        method="manual_offset",
        offset_rad=reference_offset_rad,
    )

    expected_referenced_phase = true_phase - reference_offset_rad
    np.testing.assert_allclose(
        referenced.phase_referenced.values,
        expected_referenced_phase,
        rtol=0.0,
        atol=1e-14,
    )
    pairwise_dswe = compute_leinss_dswe(
        referenced.phase_referenced,
        referenced.incidence_angle,
        wavelength_m=WAVELENGTH_M,
    )
    support = build_support_dataset(
        product_valid=xr.DataArray(
            product_valid,
            dims=("y", "x"),
            coords=COORDS,
            name="product_valid",
        ),
        geometry_valid=xr.DataArray(
            np.ones((2, 2), dtype=bool),
            dims=("y", "x"),
            coords=COORDS,
            name="geometry_valid",
        ),
    )
    pairwise_supported = compose_support_mask(
        support,
        ["product_valid", "geometry_valid"],
        name="pairwise_supported",
    )
    referenced["dswe"] = pairwise_dswe.where(pairwise_supported)
    referenced["dswe"].attrs.update({"units": "m", "quantity": "pairwise_dSWE"})
    referenced["pairwise_supported"] = pairwise_supported
    return referenced


def test_normalize_correct_reference_support_dswe_and_accumulate_pipeline():
    first = _normalized_edge(
        0.6,
        0.1,
        "2025-01-01T00:00:00Z",
        "2025-01-13T00:00:00Z",
        product_valid=np.array([[True, True], [False, True]]),
    )
    second = _normalized_edge(
        0.4,
        0.05,
        "2025-01-13T00:00:00Z",
        "2025-01-25T00:00:00Z",
        product_valid=np.ones((2, 2), dtype=bool),
    )

    accumulated = accumulate_dswe([first, second])
    coefficient = WAVELENGTH_M / (2.0 * math.pi * (1.59 + ANGLE_RAD**2.5))
    expected_final = np.full((2, 2), (0.5 + 0.35) * coefficient)
    expected_final[1, 0] = np.nan
    np.testing.assert_allclose(
        accumulated.cumulative_dswe.values[-1],
        expected_final,
        rtol=1e-13,
        atol=1e-14,
        equal_nan=True,
    )

    assert accumulated.cumulative_dswe.dims == ("time", "y", "x")
    assert accumulated.cumulative_dswe.attrs["units"] == "m"
    assert accumulated.attrs["temporal_edge_count"] == 2
    assert accumulated.attrs["missing_support_policy"] == (
        "propagate_missing; never substitute zero"
    )
    assert accumulated.spatial_ref.attrs["epsg_code"] == 32613
    np.testing.assert_array_equal(
        accumulated.temporal_path_supported.values[-1],
        [[True, True], [False, True]],
    )
