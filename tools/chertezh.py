"""Чертёж схем в натуральную величину: координаты в миллиметрах, кегль в пунктах.

Схема рисуется сразу в том размере, в котором встаёт в отчёт, поэтому кегль
на листе равен заданному, а не тому, что останется после ужатия. Раскладка
задаётся вручную по сетке: линии идут только по горизонтали и вертикали,
с изломами в промежутках между блоками, и не заходят внутрь блоков.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle  # noqa: E402

ПТ = 25.4 / 72                      # миллиметров в пункте
ПАПКА_ШРИФТОВ = Path("/System/Library/Fonts/Supplemental")
ФАЙЛЫ = {False: ПАПКА_ШРИФТОВ / "Times New Roman.ttf",
         True: ПАПКА_ШРИФТОВ / "Times New Roman Bold.ttf"}
ЛИНИЯ = "#333333"
_метрики: dict = {}


def длина(текст: str, кегль: float, жирный: bool = False) -> float:
    """Ширина строки в миллиметрах по метрикам Times New Roman."""
    from PIL import ImageFont
    if жирный not in _метрики:
        _метрики[жирный] = ImageFont.truetype(str(ФАЙЛЫ[жирный]), 1000)
    return max(_метрики[жирный].getlength(с) for с in текст.split("\n")) / 1000 * кегль * ПТ


def шрифт(кегль: float, жирный: bool = False) -> FontProperties:
    return FontProperties(fname=str(ФАЙЛЫ[жирный]), size=кегль)


@dataclass
class Блок:
    """Прямоугольник на чертеже; строки — центры строк атрибутов по имени."""
    x: float
    y: float
    w: float
    h: float
    строки: dict = field(default_factory=dict)

    @property
    def низ(self) -> float:
        return self.y + self.h

    @property
    def право(self) -> float:
        return self.x + self.w

    def точка(self, сторона: str, где=0.5) -> tuple[float, float]:
        """Точка на стороне: где — доля длины стороны, имя строки или «+мм» от начала."""
        if сторона in "LR":
            x = self.x if сторона == "L" else self.право
            if isinstance(где, str):
                y = self.строки[где]
            elif где > 1:
                y = self.y + где
            else:
                y = self.y + self.h * где
            return x, y
        y = self.y if сторона == "T" else self.низ
        x = self.x + (где if где > 1 else self.w * где)
        return x, y


class Холст:
    def __init__(self, ширина: float, высота: float):
        self.ширина, self.высота = ширина, высота
        self.fig = plt.figure(figsize=(ширина / 25.4, высота / 25.4))
        self.ax = self.fig.add_axes((0, 0, 1, 1))
        self.ax.set_xlim(0, ширина)
        self.ax.set_ylim(высота, 0)
        self.ax.axis("off")

    # --- примитивы -----------------------------------------------------------
    def текст(self, x, y, s, кегль, жирный=False, ha="left", va="center",
              цвет="black", фон=None, z=5):
        опции = dict(fontproperties=шрифт(кегль, жирный), ha=ha, va=va,
                     color=цвет, zorder=z, linespacing=1.1)
        if фон:
            опции["bbox"] = dict(boxstyle="square,pad=0.12", facecolor=фон,
                                 edgecolor="none")
        self.ax.text(x, y, s, **опции)

    def прямоугольник(self, x, y, w, h, заливка="white", скругление=0.0,
                      толщина=0.7, цвет=ЛИНИЯ, z=2, контур=True):
        if скругление:
            p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={скругление}",
                               facecolor=заливка, edgecolor=цвет if контур else "none",
                               linewidth=толщина, zorder=z)
        else:
            p = Rectangle((x, y), w, h, facecolor=заливка,
                          edgecolor=цвет if контур else "none", linewidth=толщина, zorder=z)
        self.ax.add_patch(p)

    def линия(self, точки, толщина=0.7, цвет=ЛИНИЯ, z=3):
        xs, ys = zip(*точки)
        self.ax.plot(xs, ys, color=цвет, linewidth=толщина, zorder=z,
                     solid_capstyle="butt", solid_joinstyle="miter")

    def стрелка(self, точки, толщина=0.7, цвет=ЛИНИЯ, длина_мм=2.4, ширина_мм=1.7):
        """Ломаная с закрашенным наконечником в последней точке."""
        (x0, y0), (x1, y1) = точки[-2], точки[-1]
        dx, dy = _единичный(x1 - x0, y1 - y0)
        основание = (x1 - dx * длина_мм, y1 - dy * длина_мм)
        self.линия(list(точки[:-1]) + [основание], толщина, цвет)
        nx, ny = -dy, dx
        self.ax.add_patch(Polygon([
            (x1, y1),
            (основание[0] + nx * ширина_мм / 2, основание[1] + ny * ширина_мм / 2),
            (основание[0] - nx * ширина_мм / 2, основание[1] - ny * ширина_мм / 2)],
            closed=True, facecolor=цвет, edgecolor=цвет, linewidth=0.3, zorder=4))

    def черта(self, точка, к_блоку, отступ=2.0, размах=1.6, толщина=0.8):
        """Поперечная черта «один» на линии в отступ мм от блока."""
        x, y = точка
        dx, dy = к_блоку
        cx, cy = x - dx * отступ, y - dy * отступ
        nx, ny = -dy, dx
        self.линия([(cx + nx * размах, cy + ny * размах),
                    (cx - nx * размах, cy - ny * размах)], толщина)

    def лапка(self, точка, к_блоку, длина_мм=3.2, размах=1.6, толщина=0.7):
        """«Воронья лапка» — много: три зубца сходятся на линии, концы на границе блока."""
        x, y = точка
        dx, dy = к_блоку
        cx, cy = x - dx * длина_мм, y - dy * длина_мм
        nx, ny = -dy, dx
        for k in (-1, 0, 1):
            self.линия([(cx, cy), (x + nx * размах * k, y + ny * размах * k)], толщина)

    def сохранить(self, путь: Path, dpi: int = 300) -> None:
        путь = Path(путь)
        self.fig.savefig(путь.with_suffix(".png"), dpi=dpi, facecolor="white")
        self.fig.savefig(путь.with_suffix(".svg"), facecolor="white")
        plt.close(self.fig)


def _единичный(dx: float, dy: float) -> tuple[float, float]:
    d = (dx * dx + dy * dy) ** 0.5
    return dx / d, dy / d


def путь(a: tuple, сторона_a: str, b: tuple, сторона_b: str,
         канал: float | None = None, через: list | None = None) -> list:
    """Ортогональная ломаная от точки a на стороне сторона_a к точке b.

    Горизонтальные стороны (L, R) выходят горизонтально, вертикальные (T, B) —
    вертикально. Излом — в канале: x для L/R→L/R, y для T/B→T/B; по умолчанию
    посередине. Через — явные промежуточные точки."""
    if через:
        return [a, *через, b]
    гор_a, гор_b = сторона_a in "LR", сторона_b in "LR"
    (xa, ya), (xb, yb) = a, b
    if гор_a and гор_b:
        if abs(ya - yb) < 1e-6:
            return [a, b]
        xm = канал if канал is not None else (xa + xb) / 2
        return [a, (xm, ya), (xm, yb), b]
    if not гор_a and not гор_b:
        if abs(xa - xb) < 1e-6:
            return [a, b]
        ym = канал if канал is not None else (ya + yb) / 2
        return [a, (xa, ym), (xb, ym), b]
    if гор_a:
        return [a, (xb, ya), b]
    return [a, (xa, yb), b]


НАПРАВЛЕНИЕ_В_БЛОК = {"L": (1, 0), "R": (-1, 0), "T": (0, 1), "B": (0, -1)}
