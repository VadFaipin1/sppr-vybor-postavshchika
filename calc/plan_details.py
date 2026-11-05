#!/usr/bin/env python3
"""Детали проекта заказа для таблиц раздела 3: строки, суммы по поставщикам,
рейтинг по одной позиции. Пишет logs/plan_details.log.

    .venv/bin/python calc/plan_details.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))
from sppr import db, plan                                              # noqa: E402
from sppr.config import Settings                                       # noqa: E402

AS_OF = date(2026, 11, 1)


def main() -> None:
    s = Settings()
    with db.connect() as c:
        d = db.load(c, s.history_start, s.history_end, AS_OF)
    p = plan.build(d, s, AS_OF)
    out = [f"позиций к заказу: {len(p.lines)}, сумма {sum(x.amount for x in p.lines):.2f}"]
    out.append("товар | ABC | XYZ | доступно | ТП | EOQ | к заказу | поставщик | срок | балл | ручной | сумма")
    for x in sorted(p.lines, key=lambda x: x.available / max(x.reorder_point, 1)):
        out.append(f"{x.name} | {x.abc} | {x.xyz} | {x.available:.0f} | {x.reorder_point:.0f} | "
                   f"{x.eoq:.0f} | {x.quantity} | {x.supplier_name} | {x.lead_days} | "
                   f"{x.score:.3f} | {'да' if x.manual else 'нет'} | {x.amount:.2f}")
    out.append("")
    out.append("суммы по поставщикам (сумма | минимум | ниже минимума):")
    суммы = {}
    for x in p.lines:
        суммы[x.supplier] = суммы.get(x.supplier, 0) + x.amount
    for sup, total in sorted(суммы.items(), key=lambda kv: -kv[1]):
        имя, минимум = d.suppliers[sup]
        out.append(f"  {имя} | {total:.2f} | {минимум:.0f} | {'да' if total < минимум else 'нет'}")
    out.append("")
    out.append("рейтинг по позиции 1 (крупа гречневая), нормировка с допуском:")
    for x in sorted((x for x in p.scores if x.item == 1), key=lambda x: -x.total):
        out.append(f"  {d.suppliers[x.supplier][0]} | цена {x.price:.3f} | срок {x.lead:.3f} | "
                   f"надёжность {x.reliability:.3f} | отсрочка {x.deferral:.3f} | итог {x.total:.3f}")
    out.append("")
    ручные = [x.name for x in p.lines if x.manual]
    out.append(f"ручной контроль: {', '.join(ручные)}")
    текст = "\n".join(out)
    print(текст)
    (BASE / "logs" / "plan_details.log").write_text(текст + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
