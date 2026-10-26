# 网页版前端 · TRAE 提示词包

> 适用项目：**《软件工程基础》课程设计 · 第 11 题 健身动作计数与姿态纠正**
> 现有代码：`C:\Users\admin\Desktop\软件工程理论基础\选题 2\选题 2`
> 目标：保留现有 Python 判定后端，新增一个**画面精美、功能对齐、可现场演示**的 Web 前端。
> 用法：按顺序把每一节的提示词粘进 TRAE，一次只做一轮，每轮验收后再进下一轮。

---

## 0. 先看结论（30 秒）

### 0.1 推荐架构

```
浏览器摄像头 / samples 演示数据
        │  (640px JPEG, 10~12 fps, 单帧在途)
        ▼
React + TypeScript + Vite 前端  ──WebSocket──▶  FastAPI 适配层（新增 web/backend）
        ▲                                        │
        │  landmarks + 计数/判定/评分/组间歇        ├─ pose_logic.py      （原样调用）
        └────────────────────────────────────────┘  ├─ training_manager.py（原样调用）
                                                    ├─ action_editor.py   （原样调用）
                                                    └─ MediaPipe PoseLandmarker（本地 .task）
```

**一句话：前端只负责“好看 + 好操作”，所有判定仍然由现有 Python 代码算。**
这样计数、评分、质量提示、历史、目标、多用户与桌面版**天然一致**，不会出现“网页版数出来 5 个、桌面版数出来 3 个”的答辩事故。

### 0.2 三个关键决定

| 决定 | 选择 | 原因 |
|---|---|---|
| 判定逻辑放哪 | **Python 后端**，前端不重写 | `pose_logic.py` 是本题核心自研模块，已有测试；复制成 TS 必然两套逻辑漂移 |
| 姿态模型放哪 | **Python 后端**，MediaPipe 0.10.35 | 满足任务书“本地部署开源模型”；不引入浏览器 WASM 的版本/显卡差异 |
| 视频帧怎么传 | WebSocket + base64 JPEG，**单帧在途、旧帧丢弃** | 实现简单、可背压；本地 640px 下延迟可控；视频不落盘 |

> 如果 TRAE 提议“用 Next.js 全栈重写”“把 pose_logic 翻译成 TypeScript”“浏览器端跑 MediaPipe”，**拒绝**。那会让核心逻辑出现第二套实现，也会让报告里的“配置解释器”证据失效。

### 0.3 最终页面清单

| 路由 | 页面 | 对应桌面版 |
|---|---|---|
| `/` | 今日总览 | 首页四卡片 + 训练数据摘要 |
| `/train`、`/train/:actionId` | 实时训练（核心） | 开始测试 + HUD + 运行日志 |
| `/actions`、`/actions/new`、`/actions/:id` | 动作库 / 新建动作 / 动作详情 | 动作管理 + 新建动作表单 |
| `/data` | 训练数据 | 训练数据（趋势 + 历史 + 错误排行） |
| `/settings` | 用户、目标与关于 | 多用户 / 每日目标 |
| `/styleguide` | 设计系统自检页（开发用） | 无 |

### 0.4 使用顺序

1. **Prompt 0**：让 TRAE 只读代码、不改代码，输出理解。
2. **Prompt A**：总纲 / 项目规则（建议同时写进 TRAE 的 Project Rules）。
3. **Prompt B**：视觉系统 + `/styleguide`，先把“好看”的底子定下来。
4. **Prompt C**：FastAPI 适配层 + WebSocket，先用脚本验收。
5. **Prompt D**：应用骨架 + 总览页。
6. **Prompt E**：实时训练页（工作量最大，单独一轮）。
7. **Prompt F**：动作库 + 新建动作。
8. **Prompt G**：训练数据。
9. **Prompt H**：用户 / 目标 / 设置。
10. **Prompt I**：联调、验收、演示脚本。
11. 出问题查第 13 节；赶时间用第 14 节的单条版。

### 0.5 时间不够时的最小可交版本

- **必须做**：Prompt 0 / A / B / C / D / E + 动作库列表与详情（F 的前半）+ 数据页（G）。
- **可以后补**：新建动作的四步向导（F 的后半）、删除用户、CSV 导出、语音播报。
- **不能省**：实时训练、动作库（能看到“判定来自配置”）、数据页。这三块是答辩的主线；只做总览会被问“后端功能去哪了”。
- 想先看页面效果：可以按附录 A 的契约用 mock 先做 D~G，但 **Prompt C 必须在答辩前完成**；否则就只是“假网页”，经不起现场提问。

---

## 1. 我读到的项目现状（提示词的事实基础）

下面这些是从你现有代码里读出来的，**提示词里会反复引用**，不要在 TRAE 里凭印象改：

- 核心判定：`pose_logic.py` —— 配置解释器 + `RepCounter` 状态机（迟滞、hold、`min_interval`、`cycles_per_rep`）+ `QualityChecker`（7 种 check、周期极值、可见性过滤、优先级、0~100 评分）+ `Action`（朝向自适应、`dxs/tilts` 符号翻正）。
- 训练管理：`training_manager.py` —— `SetManager`（组/次/休息、`set_done`/`rest_start`/`rest_end`/`all_done` 事件）、`UserStore`（多用户分目录）、`History`（会话、周趋势、评分趋势、错误汇总）、`Goals`（按动作的每日目标）。
- 动作编辑器数据层：`action_editor.py` —— `ANGLE_PARTS` / `PAIR_PARTS` 中文部位预设、`SIGNALS` / `CHECKS` / `WHENS` 人话映射、`build_action_config()`、`validate_and_save()`。
- 配置校验：`validate_config.py` —— 11 类静态检查，返回 `Report.errors` / `Report.warns`。
- 内置动作 3 份：`configs/squat.json`（7 条质量规则）、`configs/pushup.json`（7 条）、`configs/jumping_jack.json`（4 条，多条件 AND）。
- 桌面版页面：首页 → **开始测试 / 训练数据 / 动作管理 / 运行日志**；已经有“多用户、分组间歇、目标、趋势图、错误排行、报告详情”。
- 演示数据：`samples/` 有 8 份关键点 JSON（深蹲标准/浅蹲/膝前移、俯卧撑标准/塌腰、开合跳标准/手低、最简格式），**不需要摄像头就能跑出确定结果**。
- 模型：根目录 `pose_landmarker_lite.task`，`mediapipe==0.10.35` **不能升级**（macOS 26 上 1.0.x 初始化崩溃）。
- 摄像头限制：macOS 权限、iPhone 需 USB、关“中心舞台”；Web 端另有一条限制——`getUserMedia` 只在 **localhost 或 HTTPS** 下可用。
- 口径红线：阈值是“按运动学与 ACE/NASM 规范给的工程初值”，**没有做真人视频回归校准**。网页上不能写“准确率 99%”“已校准”之类的话。

### 1.1 现有能力 → Web 对应表

| 现有能力 | 现有入口 | Web 页面 | Web 接口 |
|---|---|---|---|
| 33 点实时检测 | `realtime_pose.py` + MediaPipe | `/train` | `WS /ws/train` |
| 配置驱动计数 | `pose_logic.Action` | `/train` 左侧大数字 | 同上 |
| 质量判定 + 评分 | `QualityChecker` | `/train` 右侧规则面板 | 同上 |
| 内置动作库 | `configs/*.json` | `/actions` | `GET /api/actions` |
| 新建动作 | `action_editor.py` + `fitness_ui.ActionEditor` | `/actions/new` | `POST /api/actions` |
| 配置校验 | `validate_config.py` | 新建动作最后一步 | `POST /api/actions/validate` |
| 分组间歇 | `SetManager` | `/train` 休息遮罩 | WS `sets` + `event` |
| 历史 / 趋势 / 错误排行 | `History` + `plot_trend.py` | `/data` | `GET /api/overview`、`GET /api/history` |
| 每日目标 | `Goals` | `/settings`、`/` | `GET/PUT /api/goals` |
| 多用户 | `UserStore` | `/settings` | `/api/users` |
| 数据回放 | `pose_player.py` + `samples/` | `/train` 演示模式 | `WS start_replay` |

---

## 2. 在 TRAE 里怎么用这份提示词

1. **用现有项目根目录打开 TRAE**，不要新建空项目。否则 Git 历史断了，任务书 2.1 的“提交记录作为贡献依据”就没了。
2. 先把 `CLAUDE.md`、`pose_logic.py`、`configs/*.json`、`training_manager.py`、`action_editor.py`、`validate_config.py` 留在工作区，TRAE 需要读。
3. 把 **Prompt A** 放进 TRAE 的 **Project Rules / 项目规则**（如果版本支持），这样每一轮都自动带上；否则每轮开头手动粘一次。
4. **一次只做一轮**。每轮结束让 TRAE 输出：改了哪些文件、启动命令、自测结果、还有什么没做。不要让它“顺便把后面几页也写了”。
5. 每轮都在浏览器里**实际打开看**（1440×900 截图），不要只看代码。TRAE 说“已完成”不等于页面能看。
6. 每轮验收通过就 `git add` + 中文 commit，节奏和现有 60+ 次提交保持一致。
7. 如果 TRAE 要装新依赖，只允许追加到 `requirements.txt` / `package.json`，**不许改 `mediapipe==0.10.35`**。

---

## 3. Prompt 0 · 先读代码（只读，不写）

```text
先不要写任何代码。请阅读当前项目根目录下的这些文件，然后只用中文输出一份“理解确认”：

必读：
1. CLAUDE.md
2. pose_logic.py（重点：RepCounter、QualityChecker、Action.update 的返回值）
3. configs/squat.json、configs/pushup.json、configs/jumping_jack.json
4. training_manager.py（SetManager / UserStore / History / Goals）
5. action_editor.py（部位预设、build_action_config、validate_and_save）
6. validate_config.py（Report 结构）
7. samples/README.md 与 samples/ 里任一份 JSON 的结构
8. fitness_ui.py 的页面结构（只需看首页、测试页、数据页、动作管理页的控件）

请回答：
A. 这个项目的核心设计点是什么？为什么说“新增动作不改代码”？
B. pose_logic.Action.update(points, visibilities, now) 返回哪几个值？每个值分别给 UI 提供什么？
C. QualityChecker 的 check 明细里有哪些字段？visible / checked 分别是什么含义？
D. 现有 3 个动作各自的计数信号、阈值、规则数是什么？
E. 训练历史一条记录有哪些字段？SetManager 会产生哪几种事件？
F. 如果要做网页版，哪些能力必须继续由 Python 提供，哪些可以放前端？

要求：不要修改任何文件；不要提出重构；不要给代码。等我确认你的理解后，再进入下一步。
```

---

