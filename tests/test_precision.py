"""Package-wide Float32 science boundaries, with native coordinate precision."""

import math
from datetime import UTC, datetime, timedelta

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
    summarize_support,
)
from snowin.io import (
    add_gunw_incidence,
    compute_local_incidence,
    normalize_gunw_pair,
    open_gunw,
)
from snowin.reference import (
    apply_reference_offset,
    estimate_reference_offset,
    reference_phase,
)

PHASE_ATTRS = {
    "units": "rad",
    "phase_difference_definition": "reference_minus_secondary",
}
# Offsets too small to survive a Float32 coordinate cast protect grid precision.
COORDS = {
    "y": np.array([4200000.125, 4199990.125]),
    "x": np.array([500000.001, 500010.001]),
}
ANGLE = math.radians(35)
WAVELENGTH = 0.24


def _array(values, *, dtype=np.float64, lazy=False, attrs=None):
    result = xr.DataArray(
        np.asarray(values, dtype=dtype),
        dims=("y", "x"),
        coords=COORDS,
        attrs=attrs,
        name="science",
    )
    if lazy:
        pytest.importorskip("dask.array")
        result = result.chunk({"y": 1, "x": 1})
    return result


def _pair(dtype=np.float64, lazy=False):
    # Deliberately caller-produced, so referencing must normalize its inputs.
    phase = _array(
        [[1.2, -1.2], [0, np.nan]], dtype=dtype, lazy=lazy, attrs=PHASE_ATTRS
    )
    return xr.Dataset(
        {"phase": phase, "coherence": xr.full_like(phase, 0.8)},
        coords={
            "spatial_ref": xr.DataArray(
                0,
                attrs={
                    "epsg_code": 32611,
                    "GeoTransform": "499995.001 10 0 4200005.125 0 -10",
                },
            )
        },
        attrs={"phase_difference_definition": "reference_minus_secondary"},
    )


def _assert_science_dtypes(result):
    for name, variable in result.data_vars.items():
        if name != "spatial_ref" and variable.dtype.kind == "f":
            assert variable.dtype == np.float32, name


