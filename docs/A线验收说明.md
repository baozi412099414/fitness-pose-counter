# A 线前端验收说明

作者：吕云鹏（240608352B04）  
范围：`web/frontend` 的页面、交互、mock/transport 接入层与浏览器验收；不包含 B 线后端算法与 C 线测试文档。

## 1. 环境与启动

```powershell
cd web/frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173/`。

默认使用 mock 数据与回放样本，便于在没有后端、没有摄像头时验收：

```text
VITE_USE_MOCK=true
VITE_TRAIN_MODE=mock
```

如果要验收真实后端，需要 B 线启动 FastAPI/WebSocket 后设置：

```text
VITE_USE_MOCK=false
VITE_TRAIN_MODE=live
```

## 2. 验收步骤

### 2.1 总览

打开 `/`，检查主卡数字、目标环、快速开始三张动作卡、本周趋势、目标进度、最常犯的错、最近训练与近 7 天轨道是否正常显示；点击动作卡应进入 `/train/:id`，点击错误应进入 `/data?tab=errors`。

### 2.2 实时训练（回放）

打开 `/train`，选择动作与回放样本，组数设为 2，点击“开始训练”。检查骨架、次数、阶段、评分与判定项是否随回放更新；Enter/Space 开始、R 重开、Esc 退出是否可用。

### 2.3 组间休息与汇总

第 1 组完成后应进入休息倒计时；回放模式点击“跳过休息”应进入第 2 组；最后一组完成后进入汇总，检查次数、评分、等级、用时与错误标签是否齐全。

### 2.4 数据页

打开 `/data`，切换动作与时间范围，检查四个 KPI、周柱状图、评分折线、错误排行与历史表；点击错误排行应把该错误写入 URL 并过滤历史表；点历史行应打开右侧 Drawer；“导出 CSV”应导出当前筛选记录，Excel 打开中文不乱码。

### 2.5 设置页

打开 `/settings`，检查个人档案、用户列表、每日目标与关于信息；新建/切换用户后，总览、目标与数据页应按新用户重新查询；最后一个用户不可删除。

### 2.6 异常与恢复

- 摄像头被拒：舞台显示错误，可切到回放模式。
- `VITE_TRAIN_MODE=live` 且后端未启动：出现可恢复错误，不应白屏或卡死。
- 空数据：显示 EmptyState，不出现 NaN。
- 表单校验失败：字段红框与错误文案，不应提交成功。

## 3. 构建检查

```powershell
npm run build
```

该命令先执行 `tsc --noEmit`，再执行 `vite build`；当前构建通过，产物约 900 KB（gzip 约 280 KB），主要体积来自 Recharts。

## 4. 截图索引

| 文件 | 说明 |
|---|---|
| `screenshots/01-train-idle.png` | 训练页 idle |
| `screenshots/02-train-counting.png` | 回放计数中 |
| `screenshots/03-train-resting.png` | 组间休息 |
| `screenshots/04-train-summary.png` | 训练汇总 |
| `screenshots/05-train-camera-error.png` | 摄像头被拒 |
| `screenshots/06-train-live-error.png` | live 模式后端未启动 |
| `screenshots/07-overview.png` | 总览页 |
| `screenshots/08-data.png` | 训练数据页 |
| `screenshots/09-actions.png` | 动作库 |

## 5. 已知限制

- A 线不实现姿态判定算法，计数/判定/评分由 B 线后端负责；前端只做采集、绘制与展示。
- 实时模式的断线重连、`skip_rest`、live 目标次数/组数仍需继续完善；回放模式已覆盖主要验收路径。
- 手机摄像头受 HTTPS/localhost 限制，移动端联调需要 HTTPS 隧道或 `adb reverse`。
- 截图基于 1440×900 视口；更小屏幕采用响应式布局，但未在截图中展开。
