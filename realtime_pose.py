#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时姿态捕捉 + 动作计数 + 质量提示  —— 选题 11：健身动作计数与姿态纠正

相对旧版的两处关键改动：
  1. 动作判定不再硬编码，改为从 configs/*.json 读取（pose_logic.load_action），
     新增动作 = 加一份 JSON，不改本文件。
  2. 质量提示：HUD 用英文标签 + macOS 自带 say 语音念中文提示（塌腰/手臂没伸直等）。

运行：
    .venv/bin/python realtime_pose.py --list                    # 列出摄像头
    .venv/bin/python realtime_pose.py --action pushup           # 实时（自动探测）
    .venv/bin/python realtime_pose.py --cam 1 --action pushup   # 指定设备号
    .venv/bin/python realtime_pose.py --src a.mp4 --action pushup  # 读视频调参

按 q 退出，按 r 清零计数。
注意：摄像头相关脚本必须从系统自带「终端.app」跑（见 CLAUDE.md）。
"""

import argparse
import os
import subprocess
import sys
import threading
import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from pose_logic import load_action

MODEL_PATH = "pose_landmarker_lite.task"
CONFIG_DIR = "configs"

# MediaPipe Pose 33 关键点里常用的几个（画骨架用）
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


# --------------------------------------------------------------------------
# 语音播报
# --------------------------------------------------------------------------
def say(text):
    """macOS 自带 say 命令念中文，后台执行不阻塞主循环。非 mac 平台静默跳过。"""
    if sys.platform == "darwin" and text:
        try:
            subprocess.Popen(["say", text])
        except Exception:
            pass


# --------------------------------------------------------------------------
# 主程序
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=None, help="摄像头设备号")
    ap.add_argument("--src", type=str, default=None, help="视频文件路径")
    ap.add_argument("--list", action="store_true", help="列出可用摄像头后退出")
    ap.add_argument("--model", type=str, default=MODEL_PATH)
    ap.add_argument("--action", type=str, default="pushup", help="configs/ 下的动作名（不含 .json）")
    args = ap.parse_args()

    if args.list:
        cams = probe_cameras()
        if not cams:
            print("没找到可用摄像头。若用连续互通相机，先在 Mac 上打开一次"
                  "「照片亭」把 iPhone 摄像头唤醒，再运行本程序。")
        for i, w, h in cams:
            print(f"  设备号 {i}: {w}x{h}")
        return

    # 加载动作配置（新增动作 = 加一份 JSON，不改代码）
    cfg_path = os.path.join(CONFIG_DIR, f"{args.action}.json")
    if not os.path.exists(cfg_path):
        print(f"找不到动作配置：{cfg_path}")
        print(f"{CONFIG_DIR}/ 下现有：")
        for f in sorted(os.listdir(CONFIG_DIR)):
            print(f"  {f}")
        return
    action = load_action(cfg_path)
    print(f"动作：{action.name}（{action.id}），信号类型 {action.signal_type}")

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

    fps_hist, t_prev = [], time.time()
    cam = Camera(source)
    cam.start()
    time.sleep(0.4)                     # 等第一帧

    last_say = 0.0                      # 语音节流：同一提示 2 秒内不重复念

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
            sig_txt = "--"
            count, stage, sig, hits = 0, "ready", None, []
            if res and res.pose_landmarks:
                lm = res.pose_landmarks[0]
                pts = [(int(p.x * w), int(p.y * h)) for p in lm]

                for a, b in SKELETON:
                    cv2.line(frame, pts[a], pts[b], (0, 220, 180), 2)
                for p in pts:
                    cv2.circle(frame, p, 3, (255, 255, 255), -1)

                # 配置驱动的判定：算信号 → 状态机计数 → 质量提示
                count, stage, sig, hits = action.update(pts)
                if sig is not None:
                    sig_txt = f"{sig:5.1f}"

            # 帧率
            now = time.time()
            fps_hist.append(1.0 / max(now - t_prev, 1e-6))
            t_prev = now
            if len(fps_hist) > 30:
                fps_hist.pop(0)
            fps = sum(fps_hist) / len(fps_hist)

            # HUD（OpenCV 画不了中文，用英文；中文交给 say 语音念）
            cv2.rectangle(frame, (0, 0), (340, 104), (32, 32, 32), -1)
            cv2.putText(frame, f"REPS {count}", (12, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)
            cv2.putText(frame, f"{action.id.upper():9s} {stage.upper():6s} sig {sig_txt}", (12, 68),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 255, 220), 1)
            cv2.putText(frame, f"{fps:4.1f} fps", (12, 92),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 160), 1)

            # 质量提示：HUD 英文标签，语音念中文
            y = 132
            for hit in hits:
                cv2.putText(frame, f"! {hit['name'].upper()}", (12, y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (60, 60, 255), 2)
                y += 30
            if hits and now - last_say >= 2.0:
                say(hits[0]["tip"])
                last_say = now

            cv2.imshow("realtime pose", frame)
            k = cv2.waitKey(1) & 0xFF
            if k == ord("q"):
                break
            if k == ord("r"):
                action.reset()

    cam.stop()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
