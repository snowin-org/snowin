"""Reference-phase strategies for InSAR snow workflows."""

from __future__ import annotations

import json

import numpy as np
import xarray as xr

REFERENCE_CONTRIBUTOR_DIM = "reference_contributor"
MANUAL_OFFSET_METHOD = "manual_offset"
SINGLE_STATION_METHOD = "single_station_offset"
MEAN_OFFSET_METHOD = "mean_additive_offset"
MEDIAN_OFFSET_METHOD = "median_additive_offset"
COHERENCE_WEIGHTED_METHOD = "coherence_weighted_additive_offset"
REFERENCE_METHODS = {
    MANUAL_OFFSET_METHOD,
    SINGLE_STATION_METHOD,
    MEAN_OFFSET_METHOD,
    MEDIAN_OFFSET_METHOD,
    COHERENCE_WEIGHTED_METHOD,
}


def _reference_vector(name: str, value: xr.DataArray) -> xr.DataArray:
    if not isinstance(value, xr.DataArray) or value.ndim != 1:
        raise TypeError(f"{name} must be a one-dimensional xarray.DataArray")
    dimension = value.dims[0]
    return value.rename({dimension: REFERENCE_CONTRIBUTOR_DIM})


def _scalar_value(value: xr.DataArray) -> float:
    data = value.data
    if hasattr(data, "compute"):
        data = data.compute()
    return float(np.asarray(data).item())


def _reference_inputs(
    observed_phase: xr.DataArray | None,
    expected_phase: xr.DataArray | None,
    weights: xr.DataArray | None,
    contributor_id: xr.DataArray | None,
) -> tuple[xr.DataArray, xr.DataArray, xr.DataArray, xr.DataArray]:
    if observed_phase is None or expected_phase is None or weights is None:
        raise TypeError(
            "observed_phase, expected_phase, and weights are required for "
            "contributor-based reference methods"
        )
    observed = _reference_vector("observed_phase", observed_phase)
    expected = _reference_vector("expected_phase", expected_phase)
    weight = _reference_vector("weights", weights)
    if not (
        observed.sizes == expected.sizes == weight.sizes
        and observed.sizes[REFERENCE_CONTRIBUTOR_DIM] > 0
    ):
        raise ValueError(
            "observed_phase, expected_phase, and weights must have identical "
            "non-empty lengths"
        )
    if observed.attrs.get("units") not in {"rad", "radian", "radians"}:
        raise ValueError("observed_phase must declare radians in its units metadata")
    if expected.attrs.get("units") not in {"rad", "radian", "radians"}:
        raise ValueError("expected_phase must declare radians in its units metadata")
    if contributor_id is None:
        identifiers = xr.DataArray(
            [str(index) for index in range(observed.sizes[REFERENCE_CONTRIBUTOR_DIM])],
            dims=(REFERENCE_CONTRIBUTOR_DIM,),
            coords={
                REFERENCE_CONTRIBUTOR_DIM: observed.coords.get(
                    REFERENCE_CONTRIBUTOR_DIM,
                    np.arange(observed.sizes[REFERENCE_CONTRIBUTOR_DIM]),
                )
            },
            name="reference_contributor_id",
        )
    else:
        identifiers = _reference_vector("contributor_id", contributor_id)
        if identifiers.sizes != observed.sizes:
            raise ValueError("contributor_id must match reference contributor length")
        identifiers = identifiers.astype(str).rename("reference_contributor_id")
    return observed, expected, weight, identifiers