## 4. Prompt A · 总纲与硬约束（每轮都带）

```text
你是资深前端工程师 + 产品设计师。我们在一个已经完成的 Python 课程设计项目上，新增一个 Web 前端。

【项目】
《软件工程基础》第 11 题：健身动作计数与姿态纠正。
现有 Python 后端已经实现：MediaPipe 33 点检测、配置驱动的计数状态机、动作质量判定与评分、训练组/间歇、历史/目标、多用户。
核心考点是“动作可配置”：新增动作只写一份 JSON，不改代码。

【本次目标】
在现有仓库里新增 web/ 目录，做一个画面精美的网页版：
- 视觉上像专业运动科学仪器，不像通用后台模板；
- 功能上与现有 Python 后端一一对应，所有数字来自真实接口；
- 能现场答辩演示：摄像头实时计数 + samples 数据回放兜底。

【架构（必须遵守）】
浏览器摄像头 → 前端按视频宽高比缩放到最长边 640px → JPEG(0.65) → WebSocket → FastAPI →
MediaPipe PoseLandmarker(VIDEO 模式) → pose_logic.Action → 每帧返回 landmarks + 计数/阶段/判定/评分 →
前端 canvas 画骨架 + HUD。
所有计数、质量判定、评分、组间歇、历史、目标、多用户逻辑，必须调用现有 Python 模块，禁止在前端重写。

【必读文件】
CLAUDE.md、pose_logic.py、configs/*.json、training_manager.py、action_editor.py、validate_config.py、samples/README.md、realtime_pose.py（只看校准与事件部分）。

【硬约束】
1. 只新增 web/ 目录；根目录只允许追加 requirements.txt 依赖、修改 .gitignore。
2. 严禁修改 pose_logic.py、training_manager.py、action_editor.py、validate_config.py、realtime_pose.py、fitness_ui.py 的现有行为。
3. 严禁升级 mediapipe；必须保持 0.10.35。
4. 前端不得硬编码业务数字来“装得像有数据”；没有数据就显示空状态。
5. 演示模式必须走 samples/ + 同一套后端判定，不允许前端自己写一套假计数。
6. UI 全中文；代码标识符英文；TypeScript strict，禁止 any。
7. 不做登录、注册、云同步、支付、社交、AI 聊天；不做视频录制与云端上传。
8. 不引入第二套 UI 框架；图标统一 lucide-react；不使用 emoji 当图标。
9. 视频帧只在内存中处理，不落盘；页面上要有一句隐私说明。
10. 每轮结束必须输出：改动文件、启动命令、自测结果、未完成/风险。

【技术栈】
React 18 + TypeScript + Vite 5 + Tailwind CSS 3.4 + React Router 6 + Zustand + TanStack Query v5 +
Framer Motion + Recharts + lucide-react。
字体用 @fontsource 本地包（Bebas Neue / Space Grotesk），中文用系统字体栈，不依赖 Google Fonts 网络。
包管理用 npm（不要同时出现 pnpm-lock.yaml 和 package-lock.json）。

【目录结构】
web/
  backend/
    app.py                 # FastAPI 入口、CORS、静态挂载（可选）
    settings.py            # 项目根路径、模型路径、数据目录
    schemas.py             # Pydantic 模型
    routers/actions.py
    routers/users.py
    routers/training.py
    routers/pose.py        # WebSocket /ws/train
    services/pose_engine.py
    services/session.py
    services/replay.py
    tests/
  frontend/
    src/
      app/                 # 路由、布局、providers
      components/ui/       # 自建基础组件
      components/live/     # 实时页专用组件
      features/dashboard|actions|data|settings|live/
      lib/                 # api、ws、format、landmarks、canvas
      stores/
      styles/
    public/
    index.html
    vite.config.ts
  README.md
  start_web.ps1            # Windows 一键起后端 + 前端（两个进程）

【分阶段（严格按顺序，不要一次全做）】
阶段 1：只读代码，确认理解（Prompt 0）
阶段 2：视觉系统 + /styleguide
阶段 3：FastAPI 适配层 + API/WS 契约 + 后端测试
阶段 4：应用骨架 + 总览页
阶段 5：实时训练页
阶段 6：动作库 + 新建动作
阶段 7：训练数据
阶段 8：用户 / 目标 / 设置
阶段 9：联调、性能、验收、演示脚本

现在只做我指定的阶段。开始前先用 5 句话复述你理解的目标和边界；如果发现现有代码与我的描述不一致，先指出，不要擅自改。
```

---

## 5. Prompt B · 视觉系统（先把“好看”定死）

```text
这一轮只做视觉系统，不做业务页面。

【设计概念】
“FORM LAB / 形实验室”：运动科学仪器 + 专业相机取景器 + F1 遥测面板。
关键词：克制、精密、爆发力。暗色为主，荧光绿只用在“当前正在发生的事”上。
不要做成通用 SaaS 后台，不要做成健身 App 的营销落地页。

【必须避免的“AI 味”】
- 紫蓝渐变、彩虹渐变、满屏玻璃拟态；
- 所有卡片 24px 大圆角 + 大阴影；
- emoji 当图标、圆滚滚的插画、无意义光晕；
- 居中大标题 + 三张等宽卡片的营销结构；
- 默认 Inter 字体、默认蓝色按钮；
- 到处都在动、数字滚动到停不下来。

【色彩 token】
--bg-0: #060709;          /* 页面底色 */
--bg-1: #0B0D11;          /* 次级底色 */
--surface-1: #101318;     /* 卡片 */
--surface-2: #151922;     /* 卡片内嵌 */
--surface-3: #1B202A;     /* hover / 选中 */
--line-1: #232833;        /* 1px 描边 */
--line-2: #2E3542;        /* 强描边 */
--text-1: #F5F7FA;
--text-2: #A3ACBA;
--text-3: #6C7686;
--accent: #D6FF3F;        /* 荧光绿：主操作、当前计数、达标 */
--accent-ink: #0A0C05;    /* 荧光绿上的文字 */
--cyan: #6FE3FF;          /* 数据/图表辅助 */
--amber: #FFB454;         /* 休息/校准 */
--coral: #FF6B5C;         /* 错误/危险 */
--mint: #45E0A8;          /* 成功 */
除以上颜色外，不要新增强调色；一屏最多出现两种强调色。

【字体】
--font-display: "Bebas Neue", "DIN Condensed", "Impact", sans-serif;   /* 大数字、英文标签 */
--font-ui: "MiSans", "HarmonyOS Sans SC", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
--font-mono: "Space Grotesk", "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
中文标题不要用 Bebas；大数字用 Bebas，且 font-variant-numeric: tabular-nums。

【字号与节奏】
12 / 13 / 14 / 16 / 20 / 24 / 32 / 48 / 72 / 120 / 180 px。
页面标题 24~32；卡片标题 16~20；正文 14；辅助 12~13；实时计数 clamp(96px, 12vw, 180px)。
间距 4 的倍数：8 / 12 / 16 / 20 / 24 / 32 / 40 / 56 / 72。
圆角：chips 999，卡片 14，舞台 20，弹窗 18。不要所有东西都 24。
描边：1px var(--line-1)；hover 用 var(--line-2)；不使用彩色描边大面积铺。

【背景与质感】
页面底色近黑；右上角一个非常淡的荧光绿径向光（opacity ≤ 0.06）；
叠加 2.5% 的 SVG 噪点；仅实时舞台允许 32px 点阵网格（2% 白）。
不要用大图做背景，不要用模糊光斑堆叠。

【基础组件（自建，不引入第二套 UI 库）】
Button：primary（荧光绿底黑字）/ secondary（透明底 1px 描边）/ ghost / danger（coral）。
  高度 40；圆角 10；focus-visible 2px 荧光绿 outline，offset 2。
Input / Select / NumberStepper：深色底、1px 描边、focus 时描边变荧光绿。
Card：surface-1 + 1px line-1 + 14 圆角，不用阴影。
Stat：label 12px 大写字母间距 0.12em，数字 display 字体，delta 用 mint/coral。
Badge：胶囊，12px；状态色只用于小面积。
ProgressRing：120/160px，8px 描边，圆头，荧光绿，中心数字。
RuleRow：规则名 + 实测值/阈值 + 4px 进度条 + 状态点；失败 coral，达标 mint，不可见灰，未参与判定暗灰。
TipBanner：左侧 3px coral 竖条，深红底 8%，18px 文案，只显示 1 条。
EmptyState：线框骨架 + 一句解释 + 一个 CTA，不要只写“暂无数据”。
Skeleton：深灰块，1.2s 呼吸，不要彩虹 shimmer。
Dialog / Drawer：18 圆角，遮罩 70% 黑，ESC 关闭，焦点锁定。
Toast：右上角，3s 消失；训练中不要用 toast 报动作错误（用 TipBanner）。

【动效】
统一 cubic-bezier(.2,.8,.2,1)；hover 120ms，进入 180ms，弹窗 220ms。
计数变化：旧数字上移淡出、新数字下移淡入，180ms；不要整页闪。
页面切换：淡入 + 8px 上移，160ms。
训练进行中：除了计数、倒计时、骨架，其他元素不要动。
必须支持 prefers-reduced-motion。

【响应式】
主目标 1440×900；1280×800 不出现横向滚动；1024 以下侧栏折叠、实时页提示“建议桌面/横屏”。
实时页最小宽度 1100；数据页可以单列堆叠。

【这一轮的交付】
1. Tailwind 配置写入全部 token（颜色、字体、圆角、间距、动画）。
2. 建立 components/ui 下的基础组件与样式。
3. 做一个 /styleguide 页面，展示：色板、字号、按钮 4 种、卡片、Stat、Badge、RuleRow 三种状态、
   ProgressRing、TipBanner、EmptyState、Skeleton、Dialog、Drawer。
4. 页面本身要像“设计规范”，不要像组件库文档站；左侧目录，右侧大块展示。
5. 在 1440×900 截图自检：没有 emoji、没有紫蓝渐变、没有多余强调色、对比度达标、无 console 报错。

验收标准：只看 /styleguide 的截图，就能判断这个项目“有设计”；如果它看起来像默认 Tailwind 模板，重做。
```

---

## 6. Prompt C · 后端适配层与 API 契约

