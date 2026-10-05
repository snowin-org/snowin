"""Independent signed equation and schema 0.2 pipeline regressions."""

import math

import numpy as np
import pytest
import xarray as xr
from test_nisar_adapter import _write_synthetic_gunw

from snowin import (
    accumulate_dswe,
    build_support_dataset,
    compose_support_mask,
    compute_guneriussen_dswe,
    compute_leinss_dswe,
    compute_oveisgharan_dswe,
    reference_phase,
)
from snowin.io import NISAR_GUNW_PHASE_TRANSFORM, normalize_gunw_pair, open_gunw
from snowin.reference import apply_reference_offset, estimate_reference_offset

CANONICAL = "reference_minus_secondary"
OPPOSITE = "secondary_minus_reference"
WAVELENGTH = 0.24
ANGLE = math.radians(35)


def _inputs(values, lazy=False):
    values = np.asarray([values], dtype=float)
    if lazy:
        da = pytest.importorskip("dask.array")
        values = da.from_array(values, chunks=(1, 2))
    phase = xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"y": [10.0], "x": np.arange(values.shape[1])},
        attrs={"units": "rad", "phase_difference_definition": CANONICAL},
    )
    angle = xr.full_like(phase, ANGLE)
    angle.attrs = {"units": "rad", "incidence_angle_reference": "local"}
    return phase, angle


def _normalize(phase, angle, source=CANONICAL, start=1, end=13):
    return normalize_gunw_pair(
        phase,
        angle,
        wavelength_m=WAVELENGTH,
        reference_time=f"2025-01-{start:02}T00:00:00Z",
        secondary_time=f"2025-01-{end:02}T00:00:00Z",
        source_phase_difference_definition=source,
        spatial_ref=xr.DataArray(0, attrs={"epsg_code": 32611}),
    )


@pytest.mark.parametrize("lazy", [False, True])
def test_opposite_phase_converts_once_and_canonical_reingestion_is_identity(lazy):
    phase, angle = _inputs([1, -2, 0, np.nan], lazy)
    phase.attrs["phase_difference_definition"] = OPPOSITE
    converted = _normalize(phase, angle, OPPOSITE)
    identity = _normalize(converted.phase, converted.incidence_angle)
    if lazy:
        assert hasattr(converted.phase.data, "chunks")
        assert hasattr(identity.phase.data, "chunks")
    np.testing.assert_allclose(converted.phase, -phase, rtol=0, atol=0, equal_nan=True)
    xr.testing.assert_equal(converted.phase, identity.phase)
    assert phase.attrs["phase_difference_definition"] == OPPOSITE
    assert "phase_transform" not in phase.attrs
    assert converted.attrs["phase_transform"] == "multiply_by_-1"
    assert converted.phase.attrs["source_phase_difference_definition"] == OPPOSITE
    assert identity.attrs["phase_transform"] == NISAR_GUNW_PHASE_TRANSFORM == "identity"
    assert identity.attrs["dswe_difference_definition"] == OPPOSITE
    assert identity.attrs["snowin_schema_version"] == "0.2"
    assert identity.phase.attrs["snowin_schema_version"] == "0.2"
    with pytest.raises(ValueError, match="conflicts"):
        _normalize(converted.phase, angle, OPPOSITE)


@pytest.mark.parametrize("lazy", [False, True])
def test_reader_preserves_delivered_signed_phase_and_file_cleanup(tmp_path, lazy):
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "gunw.h5"
    _write_synthetic_gunw(h5netcdf, path)
    delivered = np.array([[1, -2], [0, np.nan]], dtype=np.float32)
    with h5netcdf.File(path, "a") as source:
        group = source["science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH"]
        group["unwrappedPhase"][:] = delivered
    pair = open_gunw(path, chunks="auto" if lazy else None, progress=False)
    # Spy on the actual close callback, then invoke Dataset.close().
    close = pair._close
    closed = []

    def close_spy():
        close()
        closed.append(True)

    pair.set_close(close_spy)
    try:
        if lazy:
            assert hasattr(pair.phase.data, "chunks")
        np.testing.assert_allclose(
            pair.phase, delivered, rtol=0, atol=0, equal_nan=True
        )
        assert pair.attrs["source_phase_difference_definition"] == CANONICAL
        assert pair.phase.attrs["phase_difference_definition"] == CANONICAL
        assert pair.phase.attrs["phase_transform"] == "identity"
        assert pair.phase.attrs["units"] == "rad"
        np.testing.assert_allclose(pair.ionosphere, [[0.1, 0.2], [0.3, 0.4]])
    finally:
        pair.close()
    assert closed == [True]


