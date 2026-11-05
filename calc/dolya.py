#!/usr/bin/env python3
"""Во что обходится ограничение доли одного поставщика. Пишет logs/dolya.log.

    .venv/bin/python calc/dolya.py
"""
from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date
from pathlib import Path
from statistics import mean

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))
from sppr import db, plan                                              # noqa: E402
from sppr.config import Settings                                       # noqa: E402

AS_OF = date(2026, 11, 1)


def сводка(p) -> dict:
    сумма = sum(x.amount for x in p.lines)
    доли: dict[str, float] = {}
    for x in p.lines:
        доли[x.supplier_name] = доли.get(x.supplier_name, 0) + x.amount
    лидер = max(доли, key=доли.get)
    return {"строк": len(p.lines), "сумма": сумма, "лидер": лидер,
            "доля лидера": доли[лидер] / сумма, "поставщиков": len(доли),
            "средний балл": mean(x.score for x in p.lines),
            "средний срок": mean(x.lead_days for x in p.lines),
            "ниже минимума": len(p.below_minimum)}


def main() -> None:
    base = Settings()
    with db.connect() as c:
        d = db.load(c, base.history_start, base.history_end, AS_OF)
    без = plan.build(d, replace(base, max_supplier_share=1.0), AS_OF)
    с = plan.build(d, replace(base, max_supplier_share=0.40), AS_OF)
    а, б = сводка(без), сводка(с)
    out = [f"{'показатель':<22} {'без ограничения':>18} {'с ограничением 40 %':>20}"]
    for k in ("строк", "поставщиков", "ниже минимума"):
        out.append(f"{k:<22} {а[k]:>18} {б[k]:>20}")
    out.append(f"{'сумма, руб.':<22} {а['сумма']:>18.2f} {б['сумма']:>20.2f}")
    out.append(f"{'доля лидера, %':<22} {а['доля лидера'] * 100:>18.1f} {б['доля лидера'] * 100:>20.1f}")
    out.append(f"{'лидер':<22} {а['лидер']:>18} {б['лидер']:>20}")
    out.append(f"{'средний балл':<22} {а['средний балл']:>18.3f} {б['средний балл']:>20.3f}")
    out.append(f"{'средний срок, дней':<22} {а['средний срок']:>18.2f} {б['средний срок']:>20.2f}")
    out.append(f"разница в сумме: {б['сумма'] - а['сумма']:+.2f} руб. "
               f"({(б['сумма'] / а['сумма'] - 1) * 100:+.2f} %)")
    out.append("")
    out.append("переданы следующему в рейтинге:")
    прежние = {x.item: x for x in без.lines}
    for x in с.lines:
        if x.moved:
            п = прежние[x.item]
            out.append(f"  {x.name}: {п.supplier_name} ({п.score:.3f}, {п.amount:.2f} руб.) -> "
                       f"{x.supplier_name} ({x.score:.3f}, {x.amount:.2f} руб.)")
    текст = "\n".join(out)
    print(текст)
    (BASE / "logs" / "dolya.log").write_text(текст + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
