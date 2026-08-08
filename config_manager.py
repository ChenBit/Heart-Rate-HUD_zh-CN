import json
import os
from pathlib import Path
from copy import deepcopy


class ConfigManager:
    """配置管理器：负责读取、保存和管理用户配置"""

    DEFAULT_CONFIG = {
        # 显示内容选择
        "display": {
            "show_heart_rate": True,
            "show_stress_index": False,
            "show_heart_icon": False
        },
        # 显示大小倍率（50-500）
        "scale": 100,
        # 悬浮窗窗口尺寸（像素），与显示内容倍率相互独立
        "window_size": {
            "width": 240,
            "height": 90,
            "lock_aspect_ratio": False
        },
        # 字体设置
        "font": {
            "family": "Microsoft Yahei UI",
            "size": 16,
            "bold": False,
            "underline": False,
            "italic": False
        },
        # 颜色设置
        "foreground_color": "#FFFFFF",
        "background_color": "#00000001",
        # 边框设置
        "border_width": 0,
        "border_color": "#b9b9b94a",
        # 悬浮窗位置
        "window_position": {"x": 100, "y": 100},
        # BLE设备
        "last_device": {"name": "", "address": ""}
    }

    def __init__(self, config_path: str = None):
        if config_path is None:
            self.config_path = Path(os.path.expanduser("~")) / ".heart_rate_hud" / "config.json"
        else:
            self.config_path = Path(config_path)
        self._config = deepcopy(self.DEFAULT_CONFIG)
        self._ensure_config_dir()
        self.load_config()

    def _ensure_config_dir(self):
        """确保配置目录存在"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def load_config(self):
        """加载配置文件，若不存在或损坏则使用默认配置"""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._merge_config(data)
            except (json.JSONDecodeError, IOError, OSError):
                self._config = deepcopy(self.DEFAULT_CONFIG)
        else:
            self._config = deepcopy(self.DEFAULT_CONFIG)
            self.save_config()

    def _merge_config(self, data: dict):
        """合并配置，确保缺失的键使用默认值"""
        for key, default_value in self.DEFAULT_CONFIG.items():
            if key not in data:
                self._config[key] = deepcopy(default_value)
            else:
                if isinstance(default_value, dict) and isinstance(data[key], dict):
                    merged = deepcopy(default_value)
                    merged.update(data[key])
                    self._config[key] = merged
                else:
                    self._config[key] = data[key]

    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            return True
        except (IOError, OSError):
            return False

    def get_config(self) -> dict:
        """获取完整配置的深拷贝"""
        return deepcopy(self._config)

    def update_config(self, new_config: dict):
        """更新配置并保存"""
        for key, value in new_config.items():
            if key in self.DEFAULT_CONFIG:
                self._config[key] = deepcopy(value)
        return self.save_config()

    @property
    def display(self) -> dict:
        return deepcopy(self._config["display"])

    @display.setter
    def display(self, value: dict):
        self._config["display"].update(value)
        self.save_config()

    @property
    def scale(self) -> int:
        return self._config["scale"]

    @scale.setter
    def scale(self, value: int):
        self._config["scale"] = max(50, min(500, value))
        self.save_config()

    @property
    def window_size(self) -> dict:
        return deepcopy(self._config["window_size"])

    @window_size.setter
    def window_size(self, value: dict):
        self._config["window_size"].update(value)
        self.save_config()

    @property
    def font(self) -> dict:
        return deepcopy(self._config["font"])

    @font.setter
    def font(self, value: dict):
        self._config["font"].update(value)
        self.save_config()

    @property
    def foreground_color(self) -> str:
        return self._config["foreground_color"]

    @foreground_color.setter
    def foreground_color(self, value: str):
        self._config["foreground_color"] = value
        self.save_config()

    @property
    def background_color(self) -> str:
        return self._config["background_color"]

    @background_color.setter
    def background_color(self, value: str):
        self._config["background_color"] = value
        self.save_config()

    @property
    def border_width(self) -> int:
        return self._config["border_width"]

    @border_width.setter
    def border_width(self, value: int):
        self._config["border_width"] = max(0, value)
        self.save_config()

    @property
    def border_color(self) -> str:
        return self._config["border_color"]

    @border_color.setter
    def border_color(self, value: str):
        self._config["border_color"] = value
        self.save_config()

    @property
    def window_position(self) -> dict:
        return deepcopy(self._config["window_position"])

    @window_position.setter
    def window_position(self, value: dict):
        self._config["window_position"].update(value)
        self.save_config()

    @property
    def last_device(self) -> dict:
        return deepcopy(self._config["last_device"])

    @last_device.setter
    def last_device(self, value: dict):
        self._config["last_device"].update(value)
        self.save_config()
