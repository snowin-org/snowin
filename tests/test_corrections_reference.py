import numpy as np
import pytest

from snowin.corrections import PhaseCorrectionConfig, apply_phase_corrections
from snowin.reference import apply_reference_phase


def test_apply_phase_corrections_subtract_and_add():
    phase = np.array([[10.0]])
    sub = apply_phase_corrections(
        phase,
        ionosphere=np.array([[2.0]]),
        config=PhaseCorrectionConfig(apply_ionosphere=True, ionosphere_sign="subtract"),
    )
    add = apply_phase_corrections(
        phase,
        ionosphere=np.array([[2.0]]),
        config=PhaseCorrectionConfig(apply_ionosphere=True, ionosphere_sign="add"),
    )
    assert sub.phase_corrected[0, 0] == pytest.approx(8.0)
    assert add.phase_corrected[0, 0] == pytest.approx(12.0)


def test_apply_phase_corrections_missing_sign_raises():
    with pytest.raises(ValueError, match="explicit sign"):
        apply_phase_corrections(
            np.array([[1.0]]),
            ionosphere=np.array([[0.1]]),
            config=PhaseCorrectionConfig(apply_ionosphere=True),
        )


def test_apply_phase_corrections_missing_layer_raises():
    with pytest.raises(ValueError, match="no ionosphere layer"):
        apply_phase_corrections(
            np.array([[1.0]]),
            config=PhaseCorrectionConfig(
                apply_ionosphere=True, ionosphere_sign="subtract"
            ),
        )


def test_apply_phase_corrections_default_unchanged():
    phase = np.array([[1.0, 2.0]])
    out = apply_phase_corrections(phase)
    assert np.allclose(out.phase_corrected, phase)


def test_apply_reference_phase_none_unchanged():
    phase = np.array([[1.0, 2.0]])
    out = apply_reference_phase(phase, strategy="none")
    assert out.reference_value_rad is None
    assert np.allclose(out.phase_referenced, phase)


def test_apply_reference_phase_median_valid():
    phase = np.array([[1.0, 2.0, np.nan]])
    out = apply_reference_phase(phase, strategy="median_valid")
    assert out.reference_value_rad == pytest.approx(1.5)
    assert out.phase_referenced[0, 0] == pytest.approx(-0.5)


def test_apply_reference_phase_empty_mask_raises():
    with pytest.raises(ValueError, match="zero finite pixels"):
        apply_reference_phase(
            np.array([[1.0]]),
            strategy="user_mask",
            reference_mask=np.array([[False]]),
        )
