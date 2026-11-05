"""Метод анализа иерархий: веса критериев по матрице попарных сравнений."""
from __future__ import annotations

from dataclasses import dataclass

# случайный индекс согласованности Саати для матриц порядка n
RANDOM_INDEX = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24,
                7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}


@dataclass(frozen=True)
class AhpResult:
    weights: tuple[float, ...]
    lambda_max: float
    ci: float
    cr: float


def check_matrix(m: list[list[float]]) -> None:
    n = len(m)
    if n < 2 or any(len(row) != n for row in m):
        raise ValueError("матрица должна быть квадратной, порядка не меньше 2")
    for i in range(n):
        if abs(m[i][i] - 1) > 1e-9:
            raise ValueError(f"на диагонали стоит {m[i][i]}, а должна быть 1")
        for j in range(n):
            if m[i][j] <= 0:
                raise ValueError("элементы матрицы должны быть положительными")
            if abs(m[i][j] * m[j][i] - 1) > 1e-6:
                raise ValueError(f"нарушена обратная симметричность в ({i}, {j})")


def weights(m: list[list[float]]) -> AhpResult:
    """Главный собственный вектор методом степеней и отношение согласованности."""
    check_matrix(m)
    n = len(m)
    w = [1 / n] * n
    for _ in range(1000):
        nxt = [sum(m[i][j] * w[j] for j in range(n)) for i in range(n)]
        total = sum(nxt)
        nxt = [x / total for x in nxt]
        done = max(abs(a - b) for a, b in zip(nxt, w)) < 1e-12
        w = nxt
        if done:
            break
    lam = sum(sum(m[i][j] * w[j] for j in range(n)) / w[i] for i in range(n)) / n
    ci = (lam - n) / (n - 1)
    ri = RANDOM_INDEX[n]
    cr = ci / ri if ri else 0.0
    return AhpResult(tuple(w), lam, ci, cr)
