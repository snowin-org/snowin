import numpy as np
import pytest

from snowin.quality import build_gunw_quality_mask


def test_build_gunw_quality_mask_reasons():
    phase = np.array([[1.0, np.nan], [2.0, 3.0]])
    coherence = np.array([[0.5, 0.5], [0.1, 0.8]])
    cc = np.array([[1, 1], [1, 2]])
    mask = np.array([[0, 0], [0, 255]])
    out = build_gunw_quality_mask(
        phase,
        coherence=coherence,
        connected_components=cc,
        gunw_mask=mask,
        connected_component=1,
    )
    assert out.reason_masks["nonfinite_phase"][0, 1]
    assert out.reason_masks["low_coherence"][1, 0]
    assert out.reason_masks["invalid_connected_component"][1, 1]
    assert out.reason_masks["gunw_fill_mask"][1, 1]
    assert out.valid_mask.sum() == 1


def test_build_gunw_quality_mask_dominant_component():
    phase = np.ones((2, 3))
    cc = np.array([[1, 2, 2], [2, 3, 3]])
    out = build_gunw_quality_mask(
        phase, connected_components=cc, connected_component="dominant"
    )
    assert out.diagnostics["connected_component_selected"] == 2


def test_build_gunw_quality_mask_shape_mismatch():
    with pytest.raises(ValueError):
        build_gunw_quality_mask(np.ones((2, 2)), coherence=np.ones((3, 2)))
