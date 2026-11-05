"""Командная строка.

    python -m sppr weights                 веса критериев и согласованность
    python -m sppr check --date 2026-11-01  проверка состояния перед расчётом
    python -m sppr plan --date 2026-11-01   проект заказа и рейтинг поставщиков
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime
from pathlib import Path

from . import __version__, ahp, db, plan
from .config import CRITERIA, Settings, load

EXPECTED_TABLES = 15


def cmd_weights(s: Settings, args) -> int:
    r = ahp.weights(s.pairwise)
    for name, w in zip(CRITERIA, r.weights):
        print(f"{name:<18} {w:.3f}")
    print(f"lambda_max = {r.lambda_max:.4f}, ИС = {r.ci:.4f}, ОС = {r.cr:.4f}")
    ok = r.cr < s.max_cr
    print("матрица согласована" if ok else "матрица НЕ согласована")
    return 0 if ok else 1


def cmd_check(s: Settings, args) -> int:
    """Проверки перед расчётом; код возврата 0 — всё в порядке."""
    checks = []
    try:
        with db.connect() as conn:
            checks.append(("подключение к базе", True, "есть"))
            n = db.table_count(conn)
            checks.append(("таблиц в схеме", n == EXPECTED_TABLES, str(n)))
            cur = conn.cursor()
            cur.execute("SELECT max(data) FROM otgruzka")
            last = cur.fetchone()[0]
            age = (args.date - last).days if last else None
            checks.append(("возраст данных, дней",
                           age is not None and 0 <= age <= s.max_data_age_days,
                           str(age)))
    except Exception as e:                       # noqa: BLE001 — сообщаем любую причину
        checks.append(("подключение к базе", False, type(e).__name__))
    r = ahp.weights(s.pairwise)
    checks.append(("согласованность весов", r.cr < s.max_cr, f"ОС = {r.cr:.4f}"))
    for name, ok, value in checks:
        print(f"[{'ок' if ok else 'СБОЙ'}] {name}: {value}")
    return 0 if all(ok for _, ok, _ in checks) else 1


def cmd_plan(s: Settings, args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with db.connect() as conn:
        data = db.load(conn, s.history_start, s.history_end, args.date)
        p = plan.build(data, s, args.date)
        saved = db.save_scores(conn, p.scores, args.date) if not args.dry_run else 0

    stamp = args.date.isoformat()
    with open(out / f"plan_{stamp}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["товар", "ABC", "XYZ", "доступно", "точка перезаказа",
                    "экономичная партия", "к заказу", "поставщик", "цена",
                    "срок, дней", "балл", "оценка предварительная",
                    "ручной контроль", "сумма"])
        for x in p.lines:
            w.writerow([x.name, x.abc, x.xyz, f"{x.available:.0f}",
                        f"{x.reorder_point:.0f}", f"{x.eoq:.0f}", x.quantity,
                        x.supplier_name, f"{x.price:.2f}", x.lead_days,
                        f"{x.score:.3f}", "да" if x.preliminary else "нет",
                        "да" if x.manual else "нет", f"{x.amount:.2f}"])
    with open(out / f"rating_{stamp}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["код товара", "код поставщика", "цена", "срок", "надёжность",
                    "отсрочка", "итог", "предварительная"])
        for x in sorted(p.scores, key=lambda x: (x.item, -x.total)):
            w.writerow([x.item, x.supplier, f"{x.price:.3f}", f"{x.lead:.3f}",
                        f"{x.reliability:.3f}", f"{x.deferral:.3f}",
                        f"{x.total:.3f}", "да" if x.preliminary else "нет"])

    total = sum(x.amount for x in p.lines)
    status = {
        "версия": __version__,
        "время": datetime.now().isoformat(timespec="seconds"),
        "дата расчёта": stamp,
        "позиций к заказу": len(p.lines),
        "сумма заказа": round(total, 2),
        "ручной контроль": sum(x.manual for x in p.lines),
        "поставщиков ниже минимальной суммы": len(p.below_minimum),
        "оценок записано": saved,
        "отношение согласованности": round(p.weights.cr, 4),
    }
    (out / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    for k, v in status.items():
        print(f"{k}: {v}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sppr", description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, help="файл параметров JSON")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("weights")
    for name in ("check", "plan"):
        p = sub.add_parser(name)
        p.add_argument("--date", type=date.fromisoformat, default=date.today())
    sub.choices["plan"].add_argument("--out", default="out")
    sub.choices["plan"].add_argument("--dry-run", action="store_true",
                                     help="не записывать оценки в базу")
    args = ap.parse_args(argv)
    s = load(args.config)
    handler = {"weights": cmd_weights, "check": cmd_check, "plan": cmd_plan}[args.cmd]
    try:
        return handler(s, args)
    except plan.InconsistentWeights as e:
        print("ошибка:", e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