@pytest.mark.parametrize("lazy", [False, True])
def test_normalization_preserves_native_grid_and_casts_only_science(lazy):
    pair = _pair(lazy=lazy)
    angle = xr.full_like(pair.phase, ANGLE)
    angle.attrs = {"units": "rad", "incidence_angle_reference": "local"}
    labels = xr.full_like(pair.phase, 4, dtype=np.int32)
    support = xr.full_like(pair.phase, True, dtype=bool)
    result = normalize_gunw_pair(
        pair.phase,
        angle,
        wavelength_m=WAVELENGTH,
        reference_time="2025-01-01T00:00:00Z",
        secondary_time="2025-01-13T00:00:00Z",
        source_phase_difference_definition="reference_minus_secondary",
        spatial_ref=pair.spatial_ref,
        additional_variables={
            "coherence": pair.coherence,
            "connected_component": labels,
            "product_valid": support,
        },
    )
    _assert_science_dtypes(result)
    assert result.connected_component.dtype == np.int32
    assert result.product_valid.dtype == bool
    for name in ("x", "y", "spatial_ref"):
        xr.testing.assert_identical(result[name], pair[name])
    np.testing.assert_array_equal(result.phase, pair.phase.astype(np.float32))
    assert result.attrs["phase_transform"] == "identity"
    assert pair.phase.dtype == np.float64  # Caller storage is unchanged.
    if lazy:
        for name in result.data_vars:
            assert result[name].chunks is not None


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
@pytest.mark.parametrize("lazy", [False, True])
def test_gunw_ingestion_canonicalizes_all_science_layers(tmp_path, dtype, lazy):
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "precision.h5"
    _write_synthetic_gunw(
        h5netcdf,
        path,
        science_dtype=np.dtype(dtype),
        include_connected_components=True,
        x_coordinates=COORDS["x"],
        y_coordinates=COORDS["y"],
    )
    delivered = np.array([[1.234567, -2.345678], [0, np.nan]], dtype=dtype)
    with h5netcdf.File(path, "a") as source:
        source[
            "science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/unwrappedPhase"
        ][:] = delivered
    with open_gunw(path, chunks="auto" if lazy else None, progress=False) as result:
        _assert_science_dtypes(result)
        np.testing.assert_array_equal(result.phase, delivered.astype(np.float32))
        assert result.connected_component.dtype == np.int32
        np.testing.assert_array_equal(result.connected_component, [[4, 4], [8, 8]])
        for name, coordinate in {
            "x": COORDS["x"],
            "y": COORDS["y"],
            "radar_x": COORDS["x"],
            "radar_y": COORDS["y"],
        }.items():
            assert result[name].dtype == np.float64
            np.testing.assert_array_equal(result[name], coordinate)
        assert result.radar_height.dtype == np.float64
        for name in (
            "phase",
            "coherence",
            "ionosphere",
            "ionosphere_unc",
            "hydro_tropo",
            "wet_tropo",
            "connected_component",
        ):
            if lazy:
                assert result[name].chunks is not None
            else:
                assert result[name].chunks is None
        assert (
            result.phase.attrs["phase_difference_definition"]
            == "reference_minus_secondary"
        )
        assert (
            result.phase.attrs["source_phase_difference_definition"]
            == "reference_minus_secondary"
        )
        assert result.phase.attrs["phase_transform"] == "identity"
        assert result.attrs["snowin_schema_version"] == "0.2"


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
@pytest.mark.parametrize("dtype", [np.float32, np.float64])
@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("scalar", [False, True])
def test_retrieval_precision_and_independent_equations(
    method, model, dtype, lazy, scalar
):
    phase = _pair(dtype, lazy).phase
    angle = xr.full_like(phase, ANGLE)
    angle.attrs = {"units": "rad", "incidence_angle_reference": "local"}
    density = xr.full_like(phase, 500.0)
    density.attrs = {"units": "kg m-3"}
    if scalar:
        phase, angle, density = (
            array.isel(y=0, x=0, drop=True) for array in (phase, angle, density)
        )
    kwargs = {}
    if model:
        rho = 0.5
        epsilon = {
            "guneriussen2001": 1 + 1.6 * rho + 1.8 * rho**3,
            "webb2021": 1 + 0.0014 * 500 + 2e-7 * 500**2,
            "maetzler": ((1 - rho / 0.917) + 1.4759 * (rho / 0.917)) ** 3,
        }[model]
        coefficient = (
            WAVELENGTH
            * rho
            / (
                -4
                * math.pi
                * (math.cos(ANGLE) - math.sqrt(epsilon - math.sin(ANGLE) ** 2))
            )
        )
        kwargs = {"snow_density_kg_m3": density, "permittivity_model": model}
    elif method is compute_leinss_dswe:
        coefficient = WAVELENGTH / (2 * math.pi * 1.1 * (1.59 + ANGLE**2.5))
        kwargs = {"alpha": np.float64(1.1)}
    else:
        coefficient = WAVELENGTH / (
            -4 * math.pi * (-0.6784 * ANGLE**2 + 0.2899 * ANGLE - 0.8473)
        )
    result = method(phase, angle, wavelength_m=np.float64(WAVELENGTH), **kwargs)
    assert result.dtype == np.float32
    if lazy:
        assert result.chunks is not None
    # A few ppm cover Float32 input/constant rounding and refraction subtraction.
    np.testing.assert_allclose(
        result, phase.values * coefficient, rtol=2e-6, atol=2e-9, equal_nan=True
    )
    assert result.coords.equals(phase.coords)
    assert result.attrs["phase_difference_definition"] == "reference_minus_secondary"
    assert result.attrs["dswe_difference_definition"] == "secondary_minus_reference"
    assert result.attrs["units"] == "m"


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize(
    "method,expected_offset",
    [
        ("coherence_weighted_additive_offset", 1.25),
        ("mean_additive_offset", 1.0),
        ("median_additive_offset", 1.0),
        ("single_station_offset", 0.5),
    ],
)
def test_reference_contributors_and_offset_use_float32(method, expected_offset, lazy):
    count = 1 if method == "single_station_offset" else 3
    coords = {"station": np.arange(count) + 0.00000001}
    observed = xr.DataArray(
        [1.5, 2.0, 2.5][:count], dims="station", coords=coords, attrs=PHASE_ATTRS
    )
    expected = xr.ones_like(observed)
    weight = xr.DataArray([1.0, 2.0, 5.0][:count], dims="station", coords=coords)
    if lazy:
        pytest.importorskip("dask.array")
        observed, expected, weight = (
            array.chunk({"station": 1}) for array in (observed, expected, weight)
        )
    estimate = estimate_reference_offset(observed, expected, weight, method=method)
    _assert_science_dtypes(estimate)
    # Exact dyadic residuals, and a weighted numerator of 10 / total weight 8.
    assert estimate.reference_offset_rad.item() == expected_offset
    np.testing.assert_array_equal(estimate.reference_residual, [0.5, 1.0, 1.5][:count])
    np.testing.assert_array_equal(
        estimate.reference_weighted_contribution, [0.5, 2.0, 7.5][:count]
    )
    xr.testing.assert_identical(
        estimate.reference_contributor,
        observed.station.rename({"station": "reference_contributor"}).rename(
            "reference_contributor"
        ),
    )
    assert estimate.reference_eligible.dtype == bool
    assert estimate.reference_eligible_count.dtype.kind in "iu"
    if lazy:
        for name in (
            "reference_observed_phase",
            "reference_expected_phase",
            "reference_weight",
            "reference_residual",
            "reference_weighted_contribution",
        ):
            assert estimate[name].chunks is not None
    # Apply an externally supplied Float64 estimate as well.
    external = estimate.copy(deep=False)
    external["reference_offset_rad"] = estimate.reference_offset_rad.astype(np.float64)
    result = apply_reference_offset(_pair(lazy=lazy), external)
    _assert_science_dtypes(result)
    if lazy:
        assert result.phase_referenced.chunks is not None
    assert result.phase_referenced.coords.equals(result.phase.coords)
    np.testing.assert_allclose(
        result.phase_referenced,
        [[1.2 - expected_offset, -1.2 - expected_offset], [-expected_offset, np.nan]],
        rtol=2e-6,
        atol=2e-7,
        equal_nan=True,
    )


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("supported", [False, True])
def test_reference_manual_and_missing_estimates_remain_float32(lazy, supported):
    if supported:
        result = reference_phase(
            _pair(lazy=lazy), method="manual_offset", offset_rad=0.123456789
        )
    else:
        missing = xr.DataArray([np.nan], dims="station", attrs=PHASE_ATTRS)
        result = reference_phase(
            _pair(lazy=lazy), missing, missing, xr.ones_like(missing)
        )
    _assert_science_dtypes(result)
    assert result.reference_estimate_supported.dtype == bool
    assert bool(result.reference_estimate_supported) == supported
    if not supported:
        assert np.isnan(result.phase_referenced).all()
    if lazy:
        assert result.phase_referenced.chunks is not None


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_temporal_precision_through_many_edges_and_missing_support(lazy, dtype):
    edges = []
    for index in range(8):
        start = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=12 * index)
        end = start + timedelta(days=12)
        dswe = _array(
            [[0.125, np.nan if index == 0 else 1], [-0.25, 0.5]],
            dtype=dtype,
            lazy=lazy,
            attrs={
                "units": "m",
                "dswe_difference_definition": "secondary_minus_reference",
            },
        )
        support = xr.full_like(dswe, True, dtype=bool)
        if index == 1:
            support = support & (dswe.x != COORDS["x"][1])
        edges.append(
            xr.Dataset(
                {"dswe": dswe, "pairwise_supported": support},
                attrs={
                    "reference_time": start.isoformat(),
                    "secondary_time": end.isoformat(),
                    "temporal_edge": "reference_to_secondary",
                },
            )
        )
    result = accumulate_dswe(edges)
    assert result.cumulative_dswe.dtype == np.float32
    assert result.temporal_path_supported.dtype == bool
    assert result.time.dtype == np.dtype("datetime64[ns]")
    if lazy:
        assert result.cumulative_dswe.chunks is not None
        assert result.temporal_path_supported.chunks is not None
    for name in ("x", "y"):
        xr.testing.assert_identical(result[name], edges[0][name])
    expected = np.array(
        [
            [[0.125 * n, np.nan], [-0.25 * n, 0.5 if n == 1 else np.nan]]
            for n in range(1, 9)
        ],
        dtype=np.float32,
    )
    np.testing.assert_array_equal(result.cumulative_dswe, expected)
    np.testing.assert_array_equal(result.temporal_path_supported, np.isfinite(expected))


