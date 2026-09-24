"""Property checks for cumulative dSWE along directed temporal paths."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import hypothesis.strategies as st
import numpy as np
import xarray as xr
from hypothesis import given, settings

from snowin import accumulate_dswe


def _edge(value: float, index: int, *, supported: bool = True) -> xr.Dataset:
    start = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=12 * index)
    end = start + timedelta(days=12)
    time_format = "%Y-%m-%dT%H:%M:%SZ"
    dswe = xr.DataArray(
        [[value]],
        dims=("y", "x"),
        coords={"y": [4200.0], "x": [500000.0]},
        name="dswe",
        attrs={"units": "m", "quantity": "pairwise_dSWE"},
    )
    return xr.Dataset(
        {
            "dswe": dswe,
            "pairwise_supported": xr.DataArray(
                [[supported]],
                dims=("y", "x"),
                coords=dswe.coords,
            ),
        },
        attrs={
            "reference_time": start.strftime(time_format),
            "secondary_time": end.strftime(time_format),
            "temporal_edge": "reference_to_secondary",
        },
    )


@settings(max_examples=60, derandomize=True, deadline=None)
@given(
    increments=st.lists(
        st.floats(
            min_value=-5.0,
            max_value=5.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=1,
        max_size=6,
    )
)
def test_cumulative_dswe_equals_analytical_prefix_sum(increments):
    result = accumulate_dswe([_edge(value, i) for i, value in enumerate(increments)])
    expected = np.cumsum(np.asarray(increments, dtype=np.float64))[:, None, None]

    np.testing.assert_allclose(
        result.cumulative_dswe.values,
        expected,
        rtol=1e-13,
        atol=1e-14,
    )
    assert result.cumulative_dswe.dims == ("time", "y", "x")
    assert result.attrs["temporal_edge_count"] == len(increments)


@settings(max_examples=60, derandomize=True, deadline=None)
@given(
    increments=st.lists(
        st.floats(
            min_value=-5.0,
            max_value=5.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=1,
        max_size=6,
    )
)
def test_appending_zero_dswe_adds_a_time_step_without_changing_values(increments):
    ordinary = accumulate_dswe([_edge(value, i) for i, value in enumerate(increments)])
    with_zero = accumulate_dswe(
        [
            *(_edge(value, i) for i, value in enumerate(increments)),
            _edge(0.0, len(increments)),
        ]
    )

    np.testing.assert_allclose(
        with_zero.cumulative_dswe.values[:-1],
        ordinary.cumulative_dswe.values,
        rtol=1e-13,
        atol=1e-14,
    )
    np.testing.assert_allclose(
        with_zero.cumulative_dswe.values[-1],
        ordinary.cumulative_dswe.values[-1],
        rtol=1e-13,
        atol=1e-14,
    )
    assert with_zero.sizes["time"] == ordinary.sizes["time"] + 1


@settings(max_examples=60, derandomize=True, deadline=None)
@given(
    increments=st.lists(
        st.floats(
            min_value=-5.0,
            max_value=5.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=1,
        max_size=6,
    ),
    unsupported_index=st.integers(min_value=0, max_value=5),
)
def test_unsupported_edge_remains_unsupported_for_all_later_endpoints(
    increments, unsupported_index
):
    unsupported_index = min(unsupported_index, len(increments) - 1)
    edges = [
        _edge(value, index, supported=index != unsupported_index)
        for index, value in enumerate(increments)
    ]

    result = accumulate_dswe(edges)

    assert not result.temporal_path_supported.values[unsupported_index:, 0, 0].any()
    assert np.isnan(result.cumulative_dswe.values[unsupported_index:, 0, 0]).all()
