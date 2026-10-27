"""回放会话：把 samples/*.json 的关键点喂给同一个 pose_logic。

存在的意义有两个：
1. 网页上的「回放」模式可以和后端用同一套判定（不是前端假造的数字）；
2. 没有摄像头也能验收 —— 测试直接调这里，断言计数/分数与 samples/README.md 一致。
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pose_logic  # noqa: E402
import pose_player  # noqa: E402

from .session import _checks_payload, _num  # noqa: E402


class ReplaySession:
    """一次样本回放。时间轴按数据自带的 fps 推进（不能用墙上时间）。"""

    def __init__(self, sample_id: str, action_id: str | None = None):
        path = ROOT / "samples" / f"{sample_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"没有这个样本：{path.name}")
        self.data = pose_player.load_data(str(path))
        self.sample_id = sample_id
        self.sample_name = self.data.get("name") or sample_id
        self.fps = float(self.data["fps"])
        self.frames = self.data["frames"]
        self.vis = self.data["vis"]

        self.action_id = action_id or self.data.get("action") or "squat"
        cfg_path = ROOT / "configs" / f"{self.action_id}.json"
        if not cfg_path.exists():
            raise FileNotFoundError(f"样本声明的动作不存在：{self.action_id}")
        self.config = json.loads(cfg_path.read_text(encoding="utf-8"))
        self.action = pose_logic.load_action(str(cfg_path))
        self.action_name = self.action.name
        self.camera_side = self.config.get("camera_side", "")

        self.session_id = uuid.uuid4().hex[:12]
        self.seq = 0
        self.index = 0
        # 样本坐标是合成轨迹的「画布像素」，范围不固定（甚至有负数），
        # 用整段数据的包围盒归一化，前端按 0~1 画出来才不会跑出画布。
        provided = [
            point
            for frame, vis in zip(self.frames, self.vis)
            for point, v in zip(frame, vis)
            if v > 0
        ]
        xs = [p[0] for p in provided] or [0]
        ys = [p[1] for p in provided] or [0]
        self._min_x, self._min_y = min(xs), min(ys)
        self._span_x = max(xs) - self._min_x or 1.0
        self._span_y = max(ys) - self._min_y or 1.0
        self.checks: list[dict] = []
        self.hits: list[dict] = []
        self.error_counts: dict[str, int] = {}
        self.error_tips: dict[str, str] = {}
        self.active_errors: set[str] = set()

    @property
    def done(self) -> bool:
        return self.index >= len(self.frames)

    @property
    def duration(self) -> float:
        return len(self.frames) / max(self.fps, 1e-6)

    def ready(self) -> dict:
        return {
            "type": "ready",
            "session_id": self.session_id,
            "mode": "replay",
            "action": {
                "id": self.action_id,
                "name": self.action_name,
                "camera_side": self.camera_side,
            },
            "calibration": {"needed": False},
        }

    def step(self) -> dict:
        """推进一步，返回这一帧的 state。"""
        if self.done:
            raise StopIteration
        pts = self.frames[self.index]
        vis = self.vis[self.index]
        t = self.index / max(self.fps, 1e-6)
        count, stage, sig, hits, checks = self.action.update(pts, vis, now=t)
        self._track_errors(hits)
        self.checks = _checks_payload(checks)
        self.hits = _checks_payload(hits[:2])
        state = self.state(count, stage, t)
        self.index += 1
        return state

    def _landmarks_at(self, index: int) -> list[dict]:
        index = min(index, len(self.frames) - 1)
        out = []
        for point, v in zip(self.frames[index], self.vis[index]):
            if v <= 0:
                out.append({"x": 0.0, "y": 0.0, "z": 0.0, "v": 0.0})
                continue
            out.append({
                "x": round((point[0] - self._min_x) / self._span_x, 4),
                "y": round((point[1] - self._min_y) / self._span_y, 4),
                "z": 0.0,
                "v": round(float(v), 4),
            })
        return out

    def _track_errors(self, hits) -> None:
        current = {h["name"] for h in hits}
        for hit in hits:
            name = hit["name"]
            if name in self.active_errors:
                continue
            self.error_counts[name] = self.error_counts.get(name, 0) + 1
            self.error_tips[name] = hit.get("tip") or name
        self.active_errors = current

    def state(self, count: int, stage: str, t: float) -> dict:
        self.seq += 1
        values = [_num(v) for v in (self.action.last_values or [])]
        score = self.action.last_score
        landmarks = self._landmarks_at(self.index)
        return {
            "type": "state",
            "seq": self.seq,
            "frame_id": self.index,
            "ts": round(t, 3),
            "count": int(count),
            "stage": stage,
            "signal": values[0] if values else None,
            "values": values,
            "cycle_progress": getattr(self.action.counter, "cycle_progress", 0),
            "score": _num(score, 1),
            "grade": pose_logic.QualityChecker.grade(score),
            "checks": self.checks,
            "hits": self.hits,
            "landmarks": landmarks,
            "person": True,
            "calibration": {"status": "skipped", "baseline": None, "progress": 1.0},
            "sets": {
                "current_set": 1,
                "total_sets": 1,
                "reps_in_set": int(count),
                "reps_per_set": 0,
                "total_reps": int(count),
                "rest_remaining": 0,
                "finished": False,
            },
            "metrics": {"fps": round(self.fps, 1), "latency_ms": 0, "infer_ms": 0},
        }

    def summary(self) -> dict:
        return {
            "type": "summary",
            "action": self.action_id,
            "action_name": self.action_name,
            "reps": int(self.action.counter.count),
            "score": _num(self.action.last_score, 1),
            "grade": pose_logic.QualityChecker.grade(self.action.last_score),
            "duration_sec": round(self.duration, 1),
            "errors": self.error_counts,
            "error_tips": self.error_tips,
            "person_rate": 1.0,
            "detection_rate": 1.0,
            "saved": False,
            "goal": None,
        }


