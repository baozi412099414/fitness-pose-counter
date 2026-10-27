"""WebSocket / REST 契约测试（不依赖摄像头）。

回放走的是同一条 /ws/train 通路：start_replay → 一串 state → summary，
所以这里跑通，就等于「前端拿到消息能画」这件事在协议层是成立的。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from web.backend.app import app


def test_health():
    with TestClient(app) as client:
        data = client.get("/api/health").json()
    assert data["ok"] is True
    assert "model_loaded" in data
    assert data["mediapipe"].startswith("0.10")
    assert data["project_root"].endswith("选题 3")


def test_actions_list():
    with TestClient(app) as client:
        data = client.get("/api/actions").json()
    ids = {item["id"] for item in data["items"]}
    assert {"squat", "pushup", "jumping_jack"} <= ids
    assert data["count"] == len(data["items"])


def test_replay_over_websocket():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/train") as ws:
            ws.send_json({
                "type": "start_replay",
                "sample_id": "squat_standard",
                "action_id": "squat",
                "record_history": False,
            })
            messages = []
            while True:
                msg = ws.receive_json()
                messages.append(msg)
                if msg["type"] in ("summary", "error"):
                    break

    ready = [m for m in messages if m["type"] == "ready"]
    states = [m for m in messages if m["type"] == "state"]
    assert ready and ready[0]["mode"] == "replay"
    assert len(states) > 100, "应该逐帧推送 state"
    assert states[0]["landmarks"] and len(states[0]["landmarks"]) == 33

    summary = messages[-1]
    assert summary["type"] == "summary"
    assert summary["reps"] == 3
    assert abs(summary["score"] - 78.2) <= 0.1
    assert summary["saved"] is False
