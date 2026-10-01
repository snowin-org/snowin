"""Explicit xarray support semantics for SnowIn operations."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

import numpy as np
import xarray as xr

SUPPORT_CATEGORIES = (
    "product_valid",
    "geometry_valid",
    "reference_supported",
    "pairwise_supported",
    "temporal_path_supported",
    "evaluation_supported",
    "snow_state_supported",
    "coherence_valid",
)


def _scalar(value: xr.DataArray) -> float:
    data = value.data
    if hasattr(data, "compute"):
        data = data.compute()
    return float(np.asarray(data).item())


def _validate_layer(name: str, layer: xr.DataArray) -> None:
    if not isinstance(layer, xr.DataArray):
        raise TypeError(f"support layer {name!r} must be an xarray.DataArray")
    if layer.ndim == 0:
        raise ValueError(f"support layer {name!r} must have spatial dimensions")
    if layer.dtype.kind not in "biuf":
        raise TypeError(
            f"support layer {name!r} must contain boolean or numeric 0/1 values"
        )
    data = layer.data
    if hasattr(data, "compute"):
        return
    values = np.asarray(data)
    finite = values[np.isfinite(values)]
    if finite.size and not np.isin(finite, [0, 1]).all():
        raise ValueError(f"support layer {name!r} must contain only 0, 1, or NaN")


def _support_boolean(layer: xr.DataArray) -> xr.DataArray:
    """Return supported=True while treating unknown samples as unsupported."""
    return (np.isfinite(layer) & layer.fillna(False).astype(bool)).rename(layer.name)


def _validate_alignment(
    reference: xr.DataArray,
    candidate: xr.DataArray,
    *,
    label: str,
) -> None:
    if candidate.dims != reference.dims or candidate.sizes != reference.sizes:
        raise ValueError(f"{label} dimensions/sizes do not match the support grid")
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


def build_support_dataset(
    layers: Mapping[str, xr.DataArray] | None = None,
    **support_layers: xr.DataArray,
) -> xr.Dataset:
    """Validate and package named support layers without combining them.

    Missing support evidence is not replaced with an all-true layer. Numeric
    layers may use NaN to represent unknown support; boolean layers represent
    known true/false support.
    """
    combined: dict[str, xr.DataArray] = {}
    if layers is not None:
        combined.update(dict(layers))
    combined.update(support_layers)
    if not combined:
        raise ValueError("at least one named support layer is required")

    reference: xr.DataArray | None = None
    variables: dict[str, xr.DataArray] = {}
    for name, layer in combined.items():
        if not isinstance(name, str) or not name or name == "quality_mask":
            raise ValueError(
                "support layers require non-empty names other than 'quality_mask'"
            )
        _validate_layer(name, layer)
        if reference is None:
            reference = layer
        else:
            _validate_alignment(reference, layer, label=f"support layer {name!r}")
        variables[name] = layer.rename(name)
    return xr.Dataset(
        variables,
        attrs={
            "support_semantics": "named_support_layers; no universal quality mask",
            "support_categories": json.dumps(sorted(variables)),
        },
    )


def compose_support_mask(
    support: xr.Dataset,
    required: Sequence[str],
    *,
    name: str = "support_mask",
) -> xr.DataArray:
    """Combine explicitly named support variables into a mask.

    Every requested layer must be present. Unknown samples are treated as
    unsupported in the derived mask, while the original layers remain
    available for distinguishing unknown from explicitly false support.
    """
    if not isinstance(support, xr.Dataset):
        raise TypeError("support must be an xarray.Dataset")
    required_names = tuple(dict.fromkeys(required))
    if not required_names:
        raise ValueError("required must contain at least one support category")
    missing = [category for category in required_names if category not in support]
    if missing:
        raise ValueError(f"required support layers are missing: {missing}")
    mask: xr.DataArray | None = None
    for category in required_names:
        layer = support[category]
        _validate_layer(category, layer)
        supported = _support_boolean(layer)
        mask = supported if mask is None else mask & supported
    assert mask is not None
    mask = mask.rename(name)
    mask.attrs = {
        "meaning": "explicit conjunction of named support layers",
        "support_components": json.dumps(required_names),
        "unknown_policy": "unknown treated as unsupported in derived mask",
        "source_support_semantics": "named layers remain separately available",
    }
    return mask


def summarize_support(
    support: xr.Dataset,
    *,
    categories: Sequence[str] | None = None,
) -> xr.Dataset:
    """Summarize known and supported counts for named support layers.

    Scalar reductions intentionally compute their final counts, including for
    Dask-backed inputs. The original support layers remain lazy and unchanged.
    ``support_fraction`` is supported/known, while ``known_fraction`` is
    known/total; these distinguish false support from unavailable evidence.
    """
    if not isinstance(support, xr.Dataset):
        raise TypeError("support must be an xarray.Dataset")
    selected = tuple(categories) if categories is not None else tuple(support.data_vars)
    if not selected:
        raise ValueError("support contains no categories to summarize")
    missing = [category for category in selected if category not in support]
    if missing:
        raise ValueError(f"support categories are missing: {missing}")

    reference: xr.DataArray | None = None
    total_counts: list[int] = []
    known_counts: list[int] = []
    supported_counts: list[int] = []
    for category in selected:
        layer = support[category]
        _validate_layer(category, layer)
        if reference is None:
            reference = layer
        else:
            _validate_alignment(
                reference, layer, label=f"support category {category!r}"
            )
        total_counts.append(int(layer.size))
        known = np.isfinite(layer)
        known_counts.append(int(_scalar(known.sum())))
        supported_counts.append(int(_scalar(_support_boolean(layer).sum())))

    total = np.asarray(total_counts, dtype=np.int64)
    known = np.asarray(known_counts, dtype=np.int64)
    supported = np.asarray(supported_counts, dtype=np.int64)
    with np.errstate(divide="ignore", invalid="ignore"):
        support_fraction = supported / known
        known_fraction = known / total
    return xr.Dataset(
        {
            "total_count": xr.DataArray(total, dims=("support_category",)),
            "known_count": xr.DataArray(known, dims=("support_category",)),
            "supported_count": xr.DataArray(supported, dims=("support_category",)),
            "support_fraction": xr.DataArray(
                support_fraction, dims=("support_category",)
            ),
            "known_fraction": xr.DataArray(known_fraction, dims=("support_category",)),
        },
        coords={"support_category": list(selected)},
        attrs={
            "support_semantics": "named support summary",
            "support_fraction_definition": "supported_count / known_count",
            "known_fraction_definition": "known_count / total_count",
            "unknown_support_is_not_false": True,
        },
    )


__all__ = [
    "SUPPORT_CATEGORIES",
    "build_support_dataset",
    "compose_support_mask",
    "summarize_support",
]
