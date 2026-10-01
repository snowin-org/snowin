"""Synthetic tests for the normalized SnowIn data contract."""

import numpy as np
import pytest

xr = pytest.importorskip("xarray")

_KNOWN_PHASE_DEFINITIONS = {
    "secondary_minus_reference",
    "reference_minus_secondary",
}


def _validate_phase_metadata(attrs):
    """Executable form of the source-convention contract."""
    if attrs.get("phase_difference_definition") != "secondary_minus_reference":
        raise ValueError("normalized phase must use secondary_minus_reference")

    source = attrs.get("source_phase_difference_definition")
    if source not in _KNOWN_PHASE_DEFINITIONS:
        raise ValueError("source phase convention is missing or unknown")

    expected_transform = (
        "identity" if source == "secondary_minus_reference" else "multiply_by_-1"
    )
    if attrs.get("phase_transform") != expected_transform:
        raise ValueError("phase transform does not match source convention")


def _synthetic_pair_dataset(
    *, phase_definition: str = "secondary_minus_reference"
) -> xr.Dataset:
    """Build a small pair Dataset without private product data."""
    y = np.array([4200.0, 4190.0])
    x = np.array([500000.0, 500010.0, 500020.0])
    grid_mapping = "spatial_ref"

    phase = xr.DataArray(
        np.array([[0.2, np.nan, -0.1]] * 2),
        dims=("y", "x"),
        coords={"y": y, "x": x},
        attrs={
            "units": "rad",
            "phase_kind": "unwrapped_interferometric_phase",
            "grid_mapping": grid_mapping,
        },
        name="phase",
    )
    incidence = xr.DataArray(
        np.deg2rad(np.full((2, 3), 35.0)),
        dims=("y", "x"),
        coords={"y": y, "x": x},
        attrs={
            "units": "rad",
            "incidence_angle_reference": "ellipsoid",
            "grid_mapping": grid_mapping,
        },
        name="incidence_angle",
    )
    ds = xr.Dataset(
        {
            "phase": phase,
            "incidence_angle": incidence,
            "product_valid": xr.DataArray(
                np.array([[True, False, True]] * 2),
                dims=("y", "x"),
                coords={"y": y, "x": x},
                attrs={"grid_mapping": grid_mapping},
            ),
            "coherence": xr.DataArray(
                np.full((2, 3), 0.8),
                dims=("y", "x"),
                coords={"y": y, "x": x},
                attrs={"units": "1", "grid_mapping": grid_mapping},
            ),
            "connected_component": xr.DataArray(
                np.ones((2, 3), dtype=np.int32),
                dims=("y", "x"),
                coords={"y": y, "x": x},
                attrs={"grid_mapping": grid_mapping},
            ),
        },
        coords={
            "spatial_ref": xr.DataArray(
                0,
                attrs={
                    "epsg_code": 32611,
                    "spatial_ref": "EPSG:32611",
                },
            )
        },
        attrs={
            "snowin_schema_version": "0.1",
            "snowin_data_state": "retrieval_ready_pair",
            "product_kind": "pairwise_interferogram",
            "reference_time": "2025-01-01T00:00:00Z",
            "secondary_time": "2025-01-13T00:00:00Z",
            "temporal_edge": "reference_to_secondary",
            "phase_difference_definition": phase_definition,
            "source_phase_difference_definition": "reference_minus_secondary",
            "phase_transform": "multiply_by_-1",
            "wavelength_m": 0.24,
        },
    )
    ds["x"].attrs.update({"axis": "X", "units": "m"})
    ds["y"].attrs.update({"axis": "Y", "units": "m"})
    return ds


def test_pair_contract_has_one_aligned_spatial_grid_and_explicit_units():
    ds = _synthetic_pair_dataset()

    assert ds.sizes == {"y": 2, "x": 3}
    assert tuple(ds["phase"].dims) == ("y", "x")
    assert tuple(ds["incidence_angle"].dims) == ("y", "x")
    assert ds["x"].attrs["units"] == "m"
    assert ds["y"].attrs["units"] == "m"
    assert ds["phase"].attrs["units"] == "rad"
    assert ds["incidence_angle"].attrs["units"] == "rad"
    assert ds["incidence_angle"].attrs["incidence_angle_reference"] == "ellipsoid"
    assert ds["phase"].attrs["grid_mapping"] == "spatial_ref"
    assert ds["spatial_ref"].attrs["epsg_code"] == 32611


def test_pair_direction_and_phase_definition_are_explicit():
    ds = _synthetic_pair_dataset()

    assert ds.attrs["temporal_edge"] == "reference_to_secondary"
    assert ds.attrs["reference_time"] < ds.attrs["secondary_time"]
    assert ds.attrs["phase_difference_definition"] == "secondary_minus_reference"
    assert ds.attrs["snowin_schema_version"] == "0.1"
    assert ds.attrs["source_phase_difference_definition"] == (
        "reference_minus_secondary"
    )
    assert ds.attrs["phase_transform"] == "multiply_by_-1"
    _validate_phase_metadata(ds.attrs)
    assert ds.attrs["wavelength_m"] > 0


def test_absent_layer_differs_from_invalid_present_sample():
    ds = _synthetic_pair_dataset()

    assert "ionosphere_phase" not in ds
    assert np.isnan(ds["phase"].values[0, 1])
    assert not bool(ds["product_valid"].values[0, 1])
    assert ds["product_valid"].dtype == bool


def test_support_diagnostics_and_components_remain_distinct():
    ds = _synthetic_pair_dataset()

    assert "quality_mask" not in ds
    assert "product_valid" in ds
    assert "coherence" in ds
    assert "connected_component" in ds
    assert ds["connected_component"].dtype == np.int32


def test_phase_definition_cannot_be_omitted_from_pair_metadata():
    ds = _synthetic_pair_dataset()
    del ds.attrs["phase_difference_definition"]

    required = {
        "snowin_schema_version",
        "product_kind",
        "reference_time",
        "secondary_time",
        "temporal_edge",
        "phase_difference_definition",
        "source_phase_difference_definition",
        "phase_transform",
        "wavelength_m",
    }
    assert required - ds.attrs.keys() == {"phase_difference_definition"}


def test_unknown_source_phase_convention_is_not_a_valid_contract_value():
    ds = _synthetic_pair_dataset()

    _validate_phase_metadata(ds.attrs)
    ds.attrs["source_phase_difference_definition"] = "unknown"
    with pytest.raises(ValueError, match="missing or unknown"):
        _validate_phase_metadata(ds.attrs)


def test_missing_source_phase_convention_fails():
    ds = _synthetic_pair_dataset()
    del ds.attrs["source_phase_difference_definition"]

    with pytest.raises(ValueError, match="missing or unknown"):
        _validate_phase_metadata(ds.attrs)