@pytest.mark.parametrize("lazy", [False, True])
def test_support_precision_preserves_unknowns_and_integer_and_boolean_masks(lazy):
    floating = _array([[1, 0], [np.nan, 1]], lazy=lazy)
    integer = xr.ones_like(floating, dtype=np.int16)
    boolean = xr.ones_like(floating, dtype=bool)
    result = build_support_dataset(floating=floating, integer=integer, boolean=boolean)
    assert result.floating.dtype == np.float32
    assert result.integer.dtype == np.int16
    assert result.boolean.dtype == bool
    summary = summarize_support(result)
    _assert_science_dtypes(summary)
    assert summary.known_count.dtype == np.int64
    # One division rounded to Float32, including the 2/3 support fraction.
    np.testing.assert_allclose(
        summary.support_fraction, [2 / 3, 1, 1], rtol=1e-7, atol=0
    )
    assert compose_support_mask(result, ["floating"]).dtype == bool
    if lazy:
        assert result.floating.chunks is not None
    np.testing.assert_array_equal(result.floating, floating)


@pytest.mark.parametrize("lazy", [False, True])
def test_local_incidence_science_precision_preserves_geometry_grid(lazy):
    shape = (2, 2, 2)
    dem = _array([[100, 100], [100, np.nan]], attrs={"units": "m", "epsg_code": 32611})
    incidence = compute_local_incidence(
        dem,
        np.full(shape, math.sin(ANGLE)),
        np.zeros(shape),
        np.full(shape, math.cos(ANGLE)),
        np.array([0, 200]),
        COORDS["x"],
        COORDS["y"],
        epsg_code=32611,
        geometry_chunks=(1, 1) if lazy else None,
        progress=False,
    )
    assert incidence.dtype == np.float32
    assert incidence.coords.equals(dem.coords)
    assert incidence.attrs["epsg_code"] == 32611
    if lazy:
        assert incidence.chunks is not None
    # Gradient neighbors of missing elevation have missing normals; the remaining
    # top-left normal is flat, so its exact analytical incidence is ANGLE.
    np.testing.assert_allclose(
        incidence,
        [[ANGLE, np.nan], [np.nan, np.nan]],
        rtol=1e-7,
        atol=1e-7,
        equal_nan=True,
    )


