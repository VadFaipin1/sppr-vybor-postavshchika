-- Схема данных бизнес-процесса «Закупка, приём и оптовая реализация товаров».
-- Вариант 13, учебная организация ООО «Вектор-Опт».
-- Имена таблиц латиницей, русские названия сущностей и атрибутов — в COMMENT:
-- из них же собирается логическая ER-диаграмма.

DROP SCHEMA IF EXISTS zakupki CASCADE;
CREATE SCHEMA zakupki;
SET search_path TO zakupki;

-- Справочники номенклатуры

CREATE TABLE tovarnaya_gruppa (
    id            smallint PRIMARY KEY,
    naimenovanie  text NOT NULL UNIQUE
);
COMMENT ON TABLE tovarnaya_gruppa IS 'Товарная группа';
COMMENT ON COLUMN tovarnaya_gruppa.id IS 'Код группы';
COMMENT ON COLUMN tovarnaya_gruppa.naimenovanie IS 'Название';

CREATE TABLE tovar (
    id                 integer PRIMARY KEY,
    naimenovanie       text NOT NULL,
    gruppa_id          smallint NOT NULL REFERENCES tovarnaya_gruppa (id),
    edinica            text NOT NULL,
    kratnost_upakovki  integer NOT NULL CHECK (kratnost_upakovki > 0),
    srok_godnosti_dney integer CHECK (srok_godnosti_dney > 0)
);
COMMENT ON TABLE tovar IS 'Товар';
COMMENT ON COLUMN tovar.id IS 'Код товара';
COMMENT ON COLUMN tovar.naimenovanie IS 'Название';
COMMENT ON COLUMN tovar.gruppa_id IS 'Товарная группа';
COMMENT ON COLUMN tovar.edinica IS 'Единица измерения';
COMMENT ON COLUMN tovar.kratnost_upakovki IS 'Кратность упаковки';
COMMENT ON COLUMN tovar.srok_godnosti_dney IS 'Срок годности, дней';

CREATE TABLE ostatok (
    tovar_id     integer PRIMARY KEY REFERENCES tovar (id),
    kolichestvo  numeric(12,3) NOT NULL DEFAULT 0 CHECK (kolichestvo >= 0),
    rezerv       numeric(12,3) NOT NULL DEFAULT 0 CHECK (rezerv >= 0)
);
COMMENT ON TABLE ostatok IS 'Остаток на складе';
COMMENT ON COLUMN ostatok.tovar_id IS 'Товар';
COMMENT ON COLUMN ostatok.kolichestvo IS 'Количество на складе';
COMMENT ON COLUMN ostatok.rezerv IS 'Зарезервировано под заявки';

-- Поставщики и их условия

CREATE TABLE postavshchik (
    id                integer PRIMARY KEY,
    naimenovanie      text NOT NULL,
    inn               char(10) NOT NULL UNIQUE,
    otsrochka_dney    integer NOT NULL CHECK (otsrochka_dney >= 0),
    min_summa_zakaza  numeric(12,2) NOT NULL CHECK (min_summa_zakaza >= 0)
);
COMMENT ON TABLE postavshchik IS 'Поставщик';
COMMENT ON COLUMN postavshchik.id IS 'Код поставщика';
COMMENT ON COLUMN postavshchik.naimenovanie IS 'Название';
COMMENT ON COLUMN postavshchik.inn IS 'ИНН';
COMMENT ON COLUMN postavshchik.otsrochka_dney IS 'Отсрочка платежа, дней';
COMMENT ON COLUMN postavshchik.min_summa_zakaza IS 'Минимальная сумма заказа';

CREATE TABLE prays (
    id                  integer PRIMARY KEY,
    postavshchik_id     integer NOT NULL REFERENCES postavshchik (id),
    tovar_id            integer NOT NULL REFERENCES tovar (id),
    cena                numeric(12,2) NOT NULL CHECK (cena > 0),
    srok_postavki_dney  integer NOT NULL CHECK (srok_postavki_dney > 0),
    deystvuet_s         date NOT NULL,
    UNIQUE (postavshchik_id, tovar_id, deystvuet_s)
);
COMMENT ON TABLE prays IS 'Прайс-позиция поставщика';
COMMENT ON COLUMN prays.id IS 'Код позиции прайса';
COMMENT ON COLUMN prays.postavshchik_id IS 'Поставщик';
COMMENT ON COLUMN prays.tovar_id IS 'Товар';
COMMENT ON COLUMN prays.cena IS 'Цена за единицу';
COMMENT ON COLUMN prays.srok_postavki_dney IS 'Заявленный срок поставки, дней';
COMMENT ON COLUMN prays.deystvuet_s IS 'Действует с даты';

-- Закупка

