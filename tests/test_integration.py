"""Проверки на учебной базе. Без базы пропускаются, а не падают."""
from collections import Counter
from datetime import date

import pytest

from sppr import __main__ as cli
from sppr import db, plan
from sppr.config import Settings

AS_OF = date(2026, 11, 1)


@pytest.fixture(scope="module")
def data():
    try:
        conn = db.connect()
    except Exception as e:                        # noqa: BLE001
        pytest.skip(f"нет базы: {e}")
    s = Settings()
    with conn:
        yield db.load(conn, s.history_start, s.history_end, AS_OF)


def test_classes_match_sql(data):
    # компонент обязан классифицировать так же, как запросы подраздела 2.2
    p = plan.build(data, Settings(), AS_OF)
    assert Counter(p.abc.values()) == {"A": 24, "B": 10, "C": 6}
    assert Counter(p.xyz.values()) == {"X": 3, "Y": 34, "Z": 3}


def test_plan_lines_are_valid(data):
    p = plan.build(data, Settings(), AS_OF)
    assert p.lines
    for line in p.lines:
        assert line.available <= line.reorder_point
        assert line.quantity > 0
        assert line.quantity % data.items[line.item].pack == 0


def test_plan_is_repeatable(data):
    a = plan.build(data, Settings(), AS_OF)
    b = plan.build(data, Settings(), AS_OF)
    assert a.lines == b.lines


def test_scores_rewritten_not_duplicated(data):
    p = plan.build(data, Settings(), AS_OF)
    test_day = date(2099, 1, 1)
    with db.connect() as conn:
        with conn.transaction(force_rollback=True):
            first = db.save_scores(conn, p.scores, test_day)
            db.save_scores(conn, p.scores, test_day)
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM ocenka_postavshchika "
                        "WHERE data_ocenki = %s", (test_day,))
            assert cur.fetchone()[0] == first == len(data.offers)


def test_check_passes(data):
    assert cli.main(["check", "--date", AS_OF.isoformat()]) == 0


def test_inconsistent_weights_refused(data, tmp_path):
    cfg = tmp_path / "bad.json"
    # A лучше B, B лучше C, C лучше D, но D лучше A: цикл предпочтений
    cfg.write_text('{"pairwise": [[1, 5, 1, "1/5"], ["1/5", 1, 5, 1], '
                   '[1, "1/5", 1, 5], [5, 1, "1/5", 1]]}', encoding="utf-8")
    code = cli.main(["--config", str(cfg), "plan", "--date", AS_OF.isoformat(),
                     "--out", str(tmp_path), "--dry-run"])
    assert code == 2
