#!/usr/bin/env python3
"""Компонентная схема системы и схема развёртывания для подраздела 4.2.

Сплошная рамка — проверено на стенде, пунктир — предлагается проектом.
Пишет ../img/komponenty.png и ../img/razvertyvanie.png.

    python3 tools/infra_schemy.py
"""
from __future__ import annotations

import struct
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ШРИФТ = "Times New Roman"
ЕСТЬ = 'style="filled", fillcolor="#dbe5f1"'
ПРОЕКТ = 'style="filled,dashed", fillcolor="#ffffff"'
ДАННЫЕ = 'shape=cylinder, style="filled", fillcolor="#e8f0e0"'
ЛЮДИ = 'shape=box, style="rounded,filled", fillcolor="#fdebd0"'


def шапка(имя: str, rankdir: str) -> list[str]:
    return [f"digraph {имя} {{",
            f'  graph [rankdir={rankdir}, nodesep=0.25, ranksep=0.45, '
            f'fontname="{ШРИФТ}", fontsize=12, compound=true];',
            f'  node [shape=box, fontname="{ШРИФТ}", fontsize=11, margin="0.10,0.05"];',
            f'  edge [fontname="{ШРИФТ}", fontsize=9, arrowsize=0.7, color="#444444"];']


def компоненты() -> str:
    с = шапка("K", "TB")
    с += [
        '  subgraph cluster_src { label="Источники данных"; style=rounded; color="#888888";',
        f'    uchet [label="Учётная система\\nорганизации", {ПРОЕКТ}];',
        f'    baza [label="База закупок\\nPostgreSQL", {ДАННЫЕ}];',
        '  }',
        '  subgraph cluster_sppr { label="Компонент sppr"; style=rounded; color="#3b6ea5";',
        f'    zagr [label="Загрузка данных\\n(db)", {ЕСТЬ}];',
        f'    klass [label="Классы ABC и XYZ\\n(klassy)", {ЕСТЬ}];',
        f'    zap [label="Точка перезаказа,\\nэкономичная партия\\n(zapasy)", {ЕСТЬ}];',
        f'    ves [label="Веса критериев\\nметодом анализа иерархий\\n(ahp)", {ЕСТЬ}];',
        f'    rejt [label="Рейтинг поставщиков\\n(rejting)", {ЕСТЬ}];',
        f'    plan [label="Проект заказа,\\nпредел доли поставщика\\n(plan)", {ЕСТЬ}];',
        f'    param [label="Параметры:\\nматрица, допуски, предел", {ЕСТЬ}];',
        '  }',
        '  subgraph cluster_out { label="Результаты"; style=rounded; color="#888888";',
        f'    csv [label="Проект заказа\\nи рейтинг (CSV)", {ЕСТЬ}];',
        f'    status [label="Сводка состояния\\n(status.json)", {ЕСТЬ}];',
        f'    ui [label="Экран проверки\\nпроекта заказа", {ПРОЕКТ}];',
        '  }',
        f'  men [label="Менеджер\\nпо закупкам", {ЛЮДИ}];',
        f'  vlad [label="Владелец процесса", {ЛЮДИ}];',
        '  uchet -> baza [label="выгрузка", style=dashed];',
        '  baza -> zagr;',
        '  zagr -> klass; zagr -> zap; zagr -> rejt;',
        '  klass -> zap [label="уровень\\nобслуживания"];',
        '  param -> ves; ves -> rejt [label="веса"];',
        '  rejt -> plan [label="лучший\\nпоставщик"]; zap -> plan;',
        '  plan -> csv; plan -> status; plan -> baza [label="оценки", constraint=false];',
        '  csv -> ui [style=dashed]; csv -> men; ui -> men [style=dashed];',
        '  vlad -> param;',
        "}",
    ]
    return "\n".join(с) + "\n"


def развёртывание() -> str:
    с = шапка("R", "TB")
    с += [
        f'  ans [label="Ansible:\\ndeploy, run, backup, restore", {ЕСТЬ}];',
        '  subgraph cluster_host { label="Сервер Linux, Docker Compose"; style=rounded; color="#3b6ea5";',
        f'    db [label="db: PostgreSQL 17\\nпроверка здоровья по сети", {ЕСТЬ}];',
        f'    vol [label="Том dbdata", {ДАННЫЕ}];',
        f'    sppr [label="sppr: компонент\\nзапуск по требованию", {ЕСТЬ}];',
        f'    timer [label="Ежедневный запуск\\nпо расписанию", {ПРОЕКТ}];',
        f'    bk [label="Резервные копии\\npg_dump", {ЕСТЬ}];',
        f'    pexp [label="postgres_exporter,\\nnode_exporter", {ПРОЕКТ}];',
        f'    prom [label="Prometheus", {ПРОЕКТ}];',
        f'    graf [label="Grafana:\\nпанели и оповещения", {ПРОЕКТ}];',
        '  }',
        f'  off [label="Внешнее хранилище копий", {ПРОЕКТ}];',
        '  ans -> db [label="настройка", lhead=cluster_host];',
        '  db -> vol [dir=none];',
        '  timer -> sppr [style=dashed]; sppr -> db [label="расчёт"];',
        '  db -> bk [label="копия"]; bk -> off [style=dashed];',
        '  db -> pexp [style=dashed]; pexp -> prom [style=dashed];',
        '  sppr -> prom [label="status.json", style=dashed];',
        '  prom -> graf [style=dashed];',
        "}",
    ]
    return "\n".join(с) + "\n"


def собрать(имя: str, текст: str, ширина: int, высота: int) -> None:
    dot = BASE / "tools" / f"{имя}.dot"
    dot.write_text(текст, encoding="utf-8")
    png = BASE / "img" / f"{имя}.png"
    subprocess.run(["dot", "-Tpng", "-Gdpi=150", str(dot), "-o", str(png)], check=True)
    w, h = struct.unpack(">II", png.read_bytes()[16:24])
    мм_w, мм_h = w / 150 * 25.4, h / 150 * 25.4
    k = min(ширина / мм_w, высота / мм_h, 1)
    print(f"{имя}: {w}x{h} px, на листе {мм_w * k:.0f}x{мм_h * k:.0f} мм, "
          f"кегль {11 * k:.1f} пт")


def main() -> None:
    собрать("komponenty", компоненты(), 160, 225)
    собрать("razvertyvanie", развёртывание(), 160, 225)


if __name__ == "__main__":
    main()
