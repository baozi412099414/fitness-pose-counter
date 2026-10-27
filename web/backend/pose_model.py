"""MediaPipe Pose Landmarker 的进程级单例。

为什么要单例：模型加载一次要十几秒（macOS 上首次还可能被遥测拖到一分钟），
每个连接都 new 一个等于每次开训练都卡一分钟。

为什么加锁：MediaPipe 的 Landmarker 对象**不是线程安全的**，
而我们用 `asyncio.to_thread` 把推理丢到线程池里跑，所以必须串行化。
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = ROOT / "pose_landmarker_lite.task"

# 归一化坐标与缩放无关，但太大的图会让推理变慢；最长边 640 是速度/精度的折中
MAX_SIDE = 640


class PoseModel:
    """懒加载的 PoseLandmarker 包装。"""

    def __init__(self, model_path: Path | str = DEFAULT_MODEL):
        self.model_path = Path(model_path)
        self._landmarker: vision.PoseLandmarker | None = None
        self._lock = threading.Lock()
        self._last_ts = 0
        self._load_error: str | None = None

    # ---------------------------------------------------------------- 加载
    @property
    def loaded(self) -> bool:
        return self._landmarker is not None

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def load(self) -> None:
        """同步加载模型（幂等）。失败时把原因记下来，不抛给调用方导致进程退出。"""
        if self._landmarker is not None:
            return
        with self._lock:
            if self._landmarker is not None:
                return
            try:
                if not self.model_path.exists():
                    raise FileNotFoundError(
                        f"找不到模型文件：{self.model_path}（先跑 setup_env.sh 下载）"
                    )
                options = vision.PoseLandmarkerOptions(
                    base_options=mp_python.BaseOptions(
                        model_asset_path=str(self.model_path)
                    ),
                    # 帧流用 VIDEO：时间戳自己给，比 LIVE_STREAM 的回调时序更可控
                    running_mode=vision.RunningMode.VIDEO,
                    num_poses=1,
                    min_pose_detection_confidence=0.6,
                    min_pose_presence_confidence=0.6,
                    min_tracking_confidence=0.6,
                )
                self._landmarker = vision.PoseLandmarker.create_from_options(options)
                self._load_error = None
            except Exception as exc:  # noqa: BLE001 - 启动失败要能上报给前端
                self._load_error = f"{type(exc).__name__}: {exc}"
                raise

    # ---------------------------------------------------------------- 推理
    def infer(self, bgr: np.ndarray) -> tuple[list | None, float]:
        """对一帧 BGR 图像做姿态估计。

        返回 (landmarks, infer_ms)；landmarks 为 None 表示画面里没检测到人。
        landmarks 是 MediaPipe 的 NormalizedLandmark 列表（x/y/z 归一化 0~1）。
        """
        if self._landmarker is None:
            self.load()

        h, w = bgr.shape[:2]
        longest = max(h, w)
        img = bgr
        if longest > MAX_SIDE:
            scale = MAX_SIDE / longest
            img = cv2.resize(
                bgr, (max(1, int(w * scale)), max(1, int(h * scale))),
                interpolation=cv2.INTER_AREA,
            )

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        rgb = np.ascontiguousarray(rgb)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        t0 = time.perf_counter()
        with self._lock:
            # VIDEO 模式要求时间戳严格递增；用单调时钟并把重复值挤开
            ts = int(time.monotonic() * 1000)
            if ts <= self._last_ts:
                ts = self._last_ts + 1
            self._last_ts = ts
            result = self._landmarker.detect_for_video(mp_image, ts)
        infer_ms = (time.perf_counter() - t0) * 1000

        landmarks = result.pose_landmarks[0] if result.pose_landmarks else None
        return landmarks, round(infer_ms, 1)

    def close(self) -> None:
        with self._lock:
            if self._landmarker is not None:
                self._landmarker.close()
                self._landmarker = None
