"""相机通路的离线验收：用「假模型」喂一段真实的关键点轨迹。

为什么要这么测：真正跑摄像头需要摄像头权限，CI / 助教机器上未必有。
但相机链路里除了 MediaPipe 那一步，剩下的（JPEG 解码 → 像素换算 → 校准 →
计数 → 分组 → 汇总）都是我们自己的代码，可以用桩模型完整跑一遍。

桩模型直接复用 `samples/squat_standard.json` 的轨迹，所以「相机通路」和
「回放通路」应该数出同样的次数 —— 这正好验证两条链路殊途同归。
"""

from __future__ import annotations

from types import SimpleNamespace

import cv2
import numpy as np
import pytest

import pose_player
from web.backend.pose_model import ROOT
from web.backend.session import LO_DROP, CameraSession

SAMPLE = ROOT / "samples" / "squat_standard.json"
SIZE = 1000  # 正方形画布：x/y 用同一个比例归一化，角度才不会变形


def _load_track():
    data = pose_player.load_data(str(SAMPLE))
    provided = [
        (point, v)
        for frame, vis in zip(data["frames"], data["vis"])
        for point, v in zip(frame, vis)
        if v > 0
    ]
    xs = [p[0] for p, _ in provided]
    ys = [p[1] for p, _ in provided]
    min_x, min_y = min(xs), min(ys)
    span = max(max(xs) - min_x, max(ys) - min_y) or 1.0

    frames = []
    for frame, vis in zip(data["frames"], data["vis"]):
        lms = []
        for point, v in zip(frame, vis):
            if v <= 0:
                lms.append(SimpleNamespace(x=0.0, y=0.0, z=0.0, visibility=0.0))
            else:
                lms.append(SimpleNamespace(
                    x=(point[0] - min_x) / span,
                    y=(point[1] - min_y) / span,
                    z=0.0,
                    visibility=float(v),
                ))
        frames.append(lms)
    return frames, data["fps"]


class StubModel:
    """按顺序吐出预置关键点，用来替代 MediaPipe。"""

    def __init__(self, frames):
        self.frames = frames
        self.index = 0

    def infer(self, _img):
        frame = self.frames[min(self.index, len(self.frames) - 1)]
        self.index += 1
        return frame, 1.0


def _jpeg() -> bytes:
    ok, buf = cv2.imencode(".jpg", np.zeros((SIZE, SIZE, 3), np.uint8))
    assert ok
    return buf.tobytes()


def _session(frames, **kwargs) -> CameraSession:
    session = CameraSession(
        action_id="squat",
        user="测试用户",
        sets=1,
        reps_per_set=10,
        model=StubModel(frames),
        record_history=False,
    )
    session.calib_needed = False
    session.calib_status = "skipped"
    return session


def test_camera_pipeline_counts_like_replay():
    frames, fps = _load_track()
    session = _session(frames)
    jpeg = _jpeg()

    states = []
    for i in range(len(frames)):
        messages = session.process_frame(i, jpeg, now=i / fps)
        states.extend(m for m in messages if m["type"] == "state")

    assert len(states) == len(frames)
    # 中间某一帧应该已经数到过 1 次以上（不是全程 0）
    assert max(s["count"] for s in states) >= 1

    summary = session.summary()
    assert summary["reps"] == 3
    assert summary["saved"] is False  # record_history=False
    assert summary["person_rate"] > 0.9


def test_camera_state_contract():
    frames, fps = _load_track()
    session = _session(frames)
    jpeg = _jpeg()
    messages = session.process_frame(0, jpeg, now=0.0)
    state = [m for m in messages if m["type"] == "state"][-1]

    assert state["person"] is True
    assert len(state["landmarks"]) == 33
    assert state["stage"] in ("ready", "active")
    assert state["metrics"]["infer_ms"] >= 0
    # 校准被跳过时要如实回报，别让前端一直显示「校准中」
    assert state["calibration"]["status"] == "skipped"


