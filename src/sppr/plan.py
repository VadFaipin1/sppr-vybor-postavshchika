"""Проект заказа: что, сколько и у кого заказать на дату расчёта."""
from __future__ import annotations

from dataclasses import dataclass, replace
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
    moved: bool = False   # отдана следующему в рейтинге из-за доли поставщика

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


def _line(item_id: int, top: rejting.Score, data: Data, s: Settings,
          abc: dict[int, str], xyz: dict[int, str], offer, force: bool = False):
    """Строка проекта заказа у данного поставщика; None, если заказывать рано."""
    item = data.items[item_id]
    o = offer[(top.supplier, item_id)]
    mean_daily, sigma = data.daily[item_id]
    manual = xyz.get(item_id) == "Z"
    level = s.service_level_z if manual else s.service_level[abc[item_id]]
    rop = zapasy.reorder_point(mean_daily, sigma, o.lead_days, zapasy.z_value(level))
    available = item.stock - item.reserve
    if available > rop and not force:
        return None
    q_eoq = zapasy.eoq(mean_daily * 365, s.order_cost, s.holding_rate * o.price)
    cap = zapasy.shelf_cap(mean_daily, item.shelf_days, s.shelf_life_share)
    qty = zapasy.order_quantity(q_eoq, rop - available, cap, item.pack)
    return Line(item_id, item.name, abc[item_id], xyz.get(item_id, "-"), available,
                rop, q_eoq, qty, top.supplier, data.suppliers[top.supplier][0],
                o.price, o.lead_days, top.total, top.preliminary, manual)


def cap_share(lines: list[Line], ranked: dict[int, list[rejting.Score]],
              make, limit: float) -> list[Line]:
    """Не больше limit суммы у одного поставщика: лишнее — следующему в рейтинге."""
    lines = list(lines)
    for _ in range(len(lines) * 4):
        total = sum(x.amount for x in lines)
        shares: dict[int, float] = {}
        for x in lines:
            shares[x.supplier] = shares.get(x.supplier, 0.0) + x.amount / total
        over = max(shares, key=shares.get)
        if shares[over] <= limit:
            break
        options = []
        for i, x in enumerate(lines):
            if x.supplier != over:
                continue
            rest = [r for r in ranked[x.item] if r.supplier != over]
            if rest:
                options.append((x.score - rest[0].total, i, rest[0]))
        if not options:
            break
        _, i, nxt = min(options)
        new = make(lines[i].item, nxt)
        lines[i] = replace(new, moved=True)
    return lines


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
    ranked: dict[int, list[rejting.Score]] = {}
    for sc in sorted(scores, key=lambda x: (x.item, -x.total, x.supplier)):
        ranked.setdefault(sc.item, []).append(sc)

    def make(item_id, top):
        return _line(item_id, top, data, s, abc, xyz, offer, force=True)

    lines = []
    for item_id in sorted(data.items):
        if item_id in best and item_id in data.daily:
            line = _line(item_id, best[item_id], data, s, abc, xyz, offer)
            if line is not None:
                lines.append(line)
    if s.max_supplier_share < 1:
        lines = cap_share(lines, ranked, make, s.max_supplier_share)

    totals: dict[int, float] = {}
    for line in lines:
        totals[line.supplier] = totals.get(line.supplier, 0.0) + line.amount
    below = {sup: (total, data.suppliers[sup][1]) for sup, total in totals.items()
             if total < data.suppliers[sup][1]}
    return Plan(as_of, w, lines, scores, abc, xyz, below)
