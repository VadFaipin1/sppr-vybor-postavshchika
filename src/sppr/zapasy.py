"""Точка перезаказа, страховой запас и размер партии."""
from __future__ import annotations

from math import ceil, floor, sqrt
from statistics import NormalDist


def z_value(service_level: float) -> float:
    """Коэффициент страхового запаса для заданного уровня обслуживания."""
    return NormalDist().inv_cdf(service_level)


def reorder_point(mean_daily: float, sigma_daily: float, lead_days: float,
                  z: float) -> float:
    return mean_daily * lead_days + z * sigma_daily * sqrt(lead_days)


def eoq(annual_demand: float, order_cost: float, holding_cost: float) -> float:
    """Экономичный размер заказа по формуле Уилсона."""
    if annual_demand <= 0:
        return 0.0
    return sqrt(2 * annual_demand * order_cost / holding_cost)


def shelf_cap(mean_daily: float, shelf_days: int | None,
              share: float) -> float | None:
    """Сколько можно взять, чтобы продать за долю срока годности."""
    if shelf_days is None:
        return None
    return mean_daily * shelf_days * share


def order_quantity(eoq_qty: float, shortfall: float, cap: float | None,
                   pack: int) -> int:
    """Количество к заказу, кратное упаковке; потолок по сроку годности сильнее."""
    q = max(eoq_qty, shortfall)
    if q <= 0:
        return 0
    up = ceil(q / pack) * pack
    if cap is not None and up > cap:
        return max(pack, floor(cap / pack) * pack)
    return up
