"""相机模式训练会话：一帧帧喂给 pose_logic 的计数 / 判定 / 评分。

这里**不重写任何算法**——计数用 `Action.update()`，评分用 `QualityChecker`，
分组与休息用 `training_manager.SetManager`，历史用 `History`。
适配层只做四件事：坐标换算、校准、把结果翻译成前端契约里的 JSON、攒汇总。
"""

from __future__ import annotations

import json
import math
import sys
import time
import uuid
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # 允许 `uvicorn web.backend.app:app` 之外的启动方式
    sys.path.insert(0, str(ROOT))

import pose_logic  # noqa: E402
from training_manager import Goals, History, SetManager, UserStore  # noqa: E402

# 三个偏移量：门槛不能写死，要跟着人的站立基线走。
#
# ⚠ LO_DROP 取 25 而不是 15，是 2026-10-27 实测调出来的：
#   网页端用 15° 时，站着换重心/起身这种十几度的膝盖小晃动就能穿过门槛被记成一次，
#   用户反馈「刚站起来做一次就数到 3 个」，而且那几次的判定都在报「蹲得不够深」——
#   说明数到的根本不是深蹲。深蹲真正做一次膝盖要弯 60~80°，25° 的门槛依然很宽松。
LO_DROP = 25.0        # 进入门槛 = 站立基线 − 25°
HI_DROP = 8.0         # 还原线   = 站立基线 − 8°
STRAIGHT_DROP = 10.0  # 「站起伸直」标准 = 站立基线 − 10°

CALIB_SECONDS = 2.0       # 采样时长
CALIB_TIMEOUT = 4.0       # 超过这么久还采不满，就放弃校准
CALIB_MIN_SAMPLES = 8     # 至少要这么多个有效信号值
CALIB_MAX_SPREAD = 18.0   # 采样期间信号峰谷差超过这个值 → 判定为「正在动」，放弃校准
CALIB_MIN_BASELINE = 110.0  # 站立基线的合理下限（膝角/肘角站直时都远高于此）


def _num(value, digits: int = 2):
    """把 numpy 标量 / NaN / inf 收敛成 JSON 能吃的值。"""
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return round(out, digits)


def _landmarks_payload(landmarks) -> list[dict]:
    """MediaPipe 归一化关键点 → 前端要的 [{x,y,z,v} × 33]。"""
    if not landmarks:
        return [{"x": 0.0, "y": 0.0, "z": 0.0, "v": 0.0} for _ in range(33)]
    return [
        {
            "x": round(float(p.x), 4),
            "y": round(float(p.y), 4),
            "z": round(float(p.z), 4),
            "v": round(float(getattr(p, "visibility", 1.0)), 4),
        }
        for p in landmarks
    ]


def _checks_payload(checks) -> list[dict]:
    return [
        {
            "name": c.get("name", "动作不标准"),
            "tip": c.get("tip", ""),
            "value": _num(c.get("value")),
            "limit": _num(c.get("limit")),
            "ok": bool(c.get("ok", True)),
            "visible": bool(c.get("visible", True)),
            "checked": bool(c.get("checked", True)),
            "priority": int(c.get("priority", 50)),
            "score": _num(c.get("score"), 1),
        }
        for c in (checks or [])
    ]


