#!/usr/bin/env python3
"""Замеры для проектного обоснования: объём базы, рост на всю номенклатуру
и время расчёта проекта заказа. Пишет logs/zamery.log.

    .venv/bin/python calc/zamery.py
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from statistics import median

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))
from sppr import db, plan                                              # noqa: E402
from sppr.config import Settings                                       # noqa: E402

ПОЗИЦИЙ_В_ВЫБОРКЕ = 40
ПОЗИЦИЙ_В_ОРГАНИЗАЦИИ = 3400        # Таблица 1.1
ПРОГОНОВ = 5


def main() -> None:
    строки = []
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT pg_database_size(current_database()), "
                    "pg_size_pretty(pg_database_size(current_database()))")
        байт, читаемо = cur.fetchone()
        cur.execute("""SELECT sum(pg_total_relation_size(c.oid))
                       FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                       WHERE n.nspname = 'zakupki' AND c.relkind = 'r'""")
        схема = int(cur.fetchone()[0])
        cur.execute("SELECT count(*) FROM stroka_otgruzki")
        строк_отгрузки = cur.fetchone()[0]
    множитель = ПОЗИЦИЙ_В_ОРГАНИЗАЦИИ / ПОЗИЦИЙ_В_ВЫБОРКЕ
    строки += [
        f"размер базы целиком: {читаемо} ({байт} байт)",
        f"размер схемы zakupki с индексами: {схема / 1024 / 1024:.1f} МБ",
        f"строк отгрузки за год: {строк_отгрузки}",
        f"масштаб на всю номенклатуру: x{множитель:.0f}",
        f"оценка схемы за год на {ПОЗИЦИЙ_В_ОРГАНИЗАЦИИ} позиций: "
        f"{схема * множитель / 1024 / 1024:.0f} МБ, строк отгрузки "
        f"{строк_отгрузки * множитель / 1e6:.2f} млн",
    ]

    s = Settings()
    времена = []
    for _ in range(ПРОГОНОВ):
        t0 = time.perf_counter()
        with db.connect() as conn:
            d = db.load(conn, s.history_start, s.history_end, date(2026, 11, 1))
        plan.build(d, s, date(2026, 11, 1))
        времена.append(time.perf_counter() - t0)
    строки.append(f"время расчёта (загрузка и план), медиана {ПРОГОНОВ} прогонов: "
                  f"{median(времена):.3f} с, разброс {min(времена):.3f}-{max(времена):.3f} с")
    текст = "\n".join(строки)
    print(текст)
    (BASE / "logs" / "zamery.log").write_text(текст + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
