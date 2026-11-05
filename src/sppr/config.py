"""Параметры расчёта; адрес базы берётся из DATABASE_URL, а не из файла."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from datetime import date
from fractions import Fraction
from pathlib import Path

# порядок критериев в матрице попарных сравнений
CRITERIA = ("цена", "срок поставки", "надёжность", "отсрочка платежа")


def _matrix() -> list[list[float]]:
    # шкала Саати: 1 — равная важность, 3 — умеренное превосходство, 5 — сильное
    return [
        [1, 2, 1, 4],
        [1 / 2, 1, 1 / 2, 3],
        [1, 2, 1, 4],
        [1 / 4, 1 / 3, 1 / 4, 1],
    ]


@dataclass
class Settings:
    pairwise: list[list[float]] = field(default_factory=_matrix)
    max_cr: float = 0.10
    normalization: str = "tolerance"   # «range» воспроизводит подраздел 2.2
    price_tolerance: float = 0.20      # дороже лучшего на 20 % — балл цены 0
    lead_tolerance: float = 2.0        # срок втрое больше лучшего — балл срока 0
    service_level: dict[str, float] = field(
        default_factory=lambda: {"A": 0.95, "B": 0.95, "C": 0.90})
    service_level_z: float = 0.98      # позиции с неустойчивым спросом
    order_cost: float = 1200.0         # стоимость размещения заказа, руб.
    holding_rate: float = 0.20         # хранение единицы в год, доля цены
    shelf_life_share: float = 0.5      # заказ не больше спроса за полсрока годности
    min_deliveries: int = 5            # меньше поставок — надёжность предварительная
    history_start: date = date(2025, 11, 1)
    history_end: date = date(2026, 10, 31)
    abc_bounds: tuple[float, float] = (0.80, 0.95)
    xyz_bounds: tuple[float, float] = (0.10, 0.25)
    max_data_age_days: int = 7         # данные старше — расчёт не запускается


def _number(value) -> float:
    """Элемент матрицы: число или дробь строкой, например «1/3»."""
    return float(Fraction(value)) if isinstance(value, str) else float(value)


def load(path: Path | None) -> Settings:
    s = Settings()
    if path is None:
        return s
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    known = {f.name for f in fields(Settings)}
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f"неизвестные параметры в {path}: {sorted(unknown)}")
    for key, value in raw.items():
        if key == "pairwise":
            value = [[_number(x) for x in row] for row in value]
        elif key in ("history_start", "history_end"):
            value = date.fromisoformat(value)
        elif key in ("abc_bounds", "xyz_bounds"):
            value = tuple(value)
        setattr(s, key, value)
    if len(s.pairwise) != len(CRITERIA):
        raise ValueError(f"матрица попарных сравнений должна быть {len(CRITERIA)}×"
                         f"{len(CRITERIA)}: критерии {', '.join(CRITERIA)}")
    return s
