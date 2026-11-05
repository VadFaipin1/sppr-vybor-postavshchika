"""Чтение исходных данных из базы и запись оценок поставщиков."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

import psycopg

from .rejting import Offer, Score, Track


@dataclass(frozen=True)
class Item:
    id: int
    name: str
    pack: int
    shelf_days: int | None
    stock: float
    reserve: float


@dataclass
class Data:
    items: dict[int, Item]
    daily: dict[int, tuple[float, float]]    # средний спрос и отклонение за день
    weekly: dict[int, list[float]]           # спрос по полным неделям
    revenue: dict[int, float]
    offers: list[Offer]
    tracks: dict[int, Track]
    suppliers: dict[int, tuple[str, float]]  # название и минимальная сумма заказа
    last_sale: date


def connect(url: str | None = None) -> psycopg.Connection:
    url = url or os.environ.get("DATABASE_URL", "postgresql:///vektor_opt")
    return psycopg.connect(url, options="-c search_path=zakupki")


def load(conn: psycopg.Connection, start: date, end: date, as_of: date) -> Data:
    cur = conn.cursor()
    cur.execute("""
        SELECT t.id, t.naimenovanie, t.kratnost_upakovki, t.srok_godnosti_dney,
               o.kolichestvo, o.rezerv
        FROM tovar t JOIN ostatok o ON o.tovar_id = t.id""")
    items = {r[0]: Item(r[0], r[1], r[2], r[3], float(r[4]), float(r[5]))
             for r in cur.fetchall()}

    # спрос по всем календарным дням периода, включая дни без отгрузок
    cur.execute("""
        WITH dni AS (
            SELECT generate_series(%s::date, %s::date, '1 day')::date AS d
        ), po_dnyam AS (
            SELECT t.id AS tovar_id, dni.d, coalesce(sum(so.kolichestvo), 0) AS q
            FROM tovar t
                CROSS JOIN dni
                LEFT JOIN otgruzka o ON o.data = dni.d
                LEFT JOIN stroka_otgruzki so
                       ON so.otgruzka_id = o.id AND so.tovar_id = t.id
            GROUP BY t.id, dni.d
        )
        SELECT tovar_id, avg(q), stddev_samp(q) FROM po_dnyam GROUP BY tovar_id""",
                (start, end))
    daily = {r[0]: (float(r[1]), float(r[2])) for r in cur.fetchall()}

    # только полные недели из шести рабочих дней
    cur.execute("""
        SELECT so.tovar_id, date_trunc('week', o.data) AS w, sum(so.kolichestvo)
        FROM stroka_otgruzki so JOIN otgruzka o ON o.id = so.otgruzka_id
        WHERE o.data BETWEEN %s AND %s
        GROUP BY so.tovar_id, w
        HAVING count(DISTINCT o.data) = 6
        ORDER BY so.tovar_id, w""", (start, end))
    weekly: dict[int, list[float]] = {}
    for item, _, q in cur.fetchall():
        weekly.setdefault(item, []).append(float(q))

    cur.execute("""
        SELECT so.tovar_id, sum(so.kolichestvo * so.cena)
        FROM stroka_otgruzki so JOIN otgruzka o ON o.id = so.otgruzka_id
        WHERE o.data BETWEEN %s AND %s
        GROUP BY so.tovar_id""", (start, end))
    revenue = {r[0]: float(r[1]) for r in cur.fetchall()}

    # действующая на дату расчёта цена: последняя из вступивших в силу
    cur.execute("""
        SELECT DISTINCT ON (pr.postavshchik_id, pr.tovar_id)
               pr.postavshchik_id, pr.tovar_id, pr.cena, pr.srok_postavki_dney,
               p.otsrochka_dney
        FROM prays pr JOIN postavshchik p ON p.id = pr.postavshchik_id
        WHERE pr.deystvuet_s <= %s
        ORDER BY pr.postavshchik_id, pr.tovar_id, pr.deystvuet_s DESC""", (as_of,))
    offers = [Offer(r[0], r[1], float(r[2]), r[3], r[4]) for r in cur.fetchall()]

    cur.execute("""
        SELECT z.postavshchik_id, count(*),
               count(*) FILTER (WHERE pv.fakt_data <= z.plan_data_postavki)
        FROM postavka pv JOIN zakaz_postavshchiku z ON z.id = pv.zakaz_id
        WHERE pv.fakt_data <= %s
        GROUP BY z.postavshchik_id""", (as_of,))
    tracks = {r[0]: Track(r[1], r[2]) for r in cur.fetchall()}

    cur.execute("SELECT id, naimenovanie, min_summa_zakaza FROM postavshchik")
    suppliers = {r[0]: (r[1], float(r[2])) for r in cur.fetchall()}

    cur.execute("SELECT max(data) FROM otgruzka")
    last_sale = cur.fetchone()[0]
    return Data(items, daily, weekly, revenue, offers, tracks, suppliers, last_sale)


def save_scores(conn: psycopg.Connection, scores: list[Score], as_of: date) -> int:
    """Оценки на дату расчёта перезаписываются, история прошлых дат остаётся."""
    with conn.transaction():
        cur = conn.cursor()
        cur.execute("DELETE FROM ocenka_postavshchika WHERE data_ocenki = %s", (as_of,))
        cur.execute("SELECT coalesce(max(id), 0) FROM ocenka_postavshchika")
        start = cur.fetchone()[0]
        cur.executemany("""
            INSERT INTO ocenka_postavshchika (id, postavshchik_id, tovar_id,
                data_ocenki, ball_cena, ball_srok, ball_nadezhnost,
                ball_otsrochka, itogovy_ball)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            [(start + i, s.supplier, s.item, as_of, round(s.price, 3),
              round(s.lead, 3), round(s.reliability, 3), round(s.deferral, 3),
              round(s.total, 3)) for i, s in enumerate(scores, 1)])
    return len(scores)


def table_count(conn: psycopg.Connection) -> int:
    cur = conn.cursor()
    cur.execute("""SELECT count(*) FROM information_schema.tables
                   WHERE table_schema = 'zakupki'""")
    return cur.fetchone()[0]