CREATE TABLE zakaz_postavshchiku (
    id                  integer PRIMARY KEY,
    postavshchik_id     integer NOT NULL REFERENCES postavshchik (id),
    data_zakaza         date NOT NULL,
    plan_data_postavki  date NOT NULL,
    status              text NOT NULL
        CHECK (status IN ('размещён', 'принят', 'отменён')),
    CHECK (plan_data_postavki >= data_zakaza)
);
COMMENT ON TABLE zakaz_postavshchiku IS 'Заказ поставщику';
COMMENT ON COLUMN zakaz_postavshchiku.id IS 'Номер заказа';
COMMENT ON COLUMN zakaz_postavshchiku.postavshchik_id IS 'Поставщик';
COMMENT ON COLUMN zakaz_postavshchiku.data_zakaza IS 'Дата размещения';
COMMENT ON COLUMN zakaz_postavshchiku.plan_data_postavki IS 'Плановая дата поставки';
COMMENT ON COLUMN zakaz_postavshchiku.status IS 'Состояние заказа';

CREATE TABLE stroka_zakaza (
    id           integer PRIMARY KEY,
    zakaz_id     integer NOT NULL REFERENCES zakaz_postavshchiku (id),
    tovar_id     integer NOT NULL REFERENCES tovar (id),
    kolichestvo  numeric(12,3) NOT NULL CHECK (kolichestvo > 0),
    cena         numeric(12,2) NOT NULL CHECK (cena > 0),
    UNIQUE (zakaz_id, tovar_id)
);
COMMENT ON TABLE stroka_zakaza IS 'Строка заказа';
COMMENT ON COLUMN stroka_zakaza.id IS 'Код строки';
COMMENT ON COLUMN stroka_zakaza.zakaz_id IS 'Заказ';
COMMENT ON COLUMN stroka_zakaza.tovar_id IS 'Товар';
COMMENT ON COLUMN stroka_zakaza.kolichestvo IS 'Заказанное количество';
COMMENT ON COLUMN stroka_zakaza.cena IS 'Цена закупки';

CREATE TABLE postavka (
    id               integer PRIMARY KEY,
    zakaz_id         integer NOT NULL REFERENCES zakaz_postavshchiku (id),
    fakt_data        date NOT NULL,
    nomer_dokumenta  text NOT NULL
);
COMMENT ON TABLE postavka IS 'Поставка';
COMMENT ON COLUMN postavka.id IS 'Код поставки';
COMMENT ON COLUMN postavka.zakaz_id IS 'Заказ';
COMMENT ON COLUMN postavka.fakt_data IS 'Фактическая дата приёмки';
COMMENT ON COLUMN postavka.nomer_dokumenta IS 'Номер накладной';

CREATE TABLE stroka_postavki (
    id           integer PRIMARY KEY,
    postavka_id  integer NOT NULL REFERENCES postavka (id),
    tovar_id     integer NOT NULL REFERENCES tovar (id),
    prinyato     numeric(12,3) NOT NULL CHECK (prinyato >= 0),
    brak         numeric(12,3) NOT NULL DEFAULT 0 CHECK (brak >= 0),
    UNIQUE (postavka_id, tovar_id)
);
COMMENT ON TABLE stroka_postavki IS 'Строка поставки';
COMMENT ON COLUMN stroka_postavki.id IS 'Код строки';
COMMENT ON COLUMN stroka_postavki.postavka_id IS 'Поставка';
COMMENT ON COLUMN stroka_postavki.tovar_id IS 'Товар';
COMMENT ON COLUMN stroka_postavki.prinyato IS 'Принятое количество';
COMMENT ON COLUMN stroka_postavki.brak IS 'Забраковано при приёмке';

-- Реализация

CREATE TABLE klient (
    id            integer PRIMARY KEY,
    naimenovanie  text NOT NULL,
    inn           char(10) NOT NULL UNIQUE
);
COMMENT ON TABLE klient IS 'Клиент';
COMMENT ON COLUMN klient.id IS 'Код клиента';
COMMENT ON COLUMN klient.naimenovanie IS 'Название';
COMMENT ON COLUMN klient.inn IS 'ИНН';

CREATE TABLE zayavka (
    id         integer PRIMARY KEY,
    klient_id  integer NOT NULL REFERENCES klient (id),
    data       date NOT NULL,
    status     text NOT NULL
        CHECK (status IN ('принята', 'отгружена', 'отменена'))
);
COMMENT ON TABLE zayavka IS 'Заявка клиента';
COMMENT ON COLUMN zayavka.id IS 'Номер заявки';
COMMENT ON COLUMN zayavka.klient_id IS 'Клиент';
COMMENT ON COLUMN zayavka.data IS 'Дата заявки';
COMMENT ON COLUMN zayavka.status IS 'Состояние заявки';

