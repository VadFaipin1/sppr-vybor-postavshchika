"""ABC- и XYZ-классификация номенклатуры."""
from __future__ import annotations

from statistics import mean, stdev


def abc(revenue: dict[int, float], bounds: tuple[float, float]) -> dict[int, str]:
    """Класс по накопленной доле выручки: A до первой границы, B до второй."""
    total = sum(revenue.values())
    out, acc = {}, 0.0
    for item, value in sorted(revenue.items(), key=lambda kv: kv[1], reverse=True):
        acc += value
        share = acc / total
        out[item] = "A" if share <= bounds[0] else "B" if share <= bounds[1] else "C"
    return out


def variation(weekly: list[float]) -> float:
    """Коэффициент вариации недельного спроса (выборочное отклонение)."""
    if len(weekly) < 2 or mean(weekly) == 0:
        return float("inf")
    return stdev(weekly) / mean(weekly)


def xyz(weekly: dict[int, list[float]], bounds: tuple[float, float]) -> dict[int, str]:
    out = {}
    for item, series in weekly.items():
        cv = variation(series)
        out[item] = "X" if cv < bounds[0] else "Y" if cv < bounds[1] else "Z"
    return out