```text
这一轮只做 web/backend，不做前端页面。目标：把现有 Python 能力完整暴露成 REST + WebSocket，并能用脚本验收。

【原则】
- 现有模块是唯一事实来源：直接 import pose_logic、training_manager、action_editor、validate_config。
- 不复制、不改写计数/判定/评分算法。
- 新增代码只放在 web/backend/ 下。
- 所有相对路径以项目根目录为基准（用 Path(__file__).resolve().parents[2]），不要依赖启动时的 CWD。
- UserStore 的数据根目录显式传项目根下的 data/users，避免 CWD 不同导致读到别的用户。
- 允许追加 fastapi、uvicorn[standard]、httpx、pytest 到 requirements.txt；不许动 mediapipe 的版本。

【REST 契约】
统一前缀 /api，UTF-8 JSON；错误统一 {"detail": "..."} 或 {"detail": {"message": "...", "errors": [...]}}。

GET  /api/health
  → {"ok": true, "model_loaded": true, "mediapipe": "0.10.35", "project_root": "..."}

GET  /api/actions
  → {"items": [ActionItem], "count": n}
  ActionItem = {
    "config": { ...原始 JSON... },
    "validation": {"errors": [], "warnings": []},
    "display": {
      "signal_text": "左膝角（髋-膝-踝）",
      "threshold_text": "低于 140° 进入动作，高于 155° 计 1 次",
      "rules": [{"name","tip","when_text","check_text","threshold_text","priority"}]
    }
  }
  display 由后端根据 action_editor 的部位预设与信号/判定映射生成；生成不了就退回原始字段，不要报错。

GET  /api/actions/{id}
  → ActionItem；不存在返回 404，detail 用中文说明可用动作列表。

POST /api/actions
  body: {
    "name": "深蹲", "id": "squat" | null,
    "signal": "angle", "points": [23,25,27],
    "start_th": 140, "end_th": 155, "first_lo": true,
    "cycles": 1, "camera_side": "侧", "calibrate": true,
    "depth_check": true, "depth_th": 105, "depth_tip": "...",
    "straight_check": true, "straight_th": 160, "straight_tip": "..."
  }
  处理：slugify_id（若 id 为空）→ build_action_config() → validate_and_save()
  → 成功 201 {"ok": true, "message": "...", "config": {...}, "path": "configs/xxx.json", "warnings": []}
  → 校验失败 422 {"ok": false, "message": "配置有问题，没有保存", "errors": ["..."]}
  ⚠ 不存在的字段不要猜；先读 action_editor.build_action_config 的参数。

POST /api/actions/validate
  body: {"id": "squat"} 或 {}（全部）
  → {"items": [{"file": "configs/squat.json", "errors": [], "warnings": []}], "ok": true}

GET  /api/users
  → {"current": "演示用户", "items": [{"name","created_at","height_cm","weight_kg","sessions","today_reps"}]}

POST /api/users        body {"name","height_cm"?,"weight_kg"?} → {"ok":true,"user":{...}}
POST /api/users/switch body {"name"} → {"ok":true,"current":"..."}
DELETE /api/users/{name} → {"ok":true,"message":"..."}；只剩一个用户时 409。

GET  /api/goals
  → {"items": [{"action","name","done","target","ratio","reached","remaining"}]}
PUT  /api/goals/{action} body {"daily_reps": 50} → {"ok":true,"goal":{...}}
DELETE /api/goals/{action} → {"ok":true}

GET  /api/overview?action=&days=14
  → {
      "user": "...",
      "today": {"reps","target","ratio","reached","remaining"},
      "week": {"reps","sessions"},
      "avg_score": 78.2 | null,
      "total_sessions": 12,
      "weekly_trend": [{"week_start","reps"}],
      "score_trend": [{"date","score": 82.5 | null}],
      "errors": [{"name","count","tip"}],
      "recent": [Session],
      "goals": [{"action","name","done","target","ratio","reached","remaining"}]
    }

GET /api/history?action=&limit=50&offset=0
  → {"total": n, "items": [Session]}
  Session = {"time","date","action","reps","sets","errors":{},"duration_sec","source","score"}

GET /api/samples
  → {"items": [{"id","name","action","fps","frames","note","duration"}]}
  扫描 samples/*.json，用 pose_player.load_data 校验并取元信息；坏文件跳过并在 warnings 里说明。

【WebSocket /ws/train】
客户端 → 服务端：
  {"type":"start","action_id":"squat","user":"演示用户","sets":3,"reps_per_set":10,"rest_seconds":30}
  {"type":"frame","frame_id":123,"image":"data:image/jpeg;base64,..."}
  {"type":"start_replay","sample_id":"squat_standard","action_id":"squat","record_history":false}
  {"type":"reset"}
  {"type":"stop"}

服务端 → 客户端：
  {"type":"ready","session_id":"...","mode":"camera"|"replay","action":{"id","name","camera_side"},
   "calibration":{"needed":true}}
  {"type":"state","seq":n,"frame_id":123,"ts":...,
   "count":3,"stage":"ready"|"active","signal":142.3,
   "values":[142.3,139.8,0.72],   // 各条件/主信号；单条件就一个；多条件动作必须全给
   "cycle_progress":0,             // 本轮已完成几个循环（cycles_per_rep>1 时显示）
   "score":78.2|null,"grade":"良好",
   "checks":[{"name","tip","value","limit","ok","visible","checked","priority","score"}],
   "hits":[...同 checks 的最多 2 条...],
   "landmarks":[{"x","y","z","v"} × 33],      // 归一化 0~1；v=0 表示缺失
   "person":true,
   "calibration":{"status":"idle"|"sampling"|"done"|"skipped","baseline":178.0,"progress":0.6},
   "sets":{"current_set":1,"total_sets":3,"reps_in_set":0,"reps_per_set":10,
           "total_reps":0,"rest_remaining":0,"finished":false},
   "metrics":{"fps":11.8,"latency_ms":86,"infer_ms":42}}
  {"type":"event","event":"set_done"|"rest_start"|"rest_end"|"all_done"|"calibrated",
   "set":1,"total_sets":3,"seconds":30,"baseline":178.0,"tip":"..."}
  {"type":"summary","action":"squat","action_name":"深蹲","reps":3,"score":78.2,"grade":"良好",
   "duration_sec":42.1,"errors":{"not_deep_enough":1},"error_tips":{},
   "person_rate":0.98,"detection_rate":0.99,"saved":true,"goal":{...}}
  {"type":"error","code":"NO_PERSON|MODEL_ERROR|BAD_FRAME|BUSY","message":"中文说明"}

【推理与判定实现要求】
- 模型只加载一次（全局单例 + asyncio.Lock 或单线程 executor）；MediaPipe 对象不是线程安全的。
- 应用启动时在后台预热模型；/api/health 的 model_loaded=false 时前端显示“模型加载中”，不要当成后端挂了。
  macOS 上 mediapipe 遥测可能让首次加载慢约 1 分钟（见 CLAUDE.md），这是已知现象，UI 要能等。
- 用 RunningMode.VIDEO + detect_for_video(mp_image, timestamp_ms)，timestamp 用会话内单调递增的毫秒；
  不要用 LIVE_STREAM 回调（Web 适配层不需要，反而增加时序复杂度）。
- 每帧先按原始宽高比缩放到最长边 640px，不裁剪、不拉伸；landmarks 归一化坐标不受缩放影响。
- pose_logic 需要像素坐标：把 landmark.x * frame_w、landmark.y * frame_h 传进去；visibility 传 v。
- MediaPipe 没检测到人时：不要调用 action.update；返回 person=false，count/stage 保持上次值，
  checks 全部 visible=false（或者空数组），前端显示“请让全身入镜”。
- 每帧只处理最新帧：前端保证单帧在途；服务端若上一帧未处理完，直接丢弃新帧并回 metrics.dropped=true。
- 校准：start 后若 action.calibrate 且 signal_type=="angle"：
  · 前 2 秒采样信号，至少 8 个有效值；取中位数 baseline；
  · lo = baseline - 15，hi = baseline - 8；
  · 对 check=="peak_min" 且没有自带 signal 的规则，min = baseline - 10；
  · 校准期间不计数；校准完成先 action.reset()，再进入 live；
  · 4 秒还采不满 8 个就跳过校准，用配置固定阈值，发 event=calibrated? status=skipped。
  · 非 angle 动作、calibrate=false、replay 模式：直接跳过校准。
- 错误计数：按“新出现的 hit 名字”做边沿计数（与 realtime_pose.py 一致），不要每帧累加。
- state 里的 score/grade 读 action.last_score / QualityChecker.grade(action.last_score)，不要在适配层重算；
  values 用 action.last_values（多条件动作要全给），cycle_progress 用 action.counter.cycle_progress，
  signal 只保留第一个条件用于兼容。
- checks 原样返回，不要改写 visible/checked/ok；UI 靠它们区分“无数据 / 未到判定时机 / 真的失败”。
- setman.on_rep(count, now) 必须每个 state tick 都调用（即使 count 没变），否则 rest_end 永远不会触发；
  sets 状态从 setman.status(now) 取。
- 停止时：只有 camera 模式、reps>0、record_history!=false 才写历史；
  History.add_session(action, reps, sets, errors, duration_sec, source="web", score=last_score)；
  然后返回 summary，并带上 Goals.progress。
- replay 模式：用 pose_player.load_data 读 samples；按 fps 推进 now=i/fps；不要用墙上时间；
  不校准、不写历史；按 30fps 推送 state（可 sleep 1/fps），让前端看到骨架动画。
- 并发：同一时间只允许一个训练会话；第二个连接返回 error code=BUSY 并关闭，避免 MediaPipe 争用。

【测试（必须做）】
web/backend/tests/test_api.py：
- health、actions 列表、action 详情、404；
- 用户创建/切换/删除保护；
- goals 设置/进度；
- overview 在空数据与有数据两种情况下的结构；
- 动作校验失败返回 422 且不落盘。
web/backend/tests/test_replay.py：
- 直接调用 replay 服务跑 samples/squat_standard.json、squat_shallow.json、pushup_sag.json、jack_low_hands.json；
- 断言计次与分数与 samples/README.md 的记录一致（允许 0.1 的舍入差）；
- 这条测试是“网页版与桌面版一致”的证据。

【启动与验收】
命令：
  python -m uvicorn web.backend.app:app --host 127.0.0.1 --port 8000
  pytest web/backend/tests -q
  curl http://127.0.0.1:8000/api/health
  curl http://127.0.0.1:8000/api/actions
验收：
1. /docs 能看到全部接口；
2. pytest 全绿；
3. 用 samples 回放能跑出 README 记录的次数/分数；
4. 不改任何现有 Python 文件（git diff 只允许 requirements.txt、.gitignore、web/）。

完成后输出：接口清单、测试结果、已知限制（例如单会话、12fps、浏览器需 localhost）。
```

---

## 7. Prompt D · 应用骨架与总览页

