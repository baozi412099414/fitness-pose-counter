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
import json
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

# 站立基线自动校准用的偏移量（见 main 里的校准逻辑）
LO_DROP = 15.0      # 下蹲门槛 = 站立基线 - 15°（调小更敏感、调大更迟钝）
HI_DROP = 8.0       # 还原线   = 站立基线 - 8°
STRAIGHT_DROP = 10.0  # 「站起伸直」标准 = 站立基线 - 10°

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


def probe_cameras(max_index=4, wait=8.0):
    """
    挨个试设备号，只认「真的能读出一帧」的那些。

    关键：连续互通相机握手要好几秒。等太短就会「刚连上就被 release 掉」，
    表现为 iPhone 亮一下马上断开、列表里还什么都没有。
    所以对每个设备号最多耐心等 wait 秒。
    （这个坑 CLAUDE.md 里记录过，camera_check.py 早就修了，这里补上。）
    """
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, _backend())
        if cap.isOpened():
            t0 = time.time()
            while time.time() - t0 < wait:
                ok, frame = cap.read()
                if ok and frame is not None:
                    h, w = frame.shape[:2]
                    found.append((i, w, h))
                    break
                time.sleep(0.4)
        cap.release()
    return found


class Camera(threading.Thread):
    """
    实时的关键：取帧放在独立线程里不停 read()，只保留最新一帧。
    主线程推理慢了也没关系——它永远拿到的是「现在」，而不是排队的旧帧。
    """

    def __init__(self, source, width=1280, height=720, fps=30):
        super().__init__(daemon=True)
        self.is_file = not isinstance(source, int)
        if not self.is_file:
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
        # 不要命名为 _stop：threading.Thread 内部有一个同名方法，join() 在线程
        # 结束时会调用它。用 Event 覆盖后，退出阶段可能报 "Event object is not callable"。
        self._stop_event = threading.Event()
        self._eof_event = threading.Event()
        source_fps = self.cap.get(cv2.CAP_PROP_FPS) if self.is_file else 0
        self._frame_interval = 1.0 / source_fps if source_fps and source_fps > 1 else 0.0

    def run(self):
        while not self._stop_event.is_set():
            ok, f = self.cap.read()
            if not ok:
                if self.is_file:
                    self._eof_event.set()
                    break
                time.sleep(0.005)
                continue
            with self._lock:
                self._frame = f          # 覆盖式写入：旧帧直接扔掉
            # 文件按原始帧率播放，避免线程瞬间读到结尾、主线程只拿到最后一帧。
            if self.is_file and self._frame_interval:
                time.sleep(self._frame_interval)

    def read(self):
        with self._lock:
            if self._frame is None:
                return None
            frame = self._frame.copy()
            if self.is_file:
                self._frame = None       # 文件每帧只消费一次；摄像头仍只取最新帧
            return frame

    @property
    def finished(self):
        with self._lock:
            return self.is_file and self._eof_event.is_set() and self._frame is None

    def stop(self):
        self._stop_event.set()
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


def bring_window_to_front():
    """
    从终端启动的 GUI 窗口默认抢不到键盘焦点，按键（q / r）会没反应。
    进程内直接调 Cocoa API 把自己设成前台 App，不经过任何外部自动化权限。
    """
    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyRegular
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        app.activateIgnoringOtherApps_(True)
    except Exception as e:
        print(f"  （抢焦点失败，可以手动点一下画面窗口：{e}）")


