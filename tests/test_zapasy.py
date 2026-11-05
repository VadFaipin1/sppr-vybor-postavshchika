import pytest

from sppr.zapasy import eoq, order_quantity, reorder_point, shelf_cap, z_value


def test_reorder_point():
    # 10 · 9 + 1,65 · 4 · √9 = 90 + 19,8
    assert reorder_point(10, 4, 9, 1.65) == pytest.approx(109.8)


def test_eoq_wilson():
    # √(2 · 20 000 · 1200 / 12) = 2000
    assert eoq(20000, 1200, 12) == pytest.approx(2000)


def test_eoq_without_demand():
    assert eoq(0, 1200, 12) == 0


def test_z_value_for_95_percent():
    assert z_value(0.95) == pytest.approx(1.6449, abs=1e-4)


def test_quantity_rounded_up_to_pack():
    assert order_quantity(101, 0, None, 12) == 108
    assert order_quantity(96, 0, None, 12) == 96


def test_shortfall_wins_over_small_batch():
    assert order_quantity(100, 250, None, 10) == 250


def test_shelf_life_cap_rounds_down():
    assert order_quantity(1000, 0, 500, 12) == 492


def test_shelf_life_cap_keeps_one_pack():
    assert order_quantity(1000, 0, 5, 12) == 12


def test_shelf_cap_for_unlimited_life():
    assert shelf_cap(10, None, 0.5) is None
    assert shelf_cap(10, 90, 0.5) == pytest.approx(450)
