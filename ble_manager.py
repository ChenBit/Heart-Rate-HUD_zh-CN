import asyncio
import struct
from dataclasses import dataclass
from typing import Callable, List, Optional, Dict, Any

from PySide6.QtCore import QObject, QThread, Signal, Slot, QTimer

try:
    from bleak import BleakScanner, BleakClient, exc as bleak_exc
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False


HEART_RATE_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HEART_RATE_MEASUREMENT_CHAR = "00002a37-0000-1000-8000-00805f9b34fb"


@dataclass
class BLEDevice:
    name: str
    address: str

    def __str__(self):
        return f"{self.name} ({self.address})" if self.name else self.address


def parse_heart_rate_measurement(data: bytes) -> Optional[int]:
    """解析心率测量特征值，返回心率BPM或None"""
    if not data or len(data) < 2:
        return None
    flags = data[0]
    format_uint16 = flags & 0x01
    if format_uint16:
        if len(data) < 3:
            return None
        return struct.unpack("<H", data[1:3])[0]
    else:
        return data[1]


class BLEWorker(QObject):
    """BLE后台工作线程，负责所有BLE异步操作"""

    devices_found = Signal(list)
    heart_rate_received = Signal(int)
    connection_state_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._client: Optional[BleakClient] = None
        self._current_device: Optional[BLEDevice] = None
        self._scanning = False

    @Slot()
    def start_event_loop(self):
        """启动事件循环"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    @Slot(str, str)
    def search_devices(self, timeout: str = "10"):
        """搜索BLE设备"""
        if not BLEAK_AVAILABLE:
            self.error_occurred.emit("bleak库未安装，请先运行 pip install bleak")
            return
        if self._loop is None:
            self.error_occurred.emit("事件循环未启动")
            return
        if self._scanning:
            return
        self._scanning = True
        timeout_val = int(timeout) if timeout.isdigit() else 10
        asyncio.run_coroutine_threadsafe(self._do_scan(timeout_val), self._loop)

    async def _do_scan(self, timeout: int):
        try:
            self.connection_state_changed.emit("正在搜寻...")
            devices = await BleakScanner.discover(timeout=timeout)
            result: List[BLEDevice] = []
            for d in devices:
                name = d.name or "未知设备"
                result.append(BLEDevice(name=name, address=d.address))
            self.devices_found.emit(result)
            self.connection_state_changed.emit("搜索完成")
        except Exception as e:
            self.error_occurred.emit(f"搜索失败: {str(e)}")
            self.connection_state_changed.emit("搜索失败")
        finally:
            self._scanning = False

    @Slot(str, str)
    def connect_device(self, name: str, address: str):
        """连接到指定BLE设备"""
        if not BLEAK_AVAILABLE:
            self.error_occurred.emit("bleak库未安装")
            return
        if self._loop is None:
            self.error_occurred.emit("事件循环未启动")
            return
        self._current_device = BLEDevice(name=name, address=address)
        asyncio.run_coroutine_threadsafe(self._do_connect(address), self._loop)

    async def _do_connect(self, address: str):
        try:
            self.connection_state_changed.emit("正在连接...")

            def disconnected_handler(client):
                self.connection_state_changed.emit("已断开连接")
                self._client = None

            self._client = BleakClient(address, disconnected_callback=disconnected_handler)
            await self._client.connect()

            if not self._client.is_connected:
                raise ConnectionError("无法建立连接")

            # 检查是否有心率服务
            services = self._client.services
            has_hr_service = any(str(s.uuid).lower() == HEART_RATE_SERVICE_UUID.lower() for s in services)
            if not has_hr_service:
                await self._client.disconnect()
                self._client = None
                self.connection_state_changed.emit("该设备不支持心率检测")
                return

            def hr_handler(sender, data):
                hr = parse_heart_rate_measurement(data)
                if hr is not None:
                    self.heart_rate_received.emit(hr)

            await self._client.start_notify(HEART_RATE_MEASUREMENT_CHAR, hr_handler)
            self.connection_state_changed.emit("已连接")
        except Exception as e:
            self.error_occurred.emit(f"连接失败: {str(e)}")
            self.connection_state_changed.emit("连接失败")
            self._client = None

    @Slot()
    def disconnect_device(self):
        """断开当前设备连接"""
        if self._loop is None or self._client is None:
            return
        asyncio.run_coroutine_threadsafe(self._do_disconnect(), self._loop)

    async def _do_disconnect(self):
        try:
            if self._client is not None and self._client.is_connected:
                try:
                    await self._client.stop_notify(HEART_RATE_MEASUREMENT_CHAR)
                except Exception:
                    pass
                await self._client.disconnect()
        except Exception:
            pass
        finally:
            self._client = None

    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    @property
    def current_device(self) -> Optional[BLEDevice]:
        return self._current_device


class BLEManager(QObject):
    """BLE管理器，提供简化的API给UI层使用"""

    devices_found = Signal(list)
    heart_rate_received = Signal(int)
    connection_state_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self._thread = QThread()
        self._worker = BLEWorker()
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.start_event_loop)

        self._worker.devices_found.connect(self.devices_found)
        self._worker.heart_rate_received.connect(self.heart_rate_received)
        self._worker.connection_state_changed.connect(self.connection_state_changed)
        self._worker.error_occurred.connect(self.error_occurred)

        self._thread.start()

    def search_devices(self, timeout: int = 10):
        """搜索设备"""
        QTimer.singleShot(0, lambda: self._worker.search_devices(str(timeout)))

    def connect_device(self, name: str, address: str):
        """连接设备"""
        QTimer.singleShot(0, lambda: self._worker.connect_device(name, address))

    def disconnect_device(self):
        """断开设备"""
        QTimer.singleShot(0, self._worker.disconnect_device)

    def is_connected(self) -> bool:
        return self._worker.is_connected()

    @property
    def current_device(self) -> Optional[BLEDevice]:
        return self._worker.current_device

    def cleanup(self):
        """清理资源"""
        try:
            self._worker.disconnect_device()
        except Exception:
            pass
        try:
            if self._worker._loop:
                self._worker._loop.call_soon_threadsafe(self._worker._loop.stop)
        except Exception:
            pass
        self._thread.quit()
        self._thread.wait(2000)
