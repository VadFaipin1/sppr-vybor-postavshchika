import pytest

from sppr.rejting import Offer, Score, Track, best, lower_is_better, reliability, score


def test_range_gives_extremes():
    assert lower_is_better(76.66, 76.66, 78.42, "range") == 1
    assert lower_is_better(78.42, 76.66, 78.42, "range") == 0


def test_single_offer_gets_full_score():
    assert lower_is_better(50, 50, 50, "range") == 1
    assert lower_is_better(50, 50, 50, "tolerance") == 1


def test_tolerance_is_linear_and_clipped():
    # дороже на 10 % при допуске 20 % — половина балла, дороже на 25 % — ноль
    assert lower_is_better(110, 100, 125, "tolerance", 0.2) == pytest.approx(0.5)
    assert lower_is_better(125, 100, 125, "tolerance", 0.2) == 0


def test_small_price_gap_stays_small():
    # разница в 2 % по размаху даёт ноль, с допуском — почти полный балл
    assert lower_is_better(102, 100, 102, "range") == 0
    assert lower_is_better(102, 100, 102, "tolerance", 0.2) == pytest.approx(0.9)


def test_new_supplier_gets_neutral_reliability():
    tracks = {1: Track(10, 9), 2: Track(10, 5), 3: Track(10, 7)}
    r = reliability(tracks, {1, 2, 3, 4}, min_deliveries=5)
    assert r[4] == (pytest.approx(0.7), True)        # медиана 0,9 0,5 0,7
    assert r[1] == (pytest.approx(0.9), False)


def test_short_history_is_preliminary():
    tracks = {1: Track(10, 9), 2: Track(10, 5), 3: Track(3, 3)}
    value, prelim = reliability(tracks, {3}, min_deliveries=5)[3]
    assert prelim and value == pytest.approx(0.7)    # не 1,0 за три поставки


def test_total_is_weighted_sum():
    offers = [Offer(1, 1, 100, 5, 30), Offer(2, 1, 110, 10, 60)]
    tracks = {1: Track(10, 10), 2: Track(10, 5)}
    got = {s.supplier: s for s in score(offers, tracks, (0.4, 0.3, 0.2, 0.1), 5, "range")}
    # поставщик 1: цена 1, срок 1, надёжность 1, отсрочка 0,5
    assert got[1].total == pytest.approx(0.4 + 0.3 + 0.2 + 0.05)
    # поставщик 2: цена 0, срок 0, надёжность 0,5, отсрочка 1
    assert got[2].total == pytest.approx(0.2 * 0.5 + 0.1)


def test_best_breaks_tie_by_code():
    s = [Score(2, 1, 0, 0, 0, 0, 0.5, False), Score(1, 1, 0, 0, 0, 0, 0.5, False)]
    assert best(s)[1].supplier == 1


def test_share_cap_moves_cheapest_loss_first():
    from sppr.plan import Line, cap_share

    def line(item, sup, price, score):
        return Line(item, f"т{item}", "A", "Y", 0, 10, 10, 10, sup, f"п{sup}", price,
                    5, score, False, False)

    # у поставщика 1 три строки из четырёх, 75 % суммы
    lines = [line(1, 1, 10, 0.9), line(2, 1, 10, 0.9), line(3, 1, 10, 0.9),
             line(4, 2, 10, 0.8)]
    ranked = {
        1: [Score(1, 1, 0, 0, 0, 0, 0.9, False), Score(3, 1, 0, 0, 0, 0, 0.5, False)],
        2: [Score(1, 2, 0, 0, 0, 0, 0.9, False), Score(3, 2, 0, 0, 0, 0, 0.85, False)],
        3: [Score(1, 3, 0, 0, 0, 0, 0.9, False), Score(3, 3, 0, 0, 0, 0, 0.7, False)],
        4: [Score(2, 4, 0, 0, 0, 0, 0.8, False)],
    }

    def make(item, top):
        return line(item, top.supplier, 10, top.total)

    out = cap_share(lines, ranked, make, limit=0.5)
    by_item = {x.item: x for x in out}
    # уходит позиция 2: у неё самая малая потеря балла, 0,05
    assert by_item[2].supplier == 3 and by_item[2].moved
    assert by_item[1].supplier == 1 and not by_item[1].moved
    assert sum(x.amount for x in out if x.supplier == 1) / sum(x.amount for x in out) <= 0.5
