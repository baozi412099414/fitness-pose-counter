#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时姿态捕捉 + 计数骨架  —— 选题 11：健身动作计数与姿态纠正

这份代码解决的是「摄像头实时接入」这一层，把三个实时的坑都处理掉了：
  1. 取帧线程与推理解耦，旧帧直接丢弃  -> 画面不会越跑越延迟
  2. MediaPipe LIVE_STREAM 异步模式     -> 推理不阻塞取帧
  3. macOS 摄像头自动探测               -> 绕开 Continuity Camera 设备号乱跳

依赖：
    pip install opencv-python mediapipe numpy

模型（lite 版约 9MB，下载一次即可，放在本文件同目录）：
    curl -L -o pose_landmarker_lite.task \
      https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task

运行：
    python realtime_pose.py              # 自动探测摄像头
    python realtime_pose.py --list       # 只列出可用摄像头
    python realtime_pose.py --cam 1      # 手动指定设备号
    python realtime_pose.py --src a.mp4  # 读视频文件（调参时用）

按 q 退出，按 r 清零计数。
"""

import argparse
import math
import sys
import threading
import time

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

MODEL_PATH = "pose_landmarker_lite.task"

# MediaPipe Pose 33 关键点里常用的几个
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW,    R_ELBOW    = 13, 14
L_WRIST,    R_WRIST    = 15, 16
L_HIP,      R_HIP      = 23, 24
L_KNEE,     R_KNEE     = 25, 26
L_ANKLE,    R_ANKLE    = 27, 28

# 画骨架用的连线
SKELETON = [
    (L_SHOULDER, R_SHOULDER), (L_SHOULDER, L_ELBOW), (L_ELBOW, L_WRIST),
    (R_SHOULDER, R_ELBOW), (R_ELBOW, R_WRIST),
    (L_SHOULDER, L_HIP), (R_SHOULDER, R_HIP), (L_HIP, R_HIP),
    (L_HIP, L_KNEE), (L_KNEE, L_ANKLE), (R_HIP, R_KNEE), (R_KNEE, R_ANKLE),
]


# --------------------------------------------------------------------------
# 摄像头：独立线程只保留最新一帧
# --------------------------------------------------------------------------
def _backend():
    """macOS 用 AVFoundation，其它平台交给 OpenCV 自己选。"""
    return cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY


def probe_cameras(max_index=4):
    """挨个试设备号，返回真正能读出画面的那些。"""
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, _backend())
        if cap.isOpened():
            ok, frame = cap.read()
            if ok and frame is not None:
                h, w = frame.shape[:2]
                found.append((i, w, h))
        cap.release()
    return found


class Camera(threading.Thread):
    """
    实时的关键：取帧放在独立线程里不停 read()，只保留最新一帧。
    主线程推理慢了也没关系——它永远拿到的是「现在」，而不是排队的旧帧。
    """

    def __init__(self, source, width=1280, height=720, fps=30):
        super().__init__(daemon=True)
        if isinstance(source, int):
            self.cap = cv2.VideoCapture(source, _backend())
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, fps)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        else:
            self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise RuntimeError(f"打不开视频源：{source}")
        self._lock = threading.Lock()
        self._frame = None
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            ok, f = self.cap.read()
            if not ok:
                time.sleep(0.005)
                continue
            with self._lock:
                self._frame = f          # 覆盖式写入：旧帧直接扔掉

    def read(self):
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def stop(self):
        self._stop.set()
        self.join(timeout=1.0)
        self.cap.release()


# --------------------------------------------------------------------------
# 角度与状态机
# --------------------------------------------------------------------------
def joint_angle(a, b, c):
    """b 为顶点，返回 a-b-c 的夹角（度）。a/b/c 是 (x, y)。"""
    ba = np.array([a[0] - b[0], a[1] - b[1]], dtype=np.float64)
    bc = np.array([c[0] - b[0], c[1] - b[1]], dtype=np.float64)
    denom = np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9
    return math.degrees(math.acos(np.clip(np.dot(ba, bc) / denom, -1.0, 1.0)))


class RepCounter:
    """
    带迟滞（hysteresis）的两态状态机。
    down_th 和 up_th 之间那段是「不表态区」，角度在阈值边缘抖动时不会反复翻转,
    这是防止重复计数最有效的一招。min_interval 再兜一层时间防抖。
    """

    def __init__(self, down_th=95.0, up_th=155.0, min_interval=0.35):
        self.down_th = down_th
        self.up_th = up_th
        self.min_interval = min_interval
        self.stage = "up"
        self.count = 0
        self._last_t = 0.0

    def update(self, angle):
        now = time.time()
        if self.stage == "up" and angle < self.down_th:
            self.stage = "down"
        elif self.stage == "down" and angle > self.up_th:
            if now - self._last_t >= self.min_interval:
                self.count += 1
                self._last_t = now
            self.stage = "up"
        return self.count, self.stage

    def reset(self):
        self.count = 0
        self.stage = "up"


# --------------------------------------------------------------------------
# 主程序
# --------------------------------------------------------------------------
class ResultBus:
    """LIVE_STREAM 模式下结果从回调里异步回来，这里做个最新值的中转。"""

    def __init__(self):
        self._lock = threading.Lock()
        self.result = None

    def put(self, result, output_image, timestamp_ms):
        with self._lock:
            self.result = result

    def get(self):
        with self._lock:
            return self.result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=None, help="摄像头设备号")
    ap.add_argument("--src", type=str, default=None, help="视频文件路径")
    ap.add_argument("--list", action="store_true", help="列出可用摄像头后退出")
    ap.add_argument("--model", type=str, default=MODEL_PATH)
    args = ap.parse_args()

    if args.list:
        cams = probe_cameras()
        if not cams:
            print("没找到可用摄像头。若用连续互通相机，先在 Mac 上打开一次"
                  "「照片亭」把 iPhone 摄像头唤醒，再运行本程序。")
        for i, w, h in cams:
            print(f"  设备号 {i}: {w}x{h}")
        return

    # 选视频源
    if args.src:
        source = args.src
    elif args.cam is not None:
        source = args.cam
    else:
        cams = probe_cameras()
        if not cams:
            print("没找到可用摄像头，试试 --list 或 --cam 0/1/2")
            return
        source = cams[0][0]
        print(f"自动选用设备号 {source}（{cams[0][1]}x{cams[0][2]}）"
              f"，不对就用 --cam 手动指定")

    bus = ResultBus()
    options = vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=args.model),
        running_mode=vision.RunningMode.LIVE_STREAM,   # 异步，不阻塞取帧
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        result_callback=bus.put,
    )

    counter = RepCounter()              # 默认参数按俯卧撑肘角设的，自己按实测曲线改
    fps_hist, t_prev = [], time.time()
    cam = Camera(source)
    cam.start()
    time.sleep(0.4)                     # 等第一帧

    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        t0 = time.time()
        while True:
            frame = cam.read()
            if frame is None:
                if cv2.waitKey(10) & 0xFF == ord("q"):
                    break
                continue

            frame = cv2.flip(frame, 1)          # 镜像，自己看着顺手
            h, w = frame.shape[:2]

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            landmarker.detect_async(mp_img, int((time.time() - t0) * 1000))

            res = bus.get()
            angle_txt = "--"
            if res and res.pose_landmarks:
                lm = res.pose_landmarks[0]
                pts = [(int(p.x * w), int(p.y * h)) for p in lm]

                for a, b in SKELETON:
                    cv2.line(frame, pts[a], pts[b], (0, 220, 180), 2)
                for p in pts:
                    cv2.circle(frame, p, 3, (255, 255, 255), -1)

                # 示例：右肘角度驱动计数（俯卧撑 / 二头弯举）
                ang = joint_angle(pts[R_SHOULDER], pts[R_ELBOW], pts[R_WRIST])
                counter.update(ang)
                angle_txt = f"{ang:5.1f}"
                cv2.putText(frame, angle_txt, (pts[R_ELBOW][0] + 10, pts[R_ELBOW][1]),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            # 帧率
            now = time.time()
            fps_hist.append(1.0 / max(now - t_prev, 1e-6))
            t_prev = now
            if len(fps_hist) > 30:
                fps_hist.pop(0)
            fps = sum(fps_hist) / len(fps_hist)

            cv2.rectangle(frame, (0, 0), (300, 100), (32, 32, 32), -1)
            cv2.putText(frame, f"REPS {counter.count}", (12, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)
            cv2.putText(frame, f"{counter.stage.upper():5s} ang {angle_txt}", (12, 68),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 255, 220), 1)
            cv2.putText(frame, f"{fps:4.1f} fps", (12, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 160), 1)

            cv2.imshow("realtime pose", frame)
            k = cv2.waitKey(1) & 0xFF
            if k == ord("q"):
                break
            if k == ord("r"):
                counter.reset()

    cam.stop()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