```text
这一轮做前端骨架 + 总览页，不做实时训练页。

【先做的事】
1. 用 Vite 创建 web/frontend（React + TS + Tailwind）。
2. 配置路径别名 @ → src；配置 Vite proxy：
   /api → http://127.0.0.1:8000
   /ws  → ws://127.0.0.1:8000（ws: true）
3. 建立 AppProviders：TanStack QueryClient、BrowserRouter、Toast、ErrorBoundary。
4. 建立全局样式：暗色底、字体、噪点、focus-visible、滚动条（细、深灰）。

【布局】
- 左侧导航：展开 220px / 折叠 84px；折叠只显示图标 + tooltip；当前项左侧 2px 荧光绿竖条。
  导航项：总览 / 训练 / 动作库 / 数据 / 设置；底部是当前用户头像缩写 + 设置入口。
- 顶栏 64px：左侧面包屑（页面名 + 可选动作名），右侧后端状态（绿点“判定服务在线”/灰点“未连接”）、
  用户切换下拉、帮助（快捷键）按钮。
- 主内容：max-width 1600，padding 32；页面进入淡入 8px。
- 移动端：侧栏变底部 tab；实时页显示“请用桌面端/横屏”。

【路由】
/            总览
/train       训练入口（未选动作时展示动作选择）
/train/:id   实时训练
/actions     动作库
/actions/new 新建动作
/actions/:id 动作详情
/data        训练数据
/settings    设置
/styleguide  设计系统（开发用，不放进导航）

【总览页 · 信息结构】
1. 问候行：北京时间问候 + 日期 + 一句“今天练什么？”；右侧是后端状态与“开始训练”主按钮。
2. Hero（左侧 5 列）：
   - label：今日完成
   - 巨大数字：today.reps（display 字体，120~180px）
   - 目标环：ratio；中心显示百分比；下方“还差 N 次 / 已达成”；
     target=0 时环用灰色虚线，文案“未设置目标 · 去设置”，不要显示 0%。
   - 与昨日对比：有数据才显示 delta，没数据不编。
3. 快速开始（右侧 7 列）：
   - 3 张动作卡（来自 /api/actions）：自定义线稿动作图标、动作名、camera_side、规则数、阈值摘要；
   - hover 边框变荧光绿，点击进入 /train/:id；
   - 底部一行次要入口：“没有摄像头？用演示数据回放”。
4. 本周趋势（左 8 列）：Recharts 柱状图，7/8 周；柱体荧光绿渐变到透明；hover tooltip 显示周起始与次数；
   无数据时显示 EmptyState（“还没有训练记录” + 去训练）。
5. 目标与错误（右 4 列）：
   - 目标进度列表（最多 3 个动作），ProgressRing 或细进度条；
   - “最常犯的错”前 3 条，显示 tip + 次数，点击跳 /data?tab=errors。
6. 最近训练（左 8 列）：表格 5 行，列：时间、动作、次数、评分、错误数；行 hover 高亮；
   空状态引导。
7. 页面底部一行小字：数据来自本地 data/users，视频帧不落盘。

【数据与状态】
- /api/health 每 10s 轮询，失败时顶栏灰点 + 总览顶部一条细提示条（不弹窗）。
- /api/overview、/api/actions、/api/users 用 TanStack Query；staleTime 30s。
- 所有卡片有 loading skeleton；请求失败有重试按钮；不要整页 spinner。
- 所有数字来自接口；没有数据就显示 0 或空状态，不要 mock。

【总览的“记忆点”】
巨大的今日次数 + 细目标环 + 一条横向的“训练轨道”（可显示最近 7 天的小方块，完成=荧光绿，未完成=深灰）。
轨道放在 Hero 下方，不要做成第二种图表。

【验收】
- 1440×900 首屏能看到：今日次数、目标进度、开始训练、三个动作入口。
- 1280×800 不横向滚动。
- 侧栏折叠/展开不导致内容跳动。
- 后端未启动时页面仍能打开，显示离线状态与重试，不发疯。
- 没有 mock 数字；没有 console error。
```

---

## 8. Prompt E · 实时训练页（核心，单独一轮）

```text
这一轮只做 /train 与 /train/:actionId。这是整个网页版最重要的页面，目标是“答辩时看起来像专业设备，且数字与桌面版一致”。

【页面结构（1440×900 一屏，不滚动）】
顶部 64px 应用顶栏保留。下面：
┌ 左栏 200px ─┬──────────── 舞台 16:9 ────────────┬─ 右栏 320px ─┐
│ 动作名/机位  │  视频 + canvas 骨架 + 取景框角标    │ 评分环        │
│ 阶段徽章     │  顶部：动作 · 阶段 · FPS · 人体状态  │ 规则明细      │
│ 巨大计数     │  底部：TipBanner + 组进度           │ （可滚动）    │
│ 组/次进度    │                                     │              │
│ 信号仪表     │                                     │              │
└─────────────┴─────────────────────────────────────┴──────────────┘

【训练前 · 准备面板】
未开始时，舞台区域显示准备面板（不是空白）：
- 左侧动作选择：横向卡片，选中态荧光绿描边；显示 camera_side 与“7 条质量规则”。
- 中间摄像头预览：16:9，权限未授予时显示“允许摄像头”按钮与说明；
  已授权显示实时画面 + 半透明骨架占位（可选）。
- 右侧设置：
  · 摄像头设备下拉（enumerateDevices，label 为空时显示“摄像头 1/2”）；
  · 镜像开关（默认开，前置摄像头）；
  · 语音提示开关（默认关；Web Speech API 不可用时置灰并说明）；
  · 分组间歇：开关 + 组数 + 每组次数 + 休息秒数；
  · 每日目标：显示当前动作目标与今日进度（来自 /api/goals），可快速设置；
  · 主按钮“开始训练”（摄像头就绪才可用）；
  · 次按钮“用演示数据”（打开 samples 选择抽屉）。
- 机位提示根据 camera_side 显示：
  侧：“把摄像头放在身体正侧方，高度约与髋同高，退到全身入镜。”
  正：“正对镜头，退到全身入镜，不要裁掉脚。”
- 检查清单 3 条：全身入镜 / 光线充足 / 背景不要有人走动；用勾选样式，但不阻塞开始。

【开始流程（严格按顺序）】
1. getUserMedia({video:{width:{ideal:1280},height:{ideal:720},facingMode:"user"},audio:false})
2. 等 videoLoadedMetadata，读取 videoWidth/videoHeight。
3. 连接 WS /ws/train，发送 start（action_id、user、sets、reps_per_set、rest_seconds）。
4. 收到 ready 后进入 calibrating 或 live。
5. 若 calibration.needed：显示校准遮罩“站直别动，正在量站立基线”，显示 progress；
   收到 event=calibrated 后显示 baseline（如“基线 178°”），1.2s 后淡出。
6. 进入 live，启动抽帧循环。

【抽帧与背压】
- 按视频原始宽高比缩放到最长边 640，不裁剪、不拉伸；目标 10~12 fps。
- 用离屏 canvas.drawImage(video) → toDataURL("image/jpeg", 0.65)（或 toBlob + FileReader）。
- **单帧在途**：发送后 pending=true；收到带同一 frame_id 的 state 才置 false；未 ack 不发下一帧。
- 页面隐藏（visibilitychange）暂停发送；回来恢复。
- 显示 metrics.fps 与 metrics.latency_ms；连续 3 秒无 state 显示“判定服务无响应”细条，并自动重连一次。
- 不允许把每一帧的 landmarks 放进 React state；放进 useRef 的可变对象。

【WebSocket 消息处理】
- state：写入 liveRef；只有 count/stage/score/grade/hits 签名变化时才 setState，最多 10Hz。
- event：set_done → 轻提示；rest_start → 休息遮罩；rest_end → 收起；all_done → 结算弹窗；calibrated → 基线提示。
- summary：打开结算弹窗，显示 reps/score/grade/errors/duration/goal/saved。
- error：按 code 显示中文：NO_PERSON、MODEL_ERROR、BAD_FRAME、BUSY；不要直接抛 alert。

【画骨架（canvas）】
- canvas 覆盖在 video 上，尺寸 = 容器 CSS 尺寸 × devicePixelRatio；resize 时重算。
- 视频用 object-fit: contain，黑底；计算 scale/offset，把归一化坐标映射到显示区域，避免拉伸错位。
- 连接关系（MediaPipe Pose 33 点常用）：
  肩 11-12、肩-肘 11-13/12-14、肘-腕 13-15/14-16、
  肩-髋 11-23/12-24、髋 23-24、髋-膝 23-25/24-26、膝-踝 25-27/26-28、
  踝-脚跟 27-29/28-30、脚跟-脚尖 29-31/30-32、脚尖 31-32。
- 线：2px 荧光绿，shadowBlur 10，globalAlpha 0.9；关节点：3px 白点，测量关节额外 6px 荧光绿环。
- visibility < 0.5 的点：不画，或画灰色虚线；不要用猜的点冒充。
- 镜像：预览镜像时，绘制前 x' = 1 - x；文字不要镜像。
- 高亮测量点：根据当前动作配置的计数 points 高亮（squat 膝 25、pushup 肘 13、jack 肩 11/12）；
  旁边显示当前角度/信号值，小号 mono 字体。
- 骨架用 requestAnimationFrame 绘制，读取 liveRef，不经过 React 重渲染。

【左栏 HUD】
- 动作名 24px；camera_side 胶囊；stage 徽章：准备（灰）/ 动作中（荧光绿，轻微呼吸）。
- 计数：display 字体 140~180px，tabular-nums；变化时 180ms 数字翻转。
- 组进度：第 1/3 组 · 本组 0/10 次；细进度条。
- 若 cycles_per_rep > 1：显示“本轮循环 1/2”（来自 counter 的 cycle_progress；后端可在 state 里加 cycle_progress）。
- 信号仪表：竖向 0~180（距离类用 0~3），标出 lo/hi 区间阴影；当前值圆点；
  lo/hi 数字标在轨道旁；让用户一眼看出“还差多少进入/还原”。
- **多条件动作（开合跳）不要只显示 `signal`**：`signal` 只是第一个条件（左肩角）。
  要显示 `values` 里的全部条件——左肩角 / 右肩角 / 脚距比，三个都达标才算一次；
  可做成一排三个迷你仪表或三行小进度，别让用户以为“手举起来就该计数”。

【右栏 HUD】
- 顶部评分环：最近一次动作的 score；中心分数，下面 grade；没有分数显示“—”，不要显示 0。
- 规则列表：每条 RuleRow：
  名称（tip 的前 8~12 字或规则名）、实测值/阈值、4px 条、状态点；
  状态：达标 mint、失败 coral、不可见灰、未参与判定暗灰。
  默认显示所有规则；超过 6 条时折叠为“全部 N 条”。
- 规则较多时右栏可滚动，但评分环固定顶部。
- 规则值每帧变化时不要做数字滚动，直接更新，避免刷屏。

【底部提示】
- 只显示 1 条最高优先级 hit；左侧 3px coral 竖条，深红底；文案 18px。
- 新 hit 出现时 160ms 上滑；hit 消失后保持 2 秒再撤（与桌面版“保持显示”一致）。
- 没有 hit 时显示当前最重要的正向提示：“动作标准，继续保持”或“保持呼吸”。
- 组进度条放在 TipBanner 上方，宽度与舞台一致。

【休息与结算】
- rest_start：舞台盖 85% 黑遮罩，琥珀色倒计时环，中央 30（display 字体）；
  文案“组间休息 · 下一组 2/3”；底部“放松肩颈，准备下一组”；呼吸圆 4s 循环。
  倒计时用服务端 rest_remaining 校准，前端本地每秒递减，收到 state 再校正。
- all_done：结算弹窗：
  - 大号 reps + “次”
  - 评分环 + grade
  - 组数/时长/检出率/错误次数
  - 错误清单（tip + 次数），最多 5 条
  - 今日目标进度条
  - “再来一组”（重置并重新开始）、“查看训练数据”（跳 /data）
  - 若 saved=false，显示“本次未写入历史”的原因，不要假装成功。
- 用户中途停止：先发 stop，等服务端 summary；若 3 秒没回，前端显示“已停止，历史可能未保存”。

【语音】
- 默认关闭；开启后使用 window.speechSynthesis：
  · 每次计数报数字，节流 1.2s；
  · 新 hit 优先报 tip，1.5s 节流；
  · 休息开始报“休息 30 秒”，结束报“开始下一组”，全部完成报“全部完成”。
- 先 cancel() 再 speak()，避免叠音；lang="zh-CN"，rate 1.05。
- 不支持时开关置灰，tooltip 说明“当前浏览器不支持中文语音”。

【键盘快捷键（答辩好用）】
- 空格：开始 / 停止（准备态开始，训练态停止）
- R：清零（发 reset）
- M：镜像
- V：语音
- F：全屏舞台
- Esc：退出全屏 / 关闭弹窗
在帮助弹窗里列出，不要藏在代码里。

【演示模式（必须做，答辩兜底）】
- 准备面板“用演示数据” → 抽屉列出 /api/samples：
  每项显示名称、动作、帧数、时长、备注（如“蹲到大腿平行”）。
- 选择后走 WS start_replay；服务端按 sample fps 推送 state；前端舞台显示深色网格 + 骨架动画，
  不显示视频；顶部加“合成数据回放”徽章。
- 演示模式不写历史；结算弹窗显示“演示数据，未写入历史”。
- 这是摄像头不可用时的唯一演示路径，必须稳定。

【错误与边界】
- 摄像头被拒绝：准备面板显示原因 + “重试” + “用演示数据”；不要弹 alert。
- 页面无人体：骨架变灰，顶部“未检测到人 · 请让全身入镜”，计数暂停（不要继续加数）。
- 后端离线：WS 重连 1 次；仍失败则显示“判定服务未启动”，并给出启动命令。
- 动作配置无效：开始前调 /api/actions/{id}，有 errors 时禁止开始并显示原因。
- 浏览器不支持 getUserMedia：提示用 Chrome/Edge，并给演示模式。
- 切后台再回来：重置 fps 统计，丢弃旧帧，不要补帧。

【验收（必须逐条自测）】
1. 1440×900 一屏不滚动；舞台 16:9 不变形。
2. 骨架与视频对齐（抬手、下蹲时关节贴合），镜像时也贴合。
3. 深蹲 3 次：计数为 3，阶段在准备/动作中之间切换，评分与桌面版同量级。
4. 故意浅蹲：出现“蹲得不够深”类提示，评分下降。
5. 开合跳：不会因为抬手/走路误计数；多条件门控生效。
6. 休息遮罩倒计时准确；下一组计数从 0 开始。
7. 停止后历史写入 /data 能看到；刷新页面数据仍在。
8. 演示模式跑 squat_standard 与 squat_shallow：3 次；分数分别接近 78.2 / 47.3。
9. 8 分钟内不内存泄漏（Chrome Performance 看 JS heap 稳定），视频不卡顿。
10. 不把 landmarks 放进 React state；训练中 React DevTools 不应每帧重渲染整页。

完成后输出：抽帧/背压策略、WS 消息处理、canvas 坐标映射、验收截图、已知限制。
```

