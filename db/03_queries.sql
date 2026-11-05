-- Период истории: 01.11.2025 - 31.10.2026

SET search_path TO zakupki;
\pset border 2
\pset numericlocale off

-- 1. Выборка с соединением: прайс по одной позиции у всех её поставщиков
SELECT t.naimenovanie AS товар,
       p.naimenovanie AS поставщик,
       pr.cena        AS цена,
       pr.srok_postavki_dney AS срок_дней,
       p.otsrochka_dney      AS отсрочка_дней
FROM prays pr
    JOIN tovar t        ON t.id = pr.tovar_id
    JOIN postavshchik p ON p.id = pr.postavshchik_id
WHERE t.id = 1
ORDER BY pr.cena;

-- 2. Группировка: продажи по товарным группам за год
SELECT g.naimenovanie                         AS группа,
       count(DISTINCT o.id)                   AS отгрузок,
       round(sum(so.kolichestvo))             AS единиц,
       round(sum(so.kolichestvo * so.cena))   AS выручка
FROM stroka_otgruzki so
    JOIN otgruzka o        ON o.id = so.otgruzka_id
    JOIN tovar t           ON t.id = so.tovar_id
    JOIN tovarnaya_gruppa g ON g.id = t.gruppa_id
GROUP BY g.naimenovanie
ORDER BY выручка DESC;

-- 3. ABC-анализ номенклатуры по выручке за год
WITH prodazhi AS (
    SELECT t.id, t.naimenovanie,
           sum(so.kolichestvo * so.cena) AS vyruchka
    FROM stroka_otgruzki so JOIN tovar t ON t.id = so.tovar_id
    GROUP BY t.id, t.naimenovanie
), dolya AS (
    SELECT naimenovanie, vyruchka,
           sum(vyruchka) OVER (ORDER BY vyruchka DESC)
               / sum(vyruchka) OVER () AS nakoplenno
    FROM prodazhi
)
SELECT CASE WHEN nakoplenno <= 0.80 THEN 'A'
            WHEN nakoplenno <= 0.95 THEN 'B'
            ELSE 'C' END          AS класс,
       count(*)                   AS позиций,
       round(sum(vyruchka))       AS выручка,
       round(100 * sum(vyruchka) / sum(sum(vyruchka)) OVER (), 1) AS доля_процентов
FROM dolya
GROUP BY класс
ORDER BY класс;

-- 4. XYZ-анализ недельного спроса, только полные недели по шесть рабочих дней
WITH nedeli AS (
    SELECT so.tovar_id, date_trunc('week', o.data) AS nedelya,
           sum(so.kolichestvo) AS spros
    FROM stroka_otgruzki so JOIN otgruzka o ON o.id = so.otgruzka_id
    GROUP BY so.tovar_id, date_trunc('week', o.data)
    HAVING count(DISTINCT o.data) = 6
), variaciya AS (
    SELECT tovar_id, avg(spros) AS sredn,
           stddev_samp(spros) / nullif(avg(spros), 0) AS cv
    FROM nedeli GROUP BY tovar_id
)
SELECT CASE WHEN cv < 0.10 THEN 'X'
            WHEN cv < 0.25 THEN 'Y'
            ELSE 'Z' END     AS класс,
       count(*)              AS позиций,
       round(min(cv), 3)     AS мин_вариация,
       round(max(cv), 3)     AS макс_вариация
FROM variaciya
GROUP BY класс
ORDER BY класс;

-- 4б. Матрица ABC-XYZ: сколько позиций в каждой клетке
WITH prodazhi AS (
    SELECT t.id, sum(so.kolichestvo * so.cena) AS vyruchka
    FROM stroka_otgruzki so JOIN tovar t ON t.id = so.tovar_id
    GROUP BY t.id
), abc AS (
    SELECT id, CASE WHEN sum(vyruchka) OVER (ORDER BY vyruchka DESC)
                         / sum(vyruchka) OVER () <= 0.80 THEN 'A'
                    WHEN sum(vyruchka) OVER (ORDER BY vyruchka DESC)
                         / sum(vyruchka) OVER () <= 0.95 THEN 'B'
                    ELSE 'C' END AS klass
    FROM prodazhi
), nedeli AS (
    SELECT so.tovar_id, date_trunc('week', o.data) AS nedelya,
           sum(so.kolichestvo) AS spros
    FROM stroka_otgruzki so JOIN otgruzka o ON o.id = so.otgruzka_id
    GROUP BY so.tovar_id, date_trunc('week', o.data)
    HAVING count(DISTINCT o.data) = 6
), xyz AS (
    SELECT tovar_id,
           CASE WHEN stddev_samp(spros) / avg(spros) < 0.10 THEN 'X'
                WHEN stddev_samp(spros) / avg(spros) < 0.25 THEN 'Y'
                ELSE 'Z' END AS klass
    FROM nedeli GROUP BY tovar_id
)
SELECT abc.klass AS abc,
       count(*) FILTER (WHERE xyz.klass = 'X') AS x,
       count(*) FILTER (WHERE xyz.klass = 'Y') AS y,
       count(*) FILTER (WHERE xyz.klass = 'Z') AS z,
       count(*)                                AS всего