class CameraSession:
    """一次「实时摄像头」训练。一个连接对应一个实例。"""

    def __init__(
        self,
        action_id: str,
        user: str = "演示用户",
        sets: int = 1,
        reps_per_set: int = 10,
        rest_seconds: float = 30.0,
        model=None,
        record_history: bool = True,
    ):
        self.session_id = uuid.uuid4().hex[:12]
        self.action_id = action_id
        self.user = user or "演示用户"
        self.model = model
        self.record_history = record_history

        cfg_path = ROOT / "configs" / f"{action_id}.json"
        if not cfg_path.exists():
            raise FileNotFoundError(f"没有这个动作配置：{cfg_path}")
        self.config = json.loads(cfg_path.read_text(encoding="utf-8"))
        self.action = pose_logic.load_action(str(cfg_path))
        self.action_name = self.action.name
        self.camera_side = self.config.get("camera_side", "")

        self.setman = SetManager(sets, reps_per_set, rest_seconds)
        self.started = time.time()
        self.seq = 0
        self.last_frame_id = None

        # 最近一次判定结果（没人时清空，避免前端显示过期数据）
        self.checks: list[dict] = []
        self.hits: list[dict] = []

        # 错误边沿计数：同一条错误持续存在只记一次
        self.error_counts: dict[str, int] = {}
        self.error_tips: dict[str, str] = {}
        self.active_errors: set[str] = set()

        self.frames_total = 0
        self.detected_frames = 0
        self.person_frames = 0
        self.infer_ms = 0.0
        self.last_infer_at = 0.0
        self.fps = 0.0

        self.calib_needed = bool(self.action.calibrate) and self.action.signal_type == "angle"
        self.calib_status = "sampling" if self.calib_needed else "skipped"
        self.calib_baseline: float | None = None
        self.calib_samples: list[float] = []
        self.calib_start = 0.0        # 校准起点（会话内秒）
        self.calib_finished_at: float | None = None

        self.finished = False
        self.count_logged = 0

    # ------------------------------------------------------------------ 工具
    @property
    def elapsed(self) -> float:
        return time.time() - self.started

    def _now(self) -> float:
        """会话内时间（秒）。开新会话前会重置，所以不会像墙上时间那样飘。"""
        return time.time() - self.started

    # ------------------------------------------------------------------ 校准
    def _apply_calibration(self, baseline: float) -> None:
        counter = self.action.counter
        counter.lo = baseline - LO_DROP
        counter.hi = baseline - HI_DROP
        for rule in self.action.quality.rules:
            # 只校准「用计数信号」的约束；自带 signal 的规则不能被角度基线污染
            if rule.get("check") == "peak_min" and "signal" not in rule:
                rule["min"] = baseline - STRAIGHT_DROP
        self.calib_baseline = round(baseline, 1)

    def _calibration_payload(self) -> dict:
        if self.calib_status == "sampling":
            progress = min(1.0, max(0.0, (self._now() - self.calib_start) / CALIB_SECONDS))
        elif self.calib_status == "done":
            progress = 1.0
        else:
            progress = 1.0 if self.calib_status == "skipped" else 0.0
        return {
            "status": self.calib_status,
            "baseline": self.calib_baseline,
            "progress": round(progress, 2),
        }

    # ------------------------------------------------------------------ 主循环
    def process_frame(self, frame_id: int, data: bytes,
                      now: float | None = None) -> list[dict]:
        """处理一帧 JPEG，返回要按顺序发给前端的消息列表。

        `now` 只给测试用：回放/单测需要按数据时间推进（摄像头模式下传 None，
        用会话内墙上时间）。和 realtime_pose.py 里「数据回放必须用数据时间」
        是同一个道理 —— 否则 `min_interval` 这类按秒的防抖全部失真。
        """
        messages: list[dict] = []
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return [{
                "type": "error",
                "code": "BAD_FRAME",
                "message": "这一帧解码失败（可能网络传输截断），已跳过",
            }]

        now = self._now() if now is None else now
        self.frames_total += 1
        landmarks, infer_ms = self.model.infer(img)
        self.infer_ms = infer_ms
        if self.last_infer_at:
            self.fps = round(1.0 / max(now - self.last_infer_at, 1e-3), 1)
        self.last_infer_at = now
        self.last_frame_id = frame_id

        h, w = img.shape[:2]
        person = False
        points = None
        vis = None

        if landmarks:
            self.detected_frames += 1
            points = [(int(p.x * w), int(p.y * h)) for p in landmarks]
            vis = [float(getattr(p, "visibility", 1.0)) for p in landmarks]
            counter_idxs: set[int] = set()
            for cond in (self.action.conditions or [{"points": self.action.signal_points}]):
                counter_idxs.update(cond["points"])
            conf = min(vis[i] for i in counter_idxs)
            person = conf >= self.action.min_visibility
            if person:
                self.person_frames += 1

        # 校准要在「没看到人」时也走：否则人一直不入镜，状态会永远停在 sampling
        messages.extend(self._calibrate_step(points if person else None,
                                             vis if person else None, now))

        if person:
            if self.calib_status != "sampling":
                count, stage, sig, hits, checks = self.action.update(points, vis, now=now)
                self._track_errors(hits)
                self.checks = _checks_payload(checks)
                self.hits = _checks_payload(hits[:2])
                if count > self.count_logged:
                    self.count_logged = count
                    sig_txt = f"{sig:.1f}°" if sig is not None else "—"
                    print(f"[计数] 第 {count} 次 · 信号 {sig_txt} · {stage}",
                          flush=True)
        else:
            # 没看到人（或可信度太低）：不喂判定，计数保持上次值
            self.checks = []
            self.hits = []

        # 组间休息必须每帧推进，而且**不能依赖画面里有没有人** ——
        # 否则人一转身走开，休息就永远不结束（前端表现为倒计时卡住）。
        messages.extend(self._set_events(self.action.counter.count, now))

        messages.append(self.state(frame_id, person=person, landmarks=landmarks,
                                   infer_ms=infer_ms, dropped=False))
        # 组数做满就当场结算：否则前端要等用户手动点「结束」才看到汇总
        if self.setman.finished and not self.finished:
            messages.append(self.summary())
        return messages

    def _calibrate_step(self, points, vis, now: float) -> list[dict]:
        """采集站立基线；只在需要校准的动作上跑。"""
        if self.calib_status != "sampling":
            return []

        if points is not None:
            sample = self.action.signal(points)
            if sample is not None:
                self.calib_samples.append(float(sample))

        elapsed = now - self.calib_start
        if elapsed >= CALIB_SECONDS and len(self.calib_samples) >= CALIB_MIN_SAMPLES:
            values = sorted(self.calib_samples)
            baseline = values[len(values) // 2]
            spread = values[-1] - values[0]
            # 校准假设「这 2 秒你是站定不动的」。如果采样期间信号在剧烈变化
            # （刚点开始就蹲下去了），中位数会落在一个毫无意义的中间值上，
            # 门槛被带偏 → 一次动作能数出好几次。宁可退回配置里的固定门槛。
            if spread > CALIB_MAX_SPREAD or baseline < CALIB_MIN_BASELINE:
                self.calib_status = "skipped"
                self.action.reset()
                print(f"[校准] 放弃：基线 {baseline:.1f}° 波动 {spread:.1f}° "
                      f"（需要站定不动再开始），改用配置固定门槛", flush=True)
                return [self.event(
                    "calibrated", baseline=None,
                    tip="这 2 秒画面在动，没能量到站立基线；已改用固定门槛，"
                        "下次开始后先站直别动 2 秒",
                )]
            self._apply_calibration(baseline)
            self.calib_status = "done"
            self.calib_finished_at = now
            self.action.reset()
            print(f"[校准] 基线 {baseline:.1f}°（波动 {spread:.1f}°）→ "
                  f"下蹲门槛 {self.action.counter.lo:.0f}° / "
                  f"还原线 {self.action.counter.hi:.0f}°", flush=True)
            return [self.event("calibrated", baseline=self.calib_baseline,
                               tip=f"校准完成：站立基线 {self.calib_baseline:.0f}°")]
        if elapsed > CALIB_TIMEOUT:
            # 采不满就放弃：宁可退回配置里的固定门槛，也不要一直卡在"校准中"
            self.calib_status = "skipped"
            self.action.reset()
            return [self.event("calibrated", baseline=None,
                               tip="站立基线采样不足，改用配置里的固定门槛")]
        return []

    def _track_errors(self, hits) -> None:
        current = {h["name"] for h in hits}
        for hit in hits:
            name = hit["name"]
            if name in self.active_errors:
                continue
            self.error_counts[name] = self.error_counts.get(name, 0) + 1
            self.error_tips[name] = hit.get("tip") or name
        self.active_errors = current

    def _set_events(self, count: int, now: float) -> list[dict]:
        """把 SetManager 的事件翻成前端的事件消息。"""
        out = []
        for ev in self.setman.on_rep(count, now):
            kind = ev.get("type")
            out.append(self.event(
                kind,
                set=ev.get("set", self.setman.current_set),
                seconds=ev.get("seconds", 0),
                tip=ev.get("tip"),
            ))
        return out

    # ------------------------------------------------------------------ 消息
    def event(self, name: str, *, set: int | None = None, seconds: float = 0,
              baseline: float | None = None, tip: str | None = None) -> dict:
        return {
            "type": "event",
            "event": name,
            "set": set if set is not None else self.setman.current_set,
            "total_sets": self.setman.total_sets,
            "seconds": seconds,
            "baseline": baseline,
            "tip": tip,
        }

    def ready(self, mode: str = "camera") -> dict:
        return {
            "type": "ready",
            "session_id": self.session_id,
            "mode": mode,
            "action": {
                "id": self.action_id,
                "name": self.action_name,
                "camera_side": self.camera_side,
            },
            "calibration": {"needed": self.calib_needed},
        }

    def state(self, frame_id, person: bool, landmarks, infer_ms: float,
              dropped: bool = False) -> dict:
        self.seq += 1
        values = [_num(v) for v in (self.action.last_values or [])] if person else []
        score = self.action.last_score
        sets = self.setman.status(self._now())
        return {
            "type": "state",
            "seq": self.seq,
            "frame_id": frame_id,
            "ts": round(self._now(), 3),
            "count": int(self.action.counter.count),
            "stage": self.action.counter.stage,
            "signal": values[0] if values else None,
            "values": values,
            "cycle_progress": getattr(self.action.counter, "cycle_progress", 0),
            "score": _num(score, 1),
            "grade": pose_logic.QualityChecker.grade(score),
            "checks": self.checks if person else [],
            "hits": self.hits if person else [],
            "landmarks": _landmarks_payload(landmarks) if person else _landmarks_payload(None),
            "person": person,
            "calibration": self._calibration_payload(),
            "sets": sets,
            "metrics": {
                "fps": self.fps,
                "latency_ms": infer_ms,
                "infer_ms": infer_ms,
                "dropped": dropped,
            },
        }

    # ------------------------------------------------------------------ 收尾
    def summary(self) -> dict:
        self.finished = True
        reps = int(self.setman.total_reps)
        duration = round(self.elapsed, 1)
        score = _num(self.action.last_score, 1)
        saved = False
        goal = None

        try:
            store = UserStore(str(ROOT / "data" / "users"))
            # 只跑过一次训练的用户也要在用户列表里出现（否则网页上找不到自己的记录）
            store.create_user(self.user)
            # 把「最近训练的人」记为当前用户：网页下次打开默认就是他
            store.switch_user(self.user)
            history = History(store, user=self.user)
            if self.record_history and reps > 0 and self.calib_status != "sampling":
                history.add_session(
                    self.action_id,
                    reps,
                    sets=self.setman.total_sets,
                    errors=self.error_counts,
                    duration_sec=duration,
                    source="web",
                    score=score,
                )
                saved = True
            goal = Goals(store, user=self.user).progress(self.action_id, history)
        except Exception as exc:  # noqa: BLE001 - 写历史失败不该毁掉整次训练
            goal = {"error": f"{type(exc).__name__}: {exc}"}

        person_rate = (self.person_frames / self.frames_total) if self.frames_total else 0.0
        detection_rate = (self.detected_frames / self.frames_total) if self.frames_total else 0.0

        return {
            "type": "summary",
            "action": self.action_id,
            "action_name": self.action_name,
            "reps": reps,
            "score": score,
            "grade": pose_logic.QualityChecker.grade(self.action.last_score),
            "duration_sec": duration,
            "errors": self.error_counts,
            "error_tips": self.error_tips,
            "person_rate": round(person_rate, 3),
            "detection_rate": round(detection_rate, 3),
            "saved": saved,
            "goal": goal,
        }