@pytest.mark.parametrize(
    "method,model",
    [
        (compute_leinss_dswe, None),
        (compute_oveisgharan_dswe, None),
        *[
            (compute_guneriussen_dswe, model)
            for model in ("guneriussen2001", "webb2021", "maetzler")
        ],
    ],
)
@pytest.mark.parametrize("lazy", [False, True])
def test_signed_retrievals_match_independent_physical_equations(method, model, lazy):
    phase, angle = _inputs([1.2, -1.2, 0, np.nan], lazy)
    kwargs = {}
    if method is compute_leinss_dswe:
        coefficient = WAVELENGTH / (2 * math.pi * (1.59 + ANGLE**2.5))
    elif method is compute_oveisgharan_dswe:
        a = -0.6784 * ANGLE**2 + 0.2899 * ANGLE - 0.8473
        coefficient = WAVELENGTH / (-4 * math.pi * a)
    else:
        density = 300.0
        rho = density / 1000
        epsilon = {
            "guneriussen2001": 1 + 1.6 * rho + 1.8 * rho**3,
            "webb2021": 1 + 1.4e-3 * density + 2e-7 * density**2,
            "maetzler": 1 + 1.5995 * rho + 1.861 * rho**3,
        }[model]
        c = math.cos(ANGLE) - math.sqrt(epsilon - math.sin(ANGLE) ** 2)
        coefficient = (density / 1000) * WAVELENGTH / (-4 * math.pi * c)
        kwargs = {"snow_density_kg_m3": density, "permittivity_model": model}
    assert coefficient > 0
    result = method(phase, angle, wavelength_m=WAVELENGTH, **kwargs)
    if lazy:
        assert hasattr(result.data, "chunks")
    # Closed-form float64 equations agree to roundoff; no empirical tolerance.
    np.testing.assert_allclose(
        result,
        [[1.2 * coefficient, -1.2 * coefficient, 0, np.nan]],
        rtol=1e-13,
        atol=1e-15,
        equal_nan=True,
    )
    assert result.attrs["dswe_difference_definition"] == OPPOSITE
    assert result.attrs["phase_difference_definition"] == CANONICAL
    assert result.attrs["units"] == "m"


