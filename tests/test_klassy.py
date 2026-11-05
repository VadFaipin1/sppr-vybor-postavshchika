from sppr.klassy import abc, variation, xyz


def test_abc_by_cumulative_share():
    # накопленные доли: 0,50 0,80 0,95 1,00
    got = abc({1: 50, 2: 30, 3: 15, 4: 5}, (0.80, 0.95))
    assert got == {1: "A", 2: "A", 3: "B", 4: "C"}


def test_xyz_by_variation():
    got = xyz({1: [100, 100, 100], 2: [100, 120, 80], 3: [10, 60, 5]}, (0.10, 0.25))
    assert got == {1: "X", 2: "Y", 3: "Z"}


def test_variation_of_one_week_is_unknown():
    assert variation([100]) == float("inf")