@pytest.mark.parametrize("resample", [False, True])
def test_ellipsoid_incidence_cast_after_resampling_preserves_grid(tmp_path, resample):
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "geometry.h5"
    _write_synthetic_gunw(
        h5netcdf, path, x_coordinates=COORDS["x"], y_coordinates=COORDS["y"]
    )
    with open_gunw(path, chunks=None, progress=False) as pair:
        pair.spatial_ref.attrs["GeoTransform"] = "499995.001 10 0 4200005.125 0 -10"
        pair["phase"] = pair.phase.astype(np.float64)
        if resample:
            pair = pair.assign_coords(
                x=COORDS["x"] + np.array([1, -1]), y=COORDS["y"] + np.array([-1, 1])
            )
        coordinates = pair.coords.copy(deep=True)
        result = add_gunw_incidence(
            pair, path, incidence_source="product_ellipsoid", progress=False
        )
        assert result.incidence_angle.dtype == np.float32
        _assert_science_dtypes(result)
        assert result.coords.equals(coordinates)
        xr.testing.assert_identical(result.spatial_ref, coordinates["spatial_ref"])
        assert result.geometry_valid.dtype == bool
        assert result.geometry_valid.all()
        np.testing.assert_allclose(
            result.incidence_angle, math.pi / 6, rtol=1e-7, atol=1e-7
        )


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("bad", ["text", 1 + 2j])
def test_retrieval_boundary_rejects_unsupported_numeric_types(lazy, bad):
    phase = _array([[1, 1], [1, 1]], lazy=lazy, attrs=PHASE_ATTRS)
    angle = xr.full_like(phase, ANGLE)
    angle.attrs = {"units": "rad", "incidence_angle_reference": "local"}
    phase = phase.astype(str if isinstance(bad, str) else complex)
    with pytest.raises(TypeError, match="real numeric values"):
        compute_leinss_dswe(phase, angle, wavelength_m=WAVELENGTH)


def test_science_boundaries_do_not_execute_dask_graphs():
    pytest.importorskip("dask.array")
    from dask.callbacks import Callback

    pair = _pair(lazy=True)
    angle = xr.full_like(pair.phase, ANGLE)
    angle.attrs = {"units": "rad", "incidence_angle_reference": "local"}
    tasks = []
    with Callback(pretask=lambda key, *_: tasks.append(key)):
        normalized = normalize_gunw_pair(
            pair.phase,
            angle,
            wavelength_m=WAVELENGTH,
            reference_time="2025-01-01T00:00:00Z",
            secondary_time="2025-01-13T00:00:00Z",
            source_phase_difference_definition="reference_minus_secondary",
            spatial_ref=pair.spatial_ref,
        )
        referenced = reference_phase(normalized, method="manual_offset", offset_rad=0.1)
        referenced["dswe"] = compute_leinss_dswe(
            referenced.phase_referenced,
            referenced.incidence_angle,
            wavelength_m=WAVELENGTH,
        )
        accumulated = accumulate_dswe([referenced])
        support = build_support_dataset(known=xr.ones_like(pair.phase))
        mask = compose_support_mask(support, ["known"])
    assert tasks == []
    assert accumulated.cumulative_dswe.chunks is not None
    assert accumulated.cumulative_dswe.dtype == np.float32
    assert mask.chunks is not None


@pytest.mark.parametrize("lazy", [False, True])
def test_validation_checks_values_before_float32_rounding(lazy):
    support = _array([[1.0 + 1e-10, 1], [1, 1]], lazy=lazy)
    if lazy:
        checked = build_support_dataset(known=support)
        assert checked.known.dtype == np.float32
        with pytest.raises(ValueError, match="only 0, 1, or NaN"):
            checked.compute()
    else:
        with pytest.raises(ValueError, match="only 0, 1, or NaN"):
            build_support_dataset(known=support)