FROM abc JOIN xyz ON xyz.tovar_id = abc.id
GROUP BY abc.klass
ORDER BY abc.klass;

-- 5. Исполнение обязательств поставщиками: сроки и количество
WITH sroki AS (
    SELECT z.postavshchik_id,
           count(*) AS postavok,
           count(*) FILTER (WHERE pv.fakt_data <= z.plan_data_postavki) AS v_srok,
           round(avg(pv.fakt_data - z.plan_data_postavki), 2) AS sredn_opozdanie
    FROM postavka pv JOIN zakaz_postavshchiku z ON z.id = pv.zakaz_id
    GROUP BY z.postavshchik_id
), kolichestvo AS (
    SELECT z.postavshchik_id,
           sum(sp.prinyato) / sum(sz.kolichestvo) AS dolya_postavleno
    FROM stroka_postavki sp
        JOIN postavka pv ON pv.id = sp.postavka_id
        JOIN zakaz_postavshchiku z ON z.id = pv.zakaz_id
        JOIN stroka_zakaza sz ON sz.zakaz_id = z.id AND sz.tovar_id = sp.tovar_id
    GROUP BY z.postavshchik_id
)
SELECT p.naimenovanie                                   AS поставщик,
       s.postavok                                       AS поставок,
       round(100.0 * s.v_srok / s.postavok, 1)          AS в_срок_процентов,
       s.sredn_opozdanie                                AS ср_опоздание_дней,
       round(100 * k.dolya_postavleno, 1)               AS исполнено_процентов
FROM sroki s
    JOIN kolichestvo k ON k.postavshchik_id = s.postavshchik_id
    JOIN postavshchik p ON p.id = s.postavshchik_id
ORDER BY в_срок_процентов DESC;

-- 6. Позиции ниже точки перезаказа, уровень обслуживания 95 % (z = 1,65)
WITH dni AS (
    SELECT generate_series(DATE '2025-11-01', DATE '2026-10-31', '1 day')::date AS d
), po_dnyam AS (
    SELECT t.id AS tovar_id, dni.d,
           coalesce(sum(so.kolichestvo), 0) AS za_den
    FROM tovar t
        CROSS JOIN dni
        LEFT JOIN otgruzka o        ON o.data = dni.d
        LEFT JOIN stroka_otgruzki so ON so.otgruzka_id = o.id AND so.tovar_id = t.id
    GROUP BY t.id, dni.d
), dnevnoy AS (
    SELECT tovar_id, avg(za_den) AS sr_den, stddev_samp(za_den) AS sigma
    FROM po_dnyam GROUP BY tovar_id
), srok AS (
    SELECT tovar_id, min(srok_postavki_dney) AS L FROM prays GROUP BY tovar_id
)
SELECT t.naimenovanie                                   AS товар,
       round(d.sr_den, 1)                               AS спрос_в_день,
       s.L                                              AS срок_дней,
       round(d.sr_den * s.L + 1.65 * d.sigma * sqrt(s.L)) AS точка_перезаказа,
       round(o.kolichestvo - o.rezerv)                  AS доступно,
       round((o.kolichestvo - o.rezerv) / nullif(d.sr_den, 0), 1) AS хватит_на_дней
FROM dnevnoy d
    JOIN srok s   ON s.tovar_id = d.tovar_id
    JOIN ostatok o ON o.tovar_id = d.tovar_id
    JOIN tovar t  ON t.id = d.tovar_id
WHERE o.kolichestvo - o.rezerv < d.sr_den * s.L + 1.65 * d.sigma * sqrt(s.L)
ORDER BY хватит_на_дней
LIMIT 12;