def estimate_reference_offset(
    observed_phase: xr.DataArray | None = None,
    expected_phase: xr.DataArray | None = None,
    weights: xr.DataArray | None = None,
    *,
    contributor_id: xr.DataArray | None = None,
    exclusion_reason: xr.DataArray | None = None,
    method: str = COHERENCE_WEIGHTED_METHOD,
    offset_rad: float | None = None,
) -> xr.Dataset:
    """Estimate an auditable additive phase offset from reference contributors.

    The estimator supports explicit reference policies without embedding
    station selection or SNOTEL I/O.  The Colorado-frozen/Zhou method is the
    coherence-weighted calibration algebra:

    ``C_hat = sum(w_i * (observed_i - expected_i)) / sum(w_i)``.

    ``manual_offset`` accepts an explicitly supplied ``offset_rad`` and does
    not require contributors.  ``single_station_offset`` requires exactly one
    eligible contributor.  ``mean_additive_offset`` takes the unweighted mean
    residual across eligible contributors.  ``median_additive_offset`` takes
    the robust median residual.  ``coherence_weighted_additive_offset`` uses
    contributor weights as calibration weights.  The latter is the only method
    here tied to the Colorado/Zhou scientific retrieval; the others are
    explicit aggregation or operational-input policies.

    For contributor-based methods, ``observed_phase`` and ``expected_phase``
    are radians.  Non-finite values, non-positive weights, and caller-marked
    exclusions are retained in contributor-level metadata. If support is
    insufficient, the result has a NaN offset and an explicit unsupported
    status rather than inventing zero support.
    """
    if method not in REFERENCE_METHODS:
        raise ValueError(
            f"unsupported reference method: {method!r}; expected one of "
            f"{sorted(REFERENCE_METHODS)}"
        )
    if method == MANUAL_OFFSET_METHOD:
        if offset_rad is None or not np.isfinite(offset_rad):
            raise ValueError("manual_offset requires a finite offset_rad")
        result = xr.Dataset(
            {
                "reference_offset_rad": xr.DataArray(float(offset_rad)),
                "reference_total_weight": xr.DataArray(np.nan),
                "reference_eligible_count": xr.DataArray(0),
            },
            attrs={
                "reference_method": method,
                "reference_offset_units": "rad",
                "reference_status": "SUPPORTED_MANUAL",
                "reference_formula": "caller-supplied reference_offset_rad",
                "reference_weight_role": "not_used_manual",
                "reference_contributor_count": 0,
                "reference_eligible_count": 0,
            },
        )
        result["reference_offset_rad"].attrs["units"] = "rad"
        result["reference_total_weight"].attrs["units"] = "1"
        return result

    observed, expected, weight, identifiers = _reference_inputs(
        observed_phase, expected_phase, weights, contributor_id
    )
    if exclusion_reason is not None:
        caller_reasons = _reference_vector("exclusion_reason", exclusion_reason)
        if caller_reasons.sizes != observed.sizes:
            raise ValueError("exclusion_reason must match reference contributor length")
        caller_reasons = caller_reasons.astype(str)
    else:
        caller_reasons = xr.DataArray(
            np.full(
                observed.sizes[REFERENCE_CONTRIBUTOR_DIM],
                "eligible",
                dtype="U8",
            ),
            dims=(REFERENCE_CONTRIBUTOR_DIM,),
            coords={
                REFERENCE_CONTRIBUTOR_DIM: observed.coords.get(
                    REFERENCE_CONTRIBUTOR_DIM,
                    np.arange(observed.sizes[REFERENCE_CONTRIBUTOR_DIM]),
                )
            },
        )
    caller_reasons = caller_reasons.rename("reference_caller_exclusion_reason")

    input_reasons = xr.where(
        ~np.isfinite(observed),
        "observed_phase_nonfinite",
        xr.where(
            ~np.isfinite(expected),
            "expected_phase_nonfinite",
            xr.where(
                ~np.isfinite(weight),
                "weight_nonfinite",
                xr.where(weight <= 0, "weight_nonpositive", "eligible"),
            ),
        ),
    )
    reasons = xr.where(
        caller_reasons != "eligible", caller_reasons, input_reasons
    ).rename("reference_exclusion_reason")

    eligible = (
        np.isfinite(observed)
        & np.isfinite(expected)
        & np.isfinite(weight)
        & (weight > 0)
        & (caller_reasons == "eligible")
    ).rename("reference_eligible")
    residual = (observed - expected).rename("reference_residual")
    contribution = (
        (weight * residual).where(eligible).rename("reference_weighted_contribution")
    )
    total_weight = weight.where(eligible).sum(
        dim=REFERENCE_CONTRIBUTOR_DIM, skipna=True
    )
    numerator = contribution.sum(dim=REFERENCE_CONTRIBUTOR_DIM, skipna=True)
    eligible_count = eligible.sum(dim=REFERENCE_CONTRIBUTOR_DIM)
    total_weight_value = _scalar_value(total_weight)
    eligible_count_value = int(_scalar_value(eligible_count))
    if method == SINGLE_STATION_METHOD and eligible_count_value > 1:
        offset = float("nan")
        status = "UNSUPPORTED_SINGLE_STATION_REQUIRES_ONE_ELIGIBLE_CONTRIBUTOR"
    elif eligible_count_value:
        if method == SINGLE_STATION_METHOD:
            offset = _scalar_value(residual.where(eligible).sum())
        elif method == MEAN_OFFSET_METHOD:
            offset = _scalar_value(residual.where(eligible).mean())
        elif method == MEDIAN_OFFSET_METHOD:
            offset = _scalar_value(residual.where(eligible).median())
        elif total_weight_value > 0:
            offset = _scalar_value(numerator) / total_weight_value
        else:  # pragma: no cover - positive eligibility implies positive weight
            offset = float("nan")
        status = "SUPPORTED"
    else:
        offset = float("nan")
        status = "UNSUPPORTED_NO_ELIGIBLE_CONTRIBUTORS"

    weight_role = {
        SINGLE_STATION_METHOD: "support_only_not_aggregation",
        MEAN_OFFSET_METHOD: "not_used_unweighted_mean",
        MEDIAN_OFFSET_METHOD: "not_used_robust_median",
        COHERENCE_WEIGHTED_METHOD: "calibration_weight",
    }[method]
    formula = {
        SINGLE_STATION_METHOD: "observed_phase - expected_phase for the one eligible contributor",
        MEAN_OFFSET_METHOD: "mean(observed_phase - expected_phase) over eligible contributors",
        MEDIAN_OFFSET_METHOD: "median(observed_phase - expected_phase) over eligible contributors",
        COHERENCE_WEIGHTED_METHOD: (
            "sum(weight * (observed_phase - expected_phase)) / "
            "sum(weight) over eligible contributors"
        ),
    }[method]

    coordinate = observed.coords.get(
        REFERENCE_CONTRIBUTOR_DIM,
        np.arange(observed.sizes[REFERENCE_CONTRIBUTOR_DIM]),
    )
    result = xr.Dataset(
        {
            "reference_contributor_id": identifiers,
            "reference_observed_phase": observed.rename("reference_observed_phase"),
            "reference_expected_phase": expected.rename("reference_expected_phase"),
            "reference_weight": weight.rename("reference_weight"),
            "reference_residual": residual,
            "reference_weighted_contribution": contribution,
            "reference_eligible": eligible,
            "reference_exclusion_reason": reasons,
            "reference_caller_exclusion_reason": caller_reasons,
            "reference_offset_rad": xr.DataArray(offset),
            "reference_total_weight": xr.DataArray(total_weight_value),
            "reference_eligible_count": xr.DataArray(eligible_count_value),
        },
        coords={REFERENCE_CONTRIBUTOR_DIM: coordinate},
        attrs={
            "reference_method": method,
            "reference_offset_units": "rad",
            "reference_status": status,
            "reference_formula": formula,
            "reference_weight_role": weight_role,
            "reference_contributor_count": int(
                observed.sizes[REFERENCE_CONTRIBUTOR_DIM]
            ),
            "reference_eligible_count": eligible_count_value,
        },
    )
    result["reference_observed_phase"].attrs["units"] = "rad"
    result["reference_expected_phase"].attrs["units"] = "rad"
    result["reference_residual"].attrs["units"] = "rad"
    result["reference_weighted_contribution"].attrs["units"] = "rad"
    result["reference_weight"].attrs["units"] = "1"
    result["reference_offset_rad"].attrs["units"] = "rad"
    result["reference_total_weight"].attrs["units"] = "1"
    return result


