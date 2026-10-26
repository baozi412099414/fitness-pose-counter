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

- 当前只有 `/styleguide` 路由，`App.tsx` 其余路径会重定向到它。
- 业务页面的数据将按 `docs/网页版前端_TRAE提示词.md` 中的 API/WebSocket 契约接入；
  开发期允许用 `src/mocks/` + `VITE_USE_MOCK`，但必须在答辩前切换为真实接口。
- 所有计数、质量判定、评分、历史、目标、多用户逻辑由 Python 后端提供，前端不重写判定算法。

## 备注

- `node_modules/`、`dist/`、`.vite/` 已在根 `.gitignore` 中忽略。
- 视频帧只在浏览器与后端内存中处理，不落盘。
- 动作判定阈值是工程初值，尚未完成真人视频回归校准；页面上不要出现“准确率 99%”“已校准”等表述。
