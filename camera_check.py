#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
摄像头通路验证  ——  把 iPhone 拍的画面实时传到 Mac 上

这是选题 11「健身动作计数与姿态纠正」的第一步：先确认 iPhone 的画面
能稳定进到 Python 程序里，再谈姿态估计。本程序不依赖 MediaPipe，
只要 opencv-python 就能跑。

它能做四件事：
  1. 探测 Mac 认得哪些摄像头（含连续互通相机接进来的 iPhone）
  2. 实时显示画面，左上角标出设备号、分辨率、实时帧率、端到端延迟
  3. 按 s 存一张截图
  4. 按 v 录一段 mp4 —— 后面调参要用的训练视频，直接在这里录

依赖：
    pip install opencv-python

用法：
    python camera_check.py --list          只列出可用摄像头
    python camera_check.py                 自动选第一个能出画面的
    python camera_check.py --cam 1         指定设备号
    python camera_check.py --cam 1 --width 1920 --height 1080

运行中的按键：
    q / ESC   退出（终端里 Ctrl+C 也能退，不依赖窗口焦点）
    s         保存截图到 captures/
    v         开始 / 停止录像，存到 captures/
    0 1 2 3   当场切换到对应设备号（方便找出哪个是 iPhone）
    f         切换镜像

注意：第一次出画面时会自动把窗口切到前台抢键盘焦点（靠 pyobjc 调系统 API，
不会弹权限框）。如果按键还是没反应，点一下画面窗口再试。
"""

import argparse
import os
import sys
import time
from collections import deque

import cv2

OUT_DIR = "captures"
WINDOW_NAME = "camera check  -  iPhone to Mac"


def bring_window_to_front():
    """
    从终端启动的 GUI 窗口默认抢不到键盘焦点，按键（q/s/v/0-3）全部没反应。
    走 AppleScript/System Events 那层不可靠（权限给了也不一定真的切过去）。
    改成进程内直接调 Cocoa API：把自己设成正常前台 App 再 activate，
    不用经过任何外部自动化权限。需要 pyobjc（pyobjc-framework-Cocoa）。
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


def backend():
    """macOS 必须显式走 AVFoundation，否则可能读不到连续互通相机。"""
    return cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY


def probe_cameras(max_index=4, verbose=True, wait=8.0):
    """
    挨个试设备号，只认「真的能读出一帧」的那些。
    光看 isOpened() 不够 —— 连续互通相机经常报 opened 但一时半会儿读不出画面。

    关键：连续互通相机握手要好几秒。等太短就会「刚连上就被 release 掉」，
    表现为 iPhone 屏幕亮一下马上断开，而列表里什么都没有。
    所以这里对每个设备号最多耐心等 wait 秒。
    """
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, backend())
        ok_open = cap.isOpened()
        ok_read, frame = (False, None)
        if ok_open:
            t0 = time.time()
            dots = 0
            while time.time() - t0 < wait:
                ok_read, frame = cap.read()
                if ok_read and frame is not None:
                    break
                if verbose:
                    if dots == 0:
                        print(f"  设备号 {i} 已连上，等它出画面 ", end="", flush=True)
                    print(".", end="", flush=True)
                    dots += 1
                time.sleep(0.4)
            if verbose and dots:
                print()
        if ok_read and frame is not None:
            h, w = frame.shape[:2]
            fps = cap.get(cv2.CAP_PROP_FPS)
            found.append({"index": i, "w": w, "h": h, "fps": fps})
            if verbose:
                print(f"  [可用] 设备号 {i}  ->  {w}x{h}  @ {fps:.0f}fps")
        elif verbose and ok_open:
            print(f"  [打开但读不出画面] 设备号 {i}  "
                  f"(等了 {wait:.0f} 秒仍无画面)")
        cap.release()
    return found


