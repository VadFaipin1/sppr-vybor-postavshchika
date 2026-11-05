#!/usr/bin/env python3
"""Графики к разделу 2 по данным базы vektor_opt.

Светлая тема: отчёт уходит преподавателю на печать (решение от 05.11.2026).
Ширина рисунков подобрана под предел 160 мм по ГОСТ.

    python3 charts.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                        # noqa: E402
from matplotlib.ticker import PercentFormatter                         # noqa: E402

HERE = Path(__file__).resolve().parent
IMG = HERE.parent / "img"
БАЗА = "vektor_opt"

ММ = 1 / 25.4
ШИРИНА = 160 * ММ
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.grid": True,
    "grid.color": "#d0d0d0",
    "grid.linewidth": 0.6,
    "axes.edgecolor": "#444444",
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
})
СИНИЙ, ЗЕЛЁНЫЙ, ОХРА, СЕРЫЙ = "#3b6ea5", "#5a9367", "#c8893b", "#8a8a8a"


def запрос(sql: str) -> list[list[str]]:
    """psql без вывода служебных строк: схема задаётся параметром подключения,
    а не командой SET, иначе её ответ попадает в выдачу отдельной строкой."""
    окружение = {**os.environ, "PGOPTIONS": "-c search_path=zakupki"}
    r = subprocess.run(["psql", "-d", БАЗА, "-At", "-F", "\x1f", "-c", sql],
                       capture_output=True, text=True, check=True, env=окружение)
    return [с.split("\x1f") for с in r.stdout.strip().split("\n") if с]


def парето() -> str:
    """Кривая ABC: накопленная доля выручки по позициям, отсортированным по убыванию."""
    строки = запрос("""
        SELECT t.naimenovanie, sum(so.kolichestvo * so.cena) AS v
        FROM stroka_otgruzki so JOIN tovar t ON t.id = so.tovar_id
        GROUP BY t.id, t.naimenovanie ORDER BY v DESC """)
    выручка = [float(v) for _, v in строки]
    всего = sum(выручка)
    накоп, s = [], 0.0
    for v in выручка:
        s += v
        накоп.append(s / всего)
    n = list(range(1, len(выручка) + 1))

    фиг, ось = plt.subplots(figsize=(ШИРИНА, 70 * ММ))
    ось.bar(n, [v / 1e6 for v in выручка], color=СИНИЙ, width=0.75,
            label="Выручка позиции")
    ось.set_xlabel("Позиции номенклатуры, упорядоченные по убыванию выручки")
    ось.set_ylabel("Выручка за год, млн руб.")
    ось.set_xlim(0.3, len(n) + 0.7)

    вторая = ось.twinx()
    вторая.plot(n, накоп, color=ОХРА, linewidth=1.8, marker="o", markersize=2.5,
                label="Накопленная доля")
    вторая.yaxis.set_major_formatter(PercentFormatter(1.0))
    вторая.set_ylabel("Накопленная доля выручки")
    вторая.set_ylim(0, 1.04)
    вторая.grid(False)
    for уровень, подпись in ((0.80, "80 %"), (0.95, "95 %")):
        вторая.axhline(уровень, color=СЕРЫЙ, linestyle="--", linewidth=0.9)
        вторая.text(len(n) + 0.5, уровень + 0.015, подпись, fontsize=8,
                    color=СЕРЫЙ, ha="right")
    # границы классов: первая позиция, перешагнувшая порог
    for порог, цвет in ((0.80, ЗЕЛЁНЫЙ), (0.95, ЗЕЛЁНЫЙ)):
        граница = next(i for i, d in enumerate(накоп, 1) if d > порог)
        ось.axvline(граница - 0.5, color=цвет, linewidth=1.0)
    линии = ось.get_legend_handles_labels()[0] + вторая.get_legend_handles_labels()[0]
    метки = ось.get_legend_handles_labels()[1] + вторая.get_legend_handles_labels()[1]
    ось.legend(линии, метки, loc="center right", framealpha=0.95, fontsize=8)
    путь = IMG / "abc_pareto.png"
    фиг.savefig(путь)
    plt.close(фиг)
    граница_a = next(i for i, d in enumerate(накоп, 1) if d > 0.80)
    граница_b = next(i for i, d in enumerate(накоп, 1) if d > 0.95)
    return (f"abc_pareto.png: позиций {len(n)}, граница A на {граница_a - 1}, "
            f"граница B на {граница_b - 1}, выручка {всего / 1e6:.1f} млн руб.")


def матрица() -> str:
    """Матрица ABC-XYZ: сколько позиций в каждой клетке."""
    строки = запрос("""
        WITH prodazhi AS (
            SELECT t.id, sum(so.kolichestvo * so.cena) AS v
            FROM stroka_otgruzki so JOIN tovar t ON t.id = so.tovar_id
            GROUP BY t.id
        ), abc AS (
            SELECT id, CASE WHEN sum(v) OVER (ORDER BY v DESC) / sum(v) OVER () <= 0.80
                            THEN 'A'
                            WHEN sum(v) OVER (ORDER BY v DESC) / sum(v) OVER () <= 0.95
                            THEN 'B' ELSE 'C' END AS k
            FROM prodazhi
        ), nedeli AS (
            SELECT so.tovar_id, date_trunc('week', o.data) AS w, sum(so.kolichestvo) AS s
            FROM stroka_otgruzki so JOIN otgruzka o ON o.id = so.otgruzka_id
            GROUP BY so.tovar_id, date_trunc('week', o.data)
            HAVING count(DISTINCT o.data) = 6
        ), xyz AS (
            SELECT tovar_id, CASE WHEN stddev_samp(s) / avg(s) < 0.10 THEN 'X'
                                  WHEN stddev_samp(s) / avg(s) < 0.25 THEN 'Y'
                                  ELSE 'Z' END AS k
            FROM nedeli GROUP BY tovar_id
        )
        SELECT abc.k, xyz.k, count(*) FROM abc JOIN xyz ON xyz.tovar_id = abc.id
        GROUP BY abc.k, xyz.k ORDER BY abc.k, xyz.k """)
    клетки = {(a, x): int(n) for a, x, n in строки}
    сетка = [[клетки.get((a, x), 0) for x in "XYZ"] for a in "ABC"]

    фиг, ось = plt.subplots(figsize=(85 * ММ, 62 * ММ))
    картинка = ось.imshow(сетка, cmap="Blues", vmin=0, vmax=max(max(с) for с in сетка))
    ось.set_xticks(range(3), ["X", "Y", "Z"])
    ось.set_yticks(range(3), ["A", "B", "C"])
    ось.set_xlabel("Устойчивость спроса (XYZ)")
    ось.set_ylabel("Вклад в выручку (ABC)")
    ось.grid(False)
    предел = max(max(с) for с in сетка) / 2
    for i in range(3):
        for j in range(3):
            ось.text(j, i, сетка[i][j], ha="center", va="center", fontsize=11,
                     color="white" if сетка[i][j] > предел else "#1a1a1a")
    фиг.colorbar(картинка, ax=ось, shrink=0.8, label="Позиций")
    путь = IMG / "abc_xyz.png"
    фиг.savefig(путь)
    plt.close(фиг)
    всего = sum(sum(с) for с in сетка)
    return (f"abc_xyz.png: позиций в матрице {всего}, "
            f"AX {клетки.get(('A','X'), 0)}, AZ {клетки.get(('A','Z'), 0)}")


def поставщики() -> str:
    """Дисциплина поставщиков: доля поставок в срок и среднее опоздание."""
    строки = запрос("""
        SELECT p.naimenovanie,
               100.0 * count(*) FILTER (WHERE pv.fakt_data <= z.plan_data_postavki)
                   / count(*),
               avg(pv.fakt_data - z.plan_data_postavki)
        FROM postavka pv
            JOIN zakaz_postavshchiku z ON z.id = pv.zakaz_id
            JOIN postavshchik p ON p.id = z.postavshchik_id
        GROUP BY p.naimenovanie ORDER BY 2 """)
    имена = [и.replace("ООО ", "").replace("АО ", "").strip("«»") for и, _, _ in строки]
    доли = [float(d) for _, d, _ in строки]
    опоздания = [float(o) for _, _, o in строки]

    фиг, (левая, правая) = plt.subplots(
        1, 2, figsize=(ШИРИНА, 78 * ММ), sharey=True,
        gridspec_kw={"width_ratios": [1.5, 1]})
    y = range(len(имена))
    левая.barh(list(y), доли, color=СИНИЙ, height=0.7)
    левая.set_yticks(list(y), имена)
    левая.set_xlabel("Поставок в срок, %")
    левая.set_xlim(0, 100)
    левая.axvline(90, color=ОХРА, linestyle="--", linewidth=1.0)
    левая.text(90.8, -0.6, "целевой уровень 90 %", fontsize=7.5, color=ОХРА)
    for i, д in enumerate(доли):
        левая.text(д + 1.2, i, f"{д:.0f}", va="center", fontsize=7.5)

    правая.barh(list(y), опоздания, color=ОХРА, height=0.7)
    правая.set_xlabel("Среднее опоздание, дней")
    for i, о in enumerate(опоздания):
        правая.text(о + 0.04, i, f"{о:.2f}", va="center", fontsize=7.5)
    правая.set_xlim(0, max(опоздания) * 1.25)
    фиг.tight_layout()
    путь = IMG / "postavshchiki.png"
    фиг.savefig(путь)
    plt.close(фиг)
    return (f"postavshchiki.png: поставщиков {len(имена)}, "
            f"худший {доли[0]:.1f} % в срок при опоздании {опоздания[0]:.2f} дня, "
            f"лучший {доли[-1]:.1f} %")


def main() -> int:
    IMG.mkdir(exist_ok=True)
    строки = [парето(), матрица(), поставщики()]
    for с in строки:
        print(с)
    (HERE.parent / "charts.log").write_text("\n".join(строки) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
