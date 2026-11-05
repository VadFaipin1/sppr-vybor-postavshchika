#!/usr/bin/env python3
"""Логическая ER-диаграмма схемы zakupki.

Состав сущностей, атрибутов и связей читается из самой базы, поэтому
диаграмма не может разойтись с таблицами. Русские названия берутся
из COMMENT, латинские имена остаются подписью под названием сущности.

Кратность показана «вороньей лапкой»: отметка на стороне родителя — один,
лапка на стороне потомка — много.

    python3 er.py           # пишет ../img/er.svg, ../img/er.png и er.dot
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMG = HERE.parent / "img"
БАЗА = "vektor_opt"
ШРИФТ = "Times New Roman"

# Предметные области: заголовок кластера и таблицы в нём
ОБЛАСТИ = [
    ("Номенклатура и склад", ["tovarnaya_gruppa", "tovar", "ostatok"]),
    ("Поставщики", ["postavshchik", "prays", "ocenka_postavshchika"]),
    ("Закупка", ["zakaz_postavshchiku", "stroka_zakaza", "postavka",
                 "stroka_postavki"]),
    ("Реализация", ["klient", "zayavka", "stroka_zayavki", "otgruzka",
                    "stroka_otgruzki"]),
]
ЦВЕТА = ["#dbe5f1", "#e5dfec", "#dff0d8", "#fdebd0"]

# На логической диаграмме показываются все ключи и только основные атрибуты:
# полный состав занимает лист целиком и текст садится до 4 пт.
# Полный перечень — в DDL, он идёт в приложение.
ГЛАВНЫЕ = {
    "tovarnaya_gruppa": ["naimenovanie"],
    "tovar": ["naimenovanie", "kratnost_upakovki"],
    "ostatok": ["kolichestvo", "rezerv"],
    "postavshchik": ["naimenovanie", "otsrochka_dney"],
    "prays": ["cena", "srok_postavki_dney"],
    "ocenka_postavshchika": ["data_ocenki", "itogovy_ball"],
    "zakaz_postavshchiku": ["data_zakaza", "plan_data_postavki"],
    "stroka_zakaza": ["kolichestvo", "cena"],
    "postavka": ["fakt_data"],
    "stroka_postavki": ["prinyato", "brak"],
    "klient": ["naimenovanie"],
    "zayavka": ["data", "status"],
    "stroka_zayavki": ["kolichestvo"],
    "otgruzka": ["data", "nomer_upd"],
    "stroka_otgruzki": ["kolichestvo", "cena"],
}


def psql(запрос: str) -> list[list[str]]:
    r = subprocess.run(["psql", "-d", БАЗА, "-At", "-F", "\x1f", "-c", запрос],
                       capture_output=True, text=True, check=True)
    return [с.split("\x1f") for с in r.stdout.strip().split("\n") if с]


def схема():
    таблицы = {и: п for и, п in psql("""
        SELECT c.relname, coalesce(obj_description(c.oid), c.relname)
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'zakupki' AND c.relkind = 'r' """)}

    столбцы: dict[str, list[tuple[str, str, bool, bool]]] = {}
    for таб, имя, подпись, пк, вк in psql("""
        SELECT c.relname, a.attname,
               coalesce(col_description(c.oid, a.attnum), a.attname),
               EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conrelid = c.oid
                       AND k.contype = 'p' AND a.attnum = ANY (k.conkey)),
               EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conrelid = c.oid
                       AND k.contype = 'f' AND a.attnum = ANY (k.conkey))
        FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0
                                   AND NOT a.attisdropped
        WHERE n.nspname = 'zakupki' AND c.relkind = 'r'
        ORDER BY c.relname, a.attnum """):
        if имя in ГЛАВНЫЕ.get(таб, []) or пк == "t" or вк == "t":
            столбцы.setdefault(таб, []).append((имя, подпись, пк == "t", вк == "t"))

    # связь считается 1:1, если внешний ключ потомка уникален
    связи = []
    for потомок, родитель, столбец, один in psql("""
        SELECT c.relname, f.relname, a.attname,
               EXISTS (SELECT 1 FROM pg_constraint u
                       WHERE u.conrelid = c.oid AND u.contype IN ('p','u')
                         AND u.conkey = k.conkey)
        FROM pg_constraint k
            JOIN pg_class c ON c.oid = k.conrelid
            JOIN pg_class f ON f.oid = k.confrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.conkey[1]
        WHERE n.nspname = 'zakupki' AND k.contype = 'f'
        ORDER BY f.relname, c.relname """):
        связи.append((родитель, потомок, столбец, один == "t"))
    return таблицы, столбцы, связи


def экран(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def узел(таб: str, подпись: str, поля, цвет: str) -> str:
    строки = [f'<TR><TD BGCOLOR="{цвет}" ALIGN="CENTER">'
              f'<B>{экран(подпись)}</B><BR/>'
              f'<FONT POINT-SIZE="9">{экран(таб)}</FONT></TD></TR>']
    for имя, текст, пк, вк in поля:
        метка = "ПК" if пк else ("ВК" if вк else "&#160;&#160;")
        жирно = (f"<B>{экран(текст)}</B>" if пк else экран(текст))
        строки.append(f'<TR><TD ALIGN="LEFT" PORT="{имя}">'
                      f'<FONT POINT-SIZE="9">{метка}</FONT> {жирно}</TD></TR>')
    тело = "\n      ".join(строки)
    return (f'  {таб} [label=<\n'
            f'    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3">\n'
            f'      {тело}\n    </TABLE>>];')


# Целиком модель на лист не ложится: 3052 px в ширину дают кегль 5,5 пт.
# В текст идут два контура, полная диаграмма — в приложение.
# Направление раскладки подбирается под лист: контур закупки идёт на альбомную
# страницу и раскладывается слева направо, контур реализации — на книжную.
СХЕМЫ = [
    ("er", None, "TB"),
    ("er_zakupka", ["tovarnaya_gruppa", "tovar", "ostatok", "postavshchik",
                    "prays", "ocenka_postavshchika", "zakaz_postavshchiku",
                    "stroka_zakaza", "postavka", "stroka_postavki"], "LR"),
    ("er_realizaciya", ["tovar", "ostatok", "klient", "zayavka",
                        "stroka_zayavki", "otgruzka", "stroka_otgruzki"], "TB"),
]


def dot(только=None, rankdir="TB") -> str:
    таблицы, столбцы, связи = схема()
    из_областей = {т for _, тс in ОБЛАСТИ for т in тс}
    лишние = set(таблицы) - из_областей
    assert not лишние, f"таблицы вне предметных областей: {лишние}"
    if только:
        таблицы = {т: п for т, п in таблицы.items() if т in только}
        связи = [с for с in связи if с[0] in только and с[1] in только]

    строки = [
        "digraph ER {",
        f'  graph [rankdir={rankdir}, splines=ortho, nodesep=0.30, ranksep=0.7,'
        f' fontname="{ШРИФТ}", fontsize=12, compound=true];',
        f'  node [shape=plaintext, fontname="{ШРИФТ}", fontsize=11];',
        f'  edge [fontname="{ШРИФТ}", fontsize=9, dir=both, color="#444444"];',
    ]
    for i, (имя, табы) in enumerate(ОБЛАСТИ):
        табы = [т for т in табы if т in таблицы]
        if not табы:
            continue
        строки.append(f"  subgraph cluster_{i} {{")
        строки.append(f'    label="{имя}"; style="rounded"; color="#888888";'
                      f' fontsize=12; margin=12;')
        for т in табы:
            строки.append("  " + узел(т, таблицы[т], столбцы[т], ЦВЕТА[i]).strip())
        строки.append("  }")
    for родитель, потомок, столбец, один in связи:
        голова = "tee" if один else "crow"
        метка = "1:1" if один else "1:N"
        строки.append(f'  {родитель} -> {потомок}:{столбец}'
                      f' [arrowtail=tee, arrowhead={голова}, label="{метка}"];')
    строки.append("}")
    return "\n".join(строки) + "\n"


def размер(png: Path) -> tuple[int, int]:
    import struct
    d = png.read_bytes()
    return struct.unpack(">II", d[16:24])


def main() -> int:
    IMG.mkdir(exist_ok=True)
    for имя, только, rankdir in СХЕМЫ:
        файл = HERE / f"{имя}.dot"
        файл.write_text(dot(только, rankdir), encoding="utf-8")
        for формат in ("svg", "png"):
            цель = IMG / f"{имя}.{формат}"
            аргументы = ["dot", f"-T{формат}", str(файл), "-o", str(цель)]
            if формат == "png":
                аргументы.insert(2, "-Gdpi=150")
            r = subprocess.run(аргументы, capture_output=True, text=True)
            if r.returncode:
                print(f"dot не смог собрать {имя}:", r.stderr.strip())
                return 1
        w, h = размер(IMG / f"{имя}.png")
        мм = w / 150 * 25.4
        print(f"{имя}: {w}x{h} px, натуральная ширина {мм:.0f} мм, "
              f"кегль на альбомном листе (257 мм) {11 * 257 / мм:.1f} пт, "
              f"высота {257 / (w / h):.0f} мм")
    таблицы, столбцы, связи = схема()
    пк = sum(1 for т in столбцы for и, _, p, _ in столбцы[т] if p)
    print(f"сущностей {len(таблицы)}, атрибутов {sum(len(v) for v in столбцы.values())}, "
          f"первичных ключей {пк}, связей {len(связи)}"
          f" (из них 1:1 — {sum(1 for *_, о in связи if о)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