---

## 9. Prompt F · 动作库与新建动作

```text
这一轮做 /actions、/actions/:id、/actions/new。核心目标：让“加动作只写配置、不改代码”这个考点在网页上看得见、摸得着。

【动作库 /actions】
- 页头：标题“动作库”，副标题“动作判定全部来自 configs/ · 新增动作不需要改代码”；
  右侧“新建动作”主按钮、“校验全部配置”次按钮。
- 顶部统计条：动作数、配置校验通过数、内置动作数；不要用大卡片，做成一排细指标。
- 动作网格：每行 3 张（1440），窄屏 2/1。
  卡片内容：
  · 自定义 SVG 线稿动作图标（深蹲/俯卧撑/开合跳各一个抽象姿态，1.5px 线，荧光绿点缀；不要用照片）；
  · 动作名 24px + id（mono，小号灰色）；
  · 标签：机位（正/侧）、信号类型（关节角度/多条件）、规则数；
  · 阈值摘要：如“140° ↓ · 155° ↑”；
  · 校验状态：通过（mint 点）/ 有问题（coral 点 + 数量）。
  · hover：1px 荧光绿描边 + 图标轻微上移，不做 3D 翻转。
- 空状态：如果 configs 为空，显示“还没有动作”+“新建动作”。
- 校验全部：调用 POST /api/actions/validate，结果用右侧 Drawer 展示每个文件的 errors/warnings；
  失败项可点击跳到详情。

【动作详情 /actions/:id】
- 顶部：动作名 + id + 校验状态 + “用这个动作训练”主按钮 + “查看 JSON”次按钮。
- 左栏（8 列）：
  · “判定逻辑”表格（人话）：
    信号 / 测量部位 / 进入阈值 / 计一次阈值 / 方向 / 最小计数间隔 / 确认时长 / 循环次数 / 校准开关。
  · “质量规则”列表：每条显示 tip、触发时机（全程/做完那一下）、判据（如“本轮最小角度 ≤ 105°”）、
    优先级（高/中/低）、ideal（如果配置有）；按 priority 降序。
  · 规则用可读句子，不要直接甩 JSON 字段名。
- 右栏（4 列）：
  · 一个静态人体骨架示意，标出该动作参与判定的关键点（用 33 点坐标画线，不需要真实比例）；
  · “配置摘要”小卡：文件路径、最后校验时间、warnings；
  · “原始 JSON”折叠区（mono 字体，可复制）。
- 如果 validation.errors 非空：顶部 coral 提示条 + 错误列表；主按钮“用这个动作训练”禁用。

【新建动作 /actions/new · 四步向导】
顶部步骤条：基本信息 → 判定信号 → 质量规则 → 校验保存。

第 1 步 基本信息：
- 动作名称（必填，中文）；
- 动作 ID（自动从名称生成，可手改；只允许字母数字下划线；重复时提示）；
- 机位（正/侧，卡片选择，配一句说明）；
- 校准开关（默认开；说明“只对角度变小类动作有效，如深蹲；开合跳请关闭”）；
- 循环次数（1~5；说明“几个完整往返算 1 次”）。
- 右侧一个小预览卡：动作名、机位、预计规则数。

第 2 步 判定信号：
- 测量部位：下拉/搜索，选项来自 action_editor 的 ANGLE_PARTS 与 PAIR_PARTS（按三点/两点分组）；
  选中后自动填 points，并显示“将使用关键点 23 / 25 / 27”。
- 信号类型：根据部位推荐（角度类/距离类），高级里可切换；
- 阈值：双滑块（不是两个独立输入框）：
  · 角度 0~180，距离 0~3.0；
  · 两个手柄标“进入动作”“计 1 次”；
  · 中间区间用荧光绿 12% 填充，标注“迟滞区”；
  · 方向选择“信号先变小（下蹲类）/ 先变大（举手类）”，滑块上的箭头随之改变；
  · 数值输入框与滑块双向绑定。
- 高级参数（默认折叠）：min_interval 0.4、enter_hold 0.06、exit_hold 0.06、min_active_duration 0.2；
  用“推荐值”标签，不要吓用户。
- 右侧静态示意：画三点角/两点距离，标出当前阈值；不需要真实摄像头。

第 3 步 质量规则（可选）：
- 提供 2 个模板卡片，勾选后展开：
  ① “动作幅度不够”：判据 valley_max（先变小）/ peak_min（先变大），阈值输入，提示语输入；
  ② “没回到起始位置”：判据 peak_min（先变小）/ valley_max（先变大），阈值输入，提示语输入。
- 每条规则可设优先级（高 80 / 中 60 / 低 40）与提示语（默认给一句人话）。
- 说明：更多规则可以保存后编辑 JSON；网页版先覆盖这两个最常用模板。
- 右侧显示“将生成 N 条规则”的预览。

第 4 步 校验保存：
- 点击“校验配置” → 调 POST /api/actions（或先本地拼装再 validate？以服务端为准）；
  服务端返回 errors/warnings 原样展示，不要改写错误文案。
- 成功：显示保存路径、warnings、配置 JSON 预览；按钮“完成并查看”跳详情，“再建一个”重置表单。
- 失败：停在当前页，标红出错字段（能对应就对应），并显示服务端错误列表。
- 禁止前端自己判断“配置合法”；最终以 validate_config 的结果为准。

【交互细节】
- 表单未保存离开时二次确认。
- 所有输入有 label、帮助文本、错误文本；不要只用 placeholder。
- 键盘：Enter 下一步，Esc 关闭弹窗；步骤条可点击回退（已填内容保留）。
- 保存成功后动作库与训练页的动作列表要刷新（invalidateQueries），不要求用户刷新页面。
- 不做“删除动作”（现有后端没有该能力）；如果后续加了 DELETE 接口，再做二次确认删除。

【验收】
1. 新建一个“靠墙静蹲”动作：选左膝角、阈值 120/150、勾选“幅度不够”，保存成功；
2. configs/ 下出现新 JSON；/actions 立刻多一张卡；/train 能选到它；
3. 故意把阈值方向填反，服务端返回错误，页面不保存；
4. 动作详情的人话表格与 JSON 能对上；
5. 1440 下三列卡片不拥挤，1280 下两列。
```

---

## 10. Prompt G · 训练数据

