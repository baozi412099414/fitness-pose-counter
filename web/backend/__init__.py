"""FORM LAB 网页版判定服务（FastAPI 适配层）。

把现有的 `pose_logic.py`（计数状态机 / 质量判定 / 评分）原样暴露成
WebSocket `/ws/train`，前端只负责画骨架和展示数字，不重写任何判定逻辑。

启动：`python -m uvicorn web.backend.app:app --host 127.0.0.1 --port 8000`
"""
