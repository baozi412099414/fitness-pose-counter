"""FORM LAB 判定服务：REST 健康检查 + WebSocket /ws/train。

为什么需要它：浏览器里没有 MediaPipe 推理，前端只负责抓帧和画骨架；
真正的「这一帧算不算一次、动作标不标准」全部回到 `pose_logic.py`，
保证网页版和桌面版**用的是同一套判定**。

启动：
    python -m uvicorn web.backend.app:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from contextlib import asynccontextmanager

import mediapipe
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .pose_model import ROOT, PoseModel
from .replay import ReplaySession
from .rest import router as rest_router
from .session import CameraSession

model = PoseModel()


def _warmup() -> None:
    """后台预热：首次加载可能要十几秒（甚至被遥测拖到一分钟），不能卡住事件循环。"""
    try:
        model.load()
    except Exception:  # noqa: BLE001 - 失败原因记在 model.load_error 里，由 /api/health 暴露
        pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 预热是「省得用户等」的优化，不是启动前置条件：
    # 模型没就绪时 /api/health 会如实回报，前端照常能打开。
    # 测试里设 WEB_BACKEND_NO_WARMUP=1 跳过 —— 否则 pytest 退出时
    # 要等那个加载线程（macOS 上首次可能被遥测拖到一分钟）。
    task = None
    if os.environ.get("WEB_BACKEND_NO_WARMUP") != "1":
        task = asyncio.create_task(asyncio.to_thread(_warmup))
    try:
        yield
    finally:
        if task is not None:
            task.cancel()


app = FastAPI(title="FORM LAB 判定服务", lifespan=lifespan)
app.include_router(rest_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本地课程项目：允许 vite dev server 直连
    allow_methods=["*"],
    allow_headers=["*"],
)

# 同一时间只允许一路训练：MediaPipe 实例不是线程安全的，两路会互相踩。
#
# 但「只允许一路」必须配一个**僵尸回收**：浏览器标签页被直接关掉、笔记本合盖断线时，
# 服务端这一侧的连接可能不会立刻收到断开通知，BUSY 就会一直挂着，
# 用户会看到「已有一路训练在进行」却根本不知道自己开过训练（实测踩到）。
BUSY: dict = {"ws": None, "since": 0.0, "last_frame": 0.0, "action": "", "user": ""}

FRAME_IDLE_TIMEOUT = 20.0   # 会话内超过这么久没收到帧 → 判定为僵尸连接，自己关掉
TAKEOVER_IDLE = 10.0        # 新训练开始时，旧连接空闲超过这么久 → 直接抢过来


def _decode_image(data_url: str) -> bytes | None:
    """'data:image/jpeg;base64,xxx' → 原始字节。"""
    if not data_url:
        return None
    payload = data_url.split(",", 1)[1] if "," in data_url else data_url
    try:
        return base64.b64decode(payload)
    except Exception:  # noqa: BLE001 - 坏帧交给上层报 BAD_FRAME
        return None


@app.get("/api/health")
def health() -> dict:
    import platform

    return {
        "ok": True,
        "mode": "live",
        "version": "0.2.0",
        "python_version": platform.python_version(),
        "mediapipe_version": mediapipe.__version__,
        "model": "pose_landmarker_lite.task",
        "device": "本机",
        "data_dir": str(ROOT / "data"),
        "configs_dir": str(ROOT / "configs"),
        "backend_url": "http://127.0.0.1:8000",
        # 兼容旧字段
        "model_loaded": model.loaded,
        "model_error": model.load_error,
        "mediapipe": mediapipe.__version__,
        "project_root": str(ROOT),
    }


@app.get("/api/actions")
def actions() -> dict:
    """动作列表（网页版动作库暂时走 mock，这里先给一份最小可用的）。"""
    items = []
    for path in sorted((ROOT / "configs").glob("*.json")):
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        items.append({
            "id": cfg.get("id", path.stem),
            "name": cfg.get("name", path.stem),
            "camera_side": cfg.get("camera_side", ""),
            "file": f"configs/{path.name}",
        })
    return {"items": items, "count": len(items)}


@app.websocket("/ws/train")
async def ws_train(ws: WebSocket) -> None:
    await ws.accept()
    send_lock = asyncio.Lock()

    async def send(payload: dict) -> None:
        async with send_lock:
            await ws.send_text(json.dumps(payload, ensure_ascii=False))

    session: CameraSession | None = None
    box: dict = {"latest": None, "dropped": False}
    frame_event = asyncio.Event()
    processor: asyncio.Task | None = None
    replay_task: asyncio.Task | None = None
    watchdog: asyncio.Task | None = None
    claimed = False

    async def run_frames() -> None:
        """单帧流水线：只处理「最新」一帧，处理不过来的旧帧直接丢。"""
        while True:
            await frame_event.wait()
            frame_event.clear()
            item = box["latest"]
            box["latest"] = None
            if item is None:
                continue
            dropped, box["dropped"] = box["dropped"], False
            frame_id, data = item
            try:
                messages = await asyncio.to_thread(session.process_frame, frame_id, data)
            except Exception as exc:  # noqa: BLE001 - 单帧失败不能打断整场训练
                await send({
                    "type": "error",
                    "code": "MODEL_ERROR",
                    "message": f"这一帧推理失败：{type(exc).__name__}: {exc}",
                })
                continue
            if dropped and messages and messages[-1].get("type") == "state":
                messages[-1]["metrics"]["dropped"] = True
            for msg in messages:
                await send(msg)
            if session is not None and session.finished:
                # 组数已经做满：汇总已随上一批消息发出，这里收摊
                frame_event.clear()
                await ws.close()
                return

    async def watch_idle() -> None:
        """超过 FRAME_IDLE_TIMEOUT 没收到帧就把会话关掉，避免 BUSY 被僵尸连接占死。"""
        while True:
            await asyncio.sleep(5)
            if BUSY["ws"] is not ws:
                return
            idle = time.monotonic() - BUSY["last_frame"]
            if idle >= FRAME_IDLE_TIMEOUT:
                print(f"[会话] {idle:.0f}s 没收到画面，自动结束这次训练", flush=True)
                try:
                    await ws.close()
                except Exception:  # noqa: BLE001
                    pass
                return

    async def run_replay(replay: ReplaySession) -> None:
        delay = 1.0 / max(replay.fps, 1.0)
        try:
            while not replay.done:
                await send(replay.step())
                await asyncio.sleep(delay)
            await send(replay.summary())
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            await send({
                "type": "error",
                "code": "MODEL_ERROR",
                "message": f"回放失败：{type(exc).__name__}: {exc}",
            })
        finally:
            try:
                await ws.close()
            except RuntimeError:
                pass

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            kind = msg.get("type")

            if kind == "frame":
                if session is None:
                    continue
                if BUSY["ws"] is ws:
                    BUSY["last_frame"] = time.monotonic()
                data = _decode_image(msg.get("image") or "")
                if data is None:
                    await send({
                        "type": "error",
                        "code": "BAD_FRAME",
                        "message": "帧数据不是合法的 base64 图片",
                    })
                    continue
                if box["latest"] is not None:
                    box["dropped"] = True
                box["latest"] = (msg.get("frame_id"), data)
                frame_event.set()
                continue

            if kind == "start":
                if session is not None or replay_task is not None:
                    continue
                if BUSY["ws"] is not None:
                    idle = time.monotonic() - BUSY["last_frame"]
                    # 空闲太久的连接判定为僵尸（页面被关掉/网络断了），直接回收
                    if idle >= TAKEOVER_IDLE:
                        old = BUSY["ws"]
                        print(f"[会话] 回收僵尸会话：{idle:.0f}s 没收到帧"
                              f"（{BUSY['user']} / {BUSY['action']}）", flush=True)
                        try:
                            await old.close()
                        except Exception:  # noqa: BLE001
                            pass
                        BUSY.update(ws=None, since=0.0, last_frame=0.0,
                                    action="", user="")
                    else:
                        who = f"{BUSY['user']} 的{BUSY['action']}" if BUSY["user"] else "另一路"
                        await send({
                            "type": "error",
                            "code": "BUSY",
                            "message": (
                                f"已有一路训练正在进行（{who}，最近 {idle:.0f} 秒前还在传画面）。"
                                "如果那是你之前开着的旧页面，关掉它或刷新一下即可；"
                                "闲置超过 10 秒的连接会被自动回收。"
                            ),
                        })
                        await ws.close()
                        return
                if not model.loaded:
                    try:
                        await asyncio.to_thread(model.load)
                    except Exception as exc:  # noqa: BLE001
                        await send({
                            "type": "error",
                            "code": "MODEL_ERROR",
                            "message": f"姿态模型加载失败：{type(exc).__name__}: {exc}",
                        })
                        await ws.close()
                        return
                try:
                    session = CameraSession(
                        action_id=msg.get("action_id") or "squat",
                        user=msg.get("user") or "演示用户",
                        sets=int(msg.get("sets") or 1),
                        reps_per_set=int(msg.get("reps_per_set") or 10),
                        rest_seconds=float(msg.get("rest_seconds") or 30),
                        model=model,
                    )
                except Exception as exc:  # noqa: BLE001 - 配置不存在等
                    await send({
                        "type": "error",
                        "code": "MODEL_ERROR",
                        "message": f"无法开始训练：{type(exc).__name__}: {exc}",
                    })
                    await ws.close()
                    return
                BUSY.update(ws=ws, since=time.monotonic(),
                            last_frame=time.monotonic(),
                            action=session.action_name, user=session.user)
                claimed = True
                watchdog = asyncio.create_task(watch_idle())
                print(f"[会话] 开始训练：{session.user} / {session.action_name}"
                      f" · {session.setman.total_sets} 组 × {session.setman.reps_per_set} 次",
                      flush=True)
                await send(session.ready("camera"))
                processor = asyncio.create_task(run_frames())
                continue

            if kind == "start_replay":
                if session is not None or replay_task is not None:
                    continue
                try:
                    replay = ReplaySession(
                        sample_id=msg.get("sample_id") or "squat_standard",
                        action_id=msg.get("action_id"),
                    )
                except Exception as exc:  # noqa: BLE001
                    await send({
                        "type": "error",
                        "code": "BAD_FRAME",
                        "message": f"回放样本打不开：{type(exc).__name__}: {exc}",
                    })
                    continue
                await send(replay.ready())
                replay_task = asyncio.create_task(run_replay(replay))
                continue

            if kind == "stop":
                if session is not None:
                    await send(session.summary())
                await ws.close()
                break

            if kind == "reset":
                # 前端目前是「断开重连」语义，这里直接收尾即可
                await ws.close()
                break

    except WebSocketDisconnect:
        pass
    finally:
        for task in (processor, replay_task, watchdog):
            if task is not None and not task.done():
                task.cancel()
        if claimed and BUSY["ws"] is ws:
            BUSY.update(ws=None, since=0.0, last_frame=0.0, action="", user="")
            print("[会话] 训练结束，连接已释放", flush=True)
