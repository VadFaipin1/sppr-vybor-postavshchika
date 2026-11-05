#!/usr/bin/env python3
"""Диаграмма потоков данных нулевого уровня (нотация Гейна-Сарсона).

Раскладка силовая (fdp): у потоков данных нет слоёв, и послойная раскладка
dot растягивает схему в ленту 5827 px шириной, где текст садится до 3 пт.

Внешние сущности — прямоугольники, процессы — прямоугольники со скруглением
и номером, хранилища — открытые справа прямоугольники с кодом D1…D5.

    python3 dfd.py          # пишет ../img/dfd.svg и ../img/dfd.png
"""
from __future__ import annotations

import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMG = HERE.parent / "img"
ШРИФТ = "Times New Roman"

ВНЕШНИЕ = [
    ("klient", "Клиент"),
    ("postavshchik", "Поставщик"),
    ("rukovoditel", "Руководитель\nотдела закупок"),
]

ПРОЦЕССЫ = [
    ("p1", "1", "Учёт продаж\nи остатков"),
    ("p2", "2", "Расчёт потребности\nв закупке"),
    ("p3", "3", "Оценка и выбор\nпоставщика"),
    ("p4", "4", "Формирование\nи размещение заказа"),
    ("p5", "5", "Приёмка\nи оприходование"),
    ("p6", "6", "Отгрузка клиенту"),
]

ХРАНИЛИЩА = [
    ("d1", "D1", "Номенклатура и остатки"),
    ("d2", "D2", "Поставщики и прайсы"),
    ("d3", "D3", "История поставок"),
    ("d4", "D4", "История продаж"),
    ("d5", "D5", "Оценки поставщиков"),
]

ПОТОКИ = [
    ("klient", "p6", "заявка клиента"),
    ("p6", "klient", "товар, УПД"),
    ("p6", "d4", "запись о продаже"),
    ("p6", "d1", "списание остатка"),
    ("d1", "p1", "остатки и резервы"),
    ("d4", "p1", "продажи за период"),
    ("p1", "p2", "средний спрос,\nвариация спроса"),
    ("d1", "p2", "текущий остаток"),
    ("p2", "p4", "потребность:\nпозиция, количество"),
    ("d2", "p3", "цены и сроки"),
    ("d3", "p3", "исполнение\nобязательств"),
    ("p3", "d5", "баллы поставщиков"),
    ("d5", "p4", "рейтинг\nпоставщиков"),
    ("p4", "rukovoditel", "заказ\nна согласование"),
    ("rukovoditel", "p4", "решение"),
    ("p4", "postavshchik", "заказ"),
    ("postavshchik", "p5", "поставка,\nдокументы"),
    ("p5", "d1", "приход на склад"),
    ("p5", "d3", "план и факт\nпо поставке"),
]


def хранилище(ид: str, код: str, имя: str) -> str:
    """Открытый справа прямоугольник: код слева, название в теле."""
    return (f'  {ид} [shape=plaintext, label=<\n'
            f'    <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">\n'
            f'      <TR>\n'
            f'        <TD SIDES="TBL" BGCOLOR="#e8e8e8">{код}</TD>\n'
            f'        <TD SIDES="TB">{имя}</TD>\n'
            f'      </TR>\n    </TABLE>>];')


def процесс(ид: str, номер: str, имя: str) -> str:
    строки = imya_br(имя)
    return (f'  {ид} [shape=plaintext, label=<\n'
            f'    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4"'
            f' STYLE="ROUNDED" BGCOLOR="#dbe5f1">\n'
            f'      <TR><TD ALIGN="LEFT"><B>{номер}</B></TD></TR>\n'
            f'      <TR><TD>{строки}</TD></TR>\n    </TABLE>>];')


def imya_br(имя: str) -> str:
    return имя.replace("\n", "<BR/>")


def dot() -> str:
    с = ["digraph DFD {",
         '  graph [overlap=false, splines=true, K=1.6, nodesep=0.45,'
         f' fontname="{ШРИФТ}", fontsize=12];',
         f'  node [fontname="{ШРИФТ}", fontsize=11];',
         f'  edge [fontname="{ШРИФТ}", fontsize=9, color="#444444"];']
    for ид, имя in ВНЕШНИЕ:
        с.append(f'  {ид} [shape=box, style=filled, fillcolor="#fdebd0",'
                 f' label="{имя}"];')
    for ид, номер, имя in ПРОЦЕССЫ:
        с.append(процесс(ид, номер, имя))
    for ид, код, имя in ХРАНИЛИЩА:
        с.append(хранилище(ид, код, имя))
    for a, b, имя in ПОТОКИ:
        с.append(f'  {a} -> {b} [label="{имя}"];')
    с.append("}")
    return "\n".join(с) + "\n"


def main() -> int:
    IMG.mkdir(exist_ok=True)
    файл = HERE / "dfd.dot"
    файл.write_text(dot(), encoding="utf-8")
    for формат in ("svg", "png"):
        арг = ["fdp", f"-T{формат}", str(файл), "-o", str(IMG / f"dfd.{формат}")]
        if формат == "png":
            арг.insert(2, "-Gdpi=150")
        r = subprocess.run(арг, capture_output=True, text=True)
        if r.returncode:
            print("dot не смог собрать DFD:", r.stderr.strip())
            return 1
    d = (IMG / "dfd.png").read_bytes()
    w, h = struct.unpack(">II", d[16:24])
    мм = w / 150 * 25.4
    print(f"dfd: {w}x{h} px, натуральная ширина {мм:.0f} мм, "
          f"кегль на альбомном листе (257 мм) {11 * 257 / мм:.1f} пт, "
          f"высота {257 / (w / h):.0f} мм")
    print(f"внешних сущностей {len(ВНЕШНИЕ)}, процессов {len(ПРОЦЕССЫ)}, "
          f"хранилищ {len(ХРАНИЛИЩА)}, потоков {len(ПОТОКИ)}")
    безымянные = [f"{a}->{b}" for a, b, и in ПОТОКИ if not и.strip()]
    print(f"потоков без подписи: {len(безымянные)}")
    висячие = {и for и, *_ in ВНЕШНИЕ + [(x,) for x, *_ in ПРОЦЕССЫ]
               } - {a for a, *_ in ПОТОКИ} - {b for _, b, _ in ПОТОКИ}
    print(f"элементов без единого потока: {sorted(висячие) or 'нет'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