@pytest.mark.parametrize("lazy", [False, True])
def test_signed_ingestion_reference_support_retrieval_and_accumulation(lazy):
    edges = []
    # Independently specified physical SWE changes generate snow phase.
    coefficient = WAVELENGTH / (2 * math.pi * (1.59 + ANGLE**2.5))
    for snow_change, start, end in [(0.04, 1, 13), (-0.01, 13, 25)]:
        phase, angle = _inputs([snow_change / coefficient + 0.3] * 3 + [np.nan], lazy)
        pair = _normalize(phase, angle, start=start, end=end)
        attrs = {"units": "rad", "phase_difference_definition": CANONICAL}
        observed = xr.DataArray([0.5, 0.7], dims="station", attrs=attrs)
        expected = xr.DataArray([0.2, 0.4], dims="station", attrs=attrs)
        weights = xr.DataArray([1.0, 3.0], dims="station")
        referenced = reference_phase(pair, observed, expected, weights)
        assert referenced.reference_offset_rad.item() == pytest.approx(0.3)
        support = build_support_dataset(
            product_valid=xr.DataArray(
                [[True, False, True, True]], dims=phase.dims, coords=phase.coords
            )
        )
        mask = compose_support_mask(support, ["product_valid"])
        referenced["dswe"] = compute_leinss_dswe(
            referenced.phase_referenced,
            referenced.incidence_angle,
            wavelength_m=WAVELENGTH,
        ).where(mask)
        referenced["pairwise_supported"] = mask
        edges.append(referenced)
    result = accumulate_dswe(edges)
    if lazy:
        assert hasattr(result.cumulative_dswe.data, "chunks")
    np.testing.assert_allclose(
        result.cumulative_dswe,
        [[[0.04, np.nan, 0.04, np.nan]], [[0.03, np.nan, 0.03, np.nan]]],
        rtol=1e-13,
        atol=1e-15,
        equal_nan=True,
    )
    assert result.attrs["temporal_edge"] == "reference_to_secondary"
    assert result.cumulative_dswe.attrs["dswe_difference_definition"] == OPPOSITE
    assert edges[0].attrs["reference_time"] == "2025-01-01T00:00:00Z"
    assert edges[1].attrs["secondary_time"] == "2025-01-25T00:00:00Z"
    assert result.spatial_ref.attrs["epsg_code"] == 32611


def test_legacy_schema_cannot_pass_by_relabeling_phase_or_pair():
    phase, angle = _inputs([1, -1])
    pair = _normalize(phase, angle)
    pair.attrs["snowin_schema_version"] = "0.1"
    with pytest.raises(ValueError, match="legacy"):
        reference_phase(pair, method="manual_offset", offset_rad=0)
    phase.attrs["snowin_schema_version"] = "0.1"
    with pytest.raises(ValueError, match="legacy"):
        compute_leinss_dswe(phase, angle, wavelength_m=WAVELENGTH)
    with pytest.raises(ValueError, match="legacy"):
        _normalize(phase, angle)
    pair["dswe"] = xr.ones_like(phase)
    pair.dswe.attrs = {"units": "m"}
    with pytest.raises(ValueError, match="legacy"):
        accumulate_dswe([pair])


@pytest.mark.parametrize("definition", [None, "unknown", OPPOSITE])
def test_reference_rejects_noncanonical_contributors_and_offsets(definition):
    attrs = {"units": "rad", "phase_difference_definition": definition}
    contributor = xr.DataArray([1.0], dims="station", attrs=attrs)
    with pytest.raises(ValueError, match="phase_difference_definition"):
        estimate_reference_offset(contributor, contributor, xr.ones_like(contributor))
    phase, angle = _inputs([1])
    estimate = estimate_reference_offset(method="manual_offset", offset_rad=0.2)
    estimate.reference_offset_rad.attrs["phase_difference_definition"] = definition
    with pytest.raises(ValueError, match="phase_difference_definition"):
        apply_reference_offset(_normalize(phase, angle), estimate)


def test_explicit_legacy_conversion_preserves_dates_and_recomputes_dswe():
    phase, angle = _inputs([-1.2, 1.2])
    phase.attrs.update(
        snowin_schema_version="0.1", phase_difference_definition=OPPOSITE
    )
    pair = _normalize(phase, angle, OPPOSITE)
    assert pair.attrs["snowin_schema_version"] == "0.2"
    assert pair.attrs["reference_time"] == "2025-01-01T00:00:00Z"
    assert pair.attrs["secondary_time"] == "2025-01-13T00:00:00Z"
    assert pair.attrs["temporal_edge"] == "reference_to_secondary"
    coefficient = WAVELENGTH / (2 * math.pi * (1.59 + ANGLE**2.5))
    dswe = compute_leinss_dswe(
        pair.phase, pair.incidence_angle, wavelength_m=WAVELENGTH
    )
    np.testing.assert_allclose(
        dswe, [[1.2 * coefficient, -1.2 * coefficient]], rtol=1e-13, atol=1e-15
    )
