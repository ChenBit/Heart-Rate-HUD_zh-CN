"""
心率抬头显示插件 - 启动入口

功能：
- 通过BLE连接心率设备（手环/胸带等）
- 悬浮窗置顶显示心率与压力指数
- 自定义显示样式（大小/字体/颜色/边框等）
"""
import sys
import os


def hide_console_window():
    """
    在Windows上隐藏命令行控制台窗口。
    若程序由 python.exe 启动（带控制台），则立即隐藏该窗口；
    若由 pythonw.exe 启动（无控制台），则本函数无副作用。
    必须在任何GUI创建之前、尽早调用以减少窗口闪现。
    """
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        # kernel32.GetConsoleWindow() 返回当前进程关联的控制台窗口句柄，无控制台时返回 0
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            # SW_HIDE = 0
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        # 隐藏失败不应影响程序启动
        pass


def ensure_qt_env():
    """在Windows上尝试绕过Qt缩放比例等常见问题"""
    if sys.platform.startswith("win"):
        # 强制高DPI缩放
        try:
            os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
            os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
        except Exception:
            pass


def main():
    hide_console_window()
    ensure_qt_env()

    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import Qt

    app = QApplication(sys.argv)
    app.setApplicationName("心率抬头显示")
    app.setOrganizationName("HeartRateHUD")
    app.setQuitOnLastWindowClosed(False)  # 关闭主窗口不退出，保留托盘

    from config_manager import ConfigManager
    from ble_manager import BLEManager
    from stress_calculator import StressCalculator
    from hud_window import HUDWindow
    from main_window import DeviceControlWindow, make_app_icon

    app.setWindowIcon(make_app_icon(64))

    # 初始化各模块
    config = ConfigManager()
    ble = BLEManager()
    stress = StressCalculator()
    hud = HUDWindow(config)
    main_win = DeviceControlWindow(config, ble, stress, hud)

    # 显示悬浮窗和主窗口
    hud.show()
    main_win.show()

    # 安全退出：捕获未处理异常
    def excepthook(exc_type, exc_value, exc_tb):
        import traceback
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug.log"), "a", encoding="utf-8") as f:
                f.write("\n==== UNHANDLED EXCEPTION ====\n")
                f.write(tb_text)
        except Exception:
            pass
        try:
            ble.cleanup()
        except Exception:
            pass
        QMessageBox.critical(None, "程序异常", f"发生未预期的错误：\n{tb_text[-500:]}")

    sys.excepthook = excepthook

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
