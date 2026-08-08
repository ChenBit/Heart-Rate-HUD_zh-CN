import re
from typing import Dict, Optional, Tuple

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import (
    QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap, QBrush, QPen, QPainterPath, QPalette
)
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QSlider, QLineEdit, QComboBox, QPushButton, QGroupBox, QGridLayout,
    QColorDialog, QFrame, QMessageBox, QSizePolicy, QGraphicsDropShadowEffect
)

from config_manager import ConfigManager
from hud_window import parse_color, color_to_hex


SCALE_MIN = 50
SCALE_MAX = 500

# 悬浮窗窗口尺寸范围（像素）
WIN_WIDTH_MIN = 120
WIN_WIDTH_MAX = 3000
WIN_HEIGHT_MIN = 60
WIN_HEIGHT_MAX = 2000


def _color_to_hex_with_alpha(color: QColor) -> str:
    """返回 #AARRGGBB 格式（如果alpha=255则返回无alpha的短格式）"""
    if color.alpha() == 255:
        return "#{:02X}{:02X}{:02X}".format(color.red(), color.green(), color.blue())
    return "#{:02X}{:02X}{:02X}{:02X}".format(color.alpha(), color.red(), color.green(), color.blue())


class ColorPickerButton(QPushButton):
    """颜色选择按钮，显示当前颜色方块"""

    color_changed = Signal(str)

    def __init__(self, initial_color: str = "#FFFFFF", support_alpha: bool = False, parent=None):
        super().__init__(parent)
        self._support_alpha = support_alpha
        self._color: QColor = parse_color(initial_color)
        self.setMinimumSize(40, 28)
        self.setMaximumSize(60, 32)
        self.clicked.connect(self._pick_color)
        self.setText(_color_to_hex_with_alpha(self._color).upper())
        self._update_icon()
        self.setStyleSheet("text-align:left; padding-left: 4px;")

    def _update_icon(self):
        size = 18
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = pix.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor("#888"), 1))
        painter.setBrush(QBrush(self._color))
        painter.drawRoundedRect(rect, 3, 3)
        painter.end()
        self.setIcon(QIcon(pix))
        self.setIconSize(QSize(size, size))

    def _pick_color(self):
        options = QColorDialog.ColorDialogOptions()
        if self._support_alpha:
            options |= QColorDialog.ShowAlphaChannel
        dialog = QColorDialog(self._color, self)
        dialog.setWindowTitle("选择颜色")
        dialog.setOptions(options)
        if dialog.exec() == QDialog.Accepted:
            new_color = dialog.currentColor()
            if not self._support_alpha:
                new_color.setAlpha(255)
            self.set_color(new_color)

    def color(self) -> QColor:
        return QColor(self._color)

    def set_color(self, color: QColor):
        self._color = QColor(color)
        self.setText(_color_to_hex_with_alpha(self._color).upper())
        self._update_icon()
        self.color_changed.emit(_color_to_hex_with_alpha(self._color))


