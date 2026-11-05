"""Проект заказа: что, сколько и у кого заказать на дату расчёта."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import ahp, klassy, rejting, zapasy
from .config import Settings
from .db import Data


@dataclass(frozen=True)
class Line:
    item: int
    name: str
    abc: str
    xyz: str
    available: float
    reorder_point: float
    eoq: float
    quantity: int
    supplier: int
    supplier_name: str
    price: float
    lead_days: int
    score: float
    preliminary: bool
    manual: bool          # спрос неустойчив, нужен контроль менеджера

    @property
    def amount(self) -> float:
        return self.quantity * self.price


@dataclass
class Plan:
    as_of: date
    weights: ahp.AhpResult
    lines: list[Line]
    scores: list[rejting.Score]
    abc: dict[int, str]
    xyz: dict[int, str]
    below_minimum: dict[int, tuple[float, float]]   # поставщик: сумма и минимум


class InconsistentWeights(ValueError):
    pass


def build(data: Data, s: Settings, as_of: date) -> Plan:
    w = ahp.weights(s.pairwise)
    if w.cr >= s.max_cr:
        raise InconsistentWeights(
            f"отношение согласованности {w.cr:.3f} не меньше {s.max_cr}: "
            "матрицу попарных сравнений надо пересмотреть")
    abc = klassy.abc(data.revenue, s.abc_bounds)
    xyz = klassy.xyz(data.weekly, s.xyz_bounds)
    scores = rejting.score(data.offers, data.tracks, w.weights, s.min_deliveries,
                           s.normalization, s.price_tolerance, s.lead_tolerance)
    best = rejting.best(scores)
    offer = {(o.supplier, o.item): o for o in data.offers}

    lines = []
    for item_id, item in sorted(data.items.items()):
        if item_id not in best or item_id not in data.daily:
            continue
        top = best[item_id]
        o = offer[(top.supplier, item_id)]
        mean_daily, sigma = data.daily[item_id]
        manual = xyz.get(item_id) == "Z"
        level = s.service_level_z if manual else s.service_level[abc[item_id]]
        rop = zapasy.reorder_point(mean_daily, sigma, o.lead_days,
                                   zapasy.z_value(level))
        available = item.stock - item.reserve
        if available > rop:
            continue
        q_eoq = zapasy.eoq(mean_daily * 365, s.order_cost, s.holding_rate * o.price)
        cap = zapasy.shelf_cap(mean_daily, item.shelf_days, s.shelf_life_share)
        qty = zapasy.order_quantity(q_eoq, rop - available, cap, item.pack)
        lines.append(Line(item_id, item.name, abc[item_id], xyz.get(item_id, "-"),
                          available, rop, q_eoq, qty, top.supplier,
                          data.suppliers[top.supplier][0], o.price, o.lead_days,
                          top.total, top.preliminary, manual))

    totals: dict[int, float] = {}
    for line in lines:
        totals[line.supplier] = totals.get(line.supplier, 0.0) + line.amount
    below = {sup: (total, data.suppliers[sup][1]) for sup, total in totals.items()
             if total < data.suppliers[sup][1]}
    return Plan(as_of, w, lines, scores, abc, xyz, below)
