"""Named support semantics tests."""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from snowin import (
    build_support_dataset,
    compose_support_mask,
    summarize_support,
)


def _layer(values, *, name: str) -> xr.DataArray:
    return xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"y": [100.0, 80.0], "x": [10.0, 20.0]},
        name=name,
    )


def test_support_layers_remain_separate_and_summary_distinguishes_unknown():
    support = build_support_dataset(
        product_valid=_layer([[1, 0], [np.nan, 1]], name="product_valid"),
        geometry_valid=_layer([[1, 1], [1, 0]], name="geometry_valid"),
        evaluation_supported=_layer([[1, np.nan], [1, 1]], name="evaluation_supported"),
    )
    mask = compose_support_mask(
        support,
        ["product_valid", "geometry_valid", "evaluation_supported"],
    )
    np.testing.assert_array_equal(mask.values, [[True, False], [False, False]])
    assert mask.attrs["unknown_policy"].startswith("unknown treated")
    assert "quality_mask" not in support

    summary = summarize_support(support)
    assert summary.sizes["support_category"] == 3
    assert summary.sel(support_category="product_valid").known_count.item() == 3
    assert summary.sel(support_category="product_valid").supported_count.item() == 2
    assert summary.sel(
        support_category="product_valid"
    ).support_fraction.item() == pytest.approx(2 / 3)
    assert summary.sel(
        support_category="product_valid"
    ).known_fraction.item() == pytest.approx(3 / 4)
    assert bool(summary.attrs["unknown_support_is_not_false"]) is True


def test_support_requires_explicit_layers_and_aligned_grids():
    support = build_support_dataset(
        product_valid=_layer([[1, 1], [1, 1]], name="product_valid")
    )
    with pytest.raises(ValueError, match="missing"):
        compose_support_mask(support, ["geometry_valid"])

    with pytest.raises(ValueError, match="coordinates differ"):
        build_support_dataset(
            product_valid=_layer([[1, 1], [1, 1]], name="product_valid"),
            geometry_valid=xr.DataArray(
                [[1, 1], [1, 1]],
                dims=("y", "x"),
                coords={"y": [100.0, 70.0], "x": [10.0, 20.0]},
            ),
        )


def test_support_rejects_nonbinary_values_and_universal_quality_mask_name():
    with pytest.raises(ValueError, match="only 0, 1, or NaN"):
        build_support_dataset(
            product_valid=_layer([[1, 2], [1, 1]], name="product_valid")
        )
    with pytest.raises(ValueError, match="quality_mask"):
        build_support_dataset(
            quality_mask=_layer([[1, 1], [1, 1]], name="quality_mask")
        )


def test_dask_support_composition_remains_lazy():
    pytest.importorskip("dask.array")
    support = _layer([[1, 1], [1, 0]], name="evaluation_supported").chunk(
        {"y": 1, "x": 1}
    )
    composed = compose_support_mask(
        build_support_dataset(evaluation_supported=support),
        ["evaluation_supported"],
    )
    assert hasattr(composed.data, "chunks")
