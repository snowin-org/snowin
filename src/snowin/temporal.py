"""Chronological accumulation of pairwise SnowIn dSWE edges."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime

import numpy as np
import xarray as xr

from ._phase_contract import DSWE_DEFINITION
from ._precision import as_science_float
from ._timestamps import parse_utc_timestamp

_TEMPORAL_EDGE = "reference_to_secondary"
_SUPPORTED_DSWE_UNITS = {"m", "meter", "meters"}


def _parse_utc(value: object, name: str) -> datetime:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"{name} is missing; provide an ISO 8601 UTC string")
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO 8601 UTC string")
    return parse_utc_timestamp(value, name)


def _validate_alignment(
    reference: xr.DataArray,
    candidate: xr.DataArray,
    *,
    label: str,
) -> None:
    if candidate.dims != reference.dims or candidate.sizes != reference.sizes:
        raise ValueError(
            f"{label} dimensions/sizes do not match the first edge: "
            f"{candidate.dims}/{dict(candidate.sizes)} != "
            f"{reference.dims}/{dict(reference.sizes)}"
        )
    for dimension in reference.dims:
        reference_coord = reference.coords.get(dimension)
        candidate_coord = candidate.coords.get(dimension)
        if reference_coord is None or candidate_coord is None:
            if reference_coord is not None or candidate_coord is not None:
                raise ValueError(
                    f"{label} coordinate metadata differs for {dimension!r}"
                )
        elif not reference_coord.equals(candidate_coord):
            raise ValueError(f"{label} coordinates differ for {dimension!r}")


def _edge_data(edge: xr.Dataset, dswe_variable: str) -> xr.DataArray:
    if not isinstance(edge, xr.Dataset):
        raise TypeError("each temporal edge must be an xarray.Dataset")
    if edge.attrs.get("temporal_edge") != _TEMPORAL_EDGE:
        raise ValueError(
            "each temporal edge must declare temporal_edge='reference_to_secondary'"
        )
    if dswe_variable not in edge:
        raise ValueError(f"temporal edge is missing {dswe_variable!r}")
    dswe = edge[dswe_variable]
    if dswe.ndim == 0:
        raise ValueError("pairwise dSWE must have at least one spatial dimension")
    if dswe.attrs.get("units") not in _SUPPORTED_DSWE_UNITS:
        raise ValueError(
            f"{dswe_variable} must declare dSWE units in metres; "
            f"got {dswe.attrs.get('units')!r}"
        )
    if dswe.attrs.get("quantity") not in {None, "pairwise_dSWE"}:
        raise ValueError(f"{dswe_variable} does not declare pairwise dSWE")
    if "0.1" in {
        edge.attrs.get("snowin_schema_version"),
        dswe.attrs.get("snowin_schema_version"),
    }:
        raise ValueError(
            "legacy SnowIn schema 0.1 requires a provenance-aware migration; "
            "see docs/phase_migration.md; do not automatically negate saved dSWE"
        )
    dswe_definition = dswe.attrs.get("dswe_difference_definition")
    if dswe_definition is None:
        raise ValueError(
            f"{dswe_variable} dswe_difference_definition is missing; explicitly "
            "declare 'secondary_minus_reference' on the dSWE variable after "
            "verifying processing provenance. See docs/phase_migration.md."
        )
    if dswe_definition != DSWE_DEFINITION:
        raise ValueError(
            f"{dswe_variable} dswe_difference_definition is {dswe_definition!r}; "
            "expected 'secondary_minus_reference'"
        )
    phase_definition = dswe.attrs.get("phase_difference_definition")
    if phase_definition not in {None, "reference_minus_secondary"}:
        raise ValueError(
            f"{dswe_variable} uses phase definition {phase_definition!r}; expected "
            "the SnowIn convention 'reference_minus_secondary'"
        )
    return as_science_float(dswe)


def _edge_support(edge: xr.Dataset, dswe: xr.DataArray) -> xr.DataArray:
    support = np.isfinite(dswe).rename("edge_supported")
    if "pairwise_supported" in edge:
        declared = edge["pairwise_supported"]
        _validate_alignment(support, declared, label="pairwise_supported")
        if declared.dtype.kind != "b":
            raise TypeError("pairwise_supported must contain boolean values")
        support = (support & declared).rename("edge_supported")
    return support


def accumulate_dswe(
    edges: Sequence[xr.Dataset],
    *,
    dswe_variable: str = "dswe",
    initial_time: str | None = None,
) -> xr.Dataset:
    """Accumulate pairwise dSWE along one explicit chronological path.

    Each input Dataset describes one SnowIn pair and contains a pairwise dSWE
    variable. Edges must be supplied in path order, use the declared
    ``reference_to_secondary`` direction, and be contiguous in time: the next
    edge's reference acquisition must equal the prior edge's secondary
    acquisition. Cumulative values are emitted at each edge's secondary time.
    Each dSWE variable must explicitly declare
    ``dswe_difference_definition='secondary_minus_reference'``; this convention
    is never inferred from schema, Dataset attributes, or numeric values.

    Missing or unsupported edge samples remain missing. A cumulative sample is
    supported only when every edge in the path so far is supported at that
    sample; no missing edge is replaced with zero.
    """
    if not isinstance(edges, Sequence) or isinstance(edges, (str, bytes)):
        raise TypeError("edges must be a non-empty sequence of xarray.Dataset objects")
    if not edges:
        raise ValueError("edges must contain at least one temporal edge")

    records: list[dict[str, object]] = []
    cumulative_values: list[xr.DataArray] = []
    support_values: list[xr.DataArray] = []
    spatial_reference: xr.DataArray | None = None
    cumulative: xr.DataArray | None = None
    path_supported: xr.DataArray | None = None
    prior_secondary: datetime | None = None

    for index, edge in enumerate(edges):
        if not isinstance(edge, xr.Dataset):
            raise TypeError(f"edge {index} must be an xarray.Dataset")
        reference_time = _parse_utc(
            edge.attrs.get("reference_time"), f"edge {index} reference_time"
        )
        secondary_time = _parse_utc(
            edge.attrs.get("secondary_time"), f"edge {index} secondary_time"
        )
        if secondary_time <= reference_time:
            raise ValueError(
                f"edge {index} is not chronological: secondary_time must be later "
                "than reference_time"
            )
        if prior_secondary is not None and reference_time != prior_secondary:
            raise ValueError(
                f"edge {index} does not continue the chronological path: "
                f"reference_time={reference_time.isoformat()} does not equal "
                f"prior secondary_time={prior_secondary.isoformat()}"
            )
        if index == 0 and initial_time is not None:
            requested_initial = _parse_utc(initial_time, "initial_time")
            if reference_time != requested_initial:
                raise ValueError(
                    "initial_time does not match the first edge reference_time"
                )

        dswe = _edge_data(edge, dswe_variable)
        support = _edge_support(edge, dswe)
        if spatial_reference is None:
            spatial_reference = dswe
            cumulative = dswe.where(support).rename("cumulative_dswe")
            path_supported = support.rename("temporal_path_supported")
        else:
            _validate_alignment(spatial_reference, dswe, label="dSWE edge")
            _validate_alignment(spatial_reference, support, label="edge support")
            assert cumulative is not None
            assert path_supported is not None
            path_supported = (path_supported & support).rename(
                "temporal_path_supported"
            )
            cumulative = (cumulative + dswe.where(support)).where(path_supported)
            cumulative = cumulative.rename("cumulative_dswe")

        assert cumulative is not None
        assert path_supported is not None
        cumulative_values.append(cumulative)
        support_values.append(path_supported)
        records.append(
            {
                "index": index,
                "reference_time": reference_time.isoformat().replace("+00:00", "Z"),
                "secondary_time": secondary_time.isoformat().replace("+00:00", "Z"),
            }
        )
        prior_secondary = secondary_time

    assert spatial_reference is not None
    times = np.array(
        [
            datetime.fromisoformat(
                str(record["secondary_time"]).replace("Z", "+00:00")
            ).replace(tzinfo=None)
            for record in records
        ],
        dtype="datetime64[ns]",
    )
    cumulative_by_time = xr.concat(
        cumulative_values,
        dim=xr.IndexVariable("time", times),
    ).rename("cumulative_dswe")
    cumulative_by_time.attrs = dict(cumulative.attrs)
    cumulative_by_time.attrs.update(
        {
            "units": "m",
            "quantity": "cumulative_dSWE",
            "dswe_difference_definition": DSWE_DEFINITION,
            "path_start_time": records[0]["reference_time"],
            "path_end_time": records[-1]["secondary_time"],
            "temporal_edge_count": len(records),
            "missing_support_policy": "propagate_missing; never substitute zero",
        }
    )
    support_by_time = xr.concat(
        support_values,
        dim=xr.IndexVariable("time", times),
    ).rename("temporal_path_supported")
    support_by_time.attrs = {
        "scope": "per_sample_and_path_endpoint",
        "meaning": "all pairwise dSWE edges through this endpoint are supported",
    }
    return xr.Dataset(
        {
            "cumulative_dswe": cumulative_by_time,
            "temporal_path_supported": support_by_time,
        },
        attrs={
            "temporal_accumulation": "strict_chronological_path",
            "dswe_difference_definition": DSWE_DEFINITION,
            "temporal_edge": _TEMPORAL_EDGE,
            "path_start_time": records[0]["reference_time"],
            "path_end_time": records[-1]["secondary_time"],
            "temporal_edge_count": len(records),
            "temporal_path_edges": json.dumps(records, sort_keys=True),
            "missing_support_policy": "propagate_missing; never substitute zero",
        },
    )


__all__ = ["accumulate_dswe"]
