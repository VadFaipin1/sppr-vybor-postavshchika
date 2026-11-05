#!/usr/bin/env python3
"""Сравнение способов нормировки критериев рейтинга поставщиков.

Для каждого способа: что получает закупщик по всем 40 позициям — переплату
к лучшей цене, срок поставки и надёжность выбранных поставщиков.

    ../.venv/bin/python calc/normirovka.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from statistics import mean

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))
from sppr import ahp, db, rejting                                     # noqa: E402
from sppr.config import Settings                                       # noqa: E402

СПОСОБЫ = [("range", "по размаху (подраздел 2.2)"),
           ("ratio", "отношение к лучшему"),
           ("tolerance", "с допуском 20 % и втрое")]


def main() -> None:
    s = Settings()
    with db.connect() as c:
        d = db.load(c, s.history_start, s.history_end, date(2026, 11, 1))
    w = ahp.weights(s.pairwise).weights
    предложения = {(o.supplier, o.item): o for o in d.offers}
    лучшая_цена = {}
    for o in d.offers:
        лучшая_цена[o.item] = min(лучшая_цена.get(o.item, o.price), o.price)
    надёжность = {k: t.on_time / t.deliveries for k, t in d.tracks.items()}
    выбор = {}
    строки = [f"{'способ':<28} {'переплата, %':>13} {'срок, дн':>9} {'в срок, %':>10}"
              f" {'не самый дешёвый':>17} {'отличий от 2.2':>15}"]
    for метод, имя in СПОСОБЫ:
        sc = rejting.score(d.offers, d.tracks, w, s.min_deliveries, метод,
                           s.price_tolerance, s.lead_tolerance)
        выбор[метод] = rejting.best(sc)
        offers = [предложения[(b.supplier, i)] for i, b in выбор[метод].items()]
        переплата = mean((o.price / лучшая_цена[o.item] - 1) * 100 for o in offers)
        срок = mean(o.lead_days for o in offers)
        в_срок = mean(надёжность[o.supplier] * 100 for o in offers)
        не_дешёвый = sum(o.price > лучшая_цена[o.item] for o in offers)
        отличий = sum(выбор[метод][i].supplier != выбор["range"][i].supplier
                      for i in выбор[метод])
        строки.append(f"{имя:<28} {переплата:>13.2f} {срок:>9.2f} {в_срок:>10.1f}"
                      f" {не_дешёвый:>17} {отличий:>15}")
    # какую долю выгоды «отношения к лучшему» над «размахом» берёт «допуск»
    сводка = {}
    for метод, _ in СПОСОБЫ:
        offers = [предложения[(b.supplier, i)] for i, b in выбор[метод].items()]
        сводка[метод] = (mean((o.price / лучшая_цена[o.item] - 1) * 100 for o in offers),
                         mean(o.lead_days for o in offers),
                         mean(надёжность[o.supplier] * 100 for o in offers))
    р, о, д = сводка["range"], сводка["ratio"], сводка["tolerance"]
    строки.append("")
    строки.append(f"допуск берёт выгоды отношения над размахом: по сроку "
                  f"{(р[1] - д[1]) / (р[1] - о[1]) * 100:.0f} %, по поставкам в срок "
                  f"{(д[2] - р[2]) / (о[2] - р[2]) * 100:.0f} %, "
                  f"а переплаты — {(д[0] - р[0]) / (о[0] - р[0]) * 100:.0f} %")
    строки.append("")
    строки.append("предложения по позициям из текста (цена, срок, доля в срок, дороже самого дешёвого):")
    for i in (17, 27, 32):
        строки.append(f"  {d.items[i].name}:")
        for o in sorted((o for o in d.offers if o.item == i), key=lambda o: o.price):
            строки.append(f"    {d.suppliers[o.supplier][0]} | {o.price:.2f} руб. | "
                          f"{o.lead_days} дн | в срок {надёжность[o.supplier]:.3f} | "
                          f"+{(o.price / лучшая_цена[i] - 1) * 100:.1f} %")
    строки.append("")
    for i in (1, 17, 27, 32):
        имена = {м: d.suppliers[выбор[м][i].supplier][0] for м, _ in СПОСОБЫ}
        строки.append(f"{d.items[i].name}: " + "; ".join(f"{м} — {имена[м]}" for м, _ in СПОСОБЫ))
    текст = "\n".join(строки)
    print(текст)
    (BASE / "calc" / "normirovka.log").write_text(текст + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
