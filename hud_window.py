from typing import Optional

from PySide6.QtCore import (
    Qt, QPoint, QTimer, QRectF, QSize, Signal, QPropertyAnimation, QEasingCurve
)
from PySide6.QtGui import (
    QPainter, QColor, QFont, QFontMetrics, QMouseEvent, QPaintEvent,
    QBrush, QPen, QPainterPath, QIcon
)
from PySide6.QtWidgets import QWidget, QApplication, QToolTip

from config_manager import ConfigManager


def parse_color(color_str: str) -> QColor:
    """解析颜色字符串，支持 #RGB, #RRGGBB, #AARRGGBB"""
    if not color_str:
        return QColor(0, 0, 0, 0)
    s = color_str.strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) == 3:
        r, g, b = [int(c * 2, 16) for c in s]
        return QColor(r, g, b, 255)
    elif len(s) == 6:
        r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        return QColor(r, g, b, 255)
    elif len(s) == 8:
        a, r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16)
        return QColor(r, g, b, a)
    else:
        c = QColor(color_str)
        return c if c.isValid() else QColor(0, 0, 0, 0)


def color_to_hex(color: QColor, include_alpha: bool = True) -> str:
    if include_alpha:
        return "#{:02X}{:02X}{:02X}{:02X}".format(color.alpha(), color.red(), color.green(), color.blue())
    return "#{:02X}{:02X}{:02X}".format(color.red(), color.green(), color.blue())


class HeartIcon:
    """绘制心形图标并支持跳动动画"""

    @staticmethod
    def draw(painter: QPainter, x: float, y: float, size: float, color: QColor, scale: float = 1.0):
        """绘制心形 (x,y 为中心坐标)"""
        painter.save()
        painter.translate(x, y)
        painter.scale(scale, scale)
        s = size
        path = QPainterPath()
        path.moveTo(0, s * 0.3)
        path.cubicTo(-s * 0.5, -s * 0.3, -s, s * 0.1, 0, s)
        path.cubicTo(s, s * 0.1, s * 0.5, -s * 0.3, 0, s * 0.3)
        path.closeSubpath()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillPath(path, QBrush(color))
        painter.restore()


