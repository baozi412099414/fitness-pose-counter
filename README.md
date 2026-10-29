# 健身动作计数与姿态纠正

《软件工程基础》课程设计 · 第 11 题。

用普通摄像头（含 iPhone 连续互通相机）对准训练者，实时识别健身动作、自动计数，
并判断动作是否到位（蹲得够不够深、有没有塌腰、手臂直没伸直……），给出中文提示。

**本题的核心设计点：动作类型可配置。** 新增一个动作只需要一份 JSON 配置
（关键点、判定角度、上下阈值与迟滞区间、质量规则），**不改任何代码**。
网页上的「＋ 新建动作」向导会把配置写进 `configs/`，保存后立刻可用，也能在页面上删除。

---

## 快速开始（macOS）

### 方式一：双击脚本（推荐）

```bash
./start_web.command
```

脚本会依次：启动判定后端（8000）→ 等模型加载完 → 首次自动装前端依赖 → 启动前端（5173）。
浏览器打开 <http://localhost:5173>。

> 需要 Python 虚拟环境。若本目录没有 `.venv/`，脚本会退而使用上一级目录的 `.venv/`；
> 把项目挪到别处时，先执行一次 `./setup_env.sh` 建环境。

### 方式二：手动两个终端

```bash
# 终端 1：判定后端
.venv/bin/python -m uvicorn web.backend.app:app --host 127.0.0.1 --port 8000

# 终端 2：前端
cd web/frontend
npm install      # 第一次
npm run dev
```

### 拍照机位（影响识别效果）

| 动作 | 机位 |
|---|---|
| 深蹲 | 齐髋高、正侧面 |
| 俯卧撑 | 贴地、正侧面 |
| 开合跳 / 二头弯举 | 正面 |

全身入镜需要退到 2.5~3 米；iPhone 用**数据线**连接更稳，并关掉「中心舞台」等视频效果。

---

## 目录结构

```
健身动作/
├── start_web.command        一键启动（后端 + 前端）；Windows 用 start_app.ps1
├── setup_env.sh             建 Python 虚拟环境并装依赖（Windows 用 setup_env_windows.ps1）
├── requirements.txt
├── pose_landmarker_lite.task  MediaPipe Pose 模型（本地部署，5.6 MB）
│
├── pose_logic.py            ★ 核心自研：动作配置解释器（信号 / 状态机 / 质量判定 / 评分）
├── training_manager.py      训练组与间歇 / 历史与目标 / 多用户
├── action_editor.py         新建动作的数据层（部位预设 / 配置拼装 / 保存前校验）
├── validate_config.py       动作配置静态校验器
├── realtime_pose.py         桌面版实时识别（摄像头 / 视频 / 关键点数据三种输入）
├── fitness_ui.py            桌面版全模块测试台（Tkinter）
├── pose_player.py           关键点数据回放
├── motion_synth.py          合成动作轨迹（不依赖视频做阈值回归）
├── gen_bicep_curl.py        二头弯举合成数据生成器
├── plot_trend.py            训练趋势图
├── camera_check.py / diagnose_camera.py / camera_probe.py   摄像头排查工具
│
├── configs/                 动作配置：squat / pushup / jumping_jack（新建的动作也写这里）
├── samples/                 回放用的关键点数据（含二头弯举标准/半程/后仰三份）
├── data/users/              训练记录（每个用户一个目录：history / goals / profile）
├── captures/reports/        测试报告（JSON）
│
├── web/
│   ├── backend/             网页判定服务（FastAPI）
│   │   ├── app.py           /ws/train、/api/health、BUSY 与僵尸连接回收
│   │   ├── session.py       相机会话：校准 / 计数 / 判定 / 分组 / 汇总
│   │   ├── replay.py        回放会话（复用同一套判定）
│   │   ├── rest.py          用户 / 总览 / 历史 / 目标
│   │   └── actions_api.py   动作库的列表 / 详情 / 新建 / 删除 / 校验
│   └── frontend/            网页 UI（React 18 + TypeScript + Vite + Tailwind）
│       ├── src/features/    overview / actions / train / data / settings
│       └── public/samples/  回放样本
│
├── tests/                   课程模块测试（m01~m10）
├── test_pose_logic.py       配置解释器测试（37 项）
├── test_training_manager.py 训练管理测试（8 项）
├── docs/                    开发历史与功能实现记录
├── 测试用例文档.md           测试用例明细
├── 自定义动作指南.md         写配置加动作的教程
├── CLAUDE.md                项目上下文（环境坑、设计经验、阈值口径）
└── 选题/                     任务书与选题说明
```

---

## 测试

```bash
# 核心逻辑 + 训练管理 + 网页后端
.venv/bin/python -m pytest test_pose_logic.py test_training_manager.py web/backend/tests -q

# 只跑后端（回放 / 接口 / 相机链路桩模型）
.venv/bin/python -m pytest web/backend/tests -q

# 动作配置静态校验
.venv/bin/python validate_config.py configs/squat.json
```

前端：

```bash
cd web/frontend && npm run typecheck && npm run build
```

---

## 网页上新增一个动作（不改代码）

1. 动作库 → **新建动作** → 填名称 / ID / 机位；
2. 选信号（如「左肘角（肩-肘-腕）」）与两个阈值（进入 / 计一次）；
3. 勾选质量规则（幅度 / 回到起始），填阈值与提示语；
4. 保存 → 后端校验通过后写入 `configs/<id>.json`，动作库立刻多一张卡。

不想要了：打开动作详情 → 右上角 **删除动作**（内置的深蹲/俯卧撑/开合跳不可删）。

---

## 已知限制

- 判定阈值是**工程初值**（运动学几何 + ACE/NASM 规范），未经真人视频回归校准；
  受素材条件限制，报告里不要写成「已实测准确」。
- 同一时间只允许一路实时训练（MediaPipe 单例 + 线程锁）。
- 网页的「回放」模式只覆盖内置动作；自定义动作走实时。
- 实时模式下的「跳过休息」尚未接通。

更多设计细节与踩坑记录见 `CLAUDE.md` 与 `docs/`。