def apply_reference_offset(
    pair: xr.Dataset,
    estimate: xr.Dataset,
) -> xr.Dataset:
    """Apply an estimated reference offset to a normalized pair Dataset."""
    if not isinstance(pair, xr.Dataset) or "phase" not in pair:
        raise TypeError("pair must be an xarray.Dataset containing 'phase'")
    phase = pair["phase"]
    if phase.attrs.get("units") not in {"rad", "radian", "radians"}:
        raise ValueError("pair phase must declare radians in its units metadata")
    if pair.attrs.get("phase_difference_definition") != "secondary_minus_reference":
        raise ValueError("pair phase must use the SnowIn phase convention")
    if not isinstance(estimate, xr.Dataset):
        raise TypeError("estimate must be an xarray.Dataset")
    required = {
        "reference_offset_rad",
        "reference_eligible_count",
    }
    missing = required.difference(estimate.variables)
    if missing:
        raise ValueError(f"reference estimate is missing {sorted(missing)}")

    offset = _scalar_value(estimate["reference_offset_rad"])
    eligible_count = int(_scalar_value(estimate["reference_eligible_count"]))
    supported = np.isfinite(offset) and (
        eligible_count > 0
        or estimate.attrs.get("reference_status") == "SUPPORTED_MANUAL"
    )
    if supported:
        referenced = (phase - offset).rename("phase_referenced")
    else:
        referenced = xr.full_like(phase, np.nan).rename("phase_referenced")
    referenced.attrs = dict(phase.attrs)
    referenced.attrs.update(
        {
            "units": "rad",
            "phase_reference_method": estimate.attrs.get("reference_method", "unknown"),
            "reference_offset_rad": offset,
            "reference_status": estimate.attrs.get("reference_status", "UNKNOWN"),
        }
    )
    result = pair.copy(deep=False)
    result["phase_referenced"] = referenced
    result["reference_estimate_supported"] = xr.DataArray(
        bool(supported),
        attrs={
            "scope": "global_reference_estimate",
            "meaning": "reference offset is supported for this pair",
        },
    )
    result.attrs = dict(pair.attrs)
    result.attrs.update(
        {
            "phase_reference_method": estimate.attrs.get("reference_method", "unknown"),
            "phase_reference_status": estimate.attrs.get("reference_status", "UNKNOWN"),
            "phase_reference_offset_rad": offset,
            "phase_reference_offset_units": "rad",
            "phase_reference_eligible_count": eligible_count,
            "phase_reference_contributor_count": estimate.attrs.get(
                "reference_contributor_count", 0
            ),
            "phase_reference_provenance": json.dumps(
                {
                    "method": estimate.attrs.get("reference_method", "unknown"),
                    "status": estimate.attrs.get("reference_status", "UNKNOWN"),
                    "offset_rad": offset,
                    "eligible_count": eligible_count,
                },
                sort_keys=True,
            ),
        }
    )
    for name, variable in estimate.data_vars.items():
        if name.startswith("reference_"):
            result[name] = variable
    return result


def reference_phase(
    pair: xr.Dataset,
    observed_phase: xr.DataArray | None = None,
    expected_phase: xr.DataArray | None = None,
    weights: xr.DataArray | None = None,
    *,
    contributor_id: xr.DataArray | None = None,
    exclusion_reason: xr.DataArray | None = None,
    method: str = COHERENCE_WEIGHTED_METHOD,
    offset_rad: float | None = None,
) -> xr.Dataset:
    """Estimate and apply an explicit xarray-native phase reference.

    For contributor methods, the caller supplies reference observations,
    expected phase, and support weights.  ``method='manual_offset'`` instead
    accepts ``offset_rad`` directly.  This keeps station data access, date
    matching, snow-model choices, and study allowlists outside SnowIn while
    making every phase calibration auditable.
    """
    estimate = estimate_reference_offset(
        observed_phase,
        expected_phase,
        weights,
        contributor_id=contributor_id,
        exclusion_reason=exclusion_reason,
        method=method,
        offset_rad=offset_rad,
    )
    return apply_reference_offset(pair, estimate)
