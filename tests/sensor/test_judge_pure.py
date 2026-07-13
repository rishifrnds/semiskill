import pytest
from semiskill.sensor.judge import cohen_kappa, detect_drift


def test_kappa_perfect_agreement():
    assert cohen_kappa([1, 1, 0, 0], [1, 1, 0, 0]) == 1.0


def test_kappa_no_better_than_chance():
    # machine all-0 vs human [1,1,0,0]: p_o=0.5, p_e=0.5 -> κ=0
    assert cohen_kappa([1, 1, 0, 0], [0, 0, 0, 0]) == 0.0


def test_kappa_length_mismatch_raises():
    with pytest.raises(ValueError):
        cohen_kappa([1, 0], [1])


def test_drift_floor():
    v = detect_drift([0.3], min_kappa=0.6)
    assert v.drifted and v.reason == "floor"


def test_drift_drop_from_baseline():
    v = detect_drift([0.9, 0.7], min_kappa=0.6, max_drop=0.1)
    assert v.drifted and v.reason == "drop" and v.baseline == 0.9 and v.drop == pytest.approx(0.2)


def test_drift_ok_when_stable():
    v = detect_drift([0.8, 0.82, 0.81], min_kappa=0.6, max_drop=0.1)
    assert not v.drifted and v.reason == "ok"


def test_drift_empty_raises():
    with pytest.raises(ValueError):
        detect_drift([])
