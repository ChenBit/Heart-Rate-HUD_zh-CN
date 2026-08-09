# 心率抬头显示

一款轻量级 Windows 桌面应用，以浮动、始终置顶的覆盖层形式显示实时心率与压力指数。它可连接蓝牙低功耗（BLE）心率设备（如智能手环或胸带），并以紧凑的 HUD 窗口呈现数据，该窗口可随意拖拽至屏幕任意位置。
## 这里只有简体中文版的应用，如果你想访问已翻译成en_US的版本，请访问：
**Here is only the Simplified Chinese version of the app. If you would like to access the version translated into en_US, please visit:**

<a href="https://github.com/ChenBit/Heart-Rate-HUD/" target="_blank">Heart Rate HUD English Version</a>

注意：en-US区的应用版本更新可能会有延迟和跳过，作者是一名学生，无法及时更新请谅解~

Note: Updates for the en-US version of the project may be delayed or skipped. The author is a student and may not be able to update it in a timely manner. We appreciate your understanding.

## 功能特性

- BLE 设备扫描与连接管理
- 来自兼容心率监测仪的实时心率更新
- 基于近期心率数据的压力指数估算
- 始终置顶的浮动 HUD 窗口
- 拖拽移动覆盖层位置
- 可自定义显示内容、缩放比例、字体、颜色和边框
- 断连后自动重连上次使用的设备
- 系统托盘支持（显示/隐藏覆盖层、退出应用）
- 无控制台启动器，便于 Windows 下使用

## 适用场景

本项目适用于：

- 游戏、直播或工作时监测心率
- 保持最小化的抬头显示，无需离开当前应用
- 将 BLE 心率传感器作为个人健康指标使用

## 项目结构

- `main.py` — 应用引导与启动初始化
- `main_window.py` — 主设备控制窗口及系统托盘逻辑
- `ble_manager.py` — BLE 发现、连接与心率监测
- `hud_window.py` — 浮动覆盖层渲染与拖拽行为
- `settings_window.py` — 样式自定义设置面板
- `stress_calculator.py` — 本地压力估算逻辑
- `config_manager.py` — 配置保存/加载管理
- `run.pyw` — Windows 启动器，无可见控制台窗口
- `requirements.txt` — Python 依赖项

## 系统要求

- Windows 10 或更高版本
- Python 3.10+
- 支持标准心率服务的蓝牙低功耗心率设备

## 安装步骤

1. 克隆或下载本项目。
2. 确保蓝牙适配器已启用，且目标心率设备处于配对/发现模式。

## 运行应用

### 在 Windows 上双击启动器

```text
C2R.bat
```

## 使用方法

1. 启动应用。
2. 点击“搜索设备”。
3. 从列表中选择附近的 BLE 心率设备。
4. 点击“连接”。
5. HUD 窗口将开始显示当前心率。
6. 使用设置窗口自定义：
   - 显示哪些数值
   - 尺寸与缩放比例
   - 字体与文本样式
   - 文本、背景及边框颜色
   - HUD 窗口尺寸
7. 拖拽浮动窗口至屏幕上的合适位置。

## 设置与配置

应用将设置存储于用户主目录下的 JSON 文件中：

```text
~/.heart_rate_hud/config.json
```

包含以下内容：

- 显示开关
- HUD 缩放比例
- 窗口尺寸与宽高比
- 字体设置
- 前景/背景颜色
- 边框设置
- 上次连接的设备

## 蓝牙说明

应用使用 `bleak` 库，并期望符合标准 BLE 心率配置文件。

应用会检查标准心率服务 UUID：

```text
0000180d-0000-1000-8000-00805f9b34fb
```

以及心率测量特征值：

```text
00002a37-0000-1000-8000-00805f9b34fb
```

如果设备不支持心率服务，应用会报告该设备不兼容。

## 压力指数逻辑

压力值在本地设备上计算，无需将数据发送到远程服务器。

估算器结合了：

- 平均心率与静息基线的偏差
- 近期心率样本的变异性
- 对极高心率的额外加权

结果为 0 到 100 的整数，数值越高表示压力越大。

## 故障排除

### 未找到设备

- 确保蓝牙已启用。
- 确认设备已开机并正在广播。
- 将设备置于配对或广播模式。
- 尝试重启应用并再次搜索。

### 连接失败

- 检查目标设备是否已连接其他主机。
- 确保设备支持标准 BLE 心率配置文件。
- 重新运行应用并重新连接。

### 应用无法启动

- 重新安装依赖：

```bash
pip install -r requirements.txt
```

- 如果使用启动器，请确保脚本能访问相同的项目文件夹。
- 若应用崩溃，请查看生成的调试日志。

## 注意事项

- 本应用针对 Windows 优化，使用了若干 Windows 特定行为（如隐藏控制台和高 DPI 适配）。
- 浮动覆盖层有意设计为极简、轻量，并保持在其他窗口之上。
- 本项目以源代码形式分发，无正式发行包；直接通过 Python 安装即可使用。

## 免责声明

本项目仅用于个人监测与轻量级视觉反馈，并非医疗诊断设备，心率或压力数值不应视为医疗建议。

## 贡献

如果您希望改进应用，欢迎提交拉取请求和改进建议。