-- 6б. Сколько позиций ниже точки перезаказа и не доживут до новой поставки
WITH dni AS (
    SELECT generate_series(DATE '2025-11-01', DATE '2026-10-31', '1 day')::date AS d
), po_dnyam AS (
    SELECT t.id AS tovar_id, dni.d, coalesce(sum(so.kolichestvo), 0) AS za_den
    FROM tovar t
        CROSS JOIN dni
        LEFT JOIN otgruzka o        ON o.data = dni.d
        LEFT JOIN stroka_otgruzki so ON so.otgruzka_id = o.id AND so.tovar_id = t.id
    GROUP BY t.id, dni.d
), dnevnoy AS (
    SELECT tovar_id, avg(za_den) AS sr_den, stddev_samp(za_den) AS sigma
    FROM po_dnyam GROUP BY tovar_id
), srok AS (
    SELECT tovar_id, min(srok_postavki_dney) AS L FROM prays GROUP BY tovar_id
)
SELECT count(*) FILTER (WHERE o.kolichestvo - o.rezerv
                              < d.sr_den * s.L + 1.65 * d.sigma * sqrt(s.L))
           AS ниже_точки_перезаказа,
       count(*) FILTER (WHERE (o.kolichestvo - o.rezerv) / d.sr_den < s.L)
           AS кончатся_до_поставки,
       count(*) AS всего_позиций
FROM dnevnoy d
    JOIN srok s    USING (tovar_id)
    JOIN ostatok o USING (tovar_id);

-- 7. Рейтинг поставщиков: веса 0,35, 0,25, 0,30, 0,10, баллы от 0 до 1
TRUNCATE ocenka_postavshchika;
INSERT INTO ocenka_postavshchika (id, postavshchik_id, tovar_id, data_ocenki,
                                  ball_cena, ball_srok, ball_nadezhnost,
                                  ball_otsrochka, itogovy_ball)
WITH nadezhnost AS (
    SELECT z.postavshchik_id,
           count(*) FILTER (WHERE pv.fakt_data <= z.plan_data_postavki)::numeric
               / count(*) AS dolya_v_srok
    FROM postavka pv JOIN zakaz_postavshchiku z ON z.id = pv.zakaz_id
    GROUP BY z.postavshchik_id
), granicy AS (
    SELECT tovar_id, min(cena) AS c_min, max(cena) AS c_max,
           min(srok_postavki_dney) AS s_min, max(srok_postavki_dney) AS s_max
    FROM prays GROUP BY tovar_id
), bally AS (
    SELECT pr.postavshchik_id, pr.tovar_id,
           CASE WHEN g.c_max = g.c_min THEN 1
                ELSE (g.c_max - pr.cena) / (g.c_max - g.c_min) END AS b_cena,
           CASE WHEN g.s_max = g.s_min THEN 1
                ELSE (g.s_max - pr.srok_postavki_dney)::numeric
                     / (g.s_max - g.s_min) END                     AS b_srok,
           coalesce(n.dolya_v_srok, 0)                             AS b_nad,
           p.otsrochka_dney::numeric / max(p.otsrochka_dney) OVER () AS b_ots
    FROM prays pr
        JOIN granicy g      ON g.tovar_id = pr.tovar_id
        JOIN postavshchik p ON p.id = pr.postavshchik_id
        LEFT JOIN nadezhnost n ON n.postavshchik_id = pr.postavshchik_id
)
SELECT row_number() OVER (ORDER BY postavshchik_id, tovar_id),
       postavshchik_id, tovar_id, DATE '2026-11-01',
       round(b_cena, 3), round(b_srok, 3), round(b_nad, 3), round(b_ots, 3),
       round(0.35 * b_cena + 0.25 * b_srok + 0.30 * b_nad + 0.10 * b_ots, 3)
FROM bally;

-- 8. Готовый рейтинг по одной позиции: кого предложит система
SELECT t.naimenovanie   AS товар,
       p.naimenovanie   AS поставщик,
       o.ball_cena      AS цена,
       o.ball_srok      AS срок,
       o.ball_nadezhnost AS надёжность,
       o.ball_otsrochka AS отсрочка,
       o.itogovy_ball   AS итог
FROM ocenka_postavshchika o
    JOIN tovar t        ON t.id = o.tovar_id
    JOIN postavshchik p ON p.id = o.postavshchik_id
WHERE t.id = 1
ORDER BY o.itogovy_ball DESC;
