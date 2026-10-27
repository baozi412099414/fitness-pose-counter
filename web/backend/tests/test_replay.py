"""回放验收：网页后端跑出来的计数 / 分数必须和 samples/README.md 一致。

这条测试是「网页版和桌面版用的是同一套判定」的证据 —— 两边都直接调用
`pose_logic.Action.update()`，只是帧的来源不同（浏览器抓帧 vs JSON 回放）。
"""

from __future__ import annotations

import pytest

from web.backend.replay import ReplaySession

# (样本, 动作, 期望次数, 期望分数) —— 数字来自 samples/README.md，是实际跑出来的
CASES = [
    ("squat_standard", "squat", 3, 78.2),
    ("squat_shallow", "squat", 3, 47.3),
    ("squat_knee_fwd", "squat", 3, 54.6),
    ("pushup_standard", "pushup", 3, 88.3),
    ("pushup_sag", "pushup", 3, 64.3),
    ("jack_standard", "jumping_jack", 3, 100.0),
    ("jack_low_hands", "jumping_jack", 3, 48.0),
]


def run_sample(sample_id: str, action_id: str) -> dict:
    session = ReplaySession(sample_id, action_id)
    last_state = None
    while not session.done:
        last_state = session.step()
    assert last_state is not None
    # 每一帧的 state 必须是前端契约里有的形状
    assert last_state["type"] == "state"
    assert len(last_state["landmarks"]) == 33
    return session.summary()


@pytest.mark.parametrize("sample_id,action_id,reps,score", CASES)
def test_replay_matches_readme(sample_id, action_id, reps, score):
    summary = run_sample(sample_id, action_id)
    assert summary["reps"] == reps, f"{sample_id} 计次对不上"
    assert summary["score"] is not None
    assert abs(summary["score"] - score) <= 0.1, (
        f"{sample_id} 分数 {summary['score']} 与 README 的 {score} 不一致"
    )


def test_replay_state_contract():
    session = ReplaySession("squat_standard", "squat")
    state = session.step()
    for key in ("seq", "frame_id", "ts", "count", "stage", "values", "checks",
                "landmarks", "person", "calibration", "sets", "metrics"):
        assert key in state, f"state 缺字段 {key}"
    assert state["person"] is True
    assert state["sets"]["total_sets"] == 1
