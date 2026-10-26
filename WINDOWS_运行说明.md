# Windows 上怎么跑这个项目

> 项目原本在 macOS 上开发（`.venv` 是 macOS ARM64 的包，Windows 装不上）。
> 这份说明记录在 Windows 上重建环境、验证链路、以及改过的两处兼容性问题。

---

## 一、环境现状（已配好，可直接用）

| 项 | 值 |
|---|---|
| 系统 | Windows 11 (10.0.22631) |
| Python | **3.12.8**（系统 Python，非 anaconda） |
| 虚拟环境 | 项目内 `.venv`（Windows 原生，已替换掉原来的 macOS 版） |
| numpy | 2.5.4 |
| opencv-python | 5.0.0.93 |
| mediapipe | **1.1.1**（Windows 上装的是新版；macOS 那份锁的 0.10.35 是 macOS 专属限制） |
| matplotlib | 3.11.2 |
| tkinter | Tk 8.6 |
| 姿态模型 | `pose_landmarker_lite.task`（5.5 MB，项目自带） |
| 摄像头 | 设备 0，640x480 @ 30fps |

> `.venv` 已在 `.gitignore` 里，不会被提交。**换机器时每个人自己跑一次配置脚本即可。**

---

## 二、一键配置 / 运行

原版的 `setup_env.sh` 是 **macOS 专用**（bash + `sw_vers` + `.venv/bin/`），Windows 用不了。
新增了两个等价脚本：

### 首次配置（只需一次）

```powershell
cd "C:\Users\admin\Desktop\软件工程理论基础\选题 2\选题 2"
powershell -ExecutionPolicy Bypass -File setup_env_windows.ps1
```

可选参数：`-Minimal`（不装 mediapipe）、`-Mirror`（走清华镜像）。

### 日常运行

```powershell
.\start_app.ps1            # 打开全模块图形界面
.\start_app.ps1 -Test      # 跑全部测试（四个套件）
.\start_app.ps1 -Demo      # 示例数据回放（不需要摄像头）
.\start_app.ps1 -Camera    # 列出可用摄像头
```

### 或用 VS Code

项目已带 `.vscode/`：

- `settings.json` 已把解释器指到 `.venv\Scripts\python.exe`，并设好 `PYTHONUTF8=1`
- `launch.json` 有 7 个调试配置（界面 / 摄像头 / 数据回放 / 四个测试）

按 `F5` 选配置即可，也可以在 VS Code 终端里直接跑：

```powershell
.\.venv\Scripts\python.exe test_pose_logic.py
```

---

## 三、⚠ Windows 上必踩的坑：中文编码

Windows 控制台默认 **GBK**，而这个项目大量输出中文 + `✅` 等符号，
不加这一行会直接抛：

```
UnicodeEncodeError: 'gbk' codec can't encode character '\u2705'
```

**解决**：跑之前先设环境变量

```powershell
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
```

`start_app.ps1` 和 VS Code 的 `launch.json` 都已经帮你设了，直接用它们就不会遇到。

---

## 四、改过的两处 Windows 兼容性问题

### 1. `fitness_ui.py`：光标名 macOS 专用（**不改就启动崩溃**）

```diff
- cursor="pointinghand"      # macOS/Tk 认，Windows 不认
+ cursor="hand2"             # 跨平台都认
```

共 19 处。不改的话界面一启动就抛：

```
_tkinter.TclError: bad cursor spec "pointinghand"
```

原文件备份在 `fitness_ui.py.bak-before-windows-cursor`。

### 2. 新增脚本：`setup_env_windows.ps1`、`start_app.ps1`、`.vscode/`

见第二节。

### 没改、但要知道的

- `realtime_pose.py` / `camera_check.py` 里的 AppKit / Quartz 调用都有
  `if sys.platform != "darwin": return` 守卫，Windows 上自动跳过，**不影响功能**。
- `fitness_ui.py` 的 `ttk.Style().theme_use("aqua")` 在 Windows 上会抛
  `TclError`，但外面有 `except` 包着，自动回退默认主题，**无需修改**。
- `setup_env.sh` 和 `启动测试台.command` 是 macOS 专用，Windows 上不用管它们。

---

## 五、已验证的结论（Windows 本地实测）

在 Windows 上跑出来的结果，**与 macOS 上文档记录的数字一致**：

| 套件 | 命令 | 结果 |
|---|---|---|
| 动作判定核心 | `python test_pose_logic.py` | **全部通过 ✅**（43 项里的 35 项） |
| 训练管理 | `python test_training_manager.py` | **全部通过 ✅**（8 项） |
| 合成轨迹回归 | `python motion_synth.py --all` | **不符合预期 0 个**（13 条） |
| 配置校验 | `python validate_config.py` | 3 个文件，**错误 0 条** |
| 数据回放 | `python pose_player.py --data samples/squat_standard.json` | 计数 **3**，得分 **78.2**（与 `samples/README.md` 一致） |
| 图形界面 | `python fitness_ui.py` | 正常启动，四个入口卡片渲染正常 |
| 摄像头 + 模型 | 自检脚本 | 摄像头打开、44 帧、**14.6 fps**、模型加载与推理正常 |

> ⚠ **14.6 fps 这个数字要谨慎用**：那次是在空画面（没人）下测的，而且
> OpenCV 在 Windows 上缺 FFMPEG 的 `libavdevice`，走的是默认后端。
> **答辩 PPT 里要写实测帧率，就请在有人的真实画面下再测一次**，不要直接抄这个数。

---

## 六、答辩演示建议（Windows 机器）

**不需要摄像头也能演示**（最稳的一条路）：

```powershell
.\start_app.ps1 -Demo
```

或在界面里：**开始测试 → 输入选「关键点数据」→ 选 `samples\squat_standard.json`
→ 动作选「深蹲」→ 开始测试**，会走完整流程（画面、骨架、HUD、质量提示、写历史、出报告）。

**需要摄像头时**：`.\start_app.ps1` → 开始测试 → 输入选「摄像头」，
注意 Windows 上**默认设备号是 0**（macOS 代码里默认是 iPhone 的 1），
如果打不开，把设备号改成 0 或点「自定义」填 0。