# --------------------------------------------------------------------------
# 主程序
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=None, help="摄像头设备号")
    ap.add_argument("--src", type=str, default=None, help="视频文件路径")
    ap.add_argument("--list", action="store_true", help="列出可用摄像头后退出")
    ap.add_argument("--model", type=str, default=MODEL_PATH)
    ap.add_argument("--no-voice", action="store_true", help="关闭语音播报")
    ap.add_argument("--report", type=str, default=None, help="退出时保存 JSON 测试摘要")
    ap.add_argument("--action", type=str, default="pushup", help="configs/ 下的动作名（不含 .json）")
    ap.add_argument("--lo-drop", type=float, default=LO_DROP,
                    help="下蹲门槛 = 站立基线 - 该值（默认 15°；调小更敏感、调大更迟钝）")
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
        # 调高一点，减少「跟丢后还在输出幽灵骨架」的情况（另一道防线是 visibility 过滤）
        min_pose_detection_confidence=0.6,
        min_pose_presence_confidence=0.6,
        min_tracking_confidence=0.6,
        result_callback=bus.put,
    )

    fps_hist, t_prev = [], time.time()
    cam = Camera(source)
    cam.start()
    time.sleep(0.4)                     # 等第一帧

    # WINDOW_NORMAL 让窗口可拖拽缩放，也更容易拿到键盘焦点（默认 AUTOSIZE 会锁死尺寸）
    cv2.namedWindow("realtime pose", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("realtime pose", 960, 540)

    last_say = 0.0                      # 语音节流：同一提示 2 秒内不重复念
    last_count = 0                      # 上次计数，用于「刚数上一个」时语音报数
    got_first = False                   # 是否已出过画面（用来抢一次窗口焦点）
    # 启动后头 2 秒画面还在稳定（相机自动曝光、人还在站位），这期间 MediaPipe
    # 容易输出乱跳的关键点，会造成「凭空多计一次」→ 所以先不计数。
    warmup_until = time.time() + 2.0
    warmup_samples = []                 # 启动头 2 秒的信号采样（用来估算站立基线）
    baseline = None                     # 站立基线（自动校准结果）
    calib_done = False                  # 校准是否已判定完（成功或放弃）
    shown_hits = []                     # 最近命中的错误（保持显示一会儿，免得只闪一帧看不清）
    shown_until = 0.0
    last_err_say = 0.0                  # 错误播报节流（独立于报数）
    last_cnt_say = 0.0                  # 报数节流
    last_logged_count = 0               # 上次打印过判定明细的计数（终端诊断用）
    total_frames = 0                    # UI/离线验收摘要
    detected_frames = 0
    error_counts = {}
    active_error_names = set()
    stopped_reason = "user"

    # MediaPipe 启动时可能尝试联网上报遥测，网络不通时会等一会儿才继续（见 CLAUDE.md）。
    # 这里提前说明，免得用户以为程序卡死了。
    print("正在初始化姿态模型 …（首次启动可能要等十几秒到一分钟，请稍候）")
    t_init = time.time()
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        print(f"  模型就绪，初始化用时 {time.time() - t_init:.0f} 秒\n")
        t0 = time.time()
        while True:
            frame = cam.read()
            if frame is None:
                if cam.finished:
                    stopped_reason = "eof"
                    print("\n视频播放完成，自动结束测试。")
                    break
                if cv2.waitKey(10) & 0xFF == ord("q"):
                    break
                continue

            total_frames += 1

            frame = cv2.flip(frame, 1)          # 镜像，自己看着顺手
            h, w = frame.shape[:2]

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            landmarker.detect_async(mp_img, int((time.time() - t0) * 1000))

            res = bus.get()
            sig_txt = "--"
            count, stage, sig, hits, checks = 0, "ready", None, [], []
            conf = 0.0                      # 计数关键点的最低可信度
            person_ok = False               # 可信度够不够（不够就暂停计数）
            if res and res.pose_landmarks:
                detected_frames += 1
                lm = res.pose_landmarks[0]
                pts = [(int(p.x * w), int(p.y * h)) for p in lm]
                # 关键点可信度：人没拍到 / 跟丢时 MediaPipe 会输出「幽灵骨架」，
                # 计数和质量判定都必须先看这个，否则会凭空加数、凭空报警
                vis = [p.visibility for p in lm]
                counter_idxs = set()
                for condition in (action.conditions or [{"points": action.signal_points}]):
                    counter_idxs.update(condition["points"])
                conf = min(vis[i] for i in counter_idxs)
                person_ok = conf >= action.min_visibility

                # ---- 站立基线自动校准 ----
                # 启动头 2 秒你应该是站着的，用这段时间信号的中位数当「站立基线」，
                # 再自动定门槛：下蹲门槛 = 基线-25°，还原线 = 基线-8°，
                # 「站起伸直」标准 = 基线-10°。换个人 / 换机位都不必回来改配置。
                # 注意：只对「角度类」动作有效；距离类（如开合跳的脚距/肩宽比值）
                # 单位不是度，用不了这套减法，所以直接跳过、用配置里的固定阈值。
                # 注意：自动校准的公式是「基线 − 偏移」，只适合「角度变小」的动作（如深蹲下蹲）。
                # 开合跳是「角度变大」（举手），套这个公式会把门槛设到站立值以下 ——
                # 站着就满足「手举起」，手机一晃就计数。所以配置里可以关掉校准。
                if not calib_done and person_ok:
                    if not getattr(action, "calibrate", True) or action.signal_type != "angle":
                        calib_done = True
                        print(f"  （{action.name} 用配置里的固定门槛，不做角度基线校准）")
                    elif time.time() < warmup_until:
                        sample = action.signal(pts)
                        if sample is not None:
                            warmup_samples.append(sample)
                    elif len(warmup_samples) >= 8:
                        warmup_samples.sort()
                        baseline = warmup_samples[len(warmup_samples) // 2]
                        action.counter.lo = baseline - args.lo_drop
                        action.counter.hi = baseline - HI_DROP
                        for r in action.quality.rules:
                            # 只校准「用计数信号」的约束；带自己 signal 的约束
                            # （如开合跳的「腿没张开」用的是距离比值）不能被角度基线污染
                            if r.get("check") == "peak_min" and "signal" not in r:
                                r["min"] = baseline - STRAIGHT_DROP
                        calib_done = True
                        print(f"  自动校准：站立基线 {baseline:.0f}° → 下蹲门槛 "
                              f"{action.counter.lo:.0f}° / 还原线 {action.counter.hi:.0f}° / "
                              f"站直标准 {baseline - STRAIGHT_DROP:.0f}°")
                    elif time.time() > warmup_until + 4.0:
                        calib_done = True       # 采样太少（一直没拍全），放弃校准
                        print("  （站立基线采样不足，改用配置里的固定门槛）")

                # 骨架照画（可信度低时画成灰色，一眼看出「这是猜的」）
                skel_color = (0, 220, 180) if person_ok else (110, 110, 110)
                for a, b in SKELETON:
                    cv2.line(frame, pts[a], pts[b], skel_color, 2)
                for p in pts:
                    cv2.circle(frame, p, 3, (255, 255, 255), -1)

                # 配置驱动的判定：算信号 → 状态机计数 → 质量明细
                if time.time() >= warmup_until:
                    count, stage, sig, hits, checks = action.update(pts, vis)
                else:
                    # 稳定期内只算信号拿来显示，不动状态机（避免凭空多计一次）
                    sig = action.signal(pts)
                    count, stage = action.counter.count, action.counter.stage
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
            cv2.rectangle(frame, (0, 0), (400, 152), (32, 32, 32), -1)
            cv2.putText(frame, f"REPS {count}", (12, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)
            cv2.putText(frame, f"{action.id.upper():9s} {stage.upper():6s} sig {sig_txt}", (12, 68),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 255, 220), 1)
            # 检测状态：可信度不够时明确写「PAUSED」，而不是默默加数
            det_txt = f"track {conf:.2f}  " + ("COUNTING" if person_ok else "PAUSED no-person")
            det_color = (120, 230, 120) if person_ok else (60, 60, 255)
            cv2.putText(frame, det_txt, (12, 92),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, det_color, 2)
            # 信息行：多条件动作显示各条件当前值；角度类动作显示站立基线 + 本轮最低点
            if action.conditions:
                # 注意：某帧关键点异常时信号会被丢弃成 None，这里必须处理，
                # 否则 f"{None:5.2f}" 会抛 TypeError，把整个主循环搞崩（画面「卡住」）
                vals = "  ".join("  -- " if v is None else f"{v:5.2f}"
                                 for v in action.last_values)
                info_txt = f"cond  {vals}"
            else:
                base_txt = f"{baseline:.0f}" if baseline else "calib.."
                low_txt = f"{action.depth_valley:.0f}" if action.depth_valley is not None else "--"
                info_txt = f"base {base_txt}  lowest {low_txt}"
            cv2.putText(frame, info_txt, (12, 116),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 120), 2)
            cv2.putText(frame, f"{fps:4.1f} fps", (12, 140),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 160), 1)

            # 先把「刚命中、要保持显示」的错误算出来：
            # on_rep 类约束只在计数那一帧命中，只闪一帧根本看不清 → 让结果挂 2 秒
            if hits:
                shown_hits = hits
                shown_until = now + 2.0
            elif now > shown_until:
                shown_hits = []
            current_error_names = {h["name"] for h in hits}
            for name in current_error_names - active_error_names:
                error_counts[name] = error_counts.get(name, 0) + 1
            active_error_names = current_error_names
            hit_map = {h["name"]: h for h in shown_hits}

            # 质量明细：显示「实测值 / 阈值」，一眼看出是照不全还是阈值太严
            #   OK 绿=达标   !! 红=不达标   ? 灰=点没拍全   -- 灰=本阶段不判
            y = 180
            hidden = False
            for c in checks:
                kept = hit_map.get(c["name"])
                if kept is not None:
                    # 刚命中、正在保持显示的错误（数值取命中那一刻的）
                    txt = (f"{c['name'].upper():18s} "
                           f"{kept.get('value') or 0:5.2f}/{(kept.get('limit') or 0):.2f}  !!")
                    color = (60, 60, 255)
                elif not c["visible"]:
                    hidden = True
                    txt = f"{c['name'].upper():18s}    ?   point hidden"
                    color = (150, 150, 150)
                elif not c["checked"]:
                    txt = f"{c['name'].upper():18s}   --   not this phase"
                    color = (150, 150, 150)
                elif c["ok"]:
                    txt = (f"{c['name'].upper():18s} "
                           f"{(c['value'] or 0):5.2f}/{(c['limit'] or 0):.2f}  OK")
                    color = (120, 230, 120)
                else:
                    txt = (f"{c['name'].upper():18s} "
                           f"{(c['value'] or 0):5.2f}/{(c['limit'] or 0):.2f}  !!")
                    color = (60, 60, 255)
                cv2.putText(frame, txt, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
                y += 26

            if hidden:
                cv2.putText(frame, "! POINTS HIDDEN  ->  step back, keep whole body in frame",
                            (12, y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (60, 200, 255), 2)

            if shown_hits:
                banner = "   ".join("! " + (h["name"] or "?").upper() for h in shown_hits)
                cv2.putText(frame, banner, (12, y + 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (60, 60, 255), 3)

            # 终端也打印每次计数的判定明细 —— HUD 看不清时可以直接把输出复制回来
            if count > last_logged_count:
                last_logged_count = count
                parts = [f"{c['name']}={(c['value'] or 0):.2f}/{c['limit']:.2f}"
                         f"{'OK' if c['ok'] else '!!'}"
                         for c in checks if c.get("limit") is not None]
                print(f"  第 {count} 次： " + "   ".join(parts), flush=True)

            # 语音播报：报错优先。同一次动作既计数又报错时合并成一句
            # （两个 say 会互相打断）；报错与报数各有独立节流，避免错误提示被报数挤掉。
            if not args.no_voice and hits and now - last_err_say >= 1.5:
                tip = hits[0]["tip"]
                if count > last_count:
                    tip += f"，{count}"
                    last_count = count
                say(tip)
                last_err_say = now
            elif not args.no_voice and count > last_count and now - last_cnt_say >= 1.0:
                # 没有错误提示时才单独念数字（做动作时不用盯屏幕也知道数上了）
                say(str(count))
                last_cnt_say = now
                last_count = count

            cv2.imshow("realtime pose", frame)
            if not got_first:
                # 第一次出画面时抢一下键盘焦点，否则 q / r 按了没反应
                got_first = True
                cv2.waitKey(1)
                bring_window_to_front()

            # 直接点窗口的 ✕ 关掉也要能退出（最符合直觉的方式）
            try:
                if cv2.getWindowProperty("realtime pose", cv2.WND_PROP_VISIBLE) < 1:
                    print("\n窗口已关闭，退出。")
                    break
            except cv2.error:
                break

            # q / ESC 退出，r 清零
            k = cv2.waitKey(1) & 0xFF
            if k in (ord("q"), 27):
                break
            if k == ord("r"):
                action.reset()
                last_count = 0

    cam.stop()
    cv2.destroyAllWindows()
    summary = {
        "action": action.id,
        "action_name": action.name,
        "source": str(source),
        "reps": action.counter.count,
        "total_frames": total_frames,
        "detected_frames": detected_frames,
        "detection_rate": round(detected_frames / total_frames, 4) if total_frames else 0.0,
        "errors": error_counts,
        "error_tips": {r.get("name"): r.get("tip", r.get("name"))
                       for r in action.quality.rules if r.get("name") in error_counts},
        "stopped_reason": stopped_reason,
    }
    print("测试摘要：" + json.dumps(summary, ensure_ascii=False), flush=True)
    if args.report:
        report_dir = os.path.dirname(os.path.abspath(args.report))
        os.makedirs(report_dir, exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # 窗口没抢到焦点时 q 按不动，终端里 Ctrl+C 随时能退，不依赖窗口焦点
        print("\n收到 Ctrl+C，退出。")