def test_session_auto_finishes_when_sets_done():
    """组数做满要当场给汇总，不能等用户点「结束」。"""
    frames, fps = _load_track()
    session = _session(frames)
    session.setman.total_sets = 1
    session.setman.reps_per_set = 3
    jpeg = _jpeg()

    summary = None
    for i in range(len(frames)):
        messages = session.process_frame(i, jpeg, now=i / fps)
        if messages and messages[-1]["type"] == "summary":
            summary = messages[-1]
            break

    assert summary is not None
    assert summary["reps"] == 3
    assert session.finished is True


def test_rest_counts_down_even_when_person_leaves():
    """组间休息必须按时间自己走完 —— 人转身走开也不能卡住（前端踩过）。"""
    frames, fps = _load_track()

    class NoPersonModel:
        def infer(self, _img):
            return None, 1.0

    session = CameraSession(
        action_id="squat", user="测试用户", sets=2, reps_per_set=1,
        rest_seconds=2.0, model=StubModel(frames), record_history=False,
    )
    session.calib_needed = False
    session.calib_status = "skipped"
    jpeg = _jpeg()

    t = 0.0
    rest_started = False
    remaining = []
    rest_end = False

    # 先做到第一次计数 → 触发 set_done + rest_start
    i = 0
    while i < len(frames) and not rest_started:
        msgs = session.process_frame(i, jpeg, now=i / fps)
        for m in msgs:
            if m["type"] == "event" and m["event"] == "rest_start":
                rest_started = True
            if m["type"] == "state":
                t = m["ts"]
        i += 1
    assert rest_started, "做完一组应该进入组间休息"

    # 休息期间人离开画面：仍然继续喂帧（前端现在休息阶段也发帧）
    session.model = NoPersonModel()
    for k in range(40):
        t += 0.1
        msgs = session.process_frame(1000 + k, jpeg, now=t)
        for m in msgs:
            if m["type"] == "state":
                remaining.append(m["sets"]["rest_remaining"])
            if m["type"] == "event" and m["event"] == "rest_end":
                rest_end = True

    assert rest_end, "休息结束事件必须发出来"
    assert remaining[0] > remaining[-1], "倒计时要真的在减少"
    assert remaining[-1] == 0


def _knee_pose(angle_deg: float, jitter: float = 0.0) -> list:
    """造一帧只有左腿三个关键点可信的骨架（髋 23 / 膝 25 / 踝 27）。"""
    import math
    import random

    a = math.radians(angle_deg + random.uniform(-jitter, jitter))
    pts = [SimpleNamespace(x=0.0, y=0.0, z=0.0, visibility=0.0) for _ in range(33)]
    # 归一化到 0~1 的正方形画布：膝在中间，髋在正上方，踝按角度摆
    knee = (0.5, 0.6)
    hip = (0.5, 0.25)
    ankle = (0.5 + 0.35 * math.sin(a), 0.6 - 0.35 * math.cos(a))
    for idx, (x, y) in ((23, hip), (25, knee), (27, ankle)):
        pts[idx] = SimpleNamespace(x=x, y=y, z=0.0, visibility=0.99)
    return pts


class TrackModel:
    def __init__(self, frames):
        self.frames = frames
        self.index = 0

    def infer(self, _img):
        frame = self.frames[min(self.index, len(self.frames) - 1)]
        self.index += 1
        return frame, 1.0


def _run_track(frames, baseline=178.0, fps=12.0, lo_drop=None) -> CameraSession:
    session = CameraSession(
        action_id="squat", user="测试用户", sets=1, reps_per_set=99,
        model=TrackModel(frames), record_history=False,
    )
    session.calib_needed = False
    session.calib_status = "skipped"
    # 模拟「校准过」的门槛：基线 178 → 进入 153 / 还原 170
    session.action.counter.lo = baseline - (LO_DROP if lo_drop is None else lo_drop)
    session.action.counter.hi = baseline - 8
    jpeg = _jpeg()
    for i in range(len(frames)):
        session.process_frame(i, jpeg, now=i / fps)
    return session


