# 截图说明

`/train` 实时训练页验收截图（mock 默认模式，`VITE_TRAIN_MODE` 见每张说明）。

| 文件 | 说明 |
|---|---|
| 01-train-idle.png | 初始 idle 状态：回放模式未开始，主区显示「开始训练」 |
| 02-train-counting.png | 回放计数中：骨架关键点与次数实时更新 |
| 03-train-resting.png | 组间休息倒计时（2 组训练，第 1 组完成后进入休息） |
| 04-train-summary.png | 训练汇总：评分 / 次数 / 时长与判定项结果 |
| 05-train-camera-error.png | 实时模式被拒摄像头权限后的错误态（可切回回放） |
| 06-train-live-error.png | `VITE_TRAIN_MODE=live` 且后端未启动时的可恢复错误态（无法连接 `/ws/train`） |