```text
这一轮做 /data。目标：把“训练历史与目标”这个模块做成能直接放答辩 PPT 的数据页，而不是一张丑陋的表格。

【信息结构】
页头：标题“训练数据”，副标题“按用户隔离 · 数据来自本地 JSON”；
右侧：动作筛选（全部 + 各动作）、时间范围（7/14/30 天，分段控件）、导出 CSV 次按钮。

1. KPI 行（4 个）：
   - 今日完成（today.reps / target，带细进度条）
   - 本周总次数（week.reps，带“N 次训练”）
   - 平均评分（avg_score，带 grade；没有数据显示“—”）
   - 累计训练（total_sessions 次）
   不要用四个大彩色卡片；用一条横向指标带，数字大、标签小、分隔线 1px。

2. 趋势区（两栏）：
   左（8 列）：每周训练量柱状图（weekly_trend）：
   - X 轴周起始（MM/DD），Y 轴次数；柱体荧光绿，圆角 2px；
   - 平均值虚线（灰），不要编“目标线”；
   - tooltip 显示“周起始 · N 次”；
   - 空数据：EmptyState + 去训练。
   右（4 列）：评分趋势折线（score_trend）：
   - 没有分数的天必须断开（connectNulls=false），不要连成 0；
   - Y 轴 0~100，画 60/75/90 三条淡参考线；
   - 点 hover 显示日期 + 分数；线用 cyan。

3. 错误排行（左 6 列）：
   - 横向条形图（Pareto 风格），按次数降序，最多 8 条；
   - 每条：tip（截断 18 字）+ 次数 + 占比条；颜色 coral 80% → 40%；
   - 点击一条 → 下方历史表按该错误过滤；
   - 没有错误：显示“最近没有检测到动作变形”，配一个 mint 勾。

4. 历史记录（右 6 列或全宽）：
   - 表格列：日期时间、动作、次数、组数、评分、时长、错误；
   - 评分用 Badge（优秀/良好/及格/待改进）；
   - 错误显示前 2 个 tip 的 chip，多余显示 +N；
   - 分页 10 条/页（后端 limit/offset）；排序默认时间倒序；
   - 行点击打开右侧 Drawer：完整字段 + 错误明细 + 该次动作的评分解释（如果能从 checks 拿到；
     拿不到就只显示分数，不要编）。
   - 空状态引导去训练。

【图表规范】
- 用 Recharts；容器高度 240~280；网格线只保留水平，颜色 #232833；
- 轴文字 12px #6C7686；不要 3D、不要阴影、不要渐变填充面积图（柱状可以轻微渐变）；
- 所有图表响应式；窗口 resize 不溢出；
- 动画 300ms 即可，切换筛选时不要重复入场动画。

【筛选与状态】
- 动作筛选、时间范围写入 URL query（?action=squat&days=14&tab=errors），刷新后保持；
- 用 TanStack Query 的 queryKey 包含筛选条件；
- 切换筛选时保留旧数据并显示细进度条（placeholderData），不要整页闪白；
- 后端错误：显示可重试的错误条；不要吞掉。

【导出】
- “导出 CSV”在前端把当前筛选结果拼 CSV；
- 加 UTF-8 BOM，Excel 打开中文不乱码；
- 文件名：训练数据_用户名_YYYY-MM-DD.csv；
- 不调用后端导出接口（避免新增未测试能力）。

【验收】
1. 有历史数据时，四个 KPI 与 /api/overview 一致；
2. 评分趋势没有数据的天断开，不显示 0；
3. 错误排行点击能过滤历史表；
4. 切换用户后数据整体变化（不要缓存上一个用户的数据）；
5. 空数据状态不报错、不显示 NaN；
6. 1280 下两栏变一栏，图表不横向滚动；
7. 导出 CSV 中文正常。
```

---

## 11. Prompt H · 用户、目标与设置

```text
这一轮做 /settings。目标：把多用户、每日目标、运行信息收在一个干净页面里，不抢训练页的戏。

【结构】
左侧二级导航（或顶部 tab）：个人档案 / 每日目标 / 关于与运行信息。

1. 个人档案：
- 当前用户大卡：头像缩写（取名字首字）、用户名、创建时间、身高/体重（有才显示）；
  右侧“切换用户”下拉 + “新建用户”按钮。
- 用户列表：每行 用户名、累计训练次数、今日次数、创建时间、当前徽章；
  行尾“切换”按钮；当前用户行左侧 2px 荧光绿竖条。
- 新建用户 Dialog：用户名（必填，去空格，不能重名）、身高 cm、体重 kg（可选）；
  提交后创建并切换，刷新总览与数据。
- 删除用户：危险区，红色文字按钮；二次确认 Dialog 必须显示“将删除该用户的档案、历史、目标，不可恢复”；
  只剩一个用户时按钮禁用并说明；删除当前用户后自动切到剩余第一个（以后端返回为准）。
- 说明文案：数据保存在 data/users/<用户名>/，视频帧不落盘。

2. 每日目标：
- 每个动作一行：动作名、今日已完成、目标输入（NumberStepper）、进度条、保存按钮；
- 保存调 PUT /api/goals/{action}；清除调 DELETE；保存后刷新总览；
- 目标为 0 表示未设置，显示“未设置目标”；
- 不要做“周目标”（后端只有每日目标）。

3. 关于与运行信息：
- 项目名、题目编号、技术栈、模型（MediaPipe Pose Landmarker lite / 本地部署 / CPU）、
  Python 与 mediapipe 版本（来自 /api/health）；
- 数据目录、配置文件目录、后端地址；
- “打开 API 文档”链接到 http://127.0.0.1:8000/docs；
- 隐私说明：摄像头帧仅在内存中推理，不保存视频；
- 口径说明（重要）：
  “动作判定阈值依据运动学几何与 ACE/NASM 规范给出工程初值，尚未完成真人视频回归校准；
   系统支持按用户体型与机位重新标定。”
  这段话直接来自项目 CLAUDE.md，不要改写成“高精度”。

【验收】
1. 新建“测试用户” → 切换成功 → 总览数据变为该用户（空状态）→ 切回原用户数据恢复；
2. 设置深蹲目标 50 → 总览目标环更新；
3. 删除用户有二次确认，最后一个用户不能删；
4. 刷新页面当前用户不变；
5. 关于页版本号与 /api/health 一致；
6. 页面没有“即将上线”之类假按钮。
```

---

## 12. Prompt I · 联调、验收与演示

```text
这一轮不加新功能，只做联调、修补和验收。目标：网页版能稳定跑完一套答辩流程。

【A. 功能对齐清单（逐条打勾）】
1. 动作列表来自 configs/，3 个内置动作都能选；
2. 新建动作保存后，动作库与训练页立刻出现，不用刷新；
3. 深蹲/俯卧撑/开合跳都能计数；开合跳不会抬手就误计数；
4. 质量提示与 configs 里的 tip 一致；高优先级先显示；
5. 评分 0~100 与 grade 分档正确（<60 待改进，60 及格，75 良好，90 优秀）；
6. 分组/休息倒计时正确；组完成后进入下一组；
7. 停止后写入历史；/data 能看到；刷新仍在；
8. 每日目标保存后，总览与结算弹窗同步；
9. 多用户切换后，历史/目标/总览按用户隔离；
10. 演示模式（samples）能跑，且不写历史；
11. 键盘快捷键可用；
12. 所有错误态都有中文说明和下一步操作。

【B. 一致性验收（最重要）】
用演示模式依次跑以下 samples，把网页结果与预期对齐：
| 文件 | 动作 | 预期次数 | 预期分数 |
|---|---|---|---|
| squat_standard.json | 深蹲 | 3 | 78.2 |
| squat_shallow.json | 深蹲 | 3 | 47.3 |
| squat_knee_fwd.json | 深蹲 | 3 | 54.6 |
| pushup_standard.json | 俯卧撑 | 3 | 88.3 |
| pushup_sag.json | 俯卧撑 | 3 | 64.3 |
| jack_standard.json | 开合跳 | 3 | 100.0 |
| jack_low_hands.json | 开合跳 | 3 | 48.0 |
| squat_minimal.json | 深蹲 | 3 | 75.8 |
（分数以 samples/README.md 为准，允许 0.1 舍入差；如果当前代码输出不同，先查代码版本，不要改阈值凑数。）
如果网页结果和预期不一致，按这个顺序排查：
1) replay 是否误做了基线校准（必须关闭）；
2) 时间轴是否用 i/fps，而不是墙上时间；
3) 是否把缺失关键点的 visibility 当成 1；
4) 是否用了另一份 configs；
5) 是否在 state 里丢了某条规则。
把这 8 条跑通，网页版与桌面版的判定就一致了。

【C. 性能验收】
- 实时页 1440×900：预览 ≥ 30fps（视频本身），WS state ≥ 10fps；
- 输入到画面反馈 < 300ms（本地）；
- Chrome Performance：训练 2 分钟，无长任务 > 50ms 的连续堆积；
- JS heap 稳定，不随时间线性增长；
- 服务端 CPU 单核 < 70%，内存 < 500MB；
- 首屏（localhost）< 2s，字体不闪烁。

【D. 错误态清单】
- 后端没启动；模型加载失败；摄像头拒绝；无人体；画面太暗；关键点不可见；
- 动作配置无效；历史写入失败；用户删除失败；WS 断开；帧超时；
每个状态都要有：发生了什么、为什么、下一步点哪里。禁止 alert / 空白页 / 无限 spinner。

【E. 视觉验收】
- 1440×900、1280×800、1024×768 三档截图；
- 无横向滚动；无文字截断；无遮挡；
- 只有一种主强调色；红色只用于错误；
- 数字是第一视觉层级；页面不像默认 Tailwind；
- 空状态有设计；加载有 skeleton；错误有引导；
- 中文不出现方框、乱码、行高拥挤。

【F. 可访问性】
- 所有按钮可 Tab 到，focus-visible 清晰；
- 图表有文字摘要（aria-label 或旁边列出关键数字）；
- 训练提示用 aria-live="polite"（计数不要每帧播报）；
- prefers-reduced-motion 下关闭数字翻转和呼吸动画；
- 对比度达到 WCAG AA。

【G. 代码与仓库】
- npm run build 通过；tsc --noEmit 通过；eslint 无 error；
- 不提交 node_modules、dist、.env.local；更新 .gitignore；
- 现有 Python 测试仍全绿；git diff 不包含算法文件；
- 每个阶段一个中文 commit（例：web: 实时训练页接入 WebSocket 与骨架叠加）。

【H. 答辩演示脚本（3 分钟，写进 README）】
0:00 总览：今日次数、目标、后端在线；一句话“判定全部由 Python 配置解释器完成”。
0:30 动作库：打开深蹲详情，指出 7 条质量规则是配置不是代码；展示新建动作向导最后一步的校验。
1:10 实时训练：用摄像头做 3 个深蹲；指出计数、阶段、评分、实时提示、组间歇。
1:50 演示模式：跑 squat_shallow，分数从 78 掉到 47，提示“蹲得不够深”，证明判定不是演的。
2:30 数据页：趋势、评分、错误排行；多用户切换。
2:50 收尾：新增动作只写一份 JSON，0 行代码改动。
准备 Plan B：摄像头不可用时直接进演示模式，不要现场调权限。

【交付】
输出一份 web/README.md：
- 环境要求、安装、启动（两个终端）、端口、演示模式入口；
- 3 分钟演示脚本；
- 已知限制（单会话、12fps、localhost 摄像头、阈值未做真人校准）；
- 截图 4 张（总览/训练/动作库/数据）。
```