class HUDWindow(QWidget):
    """悬浮抬头显示窗口"""

    position_changed = Signal(int, int)

    HEART_ICON_CHAR = "\u2764"

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self._config = config

        # 窗口属性：置顶、无边框、透明背景、工具窗口（不占任务栏）
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        # 当前显示数据
        self._heart_rate: Optional[int] = None
        self._stress_index: Optional[int] = None
        self._connection_status: str = "未连接"

        # 拖拽
        self._drag_position: Optional[QPoint] = None

        # 心跳动画
        self._heartbeat_phase = 0.0
        self._current_hr = 75  # 用于动画频率
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._anim_timer.start(30)

        # 尺寸
        self._min_width = 120
        self._min_height = 60
        self._update_size_from_config()

        # 位置
        pos = self._config.window_position
        self.move(pos.get("x", 100), pos.get("y", 100))

        self.setMouseTracking(True)
        self.setMinimumSize(self._min_width, self._min_height)

    def _update_size_from_config(self):
        # 窗口尺寸由 window_size 配置决定，与 scale（内容放大倍率）相互独立
        ws = self._config.window_size
        w = max(self._min_width, int(ws.get("width", 240)))
        h = max(self._min_height, int(ws.get("height", 90)))
        self._content_width = w
        self._content_height = h
        self.resize(w, h)
        self.setMinimumSize(max(80, int(w * 0.3)), max(40, int(h * 0.3)))

    def apply_config(self):
        """应用新配置后刷新"""
        self._update_size_from_config()
        self.update()

    # ---------------------- 数据接口 ----------------------
    def set_heart_rate(self, hr: Optional[int]):
        self._heart_rate = hr
        if hr is not None:
            self._current_hr = hr
        self.update()

    def set_stress_index(self, index: Optional[int]):
        self._stress_index = index
        self.update()

    def set_connection_status(self, status: str):
        self._connection_status = status
        self.update()

    # ---------------------- 动画 ----------------------
    def _on_anim_tick(self):
        # 根据心率计算每跳周期（毫秒），60秒/心率 = 每跳秒数
        period_ms = 60000.0 / max(1, self._current_hr)
        step = 30.0 / period_ms
        self._heartbeat_phase = (self._heartbeat_phase + step) % 1.0
        self.update()

    def _heartbeat_scale(self) -> float:
        """根据相位返回当前跳动缩放（1.0 ~ 1.25）"""
        p = self._heartbeat_phase
        # 双峰模拟心跳：lub-dub
        if p < 0.1:
            t = p / 0.1
            return 1.0 + 0.25 * (1 - abs(t * 2 - 1))
        elif 0.15 < p < 0.25:
            t = (p - 0.15) / 0.1
            return 1.0 + 0.15 * (1 - abs(t * 2 - 1))
        else:
            return 1.0

    # ---------------------- 绘制 ----------------------
    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        scale_ratio = self._config.scale / 100.0

        width = self.width()
        height = self.height()

        # 1. 背景与边框
        bg_color = parse_color(self._config.background_color)
        border_color = parse_color(self._config.border_color)
        border_width = self._config.border_width

        radius = 12 * scale_ratio
        rect = QRectF(0, 0, width, height)

        painter.save()
        if bg_color.alpha() > 0:
            painter.setBrush(QBrush(bg_color))
        else:
            painter.setBrush(Qt.NoBrush)

        if border_width > 0 and border_color.alpha() > 0:
            painter.setPen(QPen(border_color, max(1, int(border_width * scale_ratio))))
        else:
            painter.setPen(Qt.NoPen)

        painter.drawRoundedRect(rect.adjusted(border_width * scale_ratio / 2,
                                              border_width * scale_ratio / 2,
                                              -border_width * scale_ratio / 2,
                                              -border_width * scale_ratio / 2),
                                radius, radius)
        painter.restore()

        # 2. 内容配置
        display = self._config.display
        show_hr = display["show_heart_rate"]
        show_stress = display["show_stress_index"]
        show_icon = display["show_heart_icon"]

        if not show_hr and not show_stress and not show_icon:
            # 最少显示点什么
            show_hr = True

        # 3. 字体
        font_cfg = self._config.font
        font = QFont()
        font.setFamily(font_cfg["family"])
        font.setPointSize(max(6, int(font_cfg["size"] * scale_ratio)))
        font.setBold(font_cfg["bold"])
        font.setItalic(font_cfg["italic"])
        font.setUnderline(font_cfg["underline"])

        fg_color = parse_color(self._config.foreground_color)

        # 内边距
        pad = 8 * scale_ratio

        # 4. 计算内容布局
        items = []  # (kind, text_or_none, weight)
        if show_icon:
            items.append(("icon", None))
        if show_hr:
            hr_text = f"{self._heart_rate}" if self._heart_rate is not None else "--"
            items.append(("text", hr_text + " BPM"))
        if show_stress:
            st_text = f"{self._stress_index}" if self._stress_index is not None else "--"
            items.append(("stress", "压力 " + st_text))

        # 单行水平布局
        painter.setFont(font)
        fm = QFontMetrics(font)

        total_w = 0
        gap = 10 * scale_ratio
        sizes = []
        for kind, content in items:
            if kind == "icon":
                icon_size = max(16, int(font_cfg["size"] * 1.5 * scale_ratio))
                sizes.append(("icon", icon_size))
                total_w += icon_size
            else:
                text = content
                tw = fm.horizontalAdvance(text)
                sizes.append((kind, tw, fm.height(), text))
                total_w += tw
            total_w += gap

        total_w -= gap  # 最后一个无gap

        content_rect = rect.adjusted(pad, pad, -pad, -pad)
        x = content_rect.left() + max(0, (content_rect.width() - total_w) / 2)
        y_center = content_rect.center().y()

        for i, (kind, *rest) in enumerate(sizes):
            if kind == "icon":
                icon_size = rest[0]
                hb_scale = self._heartbeat_scale()
                # 图标颜色
                HeartIcon.draw(painter, x + icon_size / 2, y_center,
                               icon_size * 0.5, fg_color, hb_scale)
                x += icon_size
            elif kind == "text":
                tw, th, text = rest
                painter.setPen(fg_color)
                painter.setFont(font)
                painter.drawText(QRectF(x, y_center - th / 2, tw, th),
                                 Qt.AlignLeft | Qt.AlignVCenter, text)
                x += tw
            elif kind == "stress":
                tw, th, text = rest
                painter.setPen(fg_color)
                painter.setFont(font)
                painter.drawText(QRectF(x, y_center - th / 2, tw, th),
                                 Qt.AlignLeft | Qt.AlignVCenter, text)
                x += tw
            x += gap

        # 5. 状态小提示（左下角小字，未连接/重连中时）
        if self._heart_rate is None:
            small_font = QFont(font)
            small_font.setPointSize(max(6, int(font_cfg["size"] * 0.55 * scale_ratio)))
            small_font.setBold(False)
            painter.setFont(small_font)
            sfm = QFontMetrics(small_font)
            status_text = self._connection_status or "--"
            sw = sfm.horizontalAdvance(status_text)
            sh = sfm.height()
            painter.setPen(fg_color)
            painter.setOpacity(0.7)
            painter.drawText(QRectF(pad, height - pad - sh, sw + 4, sh),
                             Qt.AlignLeft | Qt.AlignBottom, status_text)
            painter.setOpacity(1.0)

    # ---------------------- 拖拽支持 ----------------------
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_position is not None and event.buttons() & Qt.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_position
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._drag_position is not None:
            self._drag_position = None
            pos = self.pos()
            self._config.window_position = {"x": pos.x(), "y": pos.y()}
            self.position_changed.emit(pos.x(), pos.y())
            event.accept()

    def contextMenuEvent(self, event):
        """右键空菜单占位，交由主程序统一处理"""
        event.ignore()
