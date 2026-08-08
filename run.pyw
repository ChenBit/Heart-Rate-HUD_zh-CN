"""
心率抬头显示 - 无控制台启动器

说明：
- .pyw 文件在 Windows 上由 pythonw.exe 解释执行，启动时不会出现命令行窗口。
- 双击本文件即可静默启动程序；如需查看日志，请查阅同目录下的 debug.log。
- 若依赖缺失，将以 Windows 消息框形式提示用户。
"""
import sys
import os
import traceback


def _show_error_box(title: str, message: str):
    """在无控制台环境下，用 Windows 消息框提示错误"""
    try:
        import ctypes
        # MB_OK | MB_ICONERROR = 0x10
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    except Exception:
        # 兜底：写文件
        try:
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n[{title}]\n{message}\n")
        except Exception:
            pass


def main():
    # 将本文件所在目录加入 import 搜索路径，确保能找到同目录模块
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    try:
        import main as main_module
    except ImportError as e:
        _show_error_box(
            "依赖缺失",
            "启动失败：缺少必要的 Python 依赖。\n\n"
            f"错误：{e}\n\n"
            "请在命令行中执行：\n"
            "    pip install -r requirements.txt\n\n"
            "然后再双击 run.pyw 启动。",
        )
        return 1
    except Exception:
        _show_error_box("启动异常", traceback.format_exc())
        return 1

    try:
        return main_module.main()
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0
    except Exception:
        _show_error_box("运行时异常", traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