---

## 13. 出问题时的修复提示词

把下面每条单独粘给 TRAE；一次只修一个问题，修完让它给出验证方法。

### 13.1 页面“AI 味”太重 / 像默认模板

```text
现在页面看起来像默认 Tailwind 后台模板，不符合“FORM LAB”的视觉方向。请只改视觉，不改功能：
1. 去掉所有紫蓝渐变、玻璃拟态、彩色大阴影；
2. 强调色只保留荧光绿 #D6FF3F，红色只用于错误；
3. 所有卡片改为 surface-1 + 1px #232833 描边，圆角 14，不用阴影；
4. 大数字改用 Bebas Neue，中文标题用系统字体，数字 tabular-nums；
5. 页面背景 #060709，加 2.5% 噪点与极淡的右上角荧光绿径向光；
6. 删掉 emoji 图标，统一 lucide-react 1.5px 线条；
7. 实时页只保留“计数/倒计时/骨架”三类动效，其余全部静态。
改完给我 1440×900 截图，并说明改了哪些文件。
```

### 13.2 骨架和视频对不上 / 镜像后错位

```text
骨架叠加错位。请按以下顺序排查并修复，不要靠调 magic number：
1. 抽帧是否按视频原始宽高比缩放到最长边 640（不裁剪、不拉伸）？
2. canvas 是否按容器 CSS 尺寸 × devicePixelRatio 设置，并在 resize 时重算？
3. 视频 object-fit 是 contain 还是 cover？如果是 contain，映射公式必须考虑上下/左右留黑：
   scale = min(displayW / videoW, displayH / videoH)
   offsetX = (displayW - videoW * scale) / 2
   offsetY = (displayH - videoH * scale) / 2
   x = offsetX + lm.x * videoW * scale
   y = offsetY + lm.y * videoH * scale
4. 镜像时是否在绘制前做了 x' = 1 - x（只镜像骨架，不镜像文字）？
5. 是否把 landmarks 的归一化坐标直接当 CSS 像素用了？
请写一个 3 个已知点的单元测试（含镜像、含 letterbox），通过后再看画面。
```

### 13.3 网页计数和桌面版不一致

```text
网页计数与桌面版不一致。先不要调阈值，按“同一份数据、同一套逻辑”排查：
1. 用演示模式跑 samples/squat_standard.json，预期 3 次 / 78.2 分；把实际 state 序列打印出来；
2. 确认 replay 没有做基线校准（replay 必须跳过校准）；
3. 确认时间轴用 i / fps，而不是 Date.now()；
4. 确认传入 pose_logic 的坐标是像素坐标，不是 0~1 归一化坐标；
5. 确认缺失关键点的 visibility 是 0，不是 1；
6. 确认加载的是 configs/ 下的同一份 JSON，且没有被缓存成旧配置；
7. 对比桌面版 `python pose_player.py --data samples/...` 的输出。
把每一步的实际值贴出来，定位到具体差异后再改。
```

### 13.4 越跑越卡 / 延迟越来越大

```text
实时页越跑越卡、延迟累积。请检查并修复：
1. 是否严格“单帧在途”：发送后 pending=true，收到同 frame_id 的 state 才发下一帧？
2. 服务端是否在上一帧未处理完时直接丢新帧，而不是排队？
3. 是否把每一帧的 landmarks/checks 放进了 React state，导致整页每帧重渲染？
   改为：数据进 useRef，canvas 用 requestAnimationFrame 读；React 只接收 count/stage/score/hits 的变化。
4. 是否每帧都 new MediaPipe / 重新加载模型？模型必须全局单例。
5. 是否每帧都创建 canvas / 不释放 ImageBitmap？
6. video 元素是否同时被 CSS 和 canvas 重复绘制？
修复后给出 2 分钟的 FPS / heap / latency 曲线。
```

### 13.5 摄像头打不开

```text
摄像头无法打开。请按顺序处理，不要只弹 alert：
1. 是否在 localhost 或 HTTPS 下？（http://192.168.x.x 下 getUserMedia 会被浏览器禁用）
2. 是否先调用 enumerateDevices 再 getUserMedia？权限未授予时 label 为空是正常的；
3. 是否处理了 NotAllowedError / NotFoundError / NotReadableError，并给出中文原因与“重试/演示模式”；
4. 切换设备时是否先 stop 旧 track 再开新流？
5. 页面卸载时是否 stop 所有 track、关闭 WS？
6. 是否在准备面板提供了“用演示数据”兜底？
写出每种错误的文案与下一步操作，并在 Chrome/Edge 各测一次。
```

### 13.6 中文乱码 / 字体变方框

```text
中文显示异常。请检查：
1. index.html 是否 <meta charset="UTF-8">；
2. 字体栈是否包含 "MiSans", "HarmonyOS Sans SC", "PingFang SC", "Microsoft YaHei"；
3. 是否用了 Bebas Neue 渲染中文（Bebas 没有中文字形，只能用于数字/英文）；
4. API 返回是否 UTF-8；FastAPI JSONResponse 不要额外编码；
5. CSS 是否设置了不合适的 letter-spacing 导致中文挤压。
改完截图总览、训练、数据三页。
```

### 13.7 后端 500 / ModuleNotFoundError

```text
后端启动报 ModuleNotFoundError 或 500。请检查：
1. 是否用项目根目录启动：python -m uvicorn web.backend.app:app --port 8000；
2. sys.path 是否加入了项目根目录（Path(__file__).resolve().parents[2]）；
3. 读 configs/、data/、samples/ 是否用了项目根绝对路径，而不是 CWD；
4. UserStore 是否显式传 data/users 绝对路径；
5. pose_landmarker_lite.task 是否存在；mediapipe 是否 0.10.35；
6. ws 路由是否注册在 app 上，Vite proxy 是否带 ws:true。
把完整 traceback 贴出来再改，不要用 try/except 吞掉。
```

### 13.8 图表把“没有数据”画成 0

```text
评分趋势里没有数据的天被画成了 0，误导成“那天很差”。请改：
1. 后端 score_trend 对无数据返回 null，不要返回 0；
2. 前端 Recharts connectNulls={false}；
3. Y 轴 domain [0,100]，但 null 不画点；
4. tooltip 对 null 显示“无记录”；
5. 空数据整体显示 EmptyState，不要画一条贴底直线。
```

### 13.9 TRAE 擅自重写了 Python 核心

```text
停止。不要修改 pose_logic.py / training_manager.py / action_editor.py / validate_config.py。
请回退这些文件的改动（git checkout -- 对应文件），只在 web/ 下新增适配代码。
如果现有函数不够用，先在回答里说明缺什么、为什么不能在前端补，等我确认后再动。
```

---

## 14. 赶时间版：一条到底提示词（不推荐，但可用）

> 如果你只想粘一次，用下面这条。生成后仍然要按第 12 节验收；复杂页面大概率需要二次修。

```text
在现有 Python 项目（第 11 题 健身动作计数与姿态纠正）中新增 web/ 网页版，保留所有现有 Python 代码与判定逻辑。

必读：CLAUDE.md、pose_logic.py、configs/*.json、training_manager.py、action_editor.py、validate_config.py、samples/README.md。

架构：
React 18 + TS + Vite + Tailwind + React Router + TanStack Query + Zustand + Framer Motion + Recharts + lucide-react；
FastAPI 适配层 + WebSocket；浏览器摄像头抽帧 640px/10~12fps → 后端 MediaPipe 0.10.35 VIDEO 模式 →
pose_logic.Action → 返回 landmarks + 计数/阶段/判定/评分；所有判定必须调用现有 Python，禁止前端重写。

页面：
1) / 总览：今日次数+目标环、本周柱状图、最近训练、错误排行、后端状态；
2) /train 实时训练：准备面板（摄像头/镜像/语音/分组/目标）、视频+canvas 骨架、巨大计数、
   阶段徽章、评分环、规则明细、信号仪表、TipBanner、休息倒计时、结算弹窗、samples 演示模式、快捷键；
3) /actions 动作库 + /actions/:id 详情 + /actions/new 四步向导（部位预设、双阈值迟滞滑块、质量规则模板、服务端校验）；
4) /data 数据：KPI、周趋势、评分折线（null 断开）、错误排行、历史表、CSV 导出；
5) /settings 用户/目标/关于。

视觉：
暗色“FORM LAB”——#060709 底、#D6FF3F 荧光绿唯一主强调、1px 描边、14px 圆角、Bebas Neue 大数字、
中文系统字体、无紫蓝渐变、无 emoji 图标、无玻璃拟态堆叠；像运动科学仪器，不像 SaaS 模板。
1440×900 一屏不滚动；实时页骨架与视频精确对齐；训练中只动计数/倒计时/骨架。

硬约束：
只新增 web/；不改算法文件；不升级 mediapipe；所有数字来自 API；演示模式走 samples；
视频帧不落盘；中文 UI；TS strict 禁止 any；不做登录/云同步/录像。

交付：
web/README.md、start_web.ps1、后端 pytest（含 samples 回放断言 3 次/78.2 等）、
npm run build 通过、4 张截图、3 分钟演示脚本。
按“骨架 → 视觉系统 → 后端接口 → 总览 → 实时训练 → 动作库 → 数据 → 设置 → 验收”的顺序做，
每步先说明计划再改代码，每步结束给出改动文件与验证命令。
```

---

## 附录 A · API / WebSocket 契约（速查）

### A.1 TypeScript 类型