def open_camera(index, width, height, fps):
    cap = cv2.VideoCapture(index, backend())
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)     # 缓冲区只留一帧，压低延迟
    return cap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="列出可用摄像头后退出")
    ap.add_argument("--cam", type=int, default=None, help="摄像头设备号")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--wait", type=float, default=8.0,
                    help="等待摄像头出画面的秒数，iPhone 握手慢可以调大")
    args = ap.parse_args()

    # 指定了 --cam 就直接开，不做探测。
    # 探测会反复「连接-释放」，对连续互通相机是有害的 —— iPhone 会刚连上就被断开。
    if args.cam is not None and not args.list:
        index = args.cam
        print(f"直接打开设备号 {index}（跳过探测）")
        cap = open_camera(index, args.width, args.height, args.fps)
        if cap is None:
            print(f"设备号 {index} 打不开。换个号试试：--cam 0 / 1 / 2")
            return
    else:
        print("正在探测摄像头 …（第一次运行会弹窗要摄像头权限，点允许）")
        cams = probe_cameras(verbose=True, wait=args.wait)

        if not cams:
            print("\n没有找到可用摄像头。按顺序试：")
            print("  1. 直接指定设备号绕开探测： --cam 0 （再试 1 / 2）")
            print("  2. 系统设置 → 隐私与安全性 → 摄像头 → 打开「终端」，")
            print("     然后 Cmd+Q 完全退出终端再重开")
            print("  3. 跑一下 diagnose_camera.py 把输出发出来")
            return
        if args.list:
            return

        index = cams[0]["index"]
        cap = open_camera(index, args.width, args.height, args.fps)
        if cap is None:
            print(f"设备号 {index} 打不开，试试 --cam 手动指定。")
            return

    print(f"\n已打开设备号 {index}。按 q 退出，s 截图，v 录像，0-3 切换摄像头。\n")
    print("  窗口边角可以拖拽调整大小；按键前先点一下画面窗口，确保焦点在窗口上。\n")

    os.makedirs(OUT_DIR, exist_ok=True)
    # WINDOW_NORMAL 让窗口可以拖拽缩放；默认的 WINDOW_AUTOSIZE 会锁死成画面原始分辨率，
    # 1920x1080 的画面很容易比屏幕还大。
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, 960, 540)
    fps_hist = deque(maxlen=30)
    t_prev = time.time()
    mirror = True
    writer = None
    rec_path = ""

    waiting_since = time.time()
    got_first = False
    warned = False

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                # 还没出画面。连续互通相机握手要几秒，耐心等，同时给点反馈。
                if not got_first:
                    waited = time.time() - waiting_since
                    if not warned and waited > 2:
                        print("  等待画面 …（iPhone 握手通常要 3~8 秒，别关窗口）")
                        warned = True
                    if waited > args.wait + 12:
                        print(f"\n等了 {waited:.0f} 秒还没画面，设备号 {index} 可能不对。")
                        print("换一个试试： --cam 0 / 1 / 2")
                        break
                if cv2.waitKey(30) & 0xFF in (ord("q"), 27):
                    break
                continue

            if not got_first:
                got_first = True
                print(f"  出画面了：{frame.shape[1]}x{frame.shape[0]}")
                cv2.imshow(WINDOW_NAME, frame)
                cv2.waitKey(1)
                bring_window_to_front()

            if mirror:
                frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]

            now = time.time()
            fps_hist.append(1.0 / max(now - t_prev, 1e-6))
            t_prev = now
            fps = sum(fps_hist) / len(fps_hist)

            if writer is not None:
                writer.write(frame)

            # ---- HUD（OpenCV 画不了中文，这里一律用英文）----
            panel = frame.copy()
            cv2.rectangle(panel, (0, 0), (330, 108), (24, 24, 24), -1)
            cv2.addWeighted(panel, 0.72, frame, 0.28, 0, frame)

            cv2.putText(frame, f"CAM {index}   {w}x{h}", (14, 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2)
            color = (120, 255, 160) if fps >= 24 else (90, 170, 255)
            cv2.putText(frame, f"{fps:5.1f} fps", (14, 62),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2)
            cv2.putText(frame, "q quit  s shot  v rec  0-3 switch  (or Ctrl+C in terminal)",
                        (14, 92), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (170, 170, 170), 1)

            if writer is not None:
                cv2.circle(frame, (w - 38, 34), 10, (60, 60, 255), -1)
                cv2.putText(frame, "REC", (w - 118, 42),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (60, 60, 255), 2)

            cv2.imshow(WINDOW_NAME, frame)

            k = cv2.waitKey(1) & 0xFF
            if k in (ord("q"), 27):
                break
            elif k == ord("f"):
                mirror = not mirror
            elif k == ord("s"):
                p = os.path.join(OUT_DIR, f"shot_{time.strftime('%H%M%S')}.jpg")
                cv2.imwrite(p, frame)
                print(f"截图已保存：{p}")
            elif k == ord("v"):
                if writer is None:
                    rec_path = os.path.join(OUT_DIR, f"rec_{time.strftime('%H%M%S')}.mp4")
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    writer = cv2.VideoWriter(rec_path, fourcc, max(fps, 15.0), (w, h))
                    print(f"开始录像：{rec_path}")
                else:
                    writer.release()
                    writer = None
                    print(f"录像已保存：{rec_path}")
            elif k in (ord("0"), ord("1"), ord("2"), ord("3")):
                new_index = k - ord("0")
                if new_index != index:
                    if writer is not None:
                        writer.release()
                        writer = None
                    cap.release()
                    newcap = open_camera(new_index, args.width, args.height, args.fps)
                    if newcap is None:
                        print(f"设备号 {new_index} 打不开，切回 {index}")
                        cap = open_camera(index, args.width, args.height, args.fps)
                    else:
                        cap, index = newcap, new_index
                        print(f"已切换到设备号 {index}")
                    fps_hist.clear()
    except KeyboardInterrupt:
        # 窗口没抢到键盘焦点时，q 按不动——终端里 Ctrl+C 随时能退，不依赖窗口焦点。
        print("\n收到 Ctrl+C，退出。")

    if writer is not None:
        writer.release()
        print(f"录像已保存：{rec_path}")
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
