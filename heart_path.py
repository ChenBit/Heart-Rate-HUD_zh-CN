"""心形路径生成工具。

使用经典心形参数方程绘制对称、饱满的心形：

    x(t) = 16 sin³(t)
    y(t) = 13 cos(t) − 5 cos(2t) − 2 cos(3t) − cos(4t)

该方程生成的心形凹口朝上、顶尖朝下，比两段三次贝塞尔曲线拼出的
“心形”更圆润对称。路径以 (0, 0) 为中心，外接框长边归一化为指定 size。
"""

import math

from PySide6.QtGui import QPainterPath


def _build_unit_heart_points(samples: int = 200):
    """计算归一化心形采样点。

    返回的点已居中于原点，并将数学包围盒的长边缩放为 1.0；
    同时翻转 y 轴以适配 Qt 坐标系（y 向下），使心形顶尖朝下。
    """
    pts = []
    two_pi = 2.0 * math.pi
    for i in range(samples):
        t = two_pi * i / samples
        sin_t = math.sin(t)
        x = 16.0 * sin_t * sin_t * sin_t
        y = (13.0 * math.cos(t)
             - 5.0 * math.cos(2.0 * t)
             - 2.0 * math.cos(3.0 * t)
             - math.cos(4.0 * t))
        pts.append((x, y))

    min_x = min(p[0] for p in pts)
    max_x = max(p[0] for p in pts)
    min_y = min(p[1] for p in pts)
    max_y = max(p[1] for p in pts)
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0
    long_side = max(max_x - min_x, max_y - min_y)
    # 翻转 y 使顶尖朝下；归一化长边为 1.0
    return [((p[0] - cx) / long_side, -(p[1] - cy) / long_side) for p in pts]


# 模块级缓存：单位心形采样点（长边 = 1.0，居中于原点），避免每帧重算三角函数
_UNIT_HEART_POINTS = _build_unit_heart_points()


def make_heart_path(size: float) -> QPainterPath:
    """生成以 (0, 0) 为中心、外接框长边为 size 的心形路径。

    Args:
        size: 心形外接框的目标长边尺寸（宽高均不超过 size）。

    Returns:
        居中于原点的 QPainterPath。
    """
    path = QPainterPath()
    for i, (ux, uy) in enumerate(_UNIT_HEART_POINTS):
        sx = ux * size
        sy = uy * size
        if i == 0:
            path.moveTo(sx, sy)
        else:
            path.lineTo(sx, sy)
    path.closeSubpath()
    return path
