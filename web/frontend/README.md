# FORM LAB · 网页版前端

《软件工程基础》课程设计 · 第 11 题「健身动作计数与姿态纠正」的 Web 前端。

当前进度：**视觉系统 + `/styleguide` 已完成**；总览、实时训练、动作库、训练数据、设置等业务页面待开发。

## 技术栈

- React 18.3 + TypeScript 5.6
- Vite 5.4
- Tailwind CSS 3.4
- React Router 6
- Framer Motion
- lucide-react
- 字体：`@fontsource/bebas-neue`、`@fontsource/space-grotesk`（本地依赖，不依赖 Google Fonts）

> 版本刻意锁定在 React 18 / Vite 5 / Tailwind 3.4，不使用最新大版本，避免配置方式变化导致返工。

## 启动

要求 Node.js 18+。**实时训练**还要先起 Python 判定服务（`web/backend`），
回放模式不需要。

```bash
# 终端 1：判定服务（项目根目录）
python -m uvicorn web.backend.app:app --host 127.0.0.1 --port 8000

# 终端 2：前端
cd web/frontend
npm install
npm run dev
```

> 两个进程都起好了以后，打开 <http://localhost:5173> 就能用「训练 → 实时」；
> 也可以直接双击项目根目录的 `start_web.command`（macOS）。

打开：

- 业务首页：<http://localhost:5173>
- 设计规范页：<http://localhost:5173/styleguide>

构建与类型检查：

```bash
npm run build      # tsc --noEmit + vite build
npm run typecheck  # 只做类型检查
```

## 目录结构

```text
web/frontend/
  src/
    app/
      styleguide/          # 设计系统自检页
    components/
      ui/                  # 基础组件（Button/Card/Stat/RuleRow/Dialog...）
      live/                # 实时训练页专用组件（待开发）
    lib/
      cn.ts                # clsx + tailwind-merge
    styles/
      globals.css          # 颜色 token、字体、噪点、焦点、滚动条
    App.tsx
    main.tsx
  tailwind.config.ts       # token → Tailwind 主题
  vite.config.ts           # @ 别名、/api 与 /ws 代理（待接入后端）
```

## 设计系统

- 设计概念：**FORM LAB / 形实验室** —— 运动科学仪器 × 专业相机取景器 × F1 遥测。
- 暗色底：`#060709`；主强调色：荧光绿 `#D6FF3F`；错误：coral `#FF6B5C`；休息：amber `#FFB454`；数据：cyan `#6FE3FF`。
- 颜色以 RGB 通道变量定义在 `src/styles/globals.css`，Tailwind 里用 `rgb(var(--accent-rgb) / <alpha-value>)`，因此支持 `bg-accent/10` 这类透明度写法。
- 大数字用 Bebas Neue；中文用 MiSans / PingFang / 微软雅黑系统栈；等宽用 Space Grotesk。
- 一屏最多两种强调色；红色只用于错误/危险操作。

完整 token、组件状态和按钮/表单/规则行/弹窗示例，见 `/styleguide`。

## 状态与接口约定

- 业务页面的数据按 `docs/网页版前端_TRAE提示词.md` 中的 REST/WebSocket 契约接入。
- 所有计数、质量判定、评分、历史、目标、多用户逻辑由 Python 后端提供，前端不重写判定算法。

### 环境变量开关

| 变量 | 取值 | 默认 | 说明 |
|---|---|---|---|
| `VITE_USE_MOCK` | `true` / `false` | `false`（走真后端） | 设 `true` 时数据层退回 `src/mocks/`（只看界面、不启动 Python 时用）；训练页的实时识别不受它影响 |
| `VITE_TRAIN_MODE` | `mock` / `live` / 不设 | 不设 | **强制**两种模式都走某个传输层；不设时按页面模式自动选（实时→WebSocket，回放→本地 mock） |

> 当前状态：训练页的「实时」接真后端（抓帧 → `/ws/train` → MediaPipe → pose_logic）；
> 总览 / 数据 / 设置走 `/api` 读真实数据（用户、训练记录、目标都在 `data/users/` 下）。
> **动作库**三个接口（列表/详情/校验/新建）暂时仍用 `src/mocks/` —— 判定配置的展示字段
> 还需要一层翻译，等那部分接好再切。

## 实时训练传输层与 WebSocket 契约

`/train` 页面通过 `TrainTransport` 接口（`src/features/train/trainTransport.ts`）消费数据，
`useTrainSession` 与页面组件不感知实现是 mock 还是 live：

- `mockTrainTransport.ts`：本地计时 + `samples/*.json` 回放，用于「回放」模式（不依赖后端）。
- `liveTrainTransport.ts`：WebSocket `/ws/train` 客户端，用于「实时」模式（经 Vite 的 `/ws` 代理到 `127.0.0.1:8000`）。
  live 模式会从 `<video>` 按 12fps 抓 640px JPEG 帧，通过 `frame` 消息发送；`start.user` 取当前用户显示名。

后端 `/ws/train` 的消息契约（字段以 `src/features/train/contract.ts` 为准，即 Prompt C §6 + 附录 A）：

```text
客户端 → 服务端：
  {"type":"start","action_id":"squat","user":"演示用户","sets":3,"reps_per_set":10,"rest_seconds":30}
  {"type":"frame","frame_id":123,"image":"data:image/jpeg;base64,..."}
  {"type":"start_replay","sample_id":"squat_standard","action_id":"squat","record_history":false}
  {"type":"reset"}
  {"type":"stop"}

服务端 → 客户端：
  {"type":"ready","session_id":"...","mode":"camera"|"replay","action":{"id","name","camera_side"},"calibration":{"needed":bool}}
  {"type":"state",...checks/landmarks/score/grade/person/calibration/sets/metrics...}
  {"type":"event","event":"set_done"|"rest_start"|"rest_end"|"all_done"|"calibrated",...}
  {"type":"summary","reps","score","grade","duration_sec","errors","error_tips",...}
  {"type":"error","code":"NO_PERSON"|"MODEL_ERROR"|"BAD_FRAME"|"BUSY","message":"..."}
```

前端只负责画 keypoints、展示后端返回的 `count / checks / score`，不在前端重写判定逻辑。

## 已知限制

- 传输层无自动重连与指数退避：`/ws/train` 断开后仅报错并回到 idle，需用户手动重开。
- `skip_rest` 客户端消息尚未支持：live 模式下「跳过休息」按钮已禁用，回放模式不受影响。
- live 的 `start.reps_per_set` 暂取样本 `sample.count`，与真后端的目标次数/组数尚未完全对齐。
- `VITE_TRAIN_MODE=live` 时是全局开关：回放模式也会走 WebSocket（`start_replay`），需要后端在。
- 同一时间只支持一路实时训练；第二个连接会被后端以 `BUSY` 拒绝（MediaPipe 实例不是线程安全的）。
- 实时页从浏览器 `getUserMedia` 取流，可选设备（含 iPhone 连续互通相机），首次拿到设备列表后会优先自动切到 iPhone；
  iPhone 未出现在列表里时按页面提示检查「连续互通相机」，无线连接在本机容易掉线，演示建议插数据线。

## 备注

- `node_modules/`、`dist/`、`.vite/` 已在根 `.gitignore` 中忽略。
- 视频帧只在浏览器与后端内存中处理，不落盘。
- 动作判定阈值是工程初值，尚未完成真人视频回归校准；页面上不要出现“准确率 99%”“已校准”等表述。