```ts
export type Stage = "ready" | "active";
export type Grade = "优秀" | "良好" | "及格" | "待改进" | "—";

export interface CheckItem {
  name: string;
  tip: string;
  value: number | null;
  limit: number | null;
  ok: boolean;
  visible: boolean;
  checked: boolean;
  priority: number;
  score: number | null;
}

export interface Landmark {
  x: number; // 0~1
  y: number; // 0~1
  z: number;
  v: number; // visibility 0~1；0 = 缺失
}

export interface SetStatus {
  current_set: number;
  total_sets: number;
  reps_in_set: number;
  reps_per_set: number;
  total_reps: number;
  rest_remaining: number;
  finished: boolean;
}

export interface CalibrationStatus {
  status: "idle" | "sampling" | "done" | "skipped";
  baseline: number | null;
  progress: number; // 0~1
}

export interface Session {
  time: string;
  date: string;
  action: string;
  reps: number;
  sets: number | null;
  errors: Record<string, number>;
  duration_sec: number | null;
  source: string | null;
  score: number | null;
}

export interface StateMessage {
  type: "state";
  seq: number;
  frame_id: number | null;
  ts: number;
  count: number;
  stage: Stage;
  signal: number | null;
  values: Array<number | null> | null; // 单条件=1 个；多条件=全部条件
  cycle_progress: number;              // cycles_per_rep>1 时显示
  score: number | null;
  grade: Grade;
  checks: CheckItem[];
  hits: CheckItem[];
  landmarks: Landmark[];
  person: boolean;
  calibration: CalibrationStatus;
  sets: SetStatus;
  metrics: { fps: number; latency_ms: number; infer_ms: number; dropped?: boolean };
}
```

### A.2 最小状态机（前端）

```
idle
  └─ 点击开始 → requesting（申请摄像头）
        ├─ 拒绝 → error(permission) → 可重试 / 演示
        └─ 成功 → connecting（WS）
              └─ ready → calibrating（需要校准）
                    ├─ 校准完成 → live
                    └─ 跳过 → live
live
  ├─ rest_start → resting → rest_end → live
  ├─ all_done → finished（结算）
  └─ stop → stopping → finished
replay：connecting → live（无摄像头、无校准）→ finished
```

### A.3 判定字段的 UI 语义

| 字段 | 含义 | UI 表现 |
|---|---|---|
| `visible=false` | 关键点没拍全，规则**不判** | 灰色“画面不全”，不要标红 |
| `checked=false` | 当前阶段不判（如 on_rep 只在计数帧判） | 暗灰，标注“完成时判定” |
| `ok=false` + visible + checked | 真的不达标 | 红色 + tip |
| `value=null` | 没有可用的实测值 | 显示“—”，不要显示 0 |
| `limit` | 阈值 | 显示“实测 / 阈值” |
| `score` | 该规则 0~100 | 细条或小数字；没有就“—” |

---

## 附录 B · 设计 token 速查

```
背景      #060709 / #0B0D11
卡片      #101318 / #151922 / #1B202A
描边      #232833 / #2E3542
文字      #F5F7FA / #A3ACBA / #6C7686
主强调    #D6FF3F（荧光绿）
数据      #6FE3FF（cyan）
休息      #FFB454（amber）
错误      #FF6B5C（coral）
成功      #45E0A8（mint）
圆角      10 / 14 / 18 / 20 / 999
间距      8 / 12 / 16 / 20 / 24 / 32 / 40 / 56 / 72
动效      120ms hover / 180ms 数字 / 220ms 弹窗 / ease(.2,.8,.2,1)
字体      数字 Bebas Neue；中文 MiSans/PingFang/微软雅黑；等宽 Space Grotesk
```

**一屏最多两种强调色。** 红色只出现在“确实不合格/危险操作”，不要拿来当装饰。

---

## 附录 C · 33 关键点与三个内置动作

### C.1 常用关键点

| 编号 | 名称 | 编号 | 名称 |
|---|---|---|---|
| 0 | 鼻子 | 11 / 12 | 左肩 / 右肩 |
| 13 / 14 | 左肘 / 右肘 | 15 / 16 | 左腕 / 右腕 |
| 23 / 24 | 左髋 / 右髋 | 25 / 26 | 左膝 / 右膝 |
| 27 / 28 | 左踝 / 右踝 | 29 / 30 | 左脚跟 / 右脚跟 |
| 31 / 32 | 左脚尖 / 右脚尖 | | |

### C.2 骨架连线（canvas 用）

```
[11,12], [11,13], [13,15], [12,14], [14,16],
[11,23], [12,24], [23,24],
[23,25], [25,27], [24,26], [26,28],
[27,29], [29,31], [28,30], [30,32], [31,32]
```

### C.3 三个内置动作（来自 configs/）

| 动作 | id | 机位 | 计数信号 | 阈值 | 规则数 | 校准 |
|---|---|---|---|---|---|---|
| 深蹲 | `squat` | 侧 | 左膝角（髋-膝-踝，23/25/27） | lo 140 / hi 155 | 7 | 开 |
| 俯卧撑 | `pushup` | 侧 | 左肘角（肩-肘-腕，11/13/15） | lo 140 / hi 160 | 7 | 开 |
| 开合跳 | `jumping_jack` | 正 | 左/右肩角 + 两踝水平距/肩宽，三条件 AND | on 75/75/0.95；off 45/45/0.75 | 4 | 关 |

深蹲的 7 条规则：蹲得不够深、右腿幅度不足、站起没伸直、右腿没伸直、膝前移、躯干小腿失配、上身前倾。
俯卧撑的 7 条：塌腰（共线）、右体线、下压不够深、右臂不够深、手臂没伸直、右臂没伸直、双臂不同步。
开合跳的 4 条：左手没举高、右手没举高、腿没张开、双臂不同步。

**这些数字只用于 UI 展示；实际判定以后端返回为准。**

---

## 附录 D · 模块—页面—接口对照（写报告可直接用）

| 任务书模块 | 现有实现 | Web 页面 | Web 接口 | 说明 |
|---|---|---|---|---|
| 1 人体关键点实时检测 | MediaPipe Pose Landmarker | `/train` | `WS /ws/train` | 后端 VIDEO 模式 |
| 2 自定义健身姿势 | 配置格式 + `pose_logic` 解释器 | `/actions/new`、`/actions/:id` | `POST /api/actions` | 核心考点 |
| 3 动作状态机与计数 | `RepCounter` | `/train` 左栏 | WS `state.count/stage` | 迟滞/hold/min_interval |
| 4 动作质量判定 | `QualityChecker` | `/train` 右栏 | WS `state.checks/hits` | 周期极值/可见性/优先级 |
| 5 内置动作库 | `configs/*.json` | `/actions` | `GET /api/actions` | 3 个动作 |
| 6 实时提示与语音播报 | `hits` + `say`（macOS） | `/train` | WS `hits` + Web Speech | Windows 上浏览器语音是加分项 |
| 7 训练组与间歇 | `SetManager` | `/train` 休息遮罩 | WS `sets/event` | 组完成/休息/全部完成 |
| 8 训练历史与目标 | `History` + `Goals` | `/data`、`/settings` | `/api/overview`、`/api/goals` | 趋势图用 Recharts |
| 9 视频回放与错误片段 | 原项目未做录像 | `/train` 演示模式 | `WS start_replay` | **只做关键点回放，不冒充录像模块** |
| 10 个人档案与多用户 | `UserStore` | `/settings` | `/api/users` | 数据按用户分目录 |

> 报告口径：网页版的“演示模式”是**关键点数据回放**，用于验证判定链路与答辩兜底；
> 它不等同于任务书模块 9 的“训练录像 + 错误片段标记”。模块 9 仍按原项目“范围选择未做”如实说明。

---

## 附录 E · samples 预期结果（验收基准）

| 文件 | 动作 | 情形 | 预期次数 | 预期分数 |
|---|---|---|---|---|
| `squat_standard.json` | 深蹲 | 蹲到大腿平行（膝角约 95°） | 3 | 78.2 |
| `squat_shallow.json` | 深蹲 | 只蹲到 135° | 3 | 47.3 |
| `squat_knee_fwd.json` | 深蹲 | 膝盖大幅前移 | 3 | 54.6 |
| `pushup_standard.json` | 俯卧撑 | 下压到肘角约 95° | 3 | 88.3 |
| `pushup_sag.json` | 俯卧撑 | 下压到位但塌腰 | 3 | 64.3 |
| `jack_standard.json` | 开合跳 | 手过头、脚张开 2.2 倍肩宽 | 3 | 100.0 |
| `jack_low_hands.json` | 开合跳 | 手只抬到肩高 | 3 | 48.0 |
| `squat_minimal.json` | 深蹲 | 只给 3 个关键点的最简数据 | 3 | 75.8 |

这些是 `samples/README.md` 记录的实际运行值。网页版必须能复现；如果复现不了，**先查链路，不要调阈值**。

---

## 附录 F · 目录与启动（Windows）

```
web/
  backend/
    app.py
    settings.py
    schemas.py
    routers/{actions,users,training,pose}.py
    services/{pose_engine,session,replay}.py
    tests/{test_api.py,test_replay.py}
  frontend/
    src/
      app/{router.tsx,layout.tsx,providers.tsx}
      components/{ui,live}
      features/{dashboard,live,actions,data,settings}
      lib/{api.ts,ws.ts,format.ts,landmarks.ts,canvas.ts}
      stores/{app.ts,live.ts}
      styles/index.css
    index.html
    vite.config.ts
    package.json
  README.md
  start_web.ps1
```

启动（两个终端）：

```powershell
# 终端 1：后端
cd "C:\Users\admin\Desktop\软件工程理论基础\选题 2\选题 2"
.venv\Scripts\python -m uvicorn web.backend.app:app --host 127.0.0.1 --port 8000

# 终端 2：前端
cd "C:\Users\admin\Desktop\软件工程理论基础\选题 2\选题 2\web\frontend"
npm install
npm run dev
# 打开 http://localhost:5173
```

> 如果 `.venv` 是 macOS 上建的，Windows 下按 `WINDOWS_运行说明.md` 重建环境；
> 网页后端与桌面版共用同一个 Python 环境和同一个 `mediapipe==0.10.35`。
> 摄像头只在 `localhost` 或 HTTPS 下可用；用局域网 IP 打开时，浏览器会禁用 `getUserMedia`。

---

## 附录 G · 每轮给 TRAE 的固定结尾

每轮提示词末尾都可以加这三句，能显著减少“跑偏”：

```text
开始前先用 5 句话说明你准备怎么做、会改哪些文件；如果我描述与现有代码冲突，先停下来指出。
完成后必须给出：改动文件清单、启动/测试命令、实际自测结果、未完成项。
不要修改 web/ 之外的文件（除非我明确说可以）；不要重写现有 Python 判定逻辑。
```

---

## 最后：三条底线

1. **漂亮不能靠假数据。** 数字、图表、提示都必须来自 Python 后端；没有数据就空着，空状态也要好看。
2. **实时页不是普通页面。** 视频、骨架、计数、提示、倒计时必须一屏协同；不要让它滚来滚去。
3. **答辩要能兜底。** 摄像头一旦不配合，3 秒内切到 samples 演示模式，仍然能讲完整条“配置 → 状态机 → 判定 → 数据”的链路。