CREATE TABLE stroka_zayavki (
    id           integer PRIMARY KEY,
    zayavka_id   integer NOT NULL REFERENCES zayavka (id),
    tovar_id     integer NOT NULL REFERENCES tovar (id),
    kolichestvo  numeric(12,3) NOT NULL CHECK (kolichestvo > 0),
    UNIQUE (zayavka_id, tovar_id)
);
COMMENT ON TABLE stroka_zayavki IS 'Строка заявки';
COMMENT ON COLUMN stroka_zayavki.id IS 'Код строки';
COMMENT ON COLUMN stroka_zayavki.zayavka_id IS 'Заявка';
COMMENT ON COLUMN stroka_zayavki.tovar_id IS 'Товар';
COMMENT ON COLUMN stroka_zayavki.kolichestvo IS 'Запрошенное количество';

CREATE TABLE otgruzka (
    id          integer PRIMARY KEY,
    zayavka_id  integer NOT NULL UNIQUE REFERENCES zayavka (id),
    data        date NOT NULL,
    nomer_upd   text NOT NULL UNIQUE
);
COMMENT ON TABLE otgruzka IS 'Отгрузка';
COMMENT ON COLUMN otgruzka.id IS 'Код отгрузки';
COMMENT ON COLUMN otgruzka.zayavka_id IS 'Заявка';
COMMENT ON COLUMN otgruzka.data IS 'Дата отгрузки';
COMMENT ON COLUMN otgruzka.nomer_upd IS 'Номер УПД';

CREATE TABLE stroka_otgruzki (
    id           integer PRIMARY KEY,
    otgruzka_id  integer NOT NULL REFERENCES otgruzka (id),
    tovar_id     integer NOT NULL REFERENCES tovar (id),
    kolichestvo  numeric(12,3) NOT NULL CHECK (kolichestvo > 0),
    cena         numeric(12,2) NOT NULL CHECK (cena > 0),
    UNIQUE (otgruzka_id, tovar_id)
);
COMMENT ON TABLE stroka_otgruzki IS 'Строка отгрузки';
COMMENT ON COLUMN stroka_otgruzki.id IS 'Код строки';
COMMENT ON COLUMN stroka_otgruzki.otgruzka_id IS 'Отгрузка';
COMMENT ON COLUMN stroka_otgruzki.tovar_id IS 'Товар';
COMMENT ON COLUMN stroka_otgruzki.kolichestvo IS 'Отгруженное количество';
COMMENT ON COLUMN stroka_otgruzki.cena IS 'Цена продажи';

-- Результат работы программного компонента

CREATE TABLE ocenka_postavshchika (
    id               integer PRIMARY KEY,
    postavshchik_id  integer NOT NULL REFERENCES postavshchik (id),
    tovar_id         integer NOT NULL REFERENCES tovar (id),
    data_ocenki      date NOT NULL,
    ball_cena        numeric(4,3) NOT NULL CHECK (ball_cena BETWEEN 0 AND 1),
    ball_srok        numeric(4,3) NOT NULL CHECK (ball_srok BETWEEN 0 AND 1),
    ball_nadezhnost  numeric(4,3) NOT NULL CHECK (ball_nadezhnost BETWEEN 0 AND 1),
    ball_otsrochka   numeric(4,3) NOT NULL CHECK (ball_otsrochka BETWEEN 0 AND 1),
    itogovy_ball     numeric(4,3) NOT NULL CHECK (itogovy_ball BETWEEN 0 AND 1),
    UNIQUE (postavshchik_id, tovar_id, data_ocenki)
);
COMMENT ON TABLE ocenka_postavshchika IS 'Оценка поставщика';
COMMENT ON COLUMN ocenka_postavshchika.id IS 'Код оценки';
COMMENT ON COLUMN ocenka_postavshchika.postavshchik_id IS 'Поставщик';
COMMENT ON COLUMN ocenka_postavshchika.tovar_id IS 'Товар';
COMMENT ON COLUMN ocenka_postavshchika.data_ocenki IS 'Дата оценки';
COMMENT ON COLUMN ocenka_postavshchika.ball_cena IS 'Балл по цене';
COMMENT ON COLUMN ocenka_postavshchika.ball_srok IS 'Балл по сроку поставки';
COMMENT ON COLUMN ocenka_postavshchika.ball_nadezhnost IS 'Балл по надёжности';
COMMENT ON COLUMN ocenka_postavshchika.ball_otsrochka IS 'Балл по отсрочке платежа';
COMMENT ON COLUMN ocenka_postavshchika.itogovy_ball IS 'Итоговый балл';

CREATE INDEX ON stroka_otgruzki (tovar_id);
CREATE INDEX ON stroka_postavki (tovar_id);
CREATE INDEX ON prays (tovar_id);
CREATE INDEX ON otgruzka (data);