def test_shallow_knee_dips_do_not_count():
    """站着换重心这种十几度的小晃动不能算一次（用户反馈「站起来就 3 个」）。"""
    frames = []
    for _ in range(240):          # 20 秒
        frames.append(_knee_pose(175, jitter=6))   # 站立 + 抖动
    for _ in range(3):            # 三次「浅蹲」：只弯到 160°
        for _ in range(8):
            frames.append(_knee_pose(160, jitter=3))
        for _ in range(8):
            frames.append(_knee_pose(175, jitter=3))

    session = _run_track(frames)
    assert session.action.counter.count == 0, (
        f"浅蹲不该计数，实际数了 {session.action.counter.count} 次"
    )


def test_real_squat_still_counts():
    """真的蹲下去（膝盖弯到 95°）必须照常计数，不能被收紧的门槛卡死。"""
    frames = []
    for _ in range(40):
        frames.append(_knee_pose(175, jitter=3))
    for _ in range(3):            # 三次完整深蹲
        for _ in range(10):
            frames.append(_knee_pose(120, jitter=2))
        for _ in range(6):
            frames.append(_knee_pose(98, jitter=2))
        for _ in range(10):
            frames.append(_knee_pose(140, jitter=2))
        for _ in range(10):
            frames.append(_knee_pose(175, jitter=2))
    session = _run_track(frames)
    assert session.action.counter.count >= 2, (
        f"完整深蹲应该能数出来，实际只有 {session.action.counter.count} 次"
    )


def test_bad_frame_is_reported_not_crashing():
    frames, _fps = _load_track()
    session = _session(frames)
    messages = session.process_frame(0, b"not-a-jpeg")
    assert messages[0]["type"] == "error"
    assert messages[0]["code"] == "BAD_FRAME"


def test_calibration_sets_thresholds_from_baseline():
    """前 2 秒站着不动 → 采到基线 → 把门槛改成「基线 − 15 / − 8」。

    注意：samples 里的轨迹是连续做的，开头并不是「站着不动」，
    所以这里拿第一帧（膝角约 176°）复制 2 秒，模拟真实的开局站姿。
    """
    frames, fps = _load_track()
    standing = frames[:1] * 80
    session = _session(standing)
    session.calib_needed = True
    session.calib_status = "sampling"
    original_lo = session.action.counter.lo
    jpeg = _jpeg()

    events = []
    for i in range(70):  # 2.3 秒
        messages = session.process_frame(i, jpeg, now=i / fps)
        events.extend(m for m in messages if m["type"] == "event")

    assert session.calib_status == "done"
    assert session.calib_baseline is not None
    assert session.calib_baseline > 170  # 站立时膝角接近 180°
    assert session.action.counter.lo != original_lo
    assert session.action.counter.lo == pytest.approx(
        session.calib_baseline - LO_DROP, abs=0.6)
    assert session.action.counter.hi == pytest.approx(session.calib_baseline - 8, abs=0.6)
    assert any(e["event"] == "calibrated" for e in events)


def test_calibration_falls_back_to_config_when_not_enough_samples():
    """一帧都采不到（没人入镜）→ 4 秒后放弃校准，退回配置门槛。"""
    frames, fps = _load_track()

    class NoPersonModel:
        def infer(self, _img):
            return None, 1.0

    session = CameraSession(
        action_id="squat", user="测试用户", sets=1, reps_per_set=10,
        model=NoPersonModel(), record_history=False,
    )
    session.calib_needed = True
    session.calib_status = "sampling"
    jpeg = _jpeg()

    for i in range(int(4.2 * fps)):
        session.process_frame(i, jpeg, now=i / fps)

    assert session.calib_status == "skipped"
    assert session.calib_baseline is None
    summary = session.summary()
    assert summary["reps"] == 0
    assert summary["saved"] is False
