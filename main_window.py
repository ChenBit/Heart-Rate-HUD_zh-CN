from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QSystemTrayIcon, QMenu,
    QApplication, QStatusBar
)

from config_manager import ConfigManager
from ble_manager import BLEManager, BLEDevice
from stress_calculator import StressCalculator
from hud_window import HUDWindow
from settings_window import SettingsWindow
from heart_path import make_heart_path


def make_app_icon(size: int = 64) -> QIcon:
    """生成一个心形图标作为托盘/窗口图标"""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)
    # 心形居中绘制，外接框留约 10% 边距
    painter.translate(size / 2, size / 2)
    path = make_heart_path(size * 0.8)
    painter.fillPath(path, QBrush(QColor("#e53935")))
    painter.end()
    return QIcon(pix)


class DeviceControlWindow(QMainWindow):
    """设备管理主窗口（搜索、连接、断开、打开设置）"""

    request_quit = Signal()

    def __init__(self, config: ConfigManager, ble: BLEManager, stress: StressCalculator, hud: HUDWindow):
        super().__init__()
        self._config = config
        self._ble = ble
        self._stress = stress
        self._hud = hud
        self._settings_window: Optional[SettingsWindow] = None

        # 自动重连
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._try_reconnect)

        self._build_ui()
        self._setup_tray()
        self._connect_signals()

        # 启动后若有上次设备，提示自动连接（稍后再连，等BLE线程就绪）
        QTimer.singleShot(1500, self._auto_connect_last_device)

    def _build_ui(self):
        self.setWindowTitle("心率抬头显示")
        self.setWindowIcon(make_app_icon(64))
        self.setMinimumSize(520, 480)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 顶部按钮行
        top_row = QHBoxLayout()
        self.btn_search = QPushButton("🔍 搜索设备")
        self.btn_search.setMinimumHeight(36)
        self.btn_connect = QPushButton("🔗 连接")
        self.btn_connect.setMinimumHeight(36)
        self.btn_connect.setEnabled(False)
        self.btn_disconnect = QPushButton("⏏ 断开")
        self.btn_disconnect.setMinimumHeight(36)
        self.btn_disconnect.setEnabled(False)
        self.btn_settings = QPushButton("⚙ 显示设置")
        self.btn_settings.setMinimumHeight(36)

        top_row.addWidget(self.btn_search)
        top_row.addWidget(self.btn_connect)
        top_row.addWidget(self.btn_disconnect)
        top_row.addStretch(1)
        top_row.addWidget(self.btn_settings)
        main_layout.addLayout(top_row)

        # 状态标签
        self.lbl_status = QLabel("状态：未连接")
        self.lbl_status.setStyleSheet("font-size: 14px; padding: 6px 10px; background: #f5f5f5; border-radius: 4px;")
        main_layout.addWidget(self.lbl_status)

        # 设备列表
        list_label = QLabel("附近设备：")
        main_layout.addWidget(list_label)
        self.list_devices = QListWidget()
        self.list_devices.setStyleSheet(
            "QListWidget { border: 1px solid #ccc; border-radius: 4px; padding: 4px; }"
            "QListWidget::item { padding: 6px; }"
            "QListWidget::item:selected { background: #1a73e8; color: white; }"
        )
        main_layout.addWidget(self.list_devices, 1)

        # 底部数据显示
        data_box = QHBoxLayout()
        self.lbl_hr = QLabel("心率：-- BPM")
        self.lbl_stress = QLabel("压力：--")
        self.lbl_hr.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.lbl_stress.setStyleSheet("font-size: 16px; font-weight: bold; color: #e65100;")
        data_box.addWidget(self.lbl_hr)
        data_box.addStretch(1)
        data_box.addWidget(self.lbl_stress)
        main_layout.addLayout(data_box)

        # 状态栏
        sb = QStatusBar()
        self.setStatusBar(sb)
        sb.showMessage("提示：点击搜索，选中设备后点击连接；悬浮窗可自由拖拽。")

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(make_app_icon(64))
        self._tray.setToolTip("心率抬头显示")

        menu = QMenu()
        act_show_hide = QAction("显示/隐藏 悬浮窗", self)
        act_show_hide.triggered.connect(self._toggle_hud_visible)
        act_settings = QAction("打开 显示设置", self)
        act_settings.triggered.connect(self._open_settings)
        act_control = QAction("打开 设备管理窗口", self)
        act_control.triggered.connect(self._show_normal)
        menu.addSeparator()
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(self._on_quit)
        menu.addAction(act_show_hide)
        menu.addAction(act_control)
        menu.addAction(act_settings)
        menu.addSeparator()
        menu.addAction(act_quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _connect_signals(self):
        self.btn_search.clicked.connect(self._on_search_clicked)
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        self.btn_disconnect.clicked.connect(self._on_disconnect_clicked)
        self.btn_settings.clicked.connect(self._open_settings)
        self.list_devices.itemSelectionChanged.connect(self._update_connect_enabled)
        self.list_devices.itemDoubleClicked.connect(lambda _: self._on_connect_clicked())

        self._ble.devices_found.connect(self._on_devices_found)
        self._ble.heart_rate_received.connect(self._on_heart_rate)
        self._ble.connection_state_changed.connect(self._on_connection_state)
        self._ble.error_occurred.connect(self._on_ble_error)

    # ---------------------- 托盘交互 ----------------------
    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self._show_normal()

    def _toggle_hud_visible(self):
        if self._hud.isVisible():
            self._hud.hide()
        else:
            self._hud.show()

    def _show_normal(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # ---------------------- 按钮逻辑 ----------------------
    def _on_search_clicked(self):
        self.list_devices.clear()
        self.lbl_status.setText("状态：正在搜寻...")
        self.btn_search.setEnabled(False)
        self._ble.search_devices(timeout=10)

    def _on_devices_found(self, devices: List[BLEDevice]):
        self.list_devices.clear()
        self.btn_search.setEnabled(True)
        if not devices:
            self.lbl_status.setText("状态：未发现设备，请确保设备处于可发现状态")
            return
        for d in devices:
            item = QListWidgetItem(f"{d.name}  —  {d.address}")
            item.setData(Qt.UserRole, (d.name, d.address))
            self.list_devices.addItem(item)
        self.lbl_status.setText(f"状态：发现 {len(devices)} 个设备，选择一个后点击连接")
        self._update_connect_enabled()

    def _update_connect_enabled(self):
        self.btn_connect.setEnabled(len(self.list_devices.selectedItems()) > 0)

    def _on_connect_clicked(self):
        items = self.list_devices.selectedItems()
        if not items:
            return
        name, address = items[0].data(Qt.UserRole)
        # 记住设备
        self._config.last_device = {"name": name, "address": address}
        self._ble.connect_device(name, address)

    def _on_disconnect_clicked(self):
        self._ble.disconnect_device()

    def _open_settings(self):
        if self._settings_window is None:
            self._settings_window = SettingsWindow(self._config, self)
            self._settings_window.config_applied.connect(self._on_config_applied)
            self._settings_window.finished.connect(lambda _: self._clear_settings_window())
        if self._settings_window.isVisible():
            self._settings_window.raise_()
            self._settings_window.activateWindow()
        else:
            self._settings_window.show()

    def _clear_settings_window(self):
        self._settings_window = None

    def _on_config_applied(self, new_cfg: dict):
        self._hud.apply_config()

    # ---------------------- BLE信号 ----------------------
    def _on_heart_rate(self, hr: int):
        stress = self._stress.add_heart_rate(hr)
        self.lbl_hr.setText(f"心率：{hr} BPM")
        self.lbl_stress.setText(f"压力：{stress}")
        self._hud.set_heart_rate(hr)
        self._hud.set_stress_index(stress)
        # 已连接，重置自动重连计数
        self._reconnect_attempts = 0
        self._reconnect_timer.stop()

    def _on_connection_state(self, state: str):
        self.lbl_status.setText(f"状态：{state}")
        self._hud.set_connection_status(state)
        if state == "已连接":
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self.btn_search.setEnabled(True)
        elif state in ("已断开连接", "连接失败", "该设备不支持心率检测"):
            self.btn_disconnect.setEnabled(False)
            self.btn_connect.setEnabled(len(self.list_devices.selectedItems()) > 0)
            self.btn_search.setEnabled(True)
            # 断开后清空显示
            if state == "已断开连接":
                self._hud.set_heart_rate(None)
                self._hud.set_stress_index(None)
                self.lbl_hr.setText("心率：-- BPM")
                self.lbl_stress.setText("压力：--")
                # 启动自动重连逻辑
                self._schedule_reconnect()
        elif "搜寻" in state or "搜索" in state:
            pass
        else:
            # 正在连接
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(False)

    def _schedule_reconnect(self):
        last_dev = self._config.last_device
        if not last_dev.get("address"):
            return
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            self.lbl_status.setText("状态：已断开连接（多次重试失败，请手动连接）")
            return
        wait_ms = 3000 + self._reconnect_attempts * 2000
        self.lbl_status.setText(f"状态：连接丢失，正在重试...（{self._reconnect_attempts + 1}/{self._max_reconnect_attempts}）")
        self._hud.set_connection_status("正在重试...")
        self._reconnect_timer.start(wait_ms)

    def _try_reconnect(self):
        last_dev = self._config.last_device
        if not last_dev.get("address"):
            return
        self._reconnect_attempts += 1
        self._ble.connect_device(last_dev.get("name", ""), last_dev["address"])

    def _auto_connect_last_device(self):
        last_dev = self._config.last_device
        if not last_dev.get("address"):
            return
        self.lbl_status.setText(f"状态：尝试连接上次设备 {last_dev.get('name', '')} ...")
        self._ble.connect_device(last_dev.get("name", ""), last_dev["address"])

    def _on_ble_error(self, msg: str):
        QMessageBox.warning(self, "蓝牙错误", msg)

    # ---------------------- 关闭 ----------------------
    def closeEvent(self, event):
        """关闭主窗口时隐藏到托盘而不是退出"""
        if self._tray.isVisible():
            self.hide()
            event.ignore()
        else:
            self._on_quit()
            event.accept()

    def _on_quit(self):
        try:
            self._reconnect_timer.stop()
            self._ble.disconnect_device()
        except Exception:
            pass
        try:
            self._ble.cleanup()
        except Exception:
            pass
        self._tray.hide()
        QApplication.instance().quit()
