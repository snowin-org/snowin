"""Stage 6 temporal-edge and accumulation invariants."""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from snowin import accumulate_dswe

COORDS = {"y": [100.0, 80.0], "x": [10.0, 20.0]}


def _edge(
    values: list[list[float]],
    reference_time: str,
    secondary_time: str,
    *,
    support: list[list[bool]] | None = None,
    coords: dict[str, list[float]] | None = None,
) -> xr.Dataset:
    dswe = xr.DataArray(
        values,
        dims=("y", "x"),
        coords=coords or COORDS,
        name="dswe",
        attrs={"units": "m", "quantity": "pairwise_dSWE"},
    )
    variables = {"dswe": dswe}
    if support is not None:
        variables["pairwise_supported"] = xr.DataArray(
            support,
            dims=("y", "x"),
            coords=coords or COORDS,
        )
    return xr.Dataset(
        variables,
        attrs={
            "reference_time": reference_time,
            "secondary_time": secondary_time,
            "temporal_edge": "reference_to_secondary",
        },
    )


def test_accumulation_preserves_path_support_and_coordinates():
    edges = [
        _edge(
            [[1.0, np.nan], [2.0, 3.0]],
            "2025-01-01T00:00:00Z",
            "2025-01-13T00:00:00Z",
        ),
        _edge(
            [[4.0, 5.0], [6.0, 7.0]],
            "2025-01-13T00:00:00Z",
            "2025-01-25T00:00:00Z",
        ),
    ]
    result = accumulate_dswe(edges)

    assert result.cumulative_dswe.dims == ("time", "y", "x")
    np.testing.assert_array_equal(result.cumulative_dswe.coords["y"], COORDS["y"])
    np.testing.assert_array_equal(result.cumulative_dswe.coords["x"], COORDS["x"])
    np.testing.assert_allclose(
        result.cumulative_dswe.values,
        [
            [[1.0, np.nan], [2.0, 3.0]],
            [[5.0, np.nan], [8.0, 10.0]],
        ],
        equal_nan=True,
    )
    np.testing.assert_array_equal(
        result.temporal_path_supported.values,
        [
            [[True, False], [True, True]],
            [[True, False], [True, True]],
        ],
    )
    assert result.attrs["temporal_edge_count"] == 2
    assert result.cumulative_dswe.attrs["units"] == "m"
    assert result.cumulative_dswe.attrs["quantity"] == "cumulative_dSWE"
    assert result.attrs["missing_support_policy"].startswith("propagate_missing")


def test_explicit_pairwise_support_is_not_replaced_by_zero():
    result = accumulate_dswe(
        [
            _edge(
                [[1.0, 2.0], [3.0, 4.0]],
                "2025-01-01T00:00:00Z",
                "2025-01-13T00:00:00Z",
                support=[[True, False], [True, True]],
            )
        ]
    )
    np.testing.assert_allclose(
        result.cumulative_dswe.values,
        [[[1.0, np.nan], [3.0, 4.0]]],
        equal_nan=True,
    )
    assert not bool(result.temporal_path_supported.values[0, 0, 1])


def test_non_chronological_edge_fails():
    with pytest.raises(ValueError, match="not chronological"):
        accumulate_dswe(
            [
                _edge(
                    [[1.0, 1.0], [1.0, 1.0]],
                    "2025-01-13T00:00:00Z",
                    "2025-01-01T00:00:00Z",
                )
            ]
        )


def test_non_contiguous_path_fails():
    first = _edge(
        [[1.0, 1.0], [1.0, 1.0]],
        "2025-01-01T00:00:00Z",
        "2025-01-13T00:00:00Z",
    )
    second = _edge(
        [[1.0, 1.0], [1.0, 1.0]],
        "2025-01-25T00:00:00Z",
        "2025-02-06T00:00:00Z",
    )
    with pytest.raises(ValueError, match="does not continue"):
        accumulate_dswe([first, second])


def test_reverse_order_does_not_get_silently_sorted():
    first = _edge(
        [[1.0, 1.0], [1.0, 1.0]],
        "2025-01-13T00:00:00Z",
        "2025-01-25T00:00:00Z",
    )
    second = _edge(
        [[1.0, 1.0], [1.0, 1.0]],
        "2025-01-01T00:00:00Z",
        "2025-01-13T00:00:00Z",
    )
    with pytest.raises(ValueError, match="does not continue"):
        accumulate_dswe([first, second])


def test_incompatible_edge_grid_fails():
    first = _edge(
        [[1.0, 1.0], [1.0, 1.0]],
        "2025-01-01T00:00:00Z",
        "2025-01-13T00:00:00Z",
    )
    second = _edge(
        [[1.0, 1.0], [1.0, 1.0]],
        "2025-01-13T00:00:00Z",
        "2025-01-25T00:00:00Z",
        coords={"y": [100.0, 70.0], "x": [10.0, 20.0]},
    )
    with pytest.raises(ValueError, match="coordinates differ"):
        accumulate_dswe([first, second])


def test_edge_contract_and_initial_time_are_required():
    edge = _edge(
        [[1.0, 1.0], [1.0, 1.0]],
        "2025-01-01T00:00:00Z",
        "2025-01-13T00:00:00Z",
    )
    edge.attrs.pop("temporal_edge")
    with pytest.raises(ValueError, match="temporal_edge"):
        accumulate_dswe([edge])

    edge.attrs["temporal_edge"] = "reference_to_secondary"
    with pytest.raises(ValueError, match="initial_time"):
        accumulate_dswe([edge], initial_time="2025-01-02T00:00:00Z")


def test_invalid_dswe_contract_fails():
    edge = _edge(
        [[1.0, 1.0], [1.0, 1.0]],
        "2025-01-01T00:00:00Z",
        "2025-01-13T00:00:00Z",
    )
    edge.dswe.attrs["units"] = "cm"
    with pytest.raises(ValueError, match="units in metres"):
        accumulate_dswe([edge])

    edge.dswe.attrs["units"] = "m"
    edge.dswe.attrs["phase_difference_definition"] = "reference_minus_secondary"
    with pytest.raises(ValueError, match="canonical phase"):
        accumulate_dswe([edge])


def test_dask_backed_accumulation_is_lazy_and_equivalent():
    pytest.importorskip("dask.array")
    edges = [
        _edge(
            [[1.0, 2.0], [3.0, 4.0]],
            "2025-01-01T00:00:00Z",
            "2025-01-13T00:00:00Z",
        ),
        _edge(
            [[5.0, 6.0], [7.0, 8.0]],
            "2025-01-13T00:00:00Z",
            "2025-01-25T00:00:00Z",
        ),
    ]
    for edge in edges:
        edge["dswe"] = edge.dswe.chunk({"y": 1, "x": 1})
    result = accumulate_dswe(edges)
    assert hasattr(result.cumulative_dswe.data, "chunks")
    np.testing.assert_allclose(
        result.cumulative_dswe.compute().values,
        [
            [[1.0, 2.0], [3.0, 4.0]],
            [[6.0, 8.0], [10.0, 12.0]],
        ],
    )
