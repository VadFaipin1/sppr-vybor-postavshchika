import pytest

from sppr.ahp import check_matrix, weights
from sppr.config import Settings


def test_equal_matrix_gives_equal_weights():
    r = weights([[1] * 4 for _ in range(4)])
    assert r.weights == pytest.approx((0.25, 0.25, 0.25, 0.25))
    assert r.cr == pytest.approx(0, abs=1e-9)


def test_saaty_example():
    # классический пример 3×3: веса около 0,637, 0,258, 0,105, ОС около 0,03
    r = weights([[1, 3, 5], [1 / 3, 1, 3], [1 / 5, 1 / 3, 1]])
    assert r.weights == pytest.approx((0.637, 0.258, 0.105), abs=0.001)
    assert r.cr == pytest.approx(0.033, abs=0.001)


def test_default_matrix_is_consistent():
    r = weights(Settings().pairwise)
    assert sum(r.weights) == pytest.approx(1)
    assert r.cr < 0.10
    # цена и надёжность заданы равнозначными
    assert r.weights[0] == pytest.approx(r.weights[2])


def test_cyclic_preferences_are_inconsistent():
    # A лучше B, B лучше C, но C лучше A — так рассуждать нельзя
    r = weights([[1, 5, 1 / 5], [1 / 5, 1, 5], [5, 1 / 5, 1]])
    assert r.cr > 0.10


def test_not_reciprocal_matrix_rejected():
    with pytest.raises(ValueError):
        check_matrix([[1, 2], [2, 1]])


def test_config_rejects_wrong_matrix_size(tmp_path):
    from sppr.config import load
    cfg = tmp_path / "small.json"
    cfg.write_text('{"pairwise": [[1, 2], ["1/2", 1]]}', encoding="utf-8")
    with pytest.raises(ValueError):
        load(cfg)