class SettingsWindow(QDialog):
    """设置窗口：包含7项自定义配置 + 校验 + Apply按钮"""

    config_applied = Signal(dict)

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("悬浮窗自定义设置")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(520)

        self._build_ui()
        self._aspect_ratio = None  # 纵横比（width/height），None 表示未锁定
        self._load_from_config()
        self._connect_signals()
        self._validate_all()

    # ---------------------- UI构建 ----------------------
    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # 1. 显示内容组
        display_box = QGroupBox("1. 显示内容")
        display_layout = QHBoxLayout(display_box)
        display_layout.setSpacing(20)
        self.cb_hr = QCheckBox("心率")
        self.cb_stress = QCheckBox("压力指数")
        self.cb_icon = QCheckBox("心脏图标")
        display_layout.addWidget(self.cb_hr)
        display_layout.addWidget(self.cb_stress)
        display_layout.addWidget(self.cb_icon)
        display_layout.addStretch(1)
        main_layout.addWidget(display_box)

        # 2. 大小倍率组
        size_box = QGroupBox("2. 显示内容大小（总体放大倍率）")
        size_box_layout = QVBoxLayout(size_box)
        size_box_layout.setSpacing(6)
        size_layout = QHBoxLayout()
        size_layout.setSpacing(10)
        self.slider_scale = QSlider(Qt.Horizontal)
        self.slider_scale.setRange(SCALE_MIN, SCALE_MAX)
        self.slider_scale.setTickPosition(QSlider.TicksBelow)
        self.slider_scale.setTickInterval(50)
        self.edit_scale = QLineEdit()
        self.edit_scale.setFixedWidth(80)
        self.edit_scale.setMaxLength(6)
        self.edit_scale.setAlignment(Qt.AlignCenter)
        size_layout.addWidget(QLabel(f"{SCALE_MIN}%"))
        size_layout.addWidget(self.slider_scale, 1)
        size_layout.addWidget(QLabel(f"{SCALE_MAX}%"))
        size_layout.addWidget(self.edit_scale)
        size_box_layout.addLayout(size_layout)
        self.lbl_scale_error = QLabel("")
        self.lbl_scale_error.setStyleSheet("color: #d93025; font-size: 11px;")
        size_box_layout.addWidget(self.lbl_scale_error)
        main_layout.addWidget(size_box)

        # 悬浮窗大小（窗口尺寸 px），与显示内容倍率相互独立
        win_size_box = QGroupBox("悬浮窗大小（窗口尺寸 px）")
        win_size_layout = QGridLayout(win_size_box)
        win_size_layout.setHorizontalSpacing(10)
        win_size_layout.setVerticalSpacing(8)

        win_size_layout.addWidget(QLabel("宽度："), 0, 0)
        self.edit_win_width = QLineEdit()
        self.edit_win_width.setFixedWidth(90)
        self.edit_win_width.setMaxLength(5)
        self.edit_win_width.setAlignment(Qt.AlignCenter)
        win_size_layout.addWidget(self.edit_win_width, 0, 1)
        win_size_layout.addWidget(QLabel("px"), 0, 2)

        win_size_layout.addWidget(QLabel("高度："), 0, 3)
        self.edit_win_height = QLineEdit()
        self.edit_win_height.setFixedWidth(90)
        self.edit_win_height.setMaxLength(5)
        self.edit_win_height.setAlignment(Qt.AlignCenter)
        win_size_layout.addWidget(self.edit_win_height, 0, 4)
        win_size_layout.addWidget(QLabel("px"), 0, 5)

        self.cb_lock_aspect = QCheckBox("🔒 锁定纵横比")
        win_size_layout.addWidget(self.cb_lock_aspect, 1, 0, 1, 3)
        self.lbl_ratio = QLabel("纵横比未锁定")
        self.lbl_ratio.setStyleSheet("color: #666; font-size: 11px;")
        win_size_layout.addWidget(self.lbl_ratio, 1, 3, 1, 3)

        self.lbl_win_size_error = QLabel("")
        self.lbl_win_size_error.setStyleSheet("color: #d93025; font-size: 11px;")
        win_size_layout.addWidget(self.lbl_win_size_error, 2, 0, 1, 6)

        main_layout.addWidget(win_size_box)

        # 3. 字体组
        font_box = QGroupBox("3. 字体设置")
        font_layout = QGridLayout(font_box)
        font_layout.addWidget(QLabel("字体："), 0, 0)
        self.combo_font = QComboBox()
        font_layout.addWidget(self.combo_font, 0, 1, 1, 3)
        font_layout.addWidget(QLabel("字号(px)："), 1, 0)
        self.edit_font_size = QLineEdit()
        self.edit_font_size.setFixedWidth(80)
        font_layout.addWidget(self.edit_font_size, 1, 1)
        self.cb_bold = QCheckBox("加粗")
        self.cb_italic = QCheckBox("斜体")
        self.cb_underline = QCheckBox("下划线")
        font_layout.addWidget(self.cb_bold, 1, 2)
        font_layout.addWidget(self.cb_italic, 1, 3)
        font_layout.addWidget(self.cb_underline, 2, 1)
        # 填充系统字体
        fonts = sorted(set(QFontDatabase.families()))
        self.combo_font.addItems(fonts)
        main_layout.addWidget(font_box)

        # 4/5/6/7. 颜色&边框组
        color_box = QGroupBox("4~7. 颜色与边框")
        color_layout = QGridLayout(color_box)
        color_layout.setHorizontalSpacing(16)
        color_layout.setVerticalSpacing(12)

        color_layout.addWidget(QLabel("4. 文字颜色："), 0, 0)
        self.btn_fg = ColorPickerButton("#FFFFFF", support_alpha=False)
        color_layout.addWidget(self.btn_fg, 0, 1)

        color_layout.addWidget(QLabel("5. 背景颜色："), 0, 2)
        self.btn_bg = ColorPickerButton("#00000000", support_alpha=True)
        color_layout.addWidget(self.btn_bg, 0, 3)

        color_layout.addWidget(QLabel("6. 边框宽度(px)："), 1, 0)
        self.edit_border_width = QLineEdit()
        self.edit_border_width.setFixedWidth(80)
        color_layout.addWidget(self.edit_border_width, 1, 1)

        color_layout.addWidget(QLabel("7. 边框颜色："), 1, 2)
        self.btn_border = ColorPickerButton("#b9b9b94a", support_alpha=True)
        color_layout.addWidget(self.btn_border, 1, 3)

        self.lbl_color_error = QLabel("")
        self.lbl_color_error.setStyleSheet("color: #d93025; font-size: 11px;")
        color_layout.addWidget(self.lbl_color_error, 2, 0, 1, 4)

        main_layout.addWidget(color_box)

        # 底部：Apply/应用 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        self.btn_apply = QPushButton("确定")
        self.btn_apply.setMinimumWidth(160)
        self.btn_apply.setMinimumHeight(36)
        self.btn_apply.setStyleSheet(
            "QPushButton { background: #1a73e8; color: white; border-radius: 6px; padding: 6px 16px; font-weight: bold; }"
            "QPushButton:hover:!disabled { background: #1557b0; }"
            "QPushButton:disabled { background: #c5c5c5; color: #888; }"
        )
        btn_layout.addWidget(self.btn_apply)
        btn_cancel = QPushButton("取消")
        btn_cancel.setMinimumHeight(36)
        btn_cancel.setStyleSheet(
            "QPushButton { background: #A8A8B5; color: white; border-radius: 6px; padding: 6px 16px; font-weight: bold; }"
            "QPushButton:hover:!disabled { background: #7D7F8A; }"
            "QPushButton:disabled { background: #c5c5c5; color: #888; }"
        )
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        main_layout.addLayout(btn_layout)

    def _connect_signals(self):
        # 大小滑块 & 文本框联动
        self.slider_scale.valueChanged.connect(self._on_slider_scale_changed)
        self.edit_scale.textChanged.connect(self._on_edit_scale_changed)
        # 颜色按钮：改变时重校验
        self.btn_fg.color_changed.connect(lambda _: self._validate_all())
        self.btn_bg.color_changed.connect(lambda _: self._validate_all())
        self.btn_border.color_changed.connect(lambda _: self._validate_all())
        # 文本框校验
        self.edit_font_size.textChanged.connect(self._validate_all)
        self.edit_border_width.textChanged.connect(self._validate_all)
        # 悬浮窗大小：纵横比绑定（textEdited 仅在用户手动编辑时触发，避免程序设值时递归）
        self.cb_lock_aspect.toggled.connect(self._on_lock_aspect_toggled)
        self.edit_win_width.textEdited.connect(self._on_win_width_edited)
        self.edit_win_height.textEdited.connect(self._on_win_height_edited)
        self.edit_win_width.textChanged.connect(lambda _: self._validate_all())
        self.edit_win_height.textChanged.connect(lambda _: self._validate_all())
        # 根据已加载的锁定状态初始化纵横比
        if self.cb_lock_aspect.isChecked():
            self._capture_aspect_ratio()
        self._update_ratio_label()
        # Apply按钮
        self.btn_apply.clicked.connect(self._on_apply_clicked)

    # ---------------------- 加载/保存 ----------------------
    def _load_from_config(self):
        cfg = self._config.get_config()

        display = cfg["display"]
        self.cb_hr.setChecked(display.get("show_heart_rate", True))
        self.cb_stress.setChecked(display.get("show_stress_index", False))
        self.cb_icon.setChecked(display.get("show_heart_icon", False))

        self.slider_scale.setValue(cfg["scale"])
        self.edit_scale.setText(str(cfg["scale"]))

        ws = cfg.get("window_size", {})
        self.edit_win_width.setText(str(ws.get("width", 240)))
        self.edit_win_height.setText(str(ws.get("height", 90)))
        self.cb_lock_aspect.setChecked(bool(ws.get("lock_aspect_ratio", False)))

        font = cfg["font"]
        # 字体：如果系统没有这个字体则退化为默认值
        idx = self.combo_font.findText(font.get("family", "Microsoft Yahei UI"))
        if idx < 0:
            idx = self.combo_font.findText("Microsoft Yahei UI")
            if idx < 0 and self.combo_font.count() > 0:
                idx = 0
        self.combo_font.setCurrentIndex(max(0, idx))
        self.edit_font_size.setText(str(font.get("size", 16)))
        self.cb_bold.setChecked(font.get("bold", False))
        self.cb_italic.setChecked(font.get("italic", False))
        self.cb_underline.setChecked(font.get("underline", False))

        self.btn_fg.set_color(parse_color(cfg.get("foreground_color", "#FFFFFF")))
        self.btn_bg.set_color(parse_color(cfg.get("background_color", "#00000000")))
        self.edit_border_width.setText(str(cfg.get("border_width", 0)))
        self.btn_border.set_color(parse_color(cfg.get("border_color", "#b9b9b94a")))

    # ---------------------- 控件联动 ----------------------
    def _on_slider_scale_changed(self, value: int):
        self.edit_scale.blockSignals(True)
        self.edit_scale.setText(str(value))
        self.edit_scale.blockSignals(False)
        self._validate_all()

    def _on_edit_scale_changed(self, text: str):
        value, valid, msg = self._parse_int_in_range(text, SCALE_MIN, SCALE_MAX)
        if valid:
            self.slider_scale.blockSignals(True)
            self.slider_scale.setValue(value)
            self.slider_scale.blockSignals(False)
        self._validate_all()

    # ---------------------- 悬浮窗大小 & 纵横比绑定 ----------------------
    @staticmethod
    def _try_parse_pos_int(text: str):
        """尝试解析正整数，失败返回 None"""
        s = text.strip()
        if re.fullmatch(r"\d+", s):
            return int(s)
        return None

    def _capture_aspect_ratio(self):
        """从当前宽高输入框捕获纵横比"""
        w = self._try_parse_pos_int(self.edit_win_width.text())
        h = self._try_parse_pos_int(self.edit_win_height.text())
        if w is not None and h is not None and w > 0 and h > 0:
            self._aspect_ratio = w / h
        else:
            self._aspect_ratio = 240 / 90  # 默认 8:3

    def _on_lock_aspect_toggled(self, checked: bool):
        """锁定/解锁纵横比"""
        if checked:
            self._capture_aspect_ratio()
        else:
            self._aspect_ratio = None
        self._update_ratio_label()
        self._validate_all()

    def _on_win_width_edited(self, text: str):
        """用户编辑宽度时，若已锁定纵横比则同步更新高度"""
        if self._aspect_ratio is not None and self._aspect_ratio > 0:
            v = self._try_parse_pos_int(text)
            if v is not None and v > 0:
                new_h = max(WIN_HEIGHT_MIN, round(v / self._aspect_ratio))
                self.edit_win_height.blockSignals(True)
                self.edit_win_height.setText(str(new_h))
                self.edit_win_height.blockSignals(False)
        self._validate_all()

    def _on_win_height_edited(self, text: str):
        """用户编辑高度时，若已锁定纵横比则同步更新宽度"""
        if self._aspect_ratio is not None and self._aspect_ratio > 0:
            v = self._try_parse_pos_int(text)
            if v is not None and v > 0:
                new_w = max(WIN_WIDTH_MIN, round(v * self._aspect_ratio))
                self.edit_win_width.blockSignals(True)
                self.edit_win_width.setText(str(new_w))
                self.edit_win_width.blockSignals(False)
        self._validate_all()

    def _update_ratio_label(self):
        """更新纵横比状态标签"""
        if self._aspect_ratio is not None and self._aspect_ratio > 0:
            self.lbl_ratio.setText(f"已锁定 ≈ {self._format_ratio(self._aspect_ratio)}")
            self.lbl_ratio.setStyleSheet("color: #1a73e8; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_ratio.setText("纵横比未锁定（宽高可独立调整）")
            self.lbl_ratio.setStyleSheet("color: #666; font-size: 11px;")

    @staticmethod
    def _format_ratio(ratio: float) -> str:
        """将小数纵横比近似为易读的整数比（如 8:3、16:9）"""
        for denom in range(1, 100):
            numer = round(ratio * denom)
            if numer > 0 and abs(numer / denom - ratio) < 0.01:
                return f"{numer}:{denom}"
        return f"{ratio:.2f}:1"

    # ---------------------- 校验 ----------------------
    @staticmethod
    def _parse_int_in_range(text: str, lo: int, hi: int) -> Tuple[Optional[int], bool, str]:
        s = text.strip()
        if not s:
            return None, False, "请输入一个整数"
        if not re.fullmatch(r"[+-]?\d+", s):
            return None, False, "必须是整数，不能包含字母或小数"
        v = int(s)
        if v < lo or v > hi:
            return v, False, f"数值必须在 {lo}~{hi} 之间"
        return v, True, ""

    @staticmethod
    def _parse_nonneg_int(text: str) -> Tuple[Optional[int], bool, str]:
        s = text.strip()
        if not s:
            return None, False, "请输入一个非负整数"
        if not re.fullmatch(r"\d+", s):
            return None, False, "必须是整数，不能包含字母、负数或小数"
        return int(s), True, ""

    def _validate_all(self) -> bool:
        errors = []

        # 倍率校验
        _, ok, msg = self._parse_int_in_range(self.edit_scale.text(), SCALE_MIN, SCALE_MAX)
        if not ok:
            errors.append(("scale", f"[倍率] {msg}"))
            self._set_widget_error_style(self.edit_scale, True)
            self._set_widget_error_style(self.slider_scale, True)
            self.lbl_scale_error.setText(msg)
        else:
            self._set_widget_error_style(self.edit_scale, False)
            self._set_widget_error_style(self.slider_scale, False)
            self.lbl_scale_error.setText("")

        # 字号
        _, ok, msg = self._parse_nonneg_int(self.edit_font_size.text())
        if not ok:
            errors.append(("font_size", f"[字号] {msg}"))
            self._set_widget_error_style(self.edit_font_size, True)
        elif int(self.edit_font_size.text().strip()) <= 0 or int(self.edit_font_size.text().strip()) > 200:
            errors.append(("font_size", "[字号] 建议范围 1~200"))
            self._set_widget_error_style(self.edit_font_size, True)
        else:
            self._set_widget_error_style(self.edit_font_size, False)

        # 边框宽度
        _, ok, msg = self._parse_nonneg_int(self.edit_border_width.text())
        if not ok:
            errors.append(("border", f"[边框宽度] {msg}"))
            self._set_widget_error_style(self.edit_border_width, True)
        elif int(self.edit_border_width.text().strip()) > 50:
            errors.append(("border", "[边框宽度] 建议范围 0~50"))
            self._set_widget_error_style(self.edit_border_width, True)
        else:
            self._set_widget_error_style(self.edit_border_width, False)

        # 悬浮窗宽度
        _, ok, msg = self._parse_int_in_range(self.edit_win_width.text(), WIN_WIDTH_MIN, WIN_WIDTH_MAX)
        if not ok:
            errors.append(("win_width", f"[窗口宽度] {msg}"))
            self._set_widget_error_style(self.edit_win_width, True)
        else:
            self._set_widget_error_style(self.edit_win_width, False)

        # 悬浮窗高度
        _, ok, msg = self._parse_int_in_range(self.edit_win_height.text(), WIN_HEIGHT_MIN, WIN_HEIGHT_MAX)
        if not ok:
            errors.append(("win_height", f"[窗口高度] {msg}"))
            self._set_widget_error_style(self.edit_win_height, True)
        else:
            self._set_widget_error_style(self.edit_win_height, False)

        # 汇总错误信息
        self.lbl_color_error.setText("； ".join(e[1] for e in errors if e[0] not in ("win_width", "win_height")))
        win_errs = [e[1] for e in errors if e[0] in ("win_width", "win_height")]
        self.lbl_win_size_error.setText("； ".join(win_errs))

        # Apply按钮
        ok_total = len(errors) == 0
        self.btn_apply.setEnabled(ok_total)

        # 窗口背景变红提示
        if not ok_total:
            self.setStyleSheet(
                "QDialog { background-color: #fff3f3; }"
                "QGroupBox { background-color: transparent; border: 1px solid #f4c7c7; border-radius: 6px; margin-top: 12px; padding: 10px; }"
                "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #8a1a1a; }"
            )
        else:
            self.setStyleSheet(
                "QDialog { background-color: #ffffff; }"
                "QGroupBox { background-color: transparent; border: 1px solid #d0d0d0; border-radius: 6px; margin-top: 12px; padding: 10px; }"
                "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #444; }"
            )

        return ok_total

    @staticmethod
    def _set_widget_error_style(widget, is_error: bool):
        if isinstance(widget, QLineEdit):
            if is_error:
                widget.setStyleSheet(
                    "QLineEdit { border: 2px solid #d93025; border-radius: 4px; padding: 2px 6px; background: #fff5f5; }"
                )
            else:
                widget.setStyleSheet(
                    "QLineEdit { border: 1px solid #bbb; border-radius: 4px; padding: 2px 6px; }"
                )
        elif isinstance(widget, QSlider):
            if is_error:
                widget.setStyleSheet(
                    "QSlider::groove:horizontal { border: 1px solid #d93025; height: 6px; background: #fff5f5; border-radius: 3px; }"
                    "QSlider::handle:horizontal { background: #d93025; border: 1px solid #b71c1c; width: 14px; margin: -6px 0; border-radius: 7px; }"
                )
            else:
                widget.setStyleSheet("")

    # ---------------------- 应用 ----------------------
    def _collect_config(self) -> Dict:
        scale_val, _, _ = self._parse_int_in_range(self.edit_scale.text(), SCALE_MIN, SCALE_MAX)
        font_size_val, _, _ = self._parse_nonneg_int(self.edit_font_size.text())
        border_w_val, _, _ = self._parse_nonneg_int(self.edit_border_width.text())
        win_w_val, _, _ = self._parse_int_in_range(self.edit_win_width.text(), WIN_WIDTH_MIN, WIN_WIDTH_MAX)
        win_h_val, _, _ = self._parse_int_in_range(self.edit_win_height.text(), WIN_HEIGHT_MIN, WIN_HEIGHT_MAX)

        return {
            "display": {
                "show_heart_rate": self.cb_hr.isChecked(),
                "show_stress_index": self.cb_stress.isChecked(),
                "show_heart_icon": self.cb_icon.isChecked(),
            },
            "scale": int(scale_val) if scale_val is not None else 100,
            "window_size": {
                "width": int(win_w_val) if win_w_val is not None else 240,
                "height": int(win_h_val) if win_h_val is not None else 90,
                "lock_aspect_ratio": self.cb_lock_aspect.isChecked(),
            },
            "font": {
                "family": self.combo_font.currentText() or "Microsoft Yahei UI",
                "size": int(font_size_val) if font_size_val is not None else 16,
                "bold": self.cb_bold.isChecked(),
                "italic": self.cb_italic.isChecked(),
                "underline": self.cb_underline.isChecked(),
            },
            "foreground_color": _color_to_hex_with_alpha(self.btn_fg.color()),
            "background_color": _color_to_hex_with_alpha(self.btn_bg.color()),
            "border_width": int(border_w_val) if border_w_val is not None else 0,
            "border_color": _color_to_hex_with_alpha(self.btn_border.color()),
        }

    def _on_apply_clicked(self):
        if not self._validate_all():
            QMessageBox.warning(self, "配置校验失败", "请先修正红色标记的错误项。")
            return
        new_cfg = self._collect_config()
        self._config.update_config(new_cfg)
        self.config_applied.emit(new_cfg)
        self.accept()
