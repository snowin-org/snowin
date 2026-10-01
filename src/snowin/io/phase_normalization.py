"""Convert NISAR phase and build an xarray pair Dataset."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import datetime
from numbers import Real
from typing import Any

import numpy as np
import xarray as xr

from .._timestamps import iso_utc_timestamp, parse_utc_timestamp
from ._nisar_hdf5 import decode_hdf5_scalar

__all__ = [
    "NISAR_GUNW_PHASE_TRANSFORM",
    "NISAR_GUNW_SOURCE_PHASE_DEFINITION",
    "normalize_gunw_pair",
]

NISAR_GUNW_SOURCE_PHASE_DEFINITION = "reference_minus_secondary"
"""The source phase orientation encoded by the NISAR/ISCE3 GUNW product."""

NISAR_GUNW_PHASE_TRANSFORM = "multiply_by_-1"
"""Transformation from source phase to the SnowIn phase convention."""

_SNOWIN_PHASE_DEFINITION = "secondary_minus_reference"
_KNOWN_PHASE_DEFINITIONS = {
    "secondary_minus_reference",
    "reference_minus_secondary",
}


def _positive_scalar(name: str, value: object) -> float:
    if value is None:
        raise TypeError(f"{name} is missing; provide a finite positive value")
    if not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite positive scalar")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be finite and > 0")
    return result


def _iso_utc(value: object, name: str) -> str:
    return iso_utc_timestamp(value, name)


def _serializable_attrs(attrs: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in attrs.items():
        decoded = decode_hdf5_scalar(value)
        if isinstance(decoded, (str, int, float, bool)) or decoded is None:
            result[str(key)] = decoded
        else:
            result[str(key)] = json.dumps(decoded, default=str)
    return result


def _require_2d(name: str, value: xr.DataArray) -> None:
    if value.dims != ("y", "x"):
        raise ValueError(f"{name} must use dimensions ('y', 'x'); got {value.dims!r}")


def _require_aligned(phase: xr.DataArray, incidence_angle: xr.DataArray) -> None:
    _require_2d("phase", phase)
    _require_2d("incidence_angle", incidence_angle)
    if phase.sizes != incidence_angle.sizes:
        raise ValueError("phase and incidence_angle must have the same grid shape")
    for dim in ("y", "x"):
        if not np.array_equal(phase.coords[dim].data, incidence_angle.coords[dim].data):
            raise ValueError(
                f"phase and incidence_angle coordinates differ for {dim!r}"
            )


def _validate_source_convention(source: object) -> str:
    if source is None or (isinstance(source, str) and not source.strip()):
        raise ValueError(
            "source_phase_difference_definition is missing; provide a known "
            "phase difference definition"
        )
    if not isinstance(source, str) or source not in _KNOWN_PHASE_DEFINITIONS:
        raise ValueError(
            f"source phase definition {source!r} is unsupported; expected "
            "'reference_minus_secondary' or 'secondary_minus_reference'"
        )
    return str(source)


def _convert_source_phase(
    phase: xr.DataArray, source_definition: str
) -> tuple[xr.DataArray, str]:
    """Convert a known source phase direction to the SnowIn convention."""
    source_definition = _validate_source_convention(source_definition)
    if source_definition == "reference_minus_secondary":
        snowin_phase = -phase
        transform = NISAR_GUNW_PHASE_TRANSFORM
    else:
        snowin_phase = phase
        transform = "identity"

    snowin_phase = snowin_phase.rename("phase")
    snowin_phase.attrs = _serializable_attrs(phase.attrs)
    snowin_phase.attrs.update(
        {
            "units": "rad",
            "phase_difference_definition": _SNOWIN_PHASE_DEFINITION,
            "source_phase_difference_definition": source_definition,
            "phase_transform": transform,
            "source_variable": phase.name or "unwrappedPhase",
            "grid_mapping": "spatial_ref",
        }
    )
    return snowin_phase, transform


def _build_phase_normalized_dataset(
    phase: xr.DataArray,
    spatial_ref: xr.DataArray,
    *,
    source_phase_difference_definition: str,
    reference_time: str,
    secondary_time: str,
    wavelength_m: float,
    source_product_type: str = "NISAR_GUNW",
    source_granule_id: str | None = None,
    additional_variables: Mapping[str, xr.DataArray] | None = None,
    native_grid_dimensions: Mapping[str, tuple[tuple[str, ...], ...]] | None = None,
    source_metadata: Mapping[str, Any] | None = None,
) -> xr.Dataset:
    """Build a pair Dataset with phase in the SnowIn convention.

    Additional variables must use the phase grid or a native-grid dimension
    layout declared by the product adapter.
    """
    source_definition = _validate_source_convention(source_phase_difference_definition)
    snowin_phase, transform = _convert_source_phase(phase, source_definition)
    reference_instant = parse_utc_timestamp(reference_time, "reference_time")
    secondary_instant = parse_utc_timestamp(secondary_time, "secondary_time")
    if secondary_instant <= reference_instant:
        raise ValueError(
            "secondary_time must be later than reference_time for a directed pair"
        )
    reference_time = iso_utc_timestamp(reference_instant, "reference_time")
    secondary_time = iso_utc_timestamp(secondary_instant, "secondary_time")
    attrs: dict[str, Any] = {
        "snowin_schema_version": "0.1",
        "snowin_data_state": "phase_normalized_product",
        "product_kind": "pairwise_interferogram",
        "reference_time": reference_time,
        "secondary_time": secondary_time,
        "temporal_edge": "reference_to_secondary",
        "phase_difference_definition": _SNOWIN_PHASE_DEFINITION,
        "source_phase_difference_definition": source_definition,
        "phase_transform": transform,
        "wavelength_m": _positive_scalar("wavelength_m", wavelength_m),
        "source_product_type": source_product_type,
    }
    if source_granule_id is not None:
        attrs["source_granule_id"] = source_granule_id
    if source_metadata:
        attrs.update(_serializable_attrs(source_metadata))

    variables: dict[str, xr.DataArray] = {"phase": snowin_phase}
    native_grid_dimensions = native_grid_dimensions or {}
    for name, variable in (additional_variables or {}).items():
        if variable.dims == ("y", "x"):
            if variable.sizes != phase.sizes:
                raise ValueError(
                    f"additional variable {name!r} does not match the phase grid"
                )
            for dim in ("y", "x"):
                if not np.array_equal(
                    phase.coords[dim].data, variable.coords[dim].data
                ):
                    raise ValueError(
                        f"additional variable {name!r} is not grid-aligned"
                    )
        elif variable.dims not in native_grid_dimensions.get(name, ()):
            raise ValueError(
                f"additional variable {name!r} has unsupported dimensions "
                f"{variable.dims!r}; expected ('y', 'x') or an explicitly "
                "declared native-grid layout"
            )
        else:
            for dim in variable.dims:
                if dim not in variable.coords or variable.coords[dim].dims != (dim,):
                    raise ValueError(
                        f"native-grid variable {name!r} must provide a 1-D "
                        f"coordinate for dimension {dim!r}"
                    )
        copied = variable.rename(name)
        copied.attrs = _serializable_attrs(variable.attrs)
        copied.attrs.setdefault("grid_mapping", "spatial_ref")
        variables[name] = copied

    result = xr.Dataset(
        variables,
        coords={
            "y": phase.coords["y"],
            "x": phase.coords["x"],
            "spatial_ref": spatial_ref.rename("spatial_ref"),
        },
        attrs=attrs,
    )
    result["x"].attrs.setdefault("units", "m")
    result["y"].attrs.setdefault("units", "m")
    return result


def normalize_gunw_pair(
    phase: xr.DataArray,
    incidence_angle: xr.DataArray,
    *,
    wavelength_m: float,
    reference_time: str | datetime,
    secondary_time: str | datetime,
    source_phase_difference_definition: str,
    spatial_ref: xr.DataArray,
    source_product_type: str = "NISAR_GUNW",
    source_granule_id: str | None = None,
    additional_variables: Mapping[str, xr.DataArray] | None = None,
    source_metadata: Mapping[str, Any] | None = None,
) -> xr.Dataset:
    """Convert source phase and build a pair Dataset with required metadata.

    The source convention is deliberately required. A product adapter may
    supply a documented product-specific value, but this function never
    infers it from phase values.
    """
    if not isinstance(phase, xr.DataArray) or not isinstance(
        incidence_angle, xr.DataArray
    ):
        raise TypeError("phase and incidence_angle must be xarray.DataArray objects")
    if not isinstance(spatial_ref, xr.DataArray) or spatial_ref.ndim != 0:
        raise TypeError("spatial_ref must be a scalar xarray.DataArray")

    source_definition = _validate_source_convention(source_phase_difference_definition)
    wavelength_m = _positive_scalar("wavelength_m", wavelength_m)
    reference_time = _iso_utc(reference_time, "reference_time")
    secondary_time = _iso_utc(secondary_time, "secondary_time")

    phase_units = phase.attrs.get("units")
    if phase_units is None or (
        isinstance(phase_units, str) and not phase_units.strip()
    ):
        raise ValueError("source phase units are missing; expected radians")
    if phase_units not in {"rad", "radian", "radians"}:
        raise ValueError(
            f"source phase units {phase_units!r} are unsupported; expected radians"
        )
    incidence_units = incidence_angle.attrs.get("units")
    if incidence_units is None or (
        isinstance(incidence_units, str) and not incidence_units.strip()
    ):
        raise ValueError("incidence_angle units are missing; expected radians")
    if incidence_units not in {"rad", "radian", "radians"}:
        raise ValueError(
            f"incidence_angle units {incidence_units!r} are unsupported; "
            "expected radians"
        )
    incidence_reference = incidence_angle.attrs.get("incidence_angle_reference")
    if incidence_reference is None:
        raise ValueError("incidence_angle_reference is missing")
    if incidence_reference not in {"ellipsoid", "local"}:
        raise ValueError(
            f"incidence_angle_reference {incidence_reference!r} is unsupported; "
            "expected 'ellipsoid' or 'local'"
        )
    _require_aligned(phase, incidence_angle)

    incidence = incidence_angle.rename("incidence_angle")
    incidence_attrs = _serializable_attrs(incidence_angle.attrs)
    incidence_attrs.update({"units": "rad", "grid_mapping": "spatial_ref"})
    incidence.attrs = incidence_attrs

    result = _build_phase_normalized_dataset(
        phase,
        spatial_ref,
        source_phase_difference_definition=source_definition,
        reference_time=reference_time,
        secondary_time=secondary_time,
        wavelength_m=wavelength_m,
        source_product_type=source_product_type,
        source_granule_id=source_granule_id,
        additional_variables=additional_variables,
        source_metadata=source_metadata,
    )
    result["incidence_angle"] = incidence
    result.attrs["snowin_data_state"] = "retrieval_ready_pair"
    return result
