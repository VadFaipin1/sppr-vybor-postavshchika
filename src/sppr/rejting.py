"""Многокритериальный рейтинг поставщиков по позиции."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True)
class Offer:
    supplier: int
    item: int
    price: float
    lead_days: int
    deferral_days: int


@dataclass(frozen=True)
class Track:
    deliveries: int
    on_time: int


@dataclass(frozen=True)
class Score:
    supplier: int
    item: int
    price: float
    lead: float
    reliability: float
    deferral: float
    total: float
    preliminary: bool


def lower_is_better(value: float, lo: float, hi: float, method: str = "tolerance",
                    tolerance: float = 0.2) -> float:
    """Нормировка критерия, у которого меньше — лучше. Лучший получает 1.

    «range» — по размаху, как в подразделе 2.2: худший получает 0, сколько бы
    он ни уступал. Разница цен в 2 % даёт тот же разброс баллов, что и в 50 %.
    «ratio» — отношение к лучшему: малая разница остаётся малой, но у цены
    разброс узкий, а у срока широкий, и цена перестаёт влиять на выбор.
    «tolerance» — балл падает линейно до 0 при отставании от лучшего
    на допуск tolerance (доля лучшего значения). Сколько стоит отставание,
    задаёт допуск, а не случайный состав предложений.
    """
    if method == "range":
        return 1.0 if hi == lo else (hi - value) / (hi - lo)
    if method == "ratio":
        return lo / value
    if method == "tolerance":
        return max(0.0, 1 - (value - lo) / (lo * tolerance))
    raise ValueError(f"неизвестный способ нормировки: {method}")


def reliability(tracks: dict[int, Track], suppliers: set[int],
                min_deliveries: int) -> dict[int, tuple[float, bool]]:
    """Доля поставок в срок.

    У поставщика с короткой историей доля ничего не говорит, а ноль закрыл бы
    ему дорогу в рейтинг. Ему ставится медиана по поставщикам с достаточной
    историей, и оценка помечается как предварительная.
    """
    known = [t.on_time / t.deliveries for t in tracks.values()
             if t.deliveries >= min_deliveries]
    neutral = median(known) if known else 0.5
    out = {}
    for s in suppliers:
        t = tracks.get(s)
        if t is None or t.deliveries < min_deliveries:
            out[s] = (neutral, True)
        else:
            out[s] = (t.on_time / t.deliveries, False)
    return out


def score(offers: list[Offer], tracks: dict[int, Track],
          weights: tuple[float, float, float, float],
          min_deliveries: int, method: str = "tolerance",
          price_tolerance: float = 0.20, lead_tolerance: float = 2.0) -> list[Score]:
    w_price, w_lead, w_rel, w_def = weights
    rel = reliability(tracks, {o.supplier for o in offers}, min_deliveries)
    max_deferral = max(o.deferral_days for o in offers) or 1
    by_item: dict[int, list[Offer]] = {}
    for o in offers:
        by_item.setdefault(o.item, []).append(o)
    out = []
    for item, group in by_item.items():
        p_lo, p_hi = min(o.price for o in group), max(o.price for o in group)
        l_lo, l_hi = min(o.lead_days for o in group), max(o.lead_days for o in group)
        for o in group:
            b_price = lower_is_better(o.price, p_lo, p_hi, method, price_tolerance)
            b_lead = lower_is_better(o.lead_days, l_lo, l_hi, method, lead_tolerance)
            b_rel, prelim = rel[o.supplier]
            b_def = o.deferral_days / max_deferral
            total = w_price * b_price + w_lead * b_lead + w_rel * b_rel + w_def * b_def
            out.append(Score(o.supplier, item, b_price, b_lead, b_rel, b_def,
                             total, prelim))
    return out


def best(scores: list[Score]) -> dict[int, Score]:
    """Лучший поставщик по каждой позиции; при равенстве — меньший код."""
    out: dict[int, Score] = {}
    for s in sorted(scores, key=lambda s: (s.item, -s.total, s.supplier)):
        out.setdefault(s.item, s)
    return out
