"""Reusable xarray evaluation metrics with explicit support provenance."""

from __future__ import annotations

import json
from collections.abc import Sequence

import numpy as np
import xarray as xr

from .support import _scalar, _support_boolean, _validate_alignment, _validate_layer

SUPPORTED_METRICS = ("bias", "mae", "rmse", "correlation")


def compute_metrics(
    observed: xr.DataArray,
    estimated: xr.DataArray,
    *,
    support: xr.DataArray | None = None,
    metrics: Sequence[str] = SUPPORTED_METRICS,
) -> xr.Dataset:
    """Compute simple global metrics over explicitly supported samples.

    Bias is defined as ``estimated - observed``. If ``support`` is supplied,
    it must be an explicitly named support layer aligned to the data grid;
    unknown support is treated as unsupported for the derived metric. If it is
    omitted, the provenance states that only finite observed/estimated pairs
    were used. No coherence, connected-component, or validation threshold is
    implied.
    """
    if not isinstance(observed, xr.DataArray) or not isinstance(
        estimated, xr.DataArray
    ):
        raise TypeError("observed and estimated must be xarray.DataArray objects")
    _validate_alignment(observed, estimated, label="estimated data")
    selected = (metrics,) if isinstance(metrics, str) else tuple(metrics)
    if not selected:
        raise ValueError("metrics must contain at least one metric name")
    unknown = [metric for metric in selected if metric not in SUPPORTED_METRICS]
    if unknown:
        raise ValueError(f"unsupported metrics: {unknown}")

    finite_pairs = np.isfinite(observed) & np.isfinite(estimated)
    if support is None:
        valid = finite_pairs.rename("metric_supported")
        support_policy = "finite_observed_and_estimated_only"
        support_components: tuple[str, ...] = ()
    else:
        if not isinstance(support, xr.DataArray):
            raise TypeError("support must be an xarray.DataArray")
        _validate_alignment(observed, support, label="metric support")
        _validate_layer(support.name or "support", support)
        valid = (finite_pairs & _support_boolean(support)).rename("metric_supported")
        support_policy = "finite_observed_and_estimated_and_explicit_support"
        support_components = (support.name or "unnamed_support",)

    supported_count = int(_scalar(valid.sum()))
    total_count = int(observed.size)
    observed_units = observed.attrs.get("units", "unknown")
    estimated_units = estimated.attrs.get("units", "unknown")
    error = estimated - observed
    values: list[float] = []
    statuses: list[str] = []
    units: list[str] = []
    if supported_count == 0:
        base_status = "UNSUPPORTED_NO_FINITE_SUPPORTED_PAIRS"
    else:
        base_status = "SUPPORTED"

    masked_error = error.where(valid)
    if supported_count:
        observed_mean = _scalar(observed.where(valid).mean(skipna=True))
        estimated_mean = _scalar(estimated.where(valid).mean(skipna=True))
    else:
        observed_mean = float("nan")
        estimated_mean = float("nan")

    for metric in selected:
        if metric == "bias":
            value = (
                _scalar(masked_error.mean(skipna=True)) if supported_count else np.nan
            )
            unit = str(estimated_units)
            status = base_status
        elif metric == "mae":
            value = (
                _scalar(np.abs(masked_error).mean(skipna=True))
                if supported_count
                else np.nan
            )
            unit = str(estimated_units)
            status = base_status
        elif metric == "rmse":
            value = (
                float(np.sqrt(_scalar((masked_error**2).mean(skipna=True))))
                if supported_count
                else np.nan
            )
            unit = str(estimated_units)
            status = base_status
        else:
            if supported_count < 2:
                value = np.nan
                status = "UNSUPPORTED_FEWER_THAN_TWO_PAIRS"
            else:
                observed_centered = observed - observed_mean
                estimated_centered = estimated - estimated_mean
                covariance = _scalar(
                    (observed_centered * estimated_centered)
                    .where(valid)
                    .sum(skipna=True)
                )
                observed_ss = _scalar(
                    (observed_centered**2).where(valid).sum(skipna=True)
                )
                estimated_ss = _scalar(
                    (estimated_centered**2).where(valid).sum(skipna=True)
                )
                if observed_ss <= 0 or estimated_ss <= 0:
                    value = np.nan
                    status = "UNSUPPORTED_ZERO_VARIANCE"
                else:
                    value = covariance / float(np.sqrt(observed_ss * estimated_ss))
                    status = "SUPPORTED"
            unit = "1"
        values.append(float(value))
        statuses.append(status)
        units.append(unit)

    result = xr.Dataset(
        {
            "value": xr.DataArray(values, dims=("metric",)),
            "metric_units": xr.DataArray(units, dims=("metric",)),
            "metric_status": xr.DataArray(statuses, dims=("metric",)),
            "supported_count": xr.DataArray(supported_count),
            "total_count": xr.DataArray(total_count),
            "support_fraction": xr.DataArray(
                float(supported_count / total_count) if total_count else np.nan
            ),
        },
        coords={"metric": list(selected)},
        attrs={
            "metric_definition": "bias=estimated-observed; mae=mean(abs(error)); rmse=sqrt(mean(error^2)); correlation=Pearson r",
            "support_policy": support_policy,
            "support_components": json.dumps(support_components),
            "observed_units": observed_units,
            "estimated_units": estimated_units,
            "unknown_support_is_not_false": True,
        },
    )
    result["value"].attrs["meaning"] = "metric value; units vary by metric_units"
    result["supported_count"].attrs["meaning"] = (
        "finite pairs satisfying explicit support"
    )
    return result


__all__ = ["SUPPORTED_METRICS", "compute_metrics"]
