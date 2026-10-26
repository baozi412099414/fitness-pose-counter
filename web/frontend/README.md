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

要求 Node.js 18+。

```bash
cd web/frontend
npm install
npm run dev
```

打开：

- 设计规范页：<http://localhost:5173/styleguide>
- 业务首页：待开发

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
| `VITE_USE_MOCK` | `true` / `false` | `true` | REST 数据层是否走 `src/mocks/`（`VITE_USE_MOCK !== "false"` 即 mock） |
| `VITE_TRAIN_MODE` | `mock` / `live` | `mock` | 实时训练传输层：`mock` 本地计时 + `samples/` 回放；`live` 走 WebSocket `/ws/train` |

> 答辩前切换为真实接口：`VITE_USE_MOCK=false` + `VITE_TRAIN_MODE=live`，并保证后端 `uvicorn web.backend.app:app` 已启动。

## 实时训练传输层与 WebSocket 契约

`/train` 页面通过 `TrainTransport` 接口（`src/features/train/trainTransport.ts`）消费数据，
`useTrainSession` 与页面组件不感知实现是 mock 还是 live：

- `mockTrainTransport.ts`：本地计时 + `samples/*.json` 回放（默认）。
- `liveTrainTransport.ts`：WebSocket `/ws/train` 客户端（`VITE_TRAIN_MODE=live` 时启用，经 Vite 的 `/ws` 代理到 `127.0.0.1:8000`）。
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
- `VITE_TRAIN_MODE` 是全局开关：设为 `live` 时，回放模式同样走 WebSocket（`start_replay`）。
- live 抓帧（12fps / 640px JPEG）尚未与真后端联调，帧率、分辨率与消息时序以接入 C 后实测为准。

## 备注

- `node_modules/`、`dist/`、`.vite/` 已在根 `.gitignore` 中忽略。
- 视频帧只在浏览器与后端内存中处理，不落盘。
- 动作判定阈值是工程初值，尚未完成真人视频回归校准；页面上不要出现“准确率 99%”“已校准”等表述。
