#!/usr/bin/env python3
"""Логическая ER-диаграмма схемы zakupki.

Состав сущностей, атрибутов и связей читается из самой базы, поэтому
диаграмма не может разойтись с таблицами. Русские названия берутся
из COMMENT, латинские имена остаются подписью под названием сущности.

Раскладка ручная, по столбцам: слева поставщики и закупка, в центре товар,
справа реализация. Связь подходит к строке внешнего ключа потомка, линии
идут только по горизонтали и вертикали. Кратность — «вороньей лапкой»:
черта на стороне родителя — один, лапка на стороне потомка — много,
черта на обеих сторонах — 1:1. Рисуется в натуральную величину листа,
поэтому кегль на листе равен заданному.

    python3 er.py      # пишет ../img/er, er_zakupka, er_realizaciya (.png и .svg)
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMG = HERE.parent / "img"
sys.path.insert(0, str(HERE.parent / "tools"))
import chertezh as ч  # noqa: E402

БАЗА = "vektor_opt"

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


@dataclass
class Стиль:
    кегль: float          # атрибуты
    имя: float            # название сущности
    лат: float            # латинское имя таблицы
    метка: float          # ПК, ВК
    строка: float         # высота строки атрибута, мм
    поле: float = 1.4     # отступ текста от рамки, мм

    @property
    def шапка(self) -> float:
        return (self.имя * 1.22 + self.лат * 1.2) * ч.ПТ + 1.4


ОБЛАСТЬ = {т: i for i, (_, тс) in enumerate(ОБЛАСТИ) for т in тс}


def метка(пк: bool, вк: bool) -> str:
    return ", ".join(x for x, да in (("ПК", пк), ("ВК", вк)) if да)


def ширина(таб, подпись, поля, ст: Стиль) -> float:
    метки = max(ч.длина(метка(пк, вк) or "ПК", ст.метка) for _, _, пк, вк in поля)
    тело = max(ч.длина(т, ст.кегль, пк) for _, т, пк, _ in поля)
    return max(ч.длина(подпись, ст.имя, True), ч.длина(таб, ст.лат),
               метки + 1.0 + тело) + 2 * ст.поле


def высота(поля, ст: Стиль) -> float:
    return ст.шапка + len(поля) * ст.строка + 0.6


def нарисовать(х: ч.Холст, б: ч.Блок, таб, подпись, поля, ст: Стиль) -> None:
    цвет = ЦВЕТА[ОБЛАСТЬ[таб]]
    х.прямоугольник(б.x, б.y, б.w, б.h, "white", толщина=0.8)
    х.прямоугольник(б.x, б.y, б.w, ст.шапка, цвет, контур=False, z=2.1)
    х.линия([(б.x, б.y + ст.шапка), (б.право, б.y + ст.шапка)], 0.6)
    центр = б.x + б.w / 2
    х.текст(центр, б.y + 0.7 + ст.имя * 0.61 * ч.ПТ, подпись, ст.имя, True, ha="center")
    х.текст(центр, б.y + ст.шапка - 0.7 - ст.лат * 0.6 * ч.ПТ, таб, ст.лат,
            ha="center", цвет="#444444")
    метки = max(ч.длина(метка(пк, вк) or "ПК", ст.метка) for _, _, пк, вк in поля)
    y = б.y + ст.шапка + 0.3
    for k, (имя, текст, пк, вк) in enumerate(поля):
        ц = y + ст.строка / 2
        б.строки[имя] = ц
        if метка(пк, вк):
            х.текст(б.x + ст.поле, ц, метка(пк, вк), ст.метка, цвет="#444444")
        х.текст(б.x + ст.поле + метки + 1.0, ц, текст, ст.кегль, пк)
        y += ст.строка
        # ключ отделён от остальных атрибутов, как в нотации IDEF1X
        if пк and (k + 1 == len(поля) or not поля[k + 1][2]):
            х.линия([(б.x, y + 0.15), (б.право, y + 0.15)], 0.35, "#777777")


# Столбцы раскладки: поставщики и закупка, их строки, товар, строки
# реализации, реализация. Контуры для текста — левая и правая части.
СТОЛБЦЫ = [
    ["postavshchik", "zakaz_postavshchiku", "postavka"],
    ["prays", "ocenka_postavshchika", "stroka_zakaza", "stroka_postavki"],
    ["tovarnaya_gruppa", "tovar", "ostatok"],
    ["stroka_zayavki", "stroka_otgruzki"],
    ["klient", "zayavka", "otgruzka"],
]
# Родитель в соседнем столбце ставится так, чтобы его ключ стоял
# вровень с внешним ключом потомка: связь идёт прямой линией.
ВРОВЕНЬ = [
    ("postavshchik", "ocenka_postavshchika", "postavshchik_id"),
    ("zakaz_postavshchiku", "stroka_zakaza", "zakaz_id"),
    ("postavka", "stroka_postavki", "postavka_id"),
    ("zayavka", "stroka_zayavki", "zayavka_id"),
    ("otgruzka", "stroka_otgruzki", "otgruzka_id"),
]


# Связи, которые выходят не сбоку, а сверху или снизу родителя: сторона и доля
ВЫХОД = {("postavshchik", "prays"): ("T", 0.8)}


@dataclass
class Вид:
    имя: str
    столбцы: list           # номера столбцов из СТОЛБЦЫ
    стиль: Стиль
    промежутки: list        # мм между соседними столбцами
    зазор: float            # мм между блоками в столбце
    ширина: float | None = None   # ширина листа: столбцы растягиваются на неё


ВИДЫ = [
    Вид("er", [0, 1, 2, 3, 4], Стиль(8, 8.5, 6.5, 6.5, 3.6), [10, 15, 12, 9], 7, 250),
    Вид("er_zakupka", [0, 1, 2], Стиль(9.5, 10, 7.5, 7.5, 4.2), [22, 26], 7.5),
    Вид("er_realizaciya", [2, 3, 4], Стиль(9.5, 10, 7.5, 7.5, 4.2), [15, 9], 9, 160),
]


def разложить(вид: Вид, таблицы, столбцы):
    ст = вид.стиль
    набор = [[т for т in СТОЛБЦЫ[i] if т in таблицы] for i in вид.столбцы]
    if вид.имя == "er_realizaciya":
        набор[0] = ["tovar", "ostatok"]
    ширины = [max(ширина(т, таблицы[т], столбцы[т], ст) for т in колонка)
              for колонка in набор]
    промежутки = list(вид.промежутки)
    if вид.ширина:
        лишнее = вид.ширина - 4 - sum(ширины) - sum(промежутки)
        assert лишнее >= 0, f"{вид.имя}: не хватает {-лишнее:.1f} мм ширины"
        промежутки = [п + лишнее / len(промежутки) for п in промежутки]
    блоки: dict[str, ч.Блок] = {}
    x = 2.0
    for колонка, w in zip(набор, ширины):
        for т in колонка:
            блоки[т] = ч.Блок(x, 0, w, высота(столбцы[т], ст))
        x += w + (промежутки.pop(0) if промежутки else 0)

    def ключ(т):           # центр строки первичного ключа от верха блока
        return ст.шапка + 0.3 + ст.строка / 2

    def строка(т, имя):
        k = [п[0] for п in столбцы[т]].index(имя)
        return ст.шапка + 0.3 + ст.строка * (k + 0.5)

    def стопка(колонка, верх=0.0):
        y = верх
        for т in колонка:
            блоки[т].y = y
            y += блоки[т].h + вид.зазор
        return y - вид.зазор

    # самый высокий столбец — опорный, остальные выравниваются по нему
    if 1 in вид.столбцы:
        низ = стопка(набор[вид.столбцы.index(1)])
    if 3 in вид.столбцы:
        колонка = набор[вид.столбцы.index(3)]
        стопка(колонка)
        # между заявкой и отгрузкой нужен зазор под связь 1:1 с подписью
        нужно = блоки["stroka_zayavki"].y + строка("stroka_zayavki", "zayavka_id") \
            - ключ("zayavka") + высота(столбцы["zayavka"], ст) + 9 \
            + ключ("otgruzka") - строка("stroka_otgruzki", "otgruzka_id")
        блоки["stroka_otgruzki"].y = max(блоки["stroka_otgruzki"].y, нужно)
    for родитель, потомок, вк in ВРОВЕНЬ:
        if родитель in блоки and потомок in блоки:
            блоки[родитель].y = блоки[потомок].y + строка(потомок, вк) - ключ(родитель)
    if "klient" in блоки:
        блоки["klient"].y = блоки["zayavka"].y - 9 - блоки["klient"].h
    # товар — посередине опорного столбца, группа над ним, остаток под ним
    т = блоки["tovar"]
    if 1 in вид.столбцы:
        т.y = низ / 2 - т.h / 2 + 4
    else:
        с = [блоки["stroka_zayavki"], блоки["stroka_otgruzki"]]
        т.y = (с[0].y + с[1].низ) / 2 - т.h / 2
    if 1 in вид.столбцы and 3 in вид.столбцы:
        правые = ["stroka_zayavki", "stroka_otgruzki", "klient", "zayavka", "otgruzka"]
        с = [блоки["stroka_zayavki"], блоки["stroka_otgruzki"]]
        сдвиг = т.y + т.h / 2 - (с[0].y + с[1].низ) / 2
        сдвиг = max(сдвиг, -блоки["klient"].y)
        сдвиг = min(сдвиг, низ - блоки["otgruzka"].низ)
        for имя in правые:
            блоки[имя].y += сдвиг
    if "tovarnaya_gruppa" in блоки:
        блоки["tovarnaya_gruppa"].y = т.y - 10 - блоки["tovarnaya_gruppa"].h
    блоки["ostatok"].y = т.низ + 10
    # всё сдвигается вниз, чтобы верх был на 2 мм от края
    сдвиг = 2 - min(б.y for б in блоки.values())
    for б in блоки.values():
        б.y += сдвиг
    return блоки


def столбец(т, вид) -> int:
    return next(i for i in вид.столбцы if т in СТОЛБЦЫ[i]) if т != "ostatok" else 2


def связи_вида(вид, блоки, связи, ст: Стиль):
    """Маршрут каждой связи: стороны, точки выхода у родителя и излом в промежутке."""
    маршруты = []
    for родитель, потомок, вк, один in связи:
        if родитель not in блоки or потомок not in блоки:
            continue
        р, п = блоки[родитель], блоки[потомок]
        if столбец(родитель, вид) == столбец(потомок, вид) or abs(р.x - п.x) < 1:
            # в одном столбце — вертикально, середина нижней и верхней сторон
            вверх = р.y > п.y
            маршруты.append(dict(р=родитель, п=потомок, один=один,
                                 сa="T" if вверх else "B", сb="B" if вверх else "T",
                                 a=р.точка("T" if вверх else "B"),
                                 b=п.точка("B" if вверх else "T")))
            continue
        вправо = р.x < п.x
        сa, сb = ("R", "L") if вправо else ("L", "R")
        м = dict(р=родитель, п=потомок, один=один, сa=сa, сb=сb, b=п.точка(сb, вк))
        if (родитель, потомок) in ВЫХОД:
            м["сa"], где = ВЫХОД[(родитель, потомок)]
            м["a"] = р.точка(м["сa"], где)
        маршруты.append(м)
    # точки выхода у родителя: вровень с потомком, если он напротив тела блока,
    # иначе по порядку потомков, не ближе 3 мм друг к другу
    группы: dict = {}
    for м in маршруты:
        if "a" not in м:
            группы.setdefault((м["р"], м["сa"]), []).append(м)
    for (родитель, сторона), мм in группы.items():
        р = блоки[родитель]
        мм.sort(key=lambda м: м["b"][1])
        строки = sorted(р.строки.values())
        k = len(мм)
        if k <= len(строки):
            лучшее = min(range(len(строки) - k + 1), key=lambda s: sum(
                abs(строки[s + i] - м["b"][1]) for i, м in enumerate(мм)))
            ys = строки[лучшее:лучшее + k]
        else:
            шаг = (р.низ - р.y - ст.шапка) / (k + 1)
            ys = [р.y + ст.шапка + шаг * (i + 1) for i in range(k)]
        x = р.x if сторона == "L" else р.право
        for м, y in zip(мм, ys):
            м["a"] = (x, y)
        # изломы: к дальнему потомку — ближе к родителю, чтобы линии не пересекались
        вверх = sorted([м for м in мм if м["b"][1] < м["a"][1] - 0.01], key=lambda м: м["b"][1])
        вниз = sorted([м for м in мм if м["b"][1] > м["a"][1] + 0.01], key=lambda м: -м["b"][1])
        знак = -1 if сторона == "L" else 1
        for ряд in (вверх, вниз):
            for k, м in enumerate(ряд):
                м["канал"] = x + знак * (3.5 + 2.8 * k)
    return маршруты


def подпись_связи(х: ч.Холст, точки, сторона_b, текст, кегль):
    """Подпись кратности — у потомка, над линией или справа от неё, вне лапки."""
    (x0, y0), (x1, y1) = точки[-2], точки[-1]
    dx, dy = ч.НАПРАВЛЕНИЕ_В_БЛОК[сторона_b]
    длина_отрезка = abs(x1 - x0) + abs(y1 - y0)
    if длина_отрезка < 8 and len(точки) >= 3 and сторона_b in "LR":
        (xa, ya), (xb, yb) = точки[-3], точки[-2]
        if abs(xa - xb) < 1e-6 and abs(ya - yb) >= 6:
            х.текст(xb - dx * 0.9, (ya + yb) / 2, текст, кегль,
                    ha="right" if dx > 0 else "left", va="center", фон="white")
            return
    назад = min(8.0, max(5.2, длина_отрезка - 2.6))
    if сторона_b in "LR":
        х.текст(x1 - dx * назад, y1 - 0.5, текст, кегль, ha="center", va="bottom",
                фон="white")
    else:
        х.текст(x1 + 0.9, y1 - dy * назад, текст, кегль, ha="left", va="center",
                фон="white")


def легенда(х: ч.Холст, y: float, кегль: float) -> None:
    x = 2.0
    for (имя, _), цвет in zip(ОБЛАСТИ, ЦВЕТА):
        х.прямоугольник(x, y - 1.6, 4.5, 3.2, цвет, толщина=0.5)
        х.текст(x + 6, y, имя, кегль)
        x += 6 + ч.длина(имя, кегль) + 7


def нарисовать_вид(вид: Вид, таблицы, столбцы, связи) -> tuple[float, float]:
    ст = вид.стиль
    блоки = разложить(вид, таблицы, столбцы)
    for т, б in блоки.items():
        for k, (имя, *_) in enumerate(столбцы[т]):
            б.строки[имя] = б.y + ст.шапка + 0.3 + ст.строка * (k + 0.5)
    ширина_листа = вид.ширина or max(б.право for б in блоки.values()) + 2
    низ = max(б.низ for б in блоки.values())
    области = sorted({ОБЛАСТЬ[т] for т in блоки})
    высота_листа = низ + 2 + 6
    х = ч.Холст(ширина_листа, высота_листа)
    for т, б in блоки.items():
        нарисовать(х, б, т, таблицы[т], столбцы[т], ст)
    кегль_подписи = ст.метка
    for м in связи_вида(вид, блоки, связи, ст):
        точки = ч.путь(м["a"], м["сa"], м["b"], м["сb"], м.get("канал"))
        х.линия(точки, 0.75)
        размах = min(1.6, 0.36 * ст.строка)
        х.черта(м["a"], ч.НАПРАВЛЕНИЕ_В_БЛОК[м["сa"]], размах=размах)
        if м["один"]:
            х.черта(м["b"], ч.НАПРАВЛЕНИЕ_В_БЛОК[м["сb"]], размах=размах)
        else:
            х.лапка(м["b"], ч.НАПРАВЛЕНИЕ_В_БЛОК[м["сb"]])
        подпись_связи(х, точки, м["сb"], "1:1" if м["один"] else "1:N", кегль_подписи)
    # легенда — только областей, которые есть на схеме
    y = низ + 2 + 3
    x = 2.0
    for i in области:
        имя = ОБЛАСТИ[i][0]
        х.прямоугольник(x, y - 1.6, 4.5, 3.2, ЦВЕТА[i], толщина=0.5)
        х.текст(x + 6, y, имя, ст.метка + 0.5)
        x += 6 + ч.длина(имя, ст.метка + 0.5) + 7
    х.сохранить(IMG / вид.имя)
    return ширина_листа, высота_листа


def main() -> int:
    IMG.mkdir(exist_ok=True)
    таблицы, столбцы, связи = схема()
    из_столбцов = {т for к in СТОЛБЦЫ for т in к}
    assert set(таблицы) == из_столбцов, set(таблицы) ^ из_столбцов
    for вид in ВИДЫ:
        w, h = нарисовать_вид(вид, таблицы, столбцы, связи)
        print(f"{вид.имя}: {w:.0f} x {h:.0f} мм, кегль атрибутов {вид.стиль.кегль} пт")
    пк = sum(1 for т in столбцы for и, _, p, _ in столбцы[т] if p)
    print(f"сущностей {len(таблицы)}, атрибутов {sum(len(v) for v in столбцы.values())}, "
          f"первичных ключей {пк}, связей {len(связи)}"
          f" (из них 1:1 — {sum(1 for *_, о in связи if о)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
