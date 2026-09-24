import numpy as np
import pytest

from snowin.diagnostics import (
    connected_component_summary,
    mask_summary,
    merge_summaries,
    numeric_summary,
)
from snowin.io.gunw import parse_acquisition_times_from_filename
from snowin.plotting.gunw import amplitude_to_db


def test_numeric_summary_handles_nans():
    arr = np.array([[1.0, 2.0], [np.nan, 4.0]])
    out = numeric_summary(arr)
    assert out["total_n"] == 4
    assert out["valid_n"] == 3
    assert out["mean"] == pytest.approx(7.0 / 3.0)
    assert out["nan_fraction"] == pytest.approx(0.25)


def test_connected_component_summary_dominant_fraction():
    arr = np.array([[1, 1, 2], [2, 2, np.nan]])
    out = connected_component_summary(arr)
    assert out["cc_n_unique"] == 2
    assert out["cc_dominant_component"] == 2
    assert out["cc_dominant_fraction"] == pytest.approx(3 / 5)


def test_mask_summary_reports_255_fraction():
    arr = np.array([[0, 255], [255, 1]])
    out = mask_summary(arr)
    assert out["mask_unique_values"] == "0;1;255"
    assert out["mask_fill_255_fraction"] == pytest.approx(0.5)


def test_amplitude_to_db_uses_20log10():
    arr = np.array([1.0, 10.0, 0.0])
    out = amplitude_to_db(arr)
    assert out[0] == pytest.approx(0.0)
    assert out[1] == pytest.approx(20.0)
    assert np.isnan(out[2])


def test_parse_gunw_filename_timing():
    name = (
        "NISAR_L2_PR_GUNW_005_042_D_069_006_4000_SH_"
        "20251113T025606_20251113T025641_"
        "20251125T025606_20251125T025641_X05010_N_F_J_001.nc"
    )
    times = parse_acquisition_times_from_filename(name)
    assert times.days_between == pytest.approx(12.0)
    assert times.ref_start.year == 2025
    assert times.sec_start.day == 25


def test_diagnostic_summaries_represent_missing_empty_and_all_invalid_layers():
    missing = numeric_summary(None)
    assert missing["valid_n"] is None
    assert missing["mean"] is None

    empty = numeric_summary(np.array([], dtype=float))
    assert empty["total_n"] == 0
    assert empty["valid_fraction"] == 0.0
    assert empty["nan_fraction"] is None

    invalid = numeric_summary(np.array([np.nan, np.inf]))
    assert invalid["valid_n"] == 0
    assert invalid["nan_fraction"] == 1.0
    assert invalid["mean"] is None

    assert connected_component_summary(None)["cc_valid_n"] is None
    assert connected_component_summary(np.array([np.nan]))["cc_n_unique"] == 0
    assert mask_summary(None)["mask_valid_n"] is None
    assert mask_summary(np.array([np.nan]))["mask_unique_values"] == ""


def test_merge_summaries_uses_later_metadata_for_duplicate_fields():
    assert merge_summaries({"units": "rad", "count": 2}, {"units": "m"}) == {
        "units": "m",
        "count": 2,
    }